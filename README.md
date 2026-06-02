# VoiceTranser

**语音输入 → AI 智能精炼 → 自动粘贴**

按住全局热键说话，松开后自动完成语音转写、智能精炼、粘贴到当前应用。专为 AI 编程助手（Claude Code、Cursor 等）设计，让语音输入从"能用"变成"好用"。

## ⚡ 一键安装

```bash
curl -fsSL https://raw.githubusercontent.com/Lumos-789/VoiceTranser/main/install.sh | bash
```

安装完成后编辑 `.env` 填入 API Key，授予辅助功能权限，即可使用。详见下方说明。

## ✨ 特性

- 🎙️ **全局热键录音** — 按住右 Cmd 说话，松开即处理
- 🧠 **本地 STT** — faster-whisper (large-v3) 离线转写，无需网络，隐私安全
- ✨ **AI 智能精炼** — 口语自动清理、去冗余、结构化，适配不同长度
- 📋 **自动粘贴** — 处理完自动粘贴到当前光标位置
- 🔔 **系统通知** — 每个阶段 macOS 通知反馈，不盯终端也知道进度
- 🍎 **macOS 原生** — 菜单点击粘贴 + 系统通知，深度系统集成

## 架构

```
Global Hotkey (hold) → Recorder (sounddevice) → Transcriber (local Whisper) → Refiner (LLM) → Output (clipboard + paste)
```

## 快速开始

### 前置要求

- macOS（目前仅支持 macOS）
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) 包管理器
- 一个 LLM API Key（支持 MiniMax、OpenAI 兼容接口等）

### 安装

```bash
git clone https://github.com/Lumos-789/VoiceTranser.git
cd VoiceTranser
uv sync
```

### 配置

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 API Key：

```env
MINIMAX_API_KEY=sk-xxx          # 必填
MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic
MINIMAX_MODEL=MiniMax-M2.7-highspeed
WHISPER_MODEL=large-v3          # tiny/base/small/medium/large-v3
HOTKEY=cmd_r                    # 全局热键
LANGUAGE=zh                     # 语音语言
```

> STT 完全本地运行，唯一的外部依赖是 LLM API Key。

### 使用

```bash
# 守护模式（全局热键，推荐日常使用）
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

这是全局热键监听（pynput）和自动粘贴所必需的。

## 智能精炼策略

VoiceTranser 根据语音长度自动选择精炼策略：

| 长度 | 策略 | 示例 |
|------|------|------|
| ≤20 字 | 原样透传 | "帮我看看这个 bug" → 不变 |
| 21~80 字 | 轻量清理 | 去填充词、去重复，保持自然语气 |
| 80+ 字 | 结构化整理 | 提取核心意图，整理为要点列表 |

精炼提示词在 `voicetranser/prompts/refine_system.txt`，可自由定制。

## 支持的热键

`cmd_r`（默认）、`cmd_l`、`alt_r`、`alt_l`、`ctrl_r`、`ctrl_l`、`shift_r`、`shift_l`、`f5`~`f8`，或任意单字符键。

## 技术栈

| 组件 | 技术 |
|------|------|
| STT | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTransate2, Apple Silicon 优化) |
| LLM 精炼 | Anthropic SDK 兼容接口 |
| 全局热键 | [pynput](https://github.com/moses-palmer/pynput) |
| 音频录制 | [sounddevice](https://python-sounddevice.readthedocs.io/) |
| 包管理 | [uv](https://docs.astral.sh/uv/) |

## License

MIT
