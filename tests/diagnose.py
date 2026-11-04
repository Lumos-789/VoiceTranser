#!/usr/bin/env python3
"""VoiceTranser 诊断脚本 — 逐层检查各组件健康状态，快速定位故障。

用法:
    .venv/bin/python tests/diagnose.py               # 全量检查
    .venv/bin/python tests/diagnose.py --skip-audio  # 麦克风不能碰时跳过音频检查
    .venv/bin/python tests/diagnose.py --fix         # 检查 + 自动重启修复

音频检查是有界的: 先查 TCC 授权状态(不触发授权框)，未授权绝不打开
InputStream；已授权才在子进程里开流，硬超时 3s，超时直接强杀。
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

# 允许从任意 cwd 直接运行本脚本
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── 颜色输出 ──────────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

# 三态结果: 跳过 ≠ 通过，汇总与退出码都要区分
PASS = "pass"
FAIL = "fail"
SKIP = "skip"

IS_MACOS = sys.platform == "darwin"
AUDIO_TIMEOUT = 3.0


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}✗{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}!{RESET} {msg}")


def header(msg: str) -> None:
    print(f"\n{BOLD}── {msg} ──{RESET}")


# ── 检查项 ────────────────────────────────────────────────────────────────

def check_python_deps() -> bool:
    """1. Python 依赖是否齐全。"""
    header("Python 依赖")
    all_ok = True
    deps = [
        "sounddevice",
        "numpy",
        "mlx_audio",
        "mlx_whisper",
        "sherpa_onnx",
        "pyperclip",
        "dotenv",
    ]
    for dep in deps:
        mod = dep if dep != "dotenv" else "dotenv"
        try:
            __import__(mod)
            ok(dep)
        except ImportError:
            fail(f"{dep} — 未安装")
            all_ok = False
    return all_ok


def check_process() -> tuple[bool, int | None]:
    """2. 守护进程是否在跑。"""
    header("守护进程")
    result = subprocess.run(
        ["pgrep", "-f", "python.*-m voicetranser"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        pid = int(result.stdout.strip().split("\n")[0])
        ok(f"进程运行中 (PID {pid})")
        return True, pid
    fail("进程未运行")
    return False, None


def resolve_server_port(cli_port: int | None = None) -> int:
    """解析守护进程实际监听的端口: --port > 应用配置(SERVER_PORT/.env/默认)。

    应用默认是 config.DEFAULT_SERVER_PORT(9876)；旧端口上的实例可能还活着，
    按写死端口诊断会拿到错误进程的绿色结果。
    """
    if cli_port is not None:
        return cli_port
    from voicetranser.config import DEFAULT_SERVER_PORT, load_config

    try:
        return load_config().server_port
    except ImportError as exc:
        warn(f"读取应用配置失败（{exc}），退回 SERVER_PORT/默认 {DEFAULT_SERVER_PORT}")
        raw = os.getenv("SERVER_PORT")
        return int(raw) if raw else DEFAULT_SERVER_PORT


def check_http_server(port: int | None = None) -> bool:
    """3. HTTP 服务器是否响应(端口按应用配置解析，不用写死值)。"""
    header("HTTP 服务器")
    port = resolve_server_port(port)
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "3", f"http://127.0.0.1:{port}/status"],
            capture_output=True, text=True, timeout=5,
        )
        body = result.stdout.strip()
        if '"status"' in body:
            ok(f"端口 {port} 正常响应: {body}")
            return True
        if result.returncode == 28:
            fail(f"端口 {port} 连接超时")
        elif result.returncode == 52:
            fail(f"端口 {port} 空响应（handler 内部崩溃）")
        elif result.returncode == 7:
            fail(f"端口 {port} 连接被拒（进程未监听）")
            warn("端口按应用配置解析; launchd 实例在 plist 里设了别的 SERVER_PORT 时用 --port 指定")
        else:
            fail(f"响应异常 (exit {result.returncode}): {body or result.stderr.strip()}")
        return False
    except subprocess.TimeoutExpired:
        fail(f"端口 {port} curl 超时")
        return False


# ── 音频检查: 权限预检 + 子进程硬超时 ───────────────────────────────────────

# 必须在独立子进程里跑: 无权限时 PortAudio 会卡死在 CoreAudio(mach_msg)等
# 系统授权框，主进程无法打断，只能靠父进程 kill。
_AUDIO_PROBE_CODE = """\
import sounddevice as sd
info = sd.query_devices(kind="input")
print(f"{info['name']} ({info['default_samplerate']}Hz)")
with sd.InputStream(samplerate=16000, channels=1, dtype="float32") as stream:
    stream.start()
    stream.stop()
