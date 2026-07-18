"""Configuration management — loads from .env file and environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    # STT engine: "sensevoice" (default, fast) or "mlx-whisper" (fallback)
    stt_engine: str = "sensevoice"
    # Local Whisper (STT) — only used when stt_engine == "mlx-whisper"
    whisper_model: str = "large-v3"
    hf_endpoint: str = "https://huggingface.co"
    # Audio & server
    server_port: int = 9876
    sample_rate: int = 16000
    language: str = "zh"
    # Feedback sounds (System/Library/Sounds/<name>.aiff). Set SOUND_ENABLED=false to mute.
    sound_enabled: bool = True
    start_sound: str = "Blow"
    done_sound: str = "Glass"
    # STT 误识词纠正(转写后、输出前)。词表为空 = 功能关闭。
    corrections_enabled: bool = True
    corrections: dict[str, str] = field(default_factory=dict)


def _to_bool(value: str, default: bool = False) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on") if value else default


def load_config(dotenv_path: Path | None = None) -> Config:
    """Load config from .env file (optional) and environment variables."""
    if dotenv_path is None:
        dotenv_path = Path(__file__).resolve().parent.parent / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)

    # Set HuggingFace mirror for China network
    hf_endpoint = os.getenv("HF_ENDPOINT", "https://huggingface.co")
    os.environ["HF_ENDPOINT"] = hf_endpoint

    # STT 误识词纠正词表。CORRECTIONS_FILE 空 → 用项目内 corrections.json;
    # 文件缺失/损坏 → 空字典(功能静默关闭)。
    from voicetranser.corrector import load_corrections

    corrections_file = os.getenv("CORRECTIONS_FILE", "")
    corrections = load_corrections(corrections_file or None)

    return Config(
        stt_engine=os.getenv("STT_ENGINE", "sensevoice"),
        whisper_model=os.getenv("WHISPER_MODEL", "large-v3"),
        hf_endpoint=hf_endpoint,
        server_port=int(os.getenv("SERVER_PORT", "9876")),
        sample_rate=int(os.getenv("SAMPLE_RATE", "16000")),
        language=os.getenv("LANGUAGE", "zh"),
        sound_enabled=_to_bool(os.getenv("SOUND_ENABLED", "true"), default=True),
        start_sound=os.getenv("START_SOUND", "Blow"),
        done_sound=os.getenv("DONE_SOUND", "Glass"),
        corrections_enabled=_to_bool(
            os.getenv("CORRECTIONS_ENABLED", "true"), default=True
        ),
        corrections=corrections,
    )
