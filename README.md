# VoiceTranser

**语音输入 → 转写 → 自动粘贴**

按住全局热键说话，松开后自动完成语音转写并粘贴到当前应用。专为 AI 编程助手（Claude Code、Cursor 等）设计，完全本地运行，零外部依赖。

## ✨ 特性

- 🎙️ **全局热键录音** — 通过外部快捷键工具（Raycast/Hammerspoon）触发 HTTP 端点
- 🧠 **本地 STT，双引擎** — 默认 [SenseVoice](https://github.com/FunAudioLLM/SenseVoice)(非自回归，中文秒出)；[mlx-whisper](https://github.com/ml-explore/mlx-whisper) large-v3 作 fallback(英文/小语种更强)。均离线，无需网络，隐私安全
- 📋 **自动粘贴** — 转写完自动粘贴到当前光标位置
- 🔔 **系统通知** — 每个阶段 macOS 通知反馈，不盯终端也知道进度
- 🍎 **macOS 原生** — 菜单点击粘贴 + 系统通知，深度系统集成

## 架构

```
External Hotkey → HTTP /toggle → Recorder (sounddevice) → Transcriber (SenseVoice / mlx-whisper) → Output (clipboard + paste)
```

## 快速开始

### 前置要求

- macOS（目前仅支持 macOS）
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) 包管理器

### 安装

```bash
git clone https://github.com/Lumos-789/VoiceTranser.git
cd VoiceTranser
uv sync
```

### 使用

```bash
# 守护模式（HTTP 服务器，推荐日常使用）
uv run python -m voicetranser

# 单次录制（调试用）
uv run python -m voicetranser --once

# 处理音频文件
uv run python -m voicetranser --file recording.wav

# 查看当前配置
uv run python -m voicetranser --config
```

### macOS 辅助功能权限

首次使用需要授予终端辅助功能权限：

**系统设置 → 隐私与安全性 → 辅助功能** → 勾选你的终端应用

这是自动粘贴功能所必需的。

## HTTP 端点

守护模式启动后监听 `http://127.0.0.1:9876`：

| 端点 | 说明 |
|------|------|
| `GET /toggle` | 切换录音（idle → recording → processing） |
| `GET /start` | 开始录音 |
| `GET /stop` | 停止录音并处理 |
| `GET /status` | 当前状态 |

配合 Raycast、Hammerspoon 等工具设置快捷键触发 `/toggle` 即可。

## 技术栈

| 组件 | 技术 |
|------|------|
| STT | [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) + SenseVoice(默认)/ [mlx-whisper](https://github.com/ml-explore/mlx-whisper)(fallback) |
| 音频录制 | [sounddevice](https://python-sounddevice.readthedocs.io/) |
| 包管理 | [uv](https://docs.astral.sh/uv/) |

## License

MIT
