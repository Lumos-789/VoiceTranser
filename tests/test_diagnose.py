#!/usr/bin/env python3
"""diagnose.py 回归测试 —— 端口解析与音频检查的边界（不得挂死、不得乱猜端口）。

音频设备路径用 fake device + 真实子进程超时覆盖：
- 权限未授予 / 探针超时 → FAIL 且绝不打开音频流（fake 记录调用次数）；
- 跳过开关 → SKIP，且不碰设备；
- 真超时用 `python -c "time.sleep(30)"` 子进程验证 0.4s 内被强杀。

运行:
    .venv/bin/python -m unittest discover -s tests -v
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from voicetranser.config import Config  # noqa: E402


def _load_diagnose():
    spec = importlib.util.spec_from_file_location(
        "voicetranser_diagnose", ROOT / "tests" / "diagnose.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


diagnose = _load_diagnose()


class FakeDevice:
    """Stand-in for the real audio device; records what the check touches."""

    def __init__(self, permission: int | None = 3, probe=None) -> None:
        self.permission = permission
        self.probe_calls = 0
        self._probe = probe if probe is not None else (lambda timeout: (True, "FakeMic (16000Hz)"))

    def permission_status(self) -> int | None:
        return self.permission

    def probe_stream(self, timeout: float):
        self.probe_calls += 1
        return self._probe(timeout)


class _StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = json.dumps({"status": "idle"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


def _serve_status() -> tuple[ThreadingHTTPServer, int]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StatusHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def _capture(fn, *args, **kwargs):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        result = fn(*args, **kwargs)
    return result, out.getvalue()


class TestServerPortResolution(unittest.TestCase):
    """FIX 2: diagnose 必须按应用配置解析端口，不能用写死的 9877。"""

    def test_default_port_is_the_application_config_default(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "SERVER_PORT"}
        with mock.patch.dict(os.environ, env, clear=True):
            port = diagnose.resolve_server_port()
        self.assertEqual(port, Config().server_port)
        self.assertEqual(port, 9876)

    def test_server_port_env_override_wins(self) -> None:
        with mock.patch.dict(os.environ, {"SERVER_PORT": "9123"}):
            self.assertEqual(diagnose.resolve_server_port(), 9123)

    def test_explicit_port_wins_over_everything(self) -> None:
        with mock.patch.dict(os.environ, {"SERVER_PORT": "9123"}):
            self.assertEqual(diagnose.resolve_server_port(9450), 9450)

    def test_http_check_probes_the_resolved_port(self) -> None:
        server, port = _serve_status()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with mock.patch.dict(os.environ, {"SERVER_PORT": str(port)}):
            passed, output = _capture(diagnose.check_http_server)
        self.assertTrue(passed)
        self.assertIn(str(port), output)
        self.assertIn("idle", output)


class TestAudioCheck(unittest.TestCase):
    """FIX 1: 音频检查必须有界、跳过要显式、失败要有 finding。"""

    def test_permission_not_granted_is_a_finding_and_never_opens_a_stream(self) -> None:
        for status in (0, 2):  # notDetermined / denied
            with self.subTest(status=status):
                device = FakeDevice(permission=status)
                result, output = _capture(diagnose.check_audio_device, device=device)
                self.assertEqual(result, diagnose.FAIL)
                self.assertEqual(device.probe_calls, 0)
                self.assertIn("audio device unavailable", output)
                self.assertIn("microphone permission not granted", output)
                self.assertIn("系统设置", output)

    def test_skip_audio_reports_skipped_and_does_not_touch_the_device(self) -> None:
        device = FakeDevice(permission=3)
        result, output = _capture(
            diagnose.check_audio_device, skip_audio=True, device=device
        )
        self.assertEqual(result, diagnose.SKIP)
        self.assertEqual(device.probe_calls, 0)
        self.assertIn("跳过", output)
        self.assertIn("--skip-audio", output)

    def test_probe_timeout_is_a_finding(self) -> None:
        def hang(timeout: float):
            raise diagnose.AudioProbeTimeout("3.0s")

        device = FakeDevice(permission=3, probe=hang)
        result, output = _capture(diagnose.check_audio_device, device=device)
        self.assertEqual(result, diagnose.FAIL)
        self.assertIn("audio device unavailable", output)
        self.assertIn("强制终止", output)

    def test_unreadable_permission_on_macos_is_not_guessed(self) -> None:
        device = FakeDevice(permission=None)
        with mock.patch.object(diagnose, "IS_MACOS", True):
            result, output = _capture(diagnose.check_audio_device, device=device)
        self.assertEqual(result, diagnose.SKIP)
        self.assertEqual(device.probe_calls, 0)
        self.assertIn("跳过", output)

    def test_granted_permission_runs_the_bounded_probe(self) -> None:
        device = FakeDevice(permission=3)
        result, output = _capture(
            diagnose.check_audio_device, device=device, timeout=2.0
        )
        self.assertEqual(result, diagnose.PASS)
        self.assertEqual(device.probe_calls, 1)
        self.assertIn("FakeMic", output)

    def test_real_probe_child_is_killed_on_timeout(self) -> None:
        device = diagnose.SystemAudioDevice(
            probe_code="import time\ntime.sleep(30)\n"
        )
        started = time.monotonic()
        with self.assertRaises(diagnose.AudioProbeTimeout):
            device.probe_stream(0.4)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 5.0, "probe hang was not bounded")

    @unittest.skipUnless(sys.platform == "darwin", "macOS TCC query")
    def test_permission_query_is_available_and_non_prompting(self) -> None:
        started = time.monotonic()
        status = diagnose.microphone_authorization_status()
        elapsed = time.monotonic() - started
        self.assertIsInstance(status, int)
        self.assertIn(status, (0, 1, 2, 3))
        self.assertLess(elapsed, 1.0)


class TestSummary(unittest.TestCase):
    """汇总不得把 skipped 当成 passed。"""

    def test_skipped_check_cannot_be_reported_as_success(self) -> None:
        results = {
            "Python 依赖": diagnose.PASS,
            "音频设备": diagnose.SKIP,
        }
        passed, failed, skipped = diagnose.summarize_results(results)
        self.assertEqual(passed, 1)
        self.assertEqual(failed, [])
        self.assertEqual(skipped, ["音频设备"])
        self.assertEqual(diagnose.exit_code(results), 1)

    def test_all_pass_exits_zero(self) -> None:
        results = {"Python 依赖": diagnose.PASS}
        self.assertEqual(diagnose.exit_code(results), 0)

    def test_main_with_skip_audio_exits_nonzero_and_says_skipped(self) -> None:
        patches = {
            "check_python_deps": mock.Mock(return_value=True),
            "check_process": mock.Mock(return_value=(True, 1234)),
            "check_http_server": mock.Mock(return_value=True),
            "check_stt_model": mock.Mock(return_value=True),
            "check_clipboard": mock.Mock(return_value=True),
            "check_cli_tools": mock.Mock(return_value=True),
            "check_recent_errors": mock.Mock(return_value=True),
        }
        output = io.StringIO()
        with mock.patch.multiple(diagnose, **patches), contextlib.redirect_stdout(
            output
        ), self.assertRaises(SystemExit) as caught:
            diagnose.main(["--skip-audio"])
        self.assertEqual(caught.exception.code, 1)
        text = output.getvalue()
        self.assertIn("跳过", text)
        self.assertIn("音频设备", text)
        self.assertNotIn("通过: 8/8", text)


if __name__ == "__main__":
    unittest.main()
