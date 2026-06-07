"""CLI entry point — daemon mode, one-shot mode, or file processing."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from voicetranser.config import Config, load_config
from voicetranser.output import output
from voicetranser.recorder import Recorder
from voicetranser.status import StatusDisplay
from voicetranser.transcriber import transcribe


def process_audio(
    audio_data: bytes,
    config: Config,
    *,
    auto_paste: bool = True,
    status: StatusDisplay | None = None,
) -> str:
    """Full pipeline: audio bytes → transcript → output."""
    use_status = status is not None

    if use_status:
        status.transcribing()
    else:
        sys.stderr.write("[Transcribing...]\n")

    transcript = transcribe(
        audio_data,
        language=config.language,
        model_size=config.whisper_model,
    )

    if not transcript:
        if use_status:
            status.clear()
        sys.stderr.write("[No speech detected]\n")
        return ""

    if not use_status:
        sys.stderr.write(f"[Transcript] {transcript}\n")

    output(transcript, auto_paste=auto_paste)

    if use_status:
        status.done()
    else:
        sys.stderr.write(f"[Done] {transcript}\n")

    return transcript


def run_once(config: Config, *, auto_paste: bool = True) -> None:
    """Record once from microphone, process, and output."""
    recorder = Recorder(sample_rate=config.sample_rate)

    sys.stderr.write("[Press Enter to start recording, press Enter again to stop]\n")
    input()
    recorder.start()

    sys.stderr.write("[Press Enter to stop recording]\n")
    input()
    audio_data = recorder.stop()

    if audio_data is None:
        sys.stderr.write("[Recording too short or no audio]\n")
        return

    process_audio(audio_data, config, auto_paste=auto_paste)


def run_file(file_path: str, config: Config, *, auto_paste: bool = False) -> None:
    """Process an audio file directly."""
    path = Path(file_path)
    if not path.exists():
        sys.stderr.write(f"[File not found: {file_path}]\n")
        sys.exit(1)

    audio_data = path.read_bytes()
    process_audio(audio_data, config, auto_paste=auto_paste)


def run_daemon(config: Config) -> None:
    """Run in daemon mode with HTTP toggle server."""
    from voicetranser.server import VoiceServer

    recorder = Recorder(sample_rate=config.sample_rate)
    status = StatusDisplay()
    server = VoiceServer(
        config=config,
        recorder=recorder,
        status=status,
        port=config.server_port,
    )
    server.start()


def show_config(config: Config) -> None:
    """Print current configuration."""
    print("VoiceTranser Configuration:")
    print(f"  Whisper Model : {config.whisper_model}")
    print(f"  Sample Rate   : {config.sample_rate}")
    print(f"  Language      : {config.language}")
    print(f"  Server Port   : {config.server_port}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="voicetranser",
        description="Voice input → transcript → auto-paste",
    )
    parser.add_argument("--once", action="store_true", help="Record once (interactive, for debugging)")
    parser.add_argument("--file", type=str, help="Process an audio file directly")
    parser.add_argument("--config", action="store_true", help="Show current configuration and exit")
    parser.add_argument("--no-paste", action="store_true", help="Copy to clipboard only, don't auto-paste")
    args = parser.parse_args()

    cfg = load_config()

    auto_paste = not args.no_paste

    if args.config:
        show_config(cfg)
        return

    if args.file:
        run_file(args.file, cfg, auto_paste=auto_paste)
    elif args.once:
        run_once(cfg, auto_paste=auto_paste)
    else:
        run_daemon(cfg)


if __name__ == "__main__":
    main()
