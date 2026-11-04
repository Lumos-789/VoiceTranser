from __future__ import annotations

import plistlib
import tempfile
import unittest
from pathlib import Path

from voicetranser.config import DEFAULT_SERVER_PORT
from voicetranser.launchd import LABEL, build_plist, write_plist


class TestLaunchdPlist(unittest.TestCase):
    def test_default_port_is_the_application_config_default(self) -> None:
        payload = build_plist(Path("/tmp/VoiceTranser-checkout"))
        self.assertEqual(
            payload["EnvironmentVariables"]["SERVER_PORT"], str(DEFAULT_SERVER_PORT)
        )

    def test_paths_follow_the_checkout_and_user_home(self) -> None:
        root = Path("/tmp/VoiceTranser-checkout")
        home = Path("/tmp/VoiceTranser-home")
        payload = build_plist(root, home=home, port=9999, engine="sensevoice")

        self.assertEqual(payload["Label"], LABEL)
        self.assertEqual(
            payload["ProgramArguments"],
            [str(root / ".venv/bin/python3"), "-m", "voicetranser"],
        )
        self.assertEqual(payload["WorkingDirectory"], str(root))
        self.assertEqual(payload["EnvironmentVariables"]["SERVER_PORT"], "9999")
        self.assertEqual(payload["EnvironmentVariables"]["STT_ENGINE"], "sensevoice")
        self.assertEqual(
            payload["StandardOutPath"],
            str(home / "Library/Logs/VoiceTranser-sense.log"),
        )

    def test_write_plist_round_trips_xml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "agent.plist"
            write_plist(
                Path("/tmp/VoiceTranser-checkout"),
                dest=dest,
                home=Path("/tmp/VoiceTranser-home"),
            )
            payload = plistlib.loads(dest.read_bytes())
            self.assertEqual(payload["Label"], LABEL)
            self.assertTrue(payload["RunAtLoad"])
            self.assertTrue(payload["KeepAlive"])


if __name__ == "__main__":
    unittest.main()
