#!/usr/bin/env python3
"""发布元数据一致性 —— 版本号与文档命令不能各说各话。

运行:
    .venv/bin/python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from voicetranser import __version__  # noqa: E402


class TestVersionMetadata(unittest.TestCase):
    def test_pyproject_package_and_lock_agree(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
        match = re.search(r'name = "voicetranser"\nversion = "([^"]+)"', lock)

        self.assertEqual(pyproject["project"]["version"], __version__)
        self.assertEqual(package["version"], __version__)
        self.assertIsNotNone(match, "uv.lock 里找不到 voicetranser 条目")
        self.assertEqual(match.group(1), __version__)

    def test_changelog_covers_the_current_version(self) -> None:
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## {__version__}", changelog)

    def test_documented_test_command_is_the_working_one(self) -> None:
        package_doc = (ROOT / "PACKAGE.md").read_text(encoding="utf-8")
        self.assertIn(".venv/bin/python -m unittest discover -s tests -v", package_doc)
        self.assertNotIn("uv run python -m unittest", package_doc)


if __name__ == "__main__":
    unittest.main()
