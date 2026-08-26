"""Audio recorder — captures microphone input via sounddevice, outputs WAV bytes."""

from __future__ import annotations

import io
import sys
import wave

import numpy as np
import sounddevice as sd

from voicetranser.watchdog import watchdog


class Recorder:
    """Record audio from the default microphone while active.

    Holds a single long-lived InputStream and starts/stops it per recording,
    so each capture begins with a warm stream (~40 ms) instead of paying the
    ~160 ms device-open cost on every key press.
    """

    def __init__(self, sample_rate: int = 16000, channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def _ensure_stream(self) -> None:
        """Lazily create the persistent input stream (once per process)."""
        if self._stream is not None:
            return
        # Stream creation talks to the same CoreAudio/HAL mutexes that can
        # deadlock (2026-08-27 incident) — guard it like start/stop.
        with watchdog:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                callback=self._audio_callback,
            )

    def start(self) -> None:
        """Start recording."""
        if self._active:
            return
        self._ensure_stream()
        self._frames.clear()
        self._active = True
        assert self._stream is not None
        with watchdog:
            self._stream.start()

    def stop(self) -> bytes | None:
        """Stop recording and return WAV bytes. Returns None if too short (<0.5s)."""
        if not self._active:
            return None
        self._active = False
        if self._stream is not None:
            # stop() is the exact call that deadlocked inside HALB_Mutex::Lock
            # on 2026-08-27 — always guarded.
            with watchdog:
                self._stream.stop()

        if not self._frames:
            return None

        audio = np.concatenate(self._frames, axis=0)
        duration = len(audio) / self.sample_rate
        if duration < 0.5:
            return None

        # float32 → int16
        audio_int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_int16.tobytes())
        return buf.getvalue()

    def _audio_callback(
        self, indata: np.ndarray, frames: int, time_info, status
    ) -> None:
        if status:
            sys.stderr.write(f"\r[Audio: {status}]\r")
        # Drain into nowhere while idle — the stream stays warm but we keep no data.
        if not self._active:
            return
        self._frames.append(indata.copy())
