"""Global hotkey listener — push-to-talk via pynput."""

from __future__ import annotations

import sys

from pynput import keyboard


# Map from config string to pynput key
_KEY_MAP = {
    "cmd_r": keyboard.Key.cmd_r,
    "cmd_l": keyboard.Key.cmd_l,
    "alt_r": keyboard.Key.alt_r,
    "alt_l": keyboard.Key.alt_l,
    "ctrl_r": keyboard.Key.ctrl_r,
    "ctrl_l": keyboard.Key.ctrl_l,
    "shift_r": keyboard.Key.shift_r,
    "shift_l": keyboard.Key.shift_l,
    "f5": keyboard.Key.f5,
    "f6": keyboard.Key.f6,
    "f7": keyboard.Key.f7,
    "f8": keyboard.Key.f8,
}


def resolve_key(key_name: str) -> keyboard.Key | keyboard.KeyCode:
    """Resolve a config key name to a pynput key object."""
    key_name = key_name.lower().strip()
    if key_name in _KEY_MAP:
        return _KEY_MAP[key_name]
    # Single character key
    if len(key_name) == 1:
        return keyboard.KeyCode.from_char(key_name)
    raise SystemExit(f"Unknown hotkey: {key_name!r}. Supported: {', '.join(_KEY_MAP)}")


class HotkeyListener:
    """Listens for a global push-to-talk hotkey.

    Usage:
        listener = HotkeyListener("cmd_r", on_press, on_release)
        listener.start()  # blocks
    """

    def __init__(
        self,
        hotkey_name: str,
        on_press: object,
        on_release: object,
    ) -> None:
        self._target_key = resolve_key(hotkey_name)
        self._on_press = on_press
        self._on_release = on_release
        self._held = False

    def start(self) -> None:
        """Start listening (blocks the current thread)."""
        sys.stderr.write(f"[VoiceTranser] Listening on hotkey (press & hold to speak, release to process)\n")

        def on_press(key: keyboard.Key | keyboard.KeyCode | None) -> None:
            if key == self._target_key and not self._held:
                self._held = True
                if self._on_press:
                    self._on_press()

        def on_release(key: keyboard.Key | keyboard.KeyCode | None) -> None:
            if key == self._target_key and self._held:
                self._held = False
                if self._on_release:
                    self._on_release()

        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
