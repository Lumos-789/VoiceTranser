# VoiceTranser

**语音输入 → 转写 → 自动粘贴**

按住全局热键说话，松开后自动完成语音转写并粘贴到当前应用。专为 AI 编程助手（Claude Code、Cursor 等）设计，完全本地运行，零外部 API 依赖。

## ✨ 特性

- 🎙️ **全局热键录音** — 通过外部快捷键工具（Karabiner-Elements/Raycast/Hammerspoon）触发 HTTP 端点，按住说话、松开出稿
- 🧠 **本地 STT，三引擎** — 默认 [Qwen3-ASR](https://huggingface.co/mlx-community/Qwen3-ASR-0.6B-4bit) 0.6B 4bit（MLX/Metal GPU 推理，RTF 0.012-0.021，中文近完美自带标点、中英夹杂强）；[SenseVoice](https://github.com/FunAudioLLM/SenseVoice) Small int8（CPU fallback，RTF 0.03）；[mlx-whisper](https://github.com/ml-explore/mlx-whisper) large-v3（英文/小语种 fallback）。均离线推理，隐私安全
- 📋 **自动粘贴** — 转写完自动粘贴到当前光标位置
- 🔧 **误识纠正** — `corrections.json` 整词词表，发现新误识加一行重启即生效
- 🔔 **系统通知** — 每个阶段 macOS 通知反馈，不盯终端也知道进度
- 🛡️ **自愈守护** — launchd KeepAlive + CoreAudio 死锁看门狗 + 8 项自检脚本
- 🍎 **macOS 原生** — 菜单点击粘贴 + 系统通知，深度系统集成

## 架构

```
External Hotkey → HTTP /start|/stop → Recorder (sounddevice 16k mono)
  → Transcriber (Qwen3-ASR MLX 默认 / SenseVoice / mlx-whisper)
  → Corrector (corrections.json 整词纠正)
  → Output (clipboard + paste)
```

## 快速开始

### 前置要求

- macOS Apple Silicon（MLX 引擎需要；Intel 机型走 SenseVoice CPU 引擎）
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) 包管理器

### 安装

```bash
git clone https://github.com/Lumos-789/VoiceTranser.git
cd VoiceTranser
uv sync   # PyPI 慢时: UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple uv sync
uv run python download_model.py   # 下 SenseVoice fallback 模型(228MB, hf-mirror 源)
```

Qwen3-ASR 主力模型（~500MB）首次运行自动从 hf-mirror 拉取，无需手动下载。

### 使用

```bash
# 守护模式（HTTP 服务器，默认引擎 qwen3-mlx）
uv run python -m voicetranser

# 临时切换引擎
STT_ENGINE=sensevoice uv run python -m voicetranser   # CPU fallback
STT_ENGINE=mlx-whisper uv run python -m voicetranser  # 英文/小语种

# 处理音频文件（不粘贴，对比引擎用）
uv run python -m voicetranser --file recording.wav --no-paste

# 8 项链路自检
uv run python tests/diagnose.py
```

### 全局热键（推荐 Karabiner-Elements）

Karabiner complex_modifications 配置：`right_option` 按下 → `curl localhost:9877/start`，松开 → `curl localhost:9877/stop`。按住说话、松开自动转写粘贴。也可用 Raycast/Hammerspoon 触发 `/toggle`。

### 常驻后台（launchd）

```bash
uv run python install_launchd.py
curl -s localhost:9877/status
```

安装脚本会按**当前 checkout 的绝对路径**生成 `~/Library/LaunchAgents/com.voicetranser-sense.plist`，再加载并启动服务；开机自启 + 崩溃自愈，服务启动时后台预热模型。需要换端口或引擎时用 `--port` / `--engine`，只生成不加载用 `--no-load`。

### macOS 辅助功能权限

首次使用需要授予终端辅助功能权限：**系统设置 → 隐私与安全性 → 辅助功能** → 勾选你的终端应用（自动粘贴所必需）。

## HTTP 端点

守护模式启动后监听 `http://127.0.0.1:9876`（默认；launchd 实例为 9877）：

| 端点 | 说明 |
|------|------|
| `GET /toggle` | 切换录音（idle → recording → processing） |
| `GET /start` | 开始录音 |
| `GET /stop` | 停止录音并处理 |
| `GET /status` | 当前状态 |

## 性能实测（2026-11，Apple Silicon，16.5s 中文）

| 引擎 | 转写耗时 | RTF | 标点 |
|------|---------|-----|------|
| Qwen3-ASR 0.6B 4bit MLX（默认） | 0.25s | 0.015 | 自带，规范 |
| SenseVoice Small int8 CPU | 0.53s | 0.033 | 自带 |
| mlx-whisper large-v3 | ~1.1s | ~0.07 | 长句易丢 |

## 技术栈

| 组件 | 技术 |
|------|------|
| STT 主力 | [mlx-audio](https://github.com/Blaizzy/mlx-audio) + Qwen3-ASR 0.6B 4bit（MLX/Metal） |
| STT fallback | [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) + SenseVoice / [mlx-whisper](https://github.com/ml-explore/mlx-whisper) |
| 音频录制 | [sounddevice](https://python-sounddevice.readthedocs.io/) |
| 包管理 | [uv](https://docs.astral.sh/uv/) |

## 作为 DSH 插件使用

本仓同时是 [DSH](https://github.com/deepseek-ai) 插件（`dsh.bundle` 已声明）：安装后 agent 获得 voicetranser 技能，可代你完成安装、launchd 配置、Karabiner 热键配置与排障。

## License

MIT
