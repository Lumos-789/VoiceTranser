"""macOS notification feedback for daemon mode."""

from __future__ import annotations

import subprocess


_SOUND_VOLUME = 0.7  # relative volume (0.0–1.0)


def _notify(title: str, text: str, sound: str | None = None) -> None:
    """Post a macOS notification via osascript, play sound at reduced volume."""
    escaped_text = text.replace("\\", "\\\\").replace('"', '\\"')
    escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
    script = f'display notification "{escaped_text}" with title "{escaped_title}"'
    subprocess.run(
        ["osascript", "-e", script],
        timeout=5,
        capture_output=True,
    )
    if sound:
        subprocess.run(
            ["afplay", "-v", str(_SOUND_VOLUME), f"/System/Library/Sounds/{sound}.aiff"],
            timeout=5,
            capture_output=True,
        )


class StatusDisplay:
    """Shows macOS notifications at each pipeline stage."""

    def recording(self) -> None:
        """Notify that recording has started."""
        _notify("VoiceTranser", "🎙️ Recording...", sound="Blow")

    def transcribing(self) -> None:
        """Notify that transcription is in progress."""
        _notify("VoiceTranser", "⠋ Transcribing...")

    def done(self) -> None:
        """Notify that the result has been pasted."""
        _notify("VoiceTranser", "✅ Done — pasted", sound="Glass")

    def clear(self) -> None:
        """No-op for notification mode (notifications auto-dismiss)."""
        pass
