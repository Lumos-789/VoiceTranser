"""Per-checkout launchd configuration for VoiceTranser."""

from __future__ import annotations

import os
import plistlib
import subprocess
from pathlib import Path
from typing import Any

from voicetranser.config import DEFAULT_SERVER_PORT

LABEL = "com.voicetranser-sense"
DEFAULT_ENGINE = "qwen3-mlx"


def build_plist(
    repo_root: Path,
    *,
    python: Path | None = None,
    home: Path | None = None,
    port: int = DEFAULT_SERVER_PORT,
    engine: str = DEFAULT_ENGINE,
) -> dict[str, Any]:
    """Build a plist whose paths point at this checkout, not the author's Mac."""
    root = repo_root.expanduser().absolute()
    home_dir = (home or Path.home()).expanduser().absolute()
    python_path = (python or root / ".venv" / "bin" / "python3").expanduser().absolute()
    log_path = home_dir / "Library" / "Logs" / f"VoiceTranser-sense.log"

    return {
        "Label": LABEL,
        "ProgramArguments": [str(python_path), "-m", "voicetranser"],
        "WorkingDirectory": str(root),
        "EnvironmentVariables": {
            "HF_ENDPOINT": "https://hf-mirror.com",
            "STT_ENGINE": engine,
            "SERVER_PORT": str(port),
        },
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(log_path),
        "StandardErrorPath": str(log_path),
    }


def write_plist(
    repo_root: Path,
    *,
    dest: Path | None = None,
    python: Path | None = None,
    home: Path | None = None,
    port: int = DEFAULT_SERVER_PORT,
    engine: str = DEFAULT_ENGINE,
) -> Path:
    home_dir = (home or Path.home()).expanduser().absolute()
    destination = dest or home_dir / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    payload = build_plist(
        repo_root,
        python=python,
        home=home_dir,
        port=port,
        engine=engine,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(plistlib.dumps(payload, fmt=plistlib.FMT_XML))
    return destination


def load_plist(dest: Path) -> None:
    domain = f"gui/{os.getuid()}"
    for label in (LABEL, "com.voicetranser"):
        subprocess.run(
            ["launchctl", "bootout", f"{domain}/{label}"],
            check=False,
            capture_output=True,
            text=True,
        )
    subprocess.run(
        ["launchctl", "bootstrap", domain, str(dest)],
        check=True,
    )
