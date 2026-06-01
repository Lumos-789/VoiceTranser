"""CLI entry point — daemon mode, one-shot mode, or file processing."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from voicetranser.config import Config, load_config
from voicetranser.output import output
from voicetranser.recorder import Recorder
from voicetranser.refiner import refine
from voicetranser.transcriber import transcribe


def process_audio(audio_data: bytes, config: Config, *, auto_paste: bool = True) -> str:
    """Full pipeline: audio bytes → transcript → refined prompt → output."""
    sys.stderr.write("[Transcribing...]\n")
    transcript = transcribe(
        audio_data,
        language=config.language,
        model_size=config.whisper_model,
    )

    if not transcript:
        sys.stderr.write("[No speech detected]\n")
        return ""

    sys.stderr.write(f"[Transcript] {transcript}\n")
    sys.stderr.write("[Refining...]\n")

    refined = refine(
        transcript,
        api_key=config.minimax_api_key,
        base_url=config.minimax_base_url,
        model=config.minimax_model,
        system_prompt=config.refine_system_prompt_text,
    )

    sys.stderr.write(f"[Refined] {refined}\n")
    output(refined, auto_paste=auto_paste)
    return refined


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
    """Run in daemon mode with global hotkey listener."""
    from voicetranser.hotkey import HotkeyListener

    recorder = Recorder(sample_rate=config.sample_rate)

    def on_press() -> None:
        recorder.start()

    def on_release() -> None:
        audio_data = recorder.stop()
        if audio_data is None:
            sys.stderr.write("[Recording too short]\n")
            return
        process_audio(audio_data, config, auto_paste=True)

    listener = HotkeyListener(config.hotkey, on_press, on_release)
    listener.start()


def show_config(config: Config) -> None:
    """Print current configuration."""
    print("VoiceTranser Configuration:")
    print(f"  MiniMax Model : {config.minimax_model}")
    print(f"  MiniMax URL   : {config.minimax_base_url}")
    print(f"  MiniMax Key   : {config.minimax_api_key[:8]}..." if config.minimax_api_key else "  MiniMax Key   : (not set)")
    print(f"  Whisper Model : {config.whisper_model}")
    print(f"  Hotkey        : {config.hotkey}")
    print(f"  Sample Rate   : {config.sample_rate}")
    print(f"  Language      : {config.language}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="voicetranser",
        description="Voice input → AI-refined prompt → auto-paste to Claude Code",
    )
    parser.add_argument("--once", action="store_true", help="Record once (interactive, for debugging)")
    parser.add_argument("--file", type=str, help="Process an audio file directly")
    parser.add_argument("--config", action="store_true", help="Show current configuration and exit")
    parser.add_argument("--no-paste", action="store_true", help="Copy to clipboard only, don't auto-paste")
    args = parser.parse_args()

    cfg = load_config()

    if args.config:
        show_config(cfg)
        return

    auto_paste = not args.no_paste

    if args.file:
        run_file(args.file, cfg, auto_paste=auto_paste)
    elif args.once:
        run_once(cfg, auto_paste=auto_paste)
    else:
        run_daemon(cfg)


if __name__ == "__main__":
    main()
