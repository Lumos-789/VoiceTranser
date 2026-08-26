#!/usr/bin/env python3
"""server 模块回归测试 — 音频操作不得持有状态锁（2026-08-27 00:55 事故）。

事故: /stop 在持有 _ctx.lock 时调 stream.stop()，CoreAudio 在
HALB_Mutex::Lock 内死锁，锁永不释放，/status 等所有端点全部挂死。
本测试用"慢 recorder"锁定该场景：慢 stop 期间 /status 必须立刻响应。

运行:
    uv run python tests/test_server.py
"""

from __future__ import annotations

import http.client
import json
import sys
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

# 让测试可以从项目根直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from voicetranser.server import _IDLE, _PROCESSING, _Handler, _ctx


class FakeRecorder:
    def __init__(
        self, stop_delay: float = 0.0, start_error: Exception | None = None
    ) -> None:
        self.stop_delay = stop_delay
        self.start_error = start_error
        self.stop_entered = threading.Event()

    def start(self) -> None:
        if self.start_error:
            raise self.start_error

    def stop(self) -> bytes | None:
        self.stop_entered.set()
        time.sleep(self.stop_delay)
        return None  # too-short path


class FakeStatus:
    def recording(self) -> None: ...
    def transcribing(self) -> None: ...
    def done(self) -> None: ...
    def clear(self) -> None: ...


class _ServerTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = (_ctx.recorder, _ctx.status, _ctx.config, _ctx.state)
        _ctx.recorder = FakeRecorder()
        _ctx.status = FakeStatus()
        _ctx.config = None
        _ctx.state = _IDLE
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        _ctx.recorder, _ctx.status, _ctx.config, _ctx.state = self._saved

    def _get(self, path: str, timeout: float = 3.0):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            conn.request("GET", path)
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read())
        finally:
            conn.close()


class TestAudioOpsOutsideLock(_ServerTest):
    def test_status_stays_responsive_while_stop_hangs(self) -> None:
        """核心回归: recorder.stop() 挂住时 /status 必须立刻返回。

        旧代码 stop() 在 _ctx.lock 内执行，锁被吊死的调用占住后
        /status 也跟着挂死（本次事故的直接症状）。
        """
        slow = FakeRecorder(stop_delay=1.0)
        _ctx.recorder = slow

        code, body = self._get("/start")
        self.assertEqual((code, body["status"]), (200, "recording"))

        result: dict = {}

        def stopper() -> None:
            result["stop"] = self._get("/stop", timeout=5)

        t = threading.Thread(target=stopper, daemon=True)
        t.start()
        self.assertTrue(slow.stop_entered.wait(2), "/stop 未进入 recorder.stop()")

        t0 = time.monotonic()
        code, body = self._get("/status", timeout=2)
        elapsed = time.monotonic() - t0
        self.assertEqual((code, body["status"]), (200, _PROCESSING))
        self.assertLess(elapsed, 0.5, "/status 队列排在了慢 stop 后面 — 状态锁被音频操作持有")

        t.join(5)
        self.assertEqual(result["stop"][0], 200)
        self.assertEqual(result["stop"][1]["status"], _IDLE)  # too-short → idle
        code, body = self._get("/status")
        self.assertEqual(body["status"], _IDLE)

    def test_status_stays_responsive_while_start_hangs(self) -> None:
        """start 方向同样不得持锁。"""
        entered = threading.Event()

        class SlowStartRecorder(FakeRecorder):
            def start(self) -> None:
                entered.set()
                time.sleep(1.0)

        _ctx.recorder = SlowStartRecorder()
        t = threading.Thread(
            target=lambda: self._get("/start", timeout=5), daemon=True
        )
        t.start()
        self.assertTrue(entered.wait(2), "/start 未进入 recorder.start()")

        t0 = time.monotonic()
        code, body = self._get("/status", timeout=2)
        elapsed = time.monotonic() - t0
        self.assertEqual((code, body["status"]), (200, "recording"))
        self.assertLess(elapsed, 0.5, "慢 start 期间 /status 不应被阻塞")
        t.join(5)


class TestStateRollback(_ServerTest):
    def test_start_failure_returns_500_and_idle(self) -> None:
        _ctx.recorder = FakeRecorder(start_error=RuntimeError("device gone"))
        code, body = self._get("/start")
        self.assertEqual(code, 500)
        self.assertEqual(body["status"], _IDLE)
        # 回滚后可立即重试
        _ctx.recorder = FakeRecorder()
        code, body = self._get("/start")
        self.assertEqual((code, body["status"]), (200, "recording"))

    def test_stop_failure_returns_500_and_idle(self) -> None:
        code, _ = self._get("/start")
        self.assertEqual(code, 200)

        class ExplodingRecorder(FakeRecorder):
            def stop(self) -> bytes | None:
                self.stop_entered.set()
                raise RuntimeError("hal wedged")

        _ctx.recorder = ExplodingRecorder()
        code, body = self._get("/stop")
        self.assertEqual(code, 500)
        self.assertEqual(body["status"], _IDLE)

    def test_stop_rejected_when_not_recording(self) -> None:
        code, body = self._get("/stop")
        self.assertEqual(code, 409)
        self.assertEqual(body["message"], "not recording")

    def test_toggle_dispatches_start_then_stop(self) -> None:
        code, body = self._get("/toggle")
        self.assertEqual((code, body["status"]), (200, "recording"))
        code, body = self._get("/toggle")
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], _IDLE)  # too-short → idle


if __name__ == "__main__":
    unittest.main()
