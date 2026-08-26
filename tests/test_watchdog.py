#!/usr/bin/env python3
"""watchdog 模块单元测试 — CoreAudio 死锁看门狗（2026-08-27 事故防护）。

运行:
    uv run python tests/test_watchdog.py
"""

from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

# 让测试可以从项目根直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voicetranser.watchdog import AudioWatchdog


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class TestDeadline(unittest.TestCase):
    def test_not_armed_never_expires(self) -> None:
        clock = FakeClock()
        wd = AudioWatchdog(timeout=2.0, poll=0.01, clock=clock)
        clock.now += 10_000
        self.assertFalse(wd.expired())

    def test_expires_only_after_timeout(self) -> None:
        clock = FakeClock()
        wd = AudioWatchdog(timeout=2.0, poll=0.01, clock=clock)
        with wd:
            clock.now += 1.9
            self.assertFalse(wd.expired(), "deadline 未到不应触发")
            clock.now += 0.2
            self.assertTrue(wd.expired(), "超时应标记过期")
        # 正常完成后解除武装，永不触发
        clock.now += 10_000
        self.assertFalse(wd.expired())

    def test_nested_enter_keeps_deadline(self) -> None:
        clock = FakeClock()
        wd = AudioWatchdog(timeout=2.0, poll=0.01, clock=clock)
        with wd:
            clock.now += 1.0
            with wd:
                clock.now += 1.5  # 超过最外层 deadline
                self.assertTrue(wd.expired())
            # 内层退出不得清除外层的 deadline
            self.assertTrue(wd.expired())


class TestFiring(unittest.TestCase):
    def test_thread_hard_exits_when_call_overruns(self) -> None:
        """模拟 CoreAudio 卡死：guard 内 __exit__ 永不执行，看门狗必须触发。"""
        wd = AudioWatchdog(timeout=0.05, poll=0.01)
        fired = threading.Event()

        def fake_exit(code: int) -> None:
            fired.set()
            raise SystemExit(code)  # 结束看门狗线程

        entered = threading.Event()
        hold = threading.Event()

        def hung_audio_op() -> None:
            with wd:
                entered.set()
                hold.wait(5)  # 卡死：deadline 保持武装

        with mock.patch("os._exit", side_effect=fake_exit):
            t = threading.Thread(target=hung_audio_op, daemon=True)
            t.start()
            self.assertTrue(entered.wait(2), "音频操作未进入 guard")
            self.assertTrue(fired.wait(2), "看门狗在 2s 内未触发")
            hold.set()
            t.join(2)

    def test_completed_call_never_fires(self) -> None:
        wd = AudioWatchdog(timeout=0.2, poll=0.02)
        fired = threading.Event()

        def fake_exit(code: int) -> None:
            fired.set()
            raise SystemExit(code)

        with mock.patch("os._exit", side_effect=fake_exit):
            with wd:
                time.sleep(0.05)  # 远小于 timeout，正常完成
            time.sleep(0.3)  # 超过 timeout 的观察窗口
        self.assertFalse(fired.wait(0), "已完成的调用不应触发看门狗")


class TestRecorderWiring(unittest.TestCase):
    def test_stream_create_start_stop_all_guarded(self) -> None:
        """Recorder 的建流/start/stop 必须全部包在 watchdog guard 里。"""
        import voicetranser.recorder as rec_mod
        from voicetranser.recorder import Recorder

        calls: list[str] = []

        class FakeStream:
            def __init__(self, **kwargs: object) -> None:
                calls.append("create")

            def start(self) -> None:
                calls.append("start")

            def stop(self) -> None:
                calls.append("stop")

        with mock.patch.object(rec_mod, "sd") as fake_sd, \
                mock.patch.object(rec_mod, "watchdog") as fake_wd:
            fake_sd.InputStream = FakeStream

            rec = Recorder()
            rec.start()
            fake_wd.__enter__.assert_called()
            fake_wd.__exit__.assert_called()

            fake_wd.reset_mock()
            rec.stop()
            fake_wd.__enter__.assert_called()
            fake_wd.__exit__.assert_called()

        self.assertEqual(calls, ["create", "start", "stop"])


if __name__ == "__main__":
    unittest.main()
