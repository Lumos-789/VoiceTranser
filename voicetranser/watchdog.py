"""Watchdog for CoreAudio calls that can deadlock inside the HAL.

Observed 2026-08-27 00:55: InputStream.stop() wedged forever inside
HALB_Mutex::Lock while the HTTP handler held the server state lock, so every
endpoint queued behind it and the daemon never recovered (launchd saw a live
process, KeepAlive never fired). Python cannot break that kernel-level
deadlock — the only recovery is to exit hard and let launchd's KeepAlive
respawn us; SenseVoice reload costs a few seconds, a wedged service costs
everything.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from typing import Callable

# 5s comfortably exceeds any legitimate stream create/start/stop (all <200 ms
# warm, up to ~1–2s cold right after wake) while still bounding a hang to one
# quick respawn.
DEFAULT_TIMEOUT = float(os.environ.get("VT_AUDIO_WATCHDOG_TIMEOUT", "5"))


class AudioWatchdog:
    """Arms a deadline around CoreAudio create/start/stop calls.

    Use as a context manager around the PortAudio calls in Recorder. When a
    guarded call overruns, a dedicated daemon thread hard-exits the process —
    a deadlocked call can never return, so __exit__ never runs and the
    deadline stays armed.
    """

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        poll: float = 0.25,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._timeout = timeout
        self._poll = poll
        self._clock = clock
        self._lock = threading.Lock()
        self._depth = 0
        self._deadline: float | None = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "AudioWatchdog":
        with self._lock:
            self._depth += 1
            if self._depth == 1:
                self._deadline = self._clock() + self._timeout
        self._ensure_thread()
        return self

    def __exit__(self, *exc: object) -> None:
        with self._lock:
            self._depth = max(0, self._depth - 1)
            if self._depth == 0:
                self._deadline = None

    def expired(self, now: float | None = None) -> bool:
        """True when an armed deadline has passed."""
        if now is None:
            now = self._clock()
        with self._lock:
            return self._deadline is not None and now > self._deadline

    def _ensure_thread(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._run, daemon=True, name="audio-watchdog"
            )
            self._thread.start()

    def _run(self) -> None:
        while True:
            time.sleep(self._poll)
            if self.expired():
                sys.stderr.write(
                    f"[VoiceTranser watchdog] audio operation exceeded "
                    f"{self._timeout:.1f}s — CoreAudio deadlock suspected, "
                    "exiting for launchd restart\n"
                )
                sys.stderr.flush()
                os._exit(1)


# Singleton shared by Recorder's stream create/start/stop (ops are serialized
# by the server state machine, so a single deadline suffices).
watchdog = AudioWatchdog()
