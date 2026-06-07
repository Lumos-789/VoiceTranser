#!/usr/bin/env python3
"""VoiceTranser 诊断脚本 — 逐层检查各组件健康状态，快速定位故障。

用法:
    python tests/diagnose.py          # 全量检查
    python tests/diagnose.py --fix    # 检查 + 自动重启修复
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

# ── 颜色输出 ──────────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


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
    deps = ["sounddevice", "numpy", "mlx_whisper", "pyperclip", "dotenv"]
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


def check_http_server(port: int = 9876) -> bool:
    """3. HTTP 服务器是否响应。"""
    header("HTTP 服务器")
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
        else:
            fail(f"响应异常 (exit {result.returncode}): {body or result.stderr.strip()}")
        return False
    except subprocess.TimeoutExpired:
        fail(f"端口 {port} curl 超时")
        return False


def check_audio_device() -> bool:
    """4. 音频设备是否可用（核心：PortAudio 能否打开 InputStream）。"""
    header("音频设备 (PortAudio)")
    try:
        import sounddevice as sd

        # 列出输入设备
        devices = sd.query_devices()
        default_in = sd.query_devices(kind="input")
        ok(f"默认输入设备: {default_in['name']} (采样率: {default_in['default_samplerate']}Hz)")

        # 尝试打开流 — 这就是 -9986 错误发生的地方
        with sd.InputStream(samplerate=16000, channels=1, dtype="float32") as stream:
            stream.start()
            stream.stop()
        ok("InputStream 打开/关闭正常")
        return True
    except Exception as e:
        fail(f"音频设备异常: {e}")
        warn("常见原因: macOS 休眠后音频子系统状态损坏、蓝牙耳机切换、虚拟音频驱动冲突")
        warn("修复: 重启进程 — launchctl kickstart -k gui/$(id -u)/com.voicetranser")
        return False


def check_whisper_model() -> bool:
    """5. Whisper 模型是否可加载。"""
    header("Whisper 模型")
    try:
        # 只检查模型仓库是否可解析，不做实际转写
        from voicetranser.config import load_config

        cfg = load_config()
        repo = f"mlx-community/whisper-{cfg.whisper_model}-mlx"

        # 检查本地缓存
        hf_home = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
        hub_cache = os.path.join(hf_home, "hub")
        model_cached = False
        if os.path.isdir(hub_cache):
            for d in os.listdir(hub_cache):
                if repo.replace("/", "--") in d:
                    model_cached = True
                    break

        if model_cached:
            ok(f"模型已缓存: {repo}")
        else:
            warn(f"模型未在本地缓存: {repo}（首次转写时会下载）")
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
        log_path = os.path.expanduser("~/Library/Logs/VoiceTranser.log")

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

def auto_fix() -> None:
    """尝试自动修复：重启守护进程。"""
    header("自动修复")
    try:
        uid = os.getuid()
        subprocess.run(
            ["launchctl", "kickstart", "-k", f"gui/{uid}/com.voicetranser"],
            check=True, capture_output=True, text=True,
        )
        import time
        time.sleep(3)

        # 验证
        result = subprocess.run(
            ["curl", "-s", "--max-time", "3", "http://127.0.0.1:9876/status"],
            capture_output=True, text=True, timeout=5,
        )
        if '"status"' in result.stdout:
            ok("重启成功，服务已恢复")
            return
        fail("重启后服务仍未响应")
    except Exception as e:
        fail(f"自动修复失败: {e}")


# ── 主流程 ────────────────────────────────────────────────────────────────

def main() -> None:
    do_fix = "--fix" in sys.argv

    print(f"{BOLD}VoiceTranser 诊断{RESET}")

    results: dict[str, bool] = {}
    results["Python 依赖"], _ = check_python_deps(), None
    results["守护进程"] = check_process()[0]
    results["HTTP 服务器"] = check_http_server()
    results["音频设备"] = check_audio_device()
    results["Whisper 模型"] = check_whisper_model()
    results["剪贴板"] = check_clipboard()
    results["外部工具"] = check_cli_tools()
    results["日志检查"] = check_recent_errors()

    # 汇总
    header("汇总")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"  通过: {passed}/{total}")

    failed = [k for k, v in results.items() if not v]
    if failed:
        print(f"  失败: {', '.join(failed)}")
        if do_fix:
            auto_fix()
        else:
            print(f"\n  提示: 加 {YELLOW}--fix{RESET} 参数可自动重启修复")

    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
