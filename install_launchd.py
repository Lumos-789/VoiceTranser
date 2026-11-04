#!/usr/bin/env python3
"""Write and load a launchd agent for the current VoiceTranser checkout."""

from __future__ import annotations

import argparse
import plistlib
import sys
from pathlib import Path

from voicetranser.config import DEFAULT_SERVER_PORT
from voicetranser.launchd import (
    DEFAULT_ENGINE,
    LABEL,
    build_plist,
    load_plist,
    write_plist,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, help="plist output path")
    parser.add_argument("--port", type=int, default=DEFAULT_SERVER_PORT)
    parser.add_argument("--engine", default=DEFAULT_ENGINE)
    parser.add_argument("--no-load", action="store_true", help="write only")
    parser.add_argument("--dry-run", action="store_true", help="print plist only")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    python = root / ".venv" / "bin" / "python3"
    if not args.dry_run and not python.exists():
        raise SystemExit(
            f"missing {python}; run `uv sync` in {root} before installing the service"
        )

    if args.dry_run:
        payload = build_plist(root, python=python, port=args.port, engine=args.engine)
        sys.stdout.buffer.write(plistlib.dumps(payload, fmt=plistlib.FMT_XML))
        return

    dest = write_plist(
        root,
        dest=args.dest,
        port=args.port,
        engine=args.engine,
    )
    print(f"wrote {dest}")
    if args.no_load:
        return

    load_plist(dest)
    print(f"loaded {LABEL}")
    print(f"check: curl -s http://127.0.0.1:{args.port}/status")


if __name__ == "__main__":
    main()
