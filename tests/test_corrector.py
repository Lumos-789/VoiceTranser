#!/usr/bin/env python3
"""corrector 模块单元测试 — STT 误识词纠正。

运行:
    uv run python tests/test_corrector.py
    # 或
    uv run python -m unittest tests.test_corrector
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# 让测试可以从项目根直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voicetranser.corrector import apply_corrections, load_corrections


class TestApplyCorrections(unittest.TestCase):
    def test_basic_replace(self) -> None:
        self.assertEqual(
            apply_corrections("open the scu menu", {"scu": "skill"}),
            "open the skill menu",
        )

    def test_case_insensitive_match(self) -> None:
        # 匹配时大小写不敏感:三种大小写形式都被识别为 'scu' → 'skill'
        # (value 原样输出,不跟着原文变大小写)
        self.assertEqual(
            apply_corrections("Scu SCU sCu", {"scu": "skill"}),
            "skill skill skill",
        )

    def test_value_kept_as_is(self) -> None:
        # value 原样输出大小写(不跟着原文变)
        self.assertEqual(
            apply_corrections("claude code rules", {"claude code": "Claude Code"}),
            "Claude Code rules",
        )

    def test_word_boundary_no_substring(self) -> None:
        # 词边界:\b 不会让 'scu' 改 'sculpture' / 'musculature'
        self.assertEqual(
            apply_corrections("sculpture and musculature scu", {"scu": "skill"}),
            "sculpture and musculature skill",
        )

    def test_phrase_priority_over_subtoken(self) -> None:
        # 多 token 短语优先于其子 token:'claude code' 不被 'code' 先吃掉
        self.assertEqual(
            apply_corrections(
                "i use claude code daily",
                {"claude code": "Claude Code", "code": "X"},
            ),
            "i use Claude Code daily",
        )

    def test_multiple_distinct_words(self) -> None:
        self.assertEqual(
            apply_corrections(
                "scu and scil here", {"scu": "skill", "scil": "skill"}
            ),
            "skill and skill here",
        )

    def test_chinese_text_unchanged(self) -> None:
        # 中文场景:词表里没匹配项时原样返回(不破坏中文)
        self.assertEqual(
            apply_corrections("你好世界 scu", {"scu": "skill"}),
            "你好世界 skill",
        )

    def test_empty_corrections_passthrough(self) -> None:
        self.assertEqual(apply_corrections("hello world", {}), "hello world")

    def test_empty_text_passthrough(self) -> None:
        self.assertEqual(apply_corrections("", {"scu": "skill"}), "")

    def test_special_chars_in_key(self) -> None:
        # key 含特殊字符(点/斜杠/连字符)应被 re.escape 安全处理
        self.assertEqual(
            apply_corrections("use c.d.py now", {"c.d.py": "module.py"}),
            "use module.py now",
        )

    def test_no_false_match_when_word_absent(self) -> None:
        self.assertEqual(
            apply_corrections("skillful skilled", {"skill": "X"}),
            "skillful skilled",
        )


class TestLoadCorrections(unittest.TestCase):
    def test_load_valid_file(self) -> None:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump({"Scu": "skill", "CODE": "Code"}, f)
            path = f.name
        try:
            result = load_corrections(path)
            # key 应被规范化为小写
            self.assertEqual(result, {"scu": "skill", "code": "Code"})
        finally:
            Path(path).unlink()

    def test_load_missing_file_returns_empty(self) -> None:
        # 缺失文件 → 空字典(功能静默关闭,不抛)
        self.assertEqual(load_corrections("/nonexistent/path/foo.json"), {})

    def test_load_invalid_json_returns_empty(self) -> None:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            f.write("{not valid json")
            path = f.name
        try:
            self.assertEqual(load_corrections(path), {})
        finally:
            Path(path).unlink()

    def test_load_filters_comment_keys_and_empty_values(self) -> None:
        # "_comment" 这种注释行和空 value 应被过滤掉
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(
                {"_comment": "this is a note", "scu": "skill", "bad": ""},
                f,
            )
            path = f.name
        try:
            result = load_corrections(path)
            self.assertEqual(result, {"scu": "skill"})
        finally:
            Path(path).unlink()

    def test_load_default_path_when_none(self) -> None:
        # path=None → 用项目内默认 corrections.json。我们只验证它返回 dict
        # 且至少包含预填的 scu(项目根那份);若不存在则返回空也算通过。
        result = load_corrections(None)
        self.assertIsInstance(result, dict)
        # 项目根那份预填了 scu → skill
        self.assertEqual(result.get("scu"), "skill")


if __name__ == "__main__":
    unittest.main(verbosity=2)
