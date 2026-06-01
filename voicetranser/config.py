"""Configuration management — loads from .env file and environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

_PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass(frozen=True)
class Config:
    # MiniMax (prompt refinement)
    minimax_api_key: str
    minimax_base_url: str = "https://api.minimaxi.com/anthropic"
    minimax_model: str = "MiniMax-M3"
    # Local Whisper (STT)
    whisper_model: str = "large-v3"
    hf_endpoint: str = "https://hf-mirror.com"
    # Audio & hotkey
    hotkey: str = "cmd_r"
    sample_rate: int = 16000
    language: str = "zh"
    # System prompt
    refine_system_prompt: str = field(default="", repr=False)

    @property
    def refine_system_prompt_text(self) -> str:
        if self.refine_system_prompt:
            return self.refine_system_prompt
        path = _PROMPTS_DIR / "refine_system.txt"
        return path.read_text(encoding="utf-8").strip()


def load_config(dotenv_path: Path | None = None) -> Config:
    """Load config from .env file (optional) and environment variables."""
    if dotenv_path is None:
        dotenv_path = Path(__file__).resolve().parent.parent / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)

    # Set HuggingFace mirror for China network
    hf_endpoint = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")
    os.environ["HF_ENDPOINT"] = hf_endpoint

    minimax_key = os.getenv("MINIMAX_API_KEY", "")

    if not minimax_key:
        raise SystemExit("MINIMAX_API_KEY is required. Set it in .env or environment.")

    return Config(
        minimax_api_key=minimax_key,
        minimax_base_url=os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/anthropic"),
        minimax_model=os.getenv("MINIMAX_MODEL", "MiniMax-M3"),
        whisper_model=os.getenv("WHISPER_MODEL", "large-v3"),
        hf_endpoint=hf_endpoint,
        hotkey=os.getenv("HOTKEY", "cmd_r"),
        sample_rate=int(os.getenv("SAMPLE_RATE", "16000")),
        language=os.getenv("LANGUAGE", "zh"),
    )
