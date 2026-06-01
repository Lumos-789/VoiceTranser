"""Output — copy refined prompt to clipboard and auto-paste."""

from __future__ import annotations

import subprocess

import pyperclip


def output(text: str, *, auto_paste: bool = True) -> None:
    """Copy text to clipboard and optionally simulate Cmd+V paste."""
    if not text:
        return

    pyperclip.copy(text)

    if auto_paste:
        # Brief delay to ensure clipboard is ready
        subprocess.run(
            [
                "osascript",
                "-e",
                'delay 0.05',
                "-e",
                'tell application "System Events" to keystroke "v" using command down',
            ],
            check=False,
        )
