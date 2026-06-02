"""macOS notification feedback for daemon mode."""

from __future__ import annotations

import subprocess


def _notify(title: str, text: str, sound: str | None = None) -> None:
    """Post a macOS notification via osascript."""
    sound_part = f' sound name "{sound}"' if sound else ""
    escaped_text = text.replace("\\", "\\\\").replace('"', '\\"')
    escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
    script = f'display notification "{escaped_text}" with title "{escaped_title}"{sound_part}'
    subprocess.run(
        ["osascript", "-e", script],
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

    def refining(self) -> None:
        """Notify that prompt refinement is in progress."""
        _notify("VoiceTranser", "✨ Refining...")

    def done(self) -> None:
        """Notify that the result has been pasted."""
        _notify("VoiceTranser", "✅ Done — pasted", sound="Glass")

    def clear(self) -> None:
        """No-op for notification mode (notifications auto-dismiss)."""
        pass
