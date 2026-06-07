# VoiceTranser

**语音输入 → AI 智能精炼 → 自动粘贴**

按住全局热键说话，松开后自动完成语音转写、AI 精炼、粘贴到当前应用。专为 AI 编程助手（Claude Code、Cursor 等）设计，让语音输入从"能用"变成"好用"。

## ✨ 特性

- 🎙️ **全局热键录音** — 按住右 Cmd 说话，松开即处理
- 🧠 **本地 STT** — faster-whisper (large-v3) 离线转写，无需网络，隐私安全
- ✨ **AI 智能精炼** — 口语自动清理、去冗余、结构化，适配不同长度（PS：作者用的模型有点菜，还会拖慢速度，所以日常没开，可按需在 .env 中开关）
- 📋 **自动粘贴** — 处理完自动粘贴到当前光标位置
- 🔔 **系统通知** — 每个阶段 macOS 通知反馈，不盯终端也知道进度
- 🍎 **macOS 原生** — 菜单点击粘贴 + 系统通知，深度系统集成

## 架构

```
Global Hotkey (hold) → Recorder (sounddevice) → Transcriber (local Whisper) → Refiner (LLM) → Output (clipboard + paste)
```

## 智能精炼策略

> 💡 **可选功能。** 作者日常未启用（模型效果一般 + 增加延迟），感兴趣可以在 `.env` 中开启，也欢迎接更强的模型试试。

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
