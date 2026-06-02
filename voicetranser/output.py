"""Output — copy refined prompt to clipboard and auto-paste."""

from __future__ import annotations

import subprocess

import pyperclip


def _paste_via_menu() -> bool:
    """Click Edit > Paste in the frontmost app. Returns False if menu not found."""
    result = subprocess.run(
        [
            "osascript",
            "-e",
            'delay 0.1',
            "-e",
            'tell application "System Events" to tell process (name of first application process whose frontmost is true) to click menu item "Paste" of menu "Edit" of menu bar 1',
        ],
        capture_output=True,
    )
    return result.returncode == 0


def _paste_via_keystroke() -> None:
    """Simulate Cmd+V via AppleScript (fallback, may cause double-paste with pynput)."""
    subprocess.run(
        [
            "osascript",
            "-e",
            'delay 0.1',
            "-e",
            'tell application "System Events" to keystroke "v" using command down',
        ],
        check=False,
    )


def output(text: str, *, auto_paste: bool = True) -> None:
    """Copy text to clipboard and optionally auto-paste.

    Prefers clicking Edit > Paste (bypasses keyboard events entirely,
    avoiding pynput CGEventTap conflicts). Falls back to keystroke
    simulation for apps without a standard Edit menu.
    """
    if not text:
        return

    pyperclip.copy(text)

    if auto_paste:
        if not _paste_via_menu():
            _paste_via_keystroke()
