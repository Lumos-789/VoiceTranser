"""Speech-to-text transcription — 三引擎,按 engine 分派。

  qwen3-mlx  : mlx-audio + Qwen3-ASR 0.6B 4bit, MLX/Metal GPU 推理。
               RTF 0.012-0.021(实测 2026-11-01, 约为 sensevoice CPU 的一半),
               纯中文近完美自带标点引号、中英夹杂/方言强、LLM 纠错。默认主力。
  sensevoice : sherpa-onnx + SenseVoice Small (int8),非自回归并行解码,
               中文秒出(RTF≈0.03),中英日韩粤母语级。CPU fallback。
  mlx-whisper: mlx-whisper large-v3,自回归,英文/小语种更强。fallback。

两个旧引擎各自懒加载、单例;互不 import(只用其中一个的实例不必装另一个的依赖)。
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import threading
import wave
from pathlib import Path

# Ensure homebrew bins on PATH — launchd doesn't inherit shell PATH
_HOMEBREW_BIN = "/opt/homebrew/bin"
if _HOMEBREW_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _HOMEBREW_BIN + ":" + os.environ.get("PATH", "")

# HF mirror for China network (mlx-whisper / mlx-audio model download)
if not os.environ.get("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

_MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "sense-voice"
_QWEN3_MLX_MODEL = "mlx-community/Qwen3-ASR-0.6B-4bit"

# ---- 单例缓存 ----
_sense_recognizer = None
_whisper_model_repo: str | None = None
_qwen3_mlx_model = None
_qwen3_mlx_lock = threading.Lock()


# ============================ Qwen3-ASR MLX (主力) ============================

def _get_qwen3_mlx_model():
    """懒加载 Qwen3-ASR 0.6B 4bit (MLX/Metal)。首次加载 ~75s, 服务常驻只发生一次。

    与预热线程并发安全: 加载全程持锁, 二次调用直接命中单例。
    """
    global _qwen3_mlx_model
    if _qwen3_mlx_model is not None:
        return _qwen3_mlx_model
    with _qwen3_mlx_lock:
        if _qwen3_mlx_model is not None:
            return _qwen3_mlx_model
        import mlx.core as mx

        # Cap the Metal allocator's buffer cache — same unbounded-growth issue
        # as mlx-whisper (see voicetranser-mlx-memory knowledge note).
        mx.set_cache_limit(1024 * 1024 * 1024)  # 1 GB
        sys.stderr.write(f"[Loading Qwen3-ASR '{_QWEN3_MLX_MODEL}' (mlx-audio)...]\n")
        from mlx_audio.stt import load_model

        model = load_model(_QWEN3_MLX_MODEL)
        mx.eval(model.parameters())
        _qwen3_mlx_model = model
        sys.stderr.write("[Qwen3-ASR ready]\n")
    return _qwen3_mlx_model


def preload_engine(engine: str) -> None:
    """预热当前引擎的模型(服务启动时后台调用, 避免首次转写等冷加载)。"""
    try:
        if engine == "qwen3-mlx":
            _get_qwen3_mlx_model()
        elif engine == "sensevoice":
            _get_sense_recognizer()
    except Exception as exc:  # 预热失败不致命, 首次转写时再暴露真实错误(fail-loud)
        sys.stderr.write(f"[preload '{engine}' failed: {exc}]\n")


def _transcribe_qwen3_mlx(audio_data: bytes) -> str:
    import mlx.core as mx
    import numpy as np

    model = _get_qwen3_mlx_model()
    # WAV bytes → float32 [-1,1](recorder 产 16k mono int16)
    with wave.open(io.BytesIO(audio_data), "rb") as wf:
        sr = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

    out = model.generate(mx.array(samples))
    return (getattr(out, "text", "") or "").strip()


# ============================ SenseVoice ============================

def _get_sense_recognizer():
    global _sense_recognizer
    if _sense_recognizer is None:
        import sherpa_onnx  # 延迟 import:只用 mlx-whisper 的实例不必装 sherpa-onnx

        onnx = _MODEL_DIR / "model.int8.onnx"
        tok = _MODEL_DIR / "tokens.txt"
        if not onnx.exists() or not tok.exists():
            raise RuntimeError(
                f"SenseVoice 模型未下载: {_MODEL_DIR}\n"
                f"请先运行: uv run python download_model.py"
            )
        sys.stderr.write("[Loading SenseVoice (sherpa-onnx)...]\n")
        _sense_recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(onnx),
            tokens=str(tok),
            num_threads=4,
            use_itn=True,        # 逆文本归一化:数字/日期转阿拉伯数字 + 加标点
            language="auto",     # 自动判语种(中英日韩粤)
        )
        sys.stderr.write("[SenseVoice ready]\n")
    return _sense_recognizer


def _transcribe_sense(audio_data: bytes) -> str:
    """SenseVoice 初始化时已 language='auto',运行时无需再传语种。"""
    import numpy as np

    recognizer = _get_sense_recognizer()
    # WAV bytes → float32 [-1,1](recorder 产 16k mono int16)
    with wave.open(io.BytesIO(audio_data), "rb") as wf:
        sr = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

    stream = recognizer.create_stream()
    stream.accept_waveform(sr, samples)
    recognizer.decode_stream(stream)
    return stream.result.text.strip()


# ============================ mlx-whisper (fallback) ============================

def _get_whisper_model_repo(model_size: str) -> str:
    global _whisper_model_repo
    if _whisper_model_repo is None:
        import mlx.core as mx
        # Cap the MLX Metal allocator's buffer cache. Without this, the reuse pool
        # of freed buffers grows unbounded across transcriptions (14 GB observed
        # after ~7 days of uptime). Model weights live outside this pool.
        mx.set_cache_limit(1024 * 1024 * 1024)  # 1 GB
        sys.stderr.write(f"[Loading Whisper model '{model_size}' via mlx-whisper...]\n")
        _whisper_model_repo = f"mlx-community/whisper-{model_size}-mlx"
        sys.stderr.write("[Whisper model ready]\n")
    return _whisper_model_repo


def _transcribe_whisper(audio_data: bytes, language: str, model_size: str) -> str:
    import mlx_whisper

    model_repo = _get_whisper_model_repo(model_size)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
        tmp.write(audio_data)
        tmp.flush()
        result = mlx_whisper.transcribe(
            tmp.name,
            path_or_hf_repo=model_repo,
            language=language,
            word_timestamps=False,
        )
    return result.get("text", "").strip()


# ============================ 公共入口 ============================

def transcribe(
    audio_data: bytes,
    language: str = "zh",
    model_size: str = "large-v3",
    engine: str = "sensevoice",
) -> str:
    """Transcribe WAV audio bytes → text.

    engine:
      "qwen3-mlx"  — Qwen3-ASR 0.6B 4bit MLX/Metal(默认主力, 中文最优+最快)
      "sensevoice" — SenseVoice(CPU fallback, 中文秒出)
      "mlx-whisper" — Whisper large-v3(英文/小语种更强,fallback)
    """
    if engine == "qwen3-mlx":
        return _transcribe_qwen3_mlx(audio_data)
    if engine == "sensevoice":
        return _transcribe_sense(audio_data)
    if engine == "mlx-whisper":
        return _transcribe_whisper(audio_data, language, model_size)
    raise ValueError(
        f"未知 STT 引擎: {engine!r},支持: qwen3-mlx / sensevoice / mlx-whisper"
    )
