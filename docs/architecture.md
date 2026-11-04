# 架构与数据流

面向改这份代码的人。使用说明在 `README.md`，装/排障流程在 `skills/voicetranser/SKILL.md`。

## 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│  外部热键工具 (Karabiner / Raycast / 快捷指令)                  │
│  按下 → curl /start     松开 → curl /stop                     │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP (127.0.0.1:<port>)
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                     VoiceTranser 守护进程                      │
│  ┌─────────┐  ┌───────────┐  ┌─────────────┐  ┌───────────┐  │
│  │ Server  │→ │ Recorder  │→ │ Transcriber │→ │  Output   │  │
│  │(HTTP API)│  │(sounddevice)│ │(qwen3-mlx/sense/whisper)│ │(剪贴板+粘贴)│
│  └─────────┘  └───────────┘  └─────────────┘  └───────────┘  │
│       │                              │              │         │
│       ▼                              ▼              ▼         │
│   状态机锁           引擎懒加载单例         osascript 模拟 Cmd+V  │
└──────────────────────────────────────────────────────────────┘
```

## 状态机

Server 维护一个三态状态机，所有请求加锁串行化：

```
        /start 或 /toggle            录音 ≥0.5s,/stop 或 /toggle
  ┌──────────────────────┐         ┌──────────────────────┐
  │                      ▼         │                      ▼
idle ◄───────────────── recording ◄────────────────── processing
  │   (录音太短/异常回 idle)                                  │
  └──────────────────────────────────────────────────────────┘
                  转写+粘贴完成,后台线程回 idle
```

- `idle` → `recording`：调用 `/start` 或 `/toggle`（空闲时）
- `recording` → `processing`：调用 `/stop` 或 `/toggle`（录音中），录音 <0.5s 直接回 `idle`
- `processing` → `idle`：后台转写线程完成后自动回 `idle`
- 处理中再次请求 → 返回 `409 busy`，拒绝

## 模块职责

| 文件 | 职责 |
|------|------|
| `voicetranser/__main__.py` | CLI 入口（守护 / 单次 / 文件处理 / 查配置），含 `process_audio` 全流水线函数 |
| `voicetranser/config.py` | 配置管理。读 `.env` + 环境变量，产出不可变 `Config` dataclass |
| `voicetranser/recorder.py` | 音频录制。`sounddevice` 流式采集 → WAV bytes。长连接 stream 复用，省每次开设备 ~160ms |
| `voicetranser/transcriber.py` | STT 三引擎分派（qwen3-mlx / sensevoice / mlx-whisper），各自懒加载、单例 |
| `voicetranser/launchd.py` | 按当前 checkout 生成 launchd plist，避免把作者本机路径带给用户 |
| `install_launchd.py` | 生成并加载当前用户的 launchd 服务（`--no-load` 只生成） |
| `voicetranser/server.py` | HTTP toggle 服务器。`/toggle` `/start` `/stop` `/status`，状态机 + 后台转写线程 |
| `voicetranser/corrector.py` | STT 误识词纠正（转写后、输出前）。纯整词匹配、大小写不敏感，词表来自 `corrections.json`，支持多 token 短语（如 `claude code`） |
| `voicetranser/watchdog.py` | CoreAudio 死锁看门狗：建流/start/stop 超时（默认 5s）即 `os._exit`，由 launchd KeepAlive 秒级拉起自愈 |
| `voicetranser/output.py` | 剪贴板写入 + 自动粘贴。菜单点击优先（Edit>Paste），失败回退 keystroke 模拟 Cmd+V |
| `voicetranser/status.py` | macOS 系统通知 + 音效反馈（afplay 异步，不阻塞 handler） |
| `download_model.py` | 下 SenseVoice 模型到 `models/sense-voice/`（hf-mirror 源，幂等） |
| `tests/diagnose.py` | 诊断脚本，逐层检查 8 项健康状态，支持 `--fix` 自动重启、`--skip-audio` 跳过麦克风 |
| `VoiceTranser.app/` | .app bundle 壳（仅授权用，内部 `cd` 到项目目录跑 `python -m voicetranser`） |

## 技术栈

| 组件 | 技术 |
|------|------|
| STT | [mlx-audio](https://github.com/Blaizzy/mlx-audio) + Qwen3-ASR（默认） / [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) + SenseVoice / [mlx-whisper](https://github.com/ml-explore/mlx-whisper) |
| 音频录制 | [sounddevice](https://python-sounddevice.readthedocs.io/) + numpy |
| HTTP 服务器 | Python 标准库 `http.server`（`ThreadingHTTPServer`） |
| 剪贴板 | [pyperclip](https://github.com/asweigart/pyperclip) |
| 配置 | [python-dotenv](https://github.com/theskumar/python-dotenv) |
| 系统集成 | `osascript`（通知 / 菜单点击粘贴）、`afplay`（音效） |
| 包管理 | [uv](https://docs.astral.sh/uv/) + `pyproject.toml` |
| Python | 3.11+ |
