"""Speech-to-text transcription via mlx-whisper (Apple Silicon optimized)."""

from __future__ import annotations

import os
import sys
import tempfile

# Ensure HF mirror is set before importing mlx_whisper
if not os.environ.get("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import mlx_whisper

# Singleton — model repo is resolved once, reused across calls
_model_repo: str | None = None


def _get_model_repo(model_size: str = "large-v3") -> str:
    global _model_repo
    if _model_repo is None:
        sys.stderr.write(f"[Loading Whisper model '{model_size}' via mlx-whisper...]\n")
        _model_repo = f"mlx-community/whisper-{model_size}"
        sys.stderr.write("[Whisper model ready]\n")
    return _model_repo


def transcribe(
    audio_data: bytes,
    language: str = "zh",
    model_size: str = "large-v3",
) -> str:
    """Transcribe WAV audio bytes to text using mlx-whisper.

    Returns the raw transcript string. Empty string if nothing detected.
    """
    model_repo = _get_model_repo(model_size)

    # mlx-whisper needs a file path — write to a temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        tmp.write(audio_data)
        tmp.flush()
        result = mlx_whisper.transcribe(
            tmp.name,
            path_or_hf_repo=model_repo,
            language=language,
            word_timestamps=False,
        )

    text = result.get("text", "").strip()
    return text
