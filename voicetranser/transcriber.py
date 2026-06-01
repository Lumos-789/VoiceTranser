"""Speech-to-text transcription via local faster-whisper (CTranslate2)."""

from __future__ import annotations

import io
import os
import sys

# Ensure HF mirror is set before importing faster_whisper
if not os.environ.get("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from faster_whisper import WhisperModel

# Singleton — model is loaded once, reused across calls
_model: WhisperModel | None = None


def _get_model(model_size: str = "large-v3") -> WhisperModel:
    global _model
    if _model is None:
        sys.stderr.write(f"[Loading Whisper model '{model_size}'...]\n")
        _model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
        )
        sys.stderr.write("[Whisper model ready]\n")
    return _model


def transcribe(
    audio_data: bytes,
    language: str = "zh",
    model_size: str = "large-v3",
) -> str:
    """Transcribe WAV audio bytes to text using local faster-whisper.

    Returns the raw transcript string. Empty string if nothing detected.
    """
    model = _get_model(model_size)

    segments, info = model.transcribe(
        io.BytesIO(audio_data),
        language=language,
        beam_size=5,
        vad_filter=True,
    )

    text = " ".join(segment.text.strip() for segment in segments)
    return text.strip()
