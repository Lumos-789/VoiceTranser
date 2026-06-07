# VoiceTranser

语音输入 → 转写 → 自动粘贴。全局热键触发 HTTP 端点录音，本地 mlx-whisper 转写，自动粘贴到当前应用。完全本地运行，零外部 API 依赖。

## 架构

```
External Hotkey → HTTP /toggle → Recorder (sounddevice) → Transcriber (mlx-whisper) → Output (clipboard + paste)
```

## 技术栈

- Python 3.11+，`pyproject.toml` + `uv`
- STT: `mlx-whisper` 本地推理（Apple Silicon 优化），无需网络
- HTTP 服务器: `http.server`（标准库）
- 音频: `sounddevice` + `numpy`

## 关键文件

| 文件 | 职责 |
|------|------|
| `voicetranser/config.py` | 配置管理，从 .env/环境变量加载 |
| `voicetranser/recorder.py` | 音频录制，sounddevice 流式采集 → WAV |
| `voicetranser/transcriber.py` | STT，本地 mlx-whisper |
| `voicetranser/server.py` | HTTP toggle 服务器（/toggle, /start, /stop, /status） |
| `voicetranser/output.py` | 剪贴板写入 + 自动粘贴（菜单点击优先，keystroke fallback） |
| `voicetranser/status.py` | macOS 系统通知反馈 |
| `voicetranser/__main__.py` | CLI 入口（守护模式 / 单次调试 / 文件处理） |

## 配置

所有配置均有默认值，无需 API key。

```bash
# .env 文件（可选）
WHISPER_MODEL=large-v3          # tiny/base/small/medium/large-v3
SAMPLE_RATE=16000
LANGUAGE=zh
SERVER_PORT=9876
```

## 使用

```bash
# 安装
cd VoiceTranser && uv sync

# 启动（守护模式，HTTP 服务器）
uv run python -m voicetranser

# 单次录制（调试）
uv run python -m voicetranser --once

# 处理音频文件
uv run python -m voicetranser --file recording.wav

# 查看配置
uv run python -m voicetranser --config
```
