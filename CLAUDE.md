# VoiceTranser

语音输入 → AI 智能精炼 → 自动粘贴到 Claude Code。全局热键按住说话，松开后自动转写、精炼、粘贴。

## 架构

```
Global Hotkey (hold) → Recorder (sounddevice) → Transcriber (local faster-whisper) → Refiner (MiniMax-M3) → Output (clipboard + paste)
```

## 技术栈

- Python 3.11+，`pyproject.toml` + `uv`
- STT: `faster-whisper` 本地推理（CTranslate2，Apple Silicon 优化），无需 API key
- Prompt 精炼: MiniMax-M3 (Anthropic SDK 兼容)
- 全局热键: `pynput`
- 音频: `sounddevice` + `numpy`

## 关键文件

| 文件 | 职责 |
|------|------|
| `voicetranser/config.py` | 配置管理，从 .env/环境变量加载 |
| `voicetranser/recorder.py` | 音频录制，sounddevice 流式采集 → WAV |
| `voicetranser/transcriber.py` | STT，本地 faster-whisper (CTranslate2) |
| `voicetranser/refiner.py` | Prompt 精炼，MiniMax-M3 |
| `voicetranser/hotkey.py` | 全局热键监听，pynput |
| `voicetranser/output.py` | 剪贴板写入 + 自动粘贴 |
| `voicetranser/__main__.py` | CLI 入口 |
| `voicetranser/prompts/refine_system.txt` | 精炼 system prompt |

## 配置

仅需一个 API key（MiniMax），STT 完全本地运行。

```bash
# .env 文件
MINIMAX_API_KEY=sk-xxx          # MiniMax token plan
MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic
MINIMAX_MODEL=MiniMax-M3
WHISPER_MODEL=small             # tiny/base/small/medium/large-v3，越大越准但越慢
HOTKEY=cmd_r                    # 全局热键
LANGUAGE=zh                     # 语音语言
```

## 使用

```bash
# 安装
cd VoiceTranser && uv sync

# 配置
cp .env.example .env  # 填入 MiniMax API key

# 启动（守护模式，全局热键）
uv run python -m voicetranser

# 单次录制（调试）
uv run python -m voicetranser --once

# 处理音频文件
uv run python -m voicetranser --file recording.wav

# 查看配置
uv run python -m voicetranser --config
```

## MiniMax 接入

复用 CC-Switch 的 Anthropic 兼容格式：
- Endpoint: `https://api.minimaxi.com/anthropic`
- Auth: `ANTHROPIC_AUTH_TOKEN`
- Model: `MiniMax-M3`
- 使用 `anthropic` SDK，`base_url` 覆盖
