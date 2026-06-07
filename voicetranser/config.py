"""Configuration management — loads from .env file and environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    # Local Whisper (STT)
    whisper_model: str = "large-v3"
    hf_endpoint: str = "https://huggingface.co"
    # Audio & server
    server_port: int = 9876
    sample_rate: int = 16000
    language: str = "zh"


def load_config(dotenv_path: Path | None = None) -> Config:
    """Load config from .env file (optional) and environment variables."""
    if dotenv_path is None:
        dotenv_path = Path(__file__).resolve().parent.parent / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)

    # Set HuggingFace mirror for China network
    hf_endpoint = os.getenv("HF_ENDPOINT", "https://huggingface.co")
    os.environ["HF_ENDPOINT"] = hf_endpoint

    return Config(
        whisper_model=os.getenv("WHISPER_MODEL", "large-v3"),
        hf_endpoint=hf_endpoint,
        server_port=int(os.getenv("SERVER_PORT", "9876")),
        sample_rate=int(os.getenv("SAMPLE_RATE", "16000")),
        language=os.getenv("LANGUAGE", "zh"),
    )
