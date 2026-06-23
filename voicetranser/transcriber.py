"""Speech-to-text transcription via mlx-whisper (Apple Silicon optimized)."""

from __future__ import annotations

import os
import sys
import tempfile

# Ensure homebrew bins (ffmpeg, etc.) are on PATH — launchd doesn't inherit shell PATH
_HOMEBREW_BIN = "/opt/homebrew/bin"
if _HOMEBREW_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _HOMEBREW_BIN + ":" + os.environ.get("PATH", "")

# HF mirror for China network
if not os.environ.get("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import mlx.core as mx
import mlx_whisper

# Cap the MLX Metal allocator's buffer cache. Without this, the reuse pool of
# freed buffers grows without bound across transcriptions (14 GB observed after
# ~7 days of uptime). Model weights live outside this pool and are unaffected.
mx.set_cache_limit(1024 * 1024 * 1024)  # 1 GB

# Singleton — model repo is resolved once, reused across calls
_model_repo: str | None = None


def _get_model_repo(model_size: str = "large-v3") -> str:
    global _model_repo
    if _model_repo is None:
        sys.stderr.write(f"[Loading Whisper model '{model_size}' via mlx-whisper...]\n")
        _model_repo = f"mlx-community/whisper-{model_size}-mlx"
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
