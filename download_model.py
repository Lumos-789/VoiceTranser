"""下载 SenseVoice int8 模型(sherpa-onnx 格式)到 models/sense-voice/。

源:HuggingFace 镜像 hf-mirror.com(国内快)。官方 GitHub release 国内龟速,
故改走镜像单文件下载(model.int8.onnx 228MB + tokens.txt 308KB)。
幂等:目标文件已存在则跳过。

用法:
    uv run python download_model.py     # 项目 venv
    python3 download_model.py           # 系统 python(仅标准库即可跑)
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent / "models" / "sense-voice"
BASE = (
    "https://hf-mirror.com/csukuangfj/"
    "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/main"
)
FILES = ("model.int8.onnx", "tokens.txt")


def _progress(blocks: int, block_size: int, total: int) -> None:
    done = blocks * block_size
    if total > 0 and blocks % 200 == 0:
        sys.stderr.write(
            f"\r[download_model] {done // 1024 // 1024}MB / "
            f"{total // 1024 // 1024}MB ({done / total * 100:.0f}%)"
        )
        sys.stderr.flush()


def _download(url: str, dest: Path) -> None:
    print(f"[download_model] 下载 {url}")
    urllib.request.urlretrieve(url, dest, reporthook=_progress)
    sys.stderr.write("\n")


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        dest = MODEL_DIR / name
        if dest.exists():
            print(f"[download_model] 已存在,跳过: {dest}")
            continue
        _download(f"{BASE}/{name}", dest)
        size_kb = dest.stat().st_size // 1024
        unit = "MB" if size_kb >= 1024 else "KB"
        size = size_kb // 1024 if size_kb >= 1024 else size_kb
        print(f"[download_model] 完成: {name} ({size}{unit})")
    print("[download_model] 模型全部就绪")


if __name__ == "__main__":
    main()
