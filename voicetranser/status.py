"""macOS notification feedback for daemon mode."""

from __future__ import annotations

import subprocess


_SOUND_VOLUME = 0.7  # relative volume (0.0–1.0)


def _notify(title: str, text: str, sound: str | None = None) -> None:
    """Post a macOS notification and play a sound — both fire-and-forget.

    Both osascript (~110 ms to fork+compile) and afplay are detached via Popen so
    neither blocks the caller. The caller (HTTP handler) invokes _notify while
    holding the state lock, so any blocking call here stalls every other request.

    The sound is started *first*: it is the time-critical "key press acknowledged"
    cue. A notification banner lagging ~100 ms is invisible; a sound lagging that
    much reads as a noticeable "half-beat delay".
    """
    # Sound first — Popen returns in ~3 ms, so the cue is heard the instant the
    # key is pressed instead of ~110 ms later.
    if sound:
        subprocess.Popen(
            ["afplay", "-v", str(_SOUND_VOLUME), f"/System/Library/Sounds/{sound}.aiff"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    # Notification detached — osascript's fork+compile overhead (~110 ms) must
    # not block the HTTP handler or delay the sound above.
    escaped_text = text.replace("\\", "\\\\").replace('"', '\\"')
    escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
    script = f'display notification "{escaped_text}" with title "{escaped_title}"'
    subprocess.Popen(
        ["osascript", "-e", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class StatusDisplay:
    """Shows macOS notifications at each pipeline stage."""

    def __init__(
        self,
        *,
        sound_enabled: bool = True,
        start_sound: str = "Blow",
        done_sound: str = "Glass",
    ) -> None:
        self._sound_enabled = sound_enabled
        self._start_sound = start_sound
        self._done_sound = done_sound

    def recording(self) -> None:
        """Notify that recording has started."""
        _notify(
            "VoiceTranser",
            "🎙️ Recording...",
            sound=self._start_sound if self._sound_enabled else None,
        )

    def transcribing(self) -> None:
        """Notify that transcription is in progress."""
        _notify("VoiceTranser", "⠋ Transcribing...")

    def done(self) -> None:
        """Notify that the result has been pasted."""
        _notify(
            "VoiceTranser",
            "✅ Done — pasted",
            sound=self._done_sound if self._sound_enabled else None,
        )

    def clear(self) -> None:
        """No-op for notification mode (notifications auto-dismiss)."""
        pass