"""

_PERMISSION_LABELS = {
    0: "notDetermined（尚未决定）",
    1: "restricted（系统策略限制）",
    2: "denied（已拒绝）",
    3: "authorized（已授权）",
}


class AudioProbeTimeout(RuntimeError):
    """打开音频流超过硬超时；子进程已被强杀。"""


def microphone_authorization_status() -> int | None:
    """查 TCC 麦克风授权状态，只读不请求，绝不弹授权框。

    macOS 上调用 AVFoundation 的 `authorizationStatusForMediaType:`
    (不是 `requestAccess...`，后者才会弹框)。返回 0/1/2/3，
    查询失败或非 macOS 返回 None。
    """
    if not IS_MACOS:
        return None
    try:
        import ctypes

        objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]

        avfoundation = ctypes.CDLL(
            "/System/Library/Frameworks/AVFoundation.framework/AVFoundation"
        )
        msg_send = objc.objc_msgSend
        msg_send.restype = ctypes.c_long
        msg_send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

        device_class = objc.objc_getClass(b"AVCaptureDevice")
        media_type = ctypes.c_void_p.in_dll(avfoundation, "AVMediaTypeAudio").value
        selector = objc.sel_registerName(b"authorizationStatusForMediaType:")
        status = int(msg_send(device_class, selector, media_type))
    except Exception:
        return None
    return status if status in _PERMISSION_LABELS else None


class SystemAudioDevice:
    """真实设备探针: 权限只查不请求；流探测有硬超时，超时强杀子进程。"""

    def __init__(
        self, python: str | None = None, probe_code: str = _AUDIO_PROBE_CODE
    ) -> None:
        self._python = python or sys.executable
        self._probe_code = probe_code

    def permission_status(self) -> int | None:
        return microphone_authorization_status()

    def probe_stream(self, timeout: float) -> tuple[bool, str]:
        proc = subprocess.Popen(
            [self._python, "-c", self._probe_code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                proc.kill()
            try:
                proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                pass
            raise AudioProbeTimeout(f"{timeout:.1f}s") from None
        if proc.returncode == 0:
            return True, stdout.strip()
        detail = (stderr or stdout).strip().splitlines()
        return False, detail[-1] if detail else f"exit {proc.returncode}"


def check_audio_device(
    *,
    skip_audio: bool = False,
    timeout: float = AUDIO_TIMEOUT,
    device=None,
) -> str:
    """4. 音频设备是否可用 — 有界、不弹权限框。

    先查授权状态(不弹框)，未授权绝不打开 InputStream；已授权才在子进程
    开流并限制在 timeout 内。无权限时 PortAudio 会无限期卡在 CoreAudio，
    诊断必须把它变成一条 finding，而不是挂死桌面。
    """
    header("音频设备 (PortAudio)")
    if skip_audio:
        warn("已跳过音频检查 (--skip-audio)：麦克风未验证，不能据此判定音频正常")
        return SKIP

    dev = device or SystemAudioDevice()

    try:
        permission = dev.permission_status()
    except Exception as exc:
        fail(f"音频设备不可用 (audio device unavailable) — 查询麦克风授权失败: {exc}")
        warn("未打开音频流：权限状态不明时开流会阻塞在系统授权框上")
        return FAIL

    if permission is not None and permission != 3:
        fail(
            "音频设备不可用 (audio device unavailable) — "
            f"麦克风权限未授予 (microphone permission not granted: "
            f"{_PERMISSION_LABELS.get(permission, permission)})"
        )
        warn("未打开音频流：无权限时 PortAudio 会卡死在 CoreAudio 等授权框，诊断拒绝阻塞桌面")
        warn("修复: 系统设置 → 隐私与安全性 → 麦克风，勾选运行诊断的终端/应用；launchd 实例需给 python 单独授权")
        warn("麦克风不能碰时先跑其余检查: .venv/bin/python tests/diagnose.py --skip-audio")
        return FAIL

    if permission is None and IS_MACOS:
        warn("无法确认麦克风授权状态，跳过音频流探测 (audio check skipped)")
        warn("未打开音频流，避免触发系统授权框；授权后重跑，或加 --skip-audio")
        return SKIP

    try:
        stream_ok, detail = dev.probe_stream(timeout)
    except AudioProbeTimeout:
        fail(
            "音频设备不可用 (audio device unavailable) — "
            f"打开 InputStream 超过 {timeout:.1f}s 未返回，已强制终止子进程"
        )
        warn("常见原因: macOS 休眠后音频子系统状态损坏、蓝牙耳机切换、虚拟音频驱动冲突")
        warn("修复: 重启进程 — launchctl kickstart -k gui/$(id -u)/com.voicetranser-sense")
        return FAIL
    except Exception as exc:
        fail(f"音频设备异常: {exc}")
        warn("常见原因: macOS 休眠后音频子系统状态损坏、蓝牙耳机切换、虚拟音频驱动冲突")
        warn("修复: 重启进程 — launchctl kickstart -k gui/$(id -u)/com.voicetranser-sense")
        return FAIL

    if stream_ok:
        ok(f"InputStream 打开/关闭正常 (设备: {detail or 'unknown'}，硬超时 {timeout:.1f}s)")
        return PASS
    fail(f"音频设备不可用 (audio device unavailable): {detail}")
    warn("常见原因: macOS 休眠后音频子系统状态损坏、蓝牙耳机切换、虚拟音频驱动冲突")
    warn("修复: 重启进程 — launchctl kickstart -k gui/$(id -u)/com.voicetranser-sense")
    return FAIL


def check_stt_model() -> bool:
    """5. 当前引擎的模型是否已缓存。"""
    header("STT 模型")
    try:
        from voicetranser.config import load_config

        cfg = load_config()
        hf_home = Path(
            os.environ.get("HF_HOME", str(Path.home() / ".cache/huggingface"))
        )
        hub_cache = hf_home / "hub"
        if cfg.stt_engine == "qwen3-mlx":
            repo = "mlx-community/Qwen3-ASR-0.6B-4bit"
            cached = (hub_cache / "models--mlx-community--Qwen3-ASR-0.6B-4bit").is_dir()
            label = f"{repo} (MLX)"
        elif cfg.stt_engine == "sensevoice":
            model_dir = Path(__file__).resolve().parent.parent / "models/sense-voice"
            cached = (model_dir / "model.int8.onnx").is_file() and (
                model_dir / "tokens.txt"
            ).is_file()
            label = str(model_dir)
        elif cfg.stt_engine == "mlx-whisper":
            repo = f"mlx-community/whisper-{cfg.whisper_model}-mlx"
            cached = (hub_cache / repo.replace("/", "--")).is_dir()
            label = repo
        else:
            fail(f"未知 STT 引擎: {cfg.stt_engine!r}")
            return False

        if cached:
            ok(f"当前引擎 {cfg.stt_engine} 模型已就绪: {label}")
        else:
            warn(f"当前引擎 {cfg.stt_engine} 模型未缓存: {label}（首次转写时会下载）")
        return True
    except Exception as e:
        fail(f"模型检查失败: {e}")
        return False


def check_clipboard() -> bool:
    """6. 剪贴板是否可读写。"""
    header("剪贴板")
    try:
        import pyperclip

        original = pyperclip.paste()
        pyperclip.copy("__voicetranser_diag__")
        result = pyperclip.paste()
        pyperclip.copy(original)
        if result == "__voicetranser_diag__":
            ok("剪贴板读写正常")
            return True
        fail("剪贴板写入后读回不一致")
        return False
    except Exception as e:
        fail(f"剪贴板异常: {e}")
        return False


def check_cli_tools() -> bool:
    """7. 外部 CLI 工具。"""
    header("外部工具")
    all_ok = True
    for tool in ["ffmpeg", "osascript"]:
        path = shutil.which(tool)
        if path:
            ok(f"{tool}: {path}")
        else:
            fail(f"{tool}: 未找到")
            all_ok = False
    return all_ok


def check_recent_errors(log_path: str | None = None) -> bool:
    """8. 最近日志中是否有错误。"""
    header("最近日志错误")
    if log_path is None:
        log_path = str(Path.home() / "Library/Logs/VoiceTranser-sense.log")
        legacy_log = Path.home() / "Library/Logs/VoiceTranser.log"
        if not os.path.isfile(log_path) and legacy_log.is_file():
            log_path = str(legacy_log)

    if not os.path.isfile(log_path):
        warn(f"日志文件不存在: {log_path}")
        return True

    try:
        # 只看最近一次启动之后的日志，忽略旧进程残留
        result = subprocess.run(
            ["grep", "-n", r"\[VoiceTranser\] HTTP server listening", log_path],
            capture_output=True, text=True, timeout=5,
        )
        tail_from = 1
        if result.stdout.strip():
            last_start = result.stdout.strip().split("\n")[-1]
            tail_from = int(last_start.split(":")[0])

        result = subprocess.run(
            ["tail", f"-n+{tail_from}", log_path],
            capture_output=True, text=True, timeout=5,
        )
        lines = result.stdout.split("\n")

        # 提取错误信息
        errors: list[str] = []
        current_error: list[str] = []
        in_error = False
        for line in lines:
            if "Exception occurred" in line or "Error" in line:
                in_error = True
                current_error = [line]
            elif in_error:
                current_error.append(line)
                if line.strip().startswith("---"):
                    errors.append("\n".join(current_error))
                    current_error = []
                    in_error = False

        if not errors:
            ok("最近 200 行无异常")
            return True

        # 只显示最近 3 条
        seen: set[str] = set()
        count = 0
        for err in reversed(errors):
            # 去重（相同错误反复出现）
            key = err.split("\n")[0]
            if key in seen:
                continue
            seen.add(key)
            # 提取关键信息
            for line in err.split("\n"):
                if "Error" in line or "PortAudio" in line or "sounddevice" in line:
                    warn(f"发现错误: {line.strip()}")
                    count += 1
                    break
            if count >= 3:
                break

        if count > 0:
            warn(f"共发现 {len(errors)} 处错误，建议重启进程")
            return False
        return True

    except Exception as e:
        warn(f"读取日志失败: {e}")
        return True


# ── 自动修复 ──────────────────────────────────────────────────────────────

def auto_fix(port: int | None = None) -> None:
    """尝试自动修复：重启守护进程。"""
    header("自动修复")
    try:
        uid = os.getuid()
        subprocess.run(
            [
                "launchctl",
                "kickstart",
                "-k",
                f"gui/{uid}/com.voicetranser-sense",
            ],
            check=True, capture_output=True, text=True,
        )
        import time
        time.sleep(3)

        # 验证
        if check_http_server(port):
            ok("重启成功，服务已恢复")
            return
        fail("重启后服务仍未响应")
    except Exception as e:
        fail(f"自动修复失败: {e}")


# ── 主流程 ────────────────────────────────────────────────────────────────

def summarize_results(results: dict[str, str]) -> tuple[int, list[str], list[str]]:
    """把三态结果拆成 (通过数, 失败项, 跳过项)；跳过不等于通过。"""
    passed = sum(1 for value in results.values() if value == PASS)
    failed = [name for name, value in results.items() if value == FAIL]
    skipped = [name for name, value in results.items() if value == SKIP]
    return passed, failed, skipped


def exit_code(results: dict[str, str]) -> int:
    """有失败或跳过都不算成功（不能拿跳过项冒充全绿）。"""
    _, failed, skipped = summarize_results(results)
    return 0 if not failed and not skipped else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="diagnose.py",
        description="VoiceTranser 诊断（音频检查有界，不触发系统授权框）",
    )
    parser.add_argument("--fix", action="store_true", help="检查后自动重启服务修复")
    parser.add_argument(
        "--skip-audio",
        action="store_true",
        help="跳过音频设备检查（麦克风不可用时用；汇总标为跳过，退出码非 0）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="HTTP 端口；默认按应用配置 SERVER_PORT -> .env -> 9876",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    print(f"{BOLD}VoiceTranser 诊断{RESET}")

    results: dict[str, str] = {
        "Python 依赖": PASS if check_python_deps() else FAIL,
        "守护进程": PASS if check_process()[0] else FAIL,
        "HTTP 服务器": PASS if check_http_server(args.port) else FAIL,
        "音频设备": check_audio_device(skip_audio=args.skip_audio),
        "STT 模型": PASS if check_stt_model() else FAIL,
        "剪贴板": PASS if check_clipboard() else FAIL,
        "外部工具": PASS if check_cli_tools() else FAIL,
        "日志检查": PASS if check_recent_errors() else FAIL,
    }

    # 汇总
    header("汇总")
    passed, failed, skipped = summarize_results(results)
    print(
        f"  通过: {passed}/{len(results)}   失败: {len(failed)}   跳过: {len(skipped)}"
    )
    if failed:
        print(f"  失败: {', '.join(failed)}")
    if skipped:
        print(f"  跳过(未验证): {', '.join(skipped)}")
        print(f"  {YELLOW}未完整通过{RESET}: 有检查未执行，不能据此判定全部正常")
    if failed:
        if args.fix:
            auto_fix(args.port)
        else:
            print(f"\n  提示: 加 {YELLOW}--fix{RESET} 参数可自动重启修复")

    sys.exit(exit_code(results))


if __name__ == "__main__":
    main()
