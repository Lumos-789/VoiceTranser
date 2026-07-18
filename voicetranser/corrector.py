"""STT 误识词纠正 — 纯整词匹配的 post-transcription fix-up.

词表存在项目根 ``corrections.json``(可经 ``CORRECTIONS_FILE`` 覆盖):

    {"scu": "skill", "claude code": "Claude Code"}

- key   = STT 常输出的误识形式(匹配时大小写不敏感)
- value = 正确写法(输出时原样保留大小写)
- 纯整词匹配,不会误伤子串(``scu`` 不会改 ``sculpture``)
- 多 token 短语按长度降序优先,避免短 key 吃掉长短语

词表缺失或 JSON 损坏 → 返回空字典 → 功能静默关闭,零风险。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "corrections.json"


def load_corrections(path: Path | str | None = None) -> dict[str, str]:
    """Load correction map from JSON.

    Returns ``{}`` on missing file or invalid JSON — the feature silently
    turns off rather than breaking the pipeline.
    """
    p = Path(path) if path else _DEFAULT_PATH
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    # key 统一小写(大小写不敏感匹配),value 原样保留;过滤掉以 "_" 开头的
    # 注释行(如 "_comment")和空 value。
    return {
        str(k).lower(): str(v)
        for k, v in data.items()
        if v and not str(k).startswith("_")
    }


def apply_corrections(text: str, corrections: dict[str, str]) -> str:
    """Replace whole-word/phrase matches case-insensitively, keep value as-is.

    A single left-to-right regex pass with keys sorted longest-first in the
    alternation: each position in the input is matched at most once, so a
    multi-token key wins over its substrings AND a previously-substituted
    value is never re-scanned (e.g. ``"claude code" → "Claude Code"`` is
    not then re-eaten by a ``"code"`` rule).
    """
    if not corrections or not text:
        return text
    # 按 key 长度降序排列进 alternation:regex 按顺序短路,长的优先匹配。
    keys_long_first = sorted(corrections, key=len, reverse=True)
    pattern = re.compile(
        r"\b(?:" + "|".join(re.escape(k) for k in keys_long_first) + r")\b",
        re.IGNORECASE,
    )
    # corrections 的 key 已在 load_corrections 中统一 lower,这里用匹配文本
    # 的小写形式回查 → 大小写不敏感匹配 + value 原样输出。
    return pattern.sub(lambda m: corrections[m.group(0).lower()], text)
