# VoiceTranser

语音输入 → 转写 → 自动粘贴。全局热键触发 HTTP 端点录音，本地 STT 转写，自动粘贴到当前应用。完全本地运行，零外部 API 依赖。

## 三引擎(2026-11-01 起)

三个 STT 引擎可切换，默认 Qwen3-ASR MLX：

- **Qwen3-ASR MLX**(mlx-audio，默认主力)：0.6B 4bit，MLX/Metal GPU 推理。实测 RTF 0.012-0.021(约为 sensevoice CPU 的一半)，纯中文近完美自带标点引号、中英夹杂/粤语方言强、LLM 纠错(如"平繁→频繁")。模型 `mlx-community/Qwen3-ASR-0.6B-4bit`(hf-mirror 拉，缓存在 `~/.cache/huggingface`)，常驻内存 ~1.5GB。
- **SenseVoice**(sherpa-onnx 1.10.46，CPU fallback)：非自回归并行解码，RTF 0.03，中英日韩粤。模型 228MB。
- **mlx-whisper large-v3**(fallback)：自回归，英文/小语种更强，长音频易丢标点，常驻 ~3GB。

实测对比(2026-11-01，TTS+官方真音)：16.5s 中文 qwen3-mlx 0.254s / sense 0.531s / qwen3-cpu 1.35s；质量 qwen3 > sense > fire-red-asr2-ctc(已否决：延迟 3.2x+code-switch 碎裂)。**质量评测勿用 TTS 合成音**(FireRed 真人语料训练对合成音泛化差，结论会反)。

引擎由 `STT_ENGINE` 环境变量切换：`qwen3-mlx`(默认)/ `sensevoice` / `mlx-whisper`。launchd plist 显式设了 `STT_ENGINE=qwen3-mlx`(优先于 .env)。

## 当前实例（2026-11-01 引擎切换）

| 实例 | launchd Label | 端口 | 引擎 | 热键 | 状态 |
|------|---------------|------|------|------|------|
| 主力 | `com.voicetranser-sense` | 9877 | qwen3-mlx | `right_option` 按下录/松开停 | ✅ 已 load，开机自启 + KeepAlive |

注：label 沿用旧名 `-sense`（2026-07 sense 转正时命名），2026-11-01 换 qwen3-mlx 引擎时未改 label，避免动 launchd/日志链路；回退引擎只改 plist/env 的 `STT_ENGINE` 重启即换。服务启动时后台线程预热模型（qwen3-mlx 缓存命中后加载仅数秒；首次冷加载 ~75s）。

热键由 Karabiner-Elements complex_modifications 配置：`right_option` 按下 → `curl localhost:9877/start`，松开 → `curl localhost:9877/stop`（见 `~/.config/karabiner/karabiner.json`）。

主力 plist：`com.voicetranser-sense.plist`(项目根)，同步装到 `~/Library/LaunchAgents/`，日志 `~/Library/Logs/VoiceTranser-sense.log`。**路径已修正为 `/Users/black-wood/IdeaProjects/myProjects/VoiceTranser`**（之前写错少一层 `myProjects`，导致重启后 launchd 找不到 python、`EX_CONFIG` 反复崩）。

**老实例收尾（2026-08-23 完成）**：已删 `~/Library/LaunchAgents/com.voicetranser.plist` 并 bootout（其路径仍指向旧 `/IdeaProjects/VoiceTranser`，每次开机以 exit 78 空转）；`.env` 去掉 `STT_ENGINE=mlx-whisper` 锁定；Karabiner 删 `right_command`→9876 规则（删前备份 `.zcode/tmp/karabiner.json.bak-20260823`）。如需恢复 mlx-whisper：改用 `STT_ENGINE=mlx-whisper` 起新实例或临时命令行运行。

## 架构

```
External Hotkey → HTTP /toggle → Recorder (sounddevice) → Transcriber (sensevoice/mlx-whisper) → Output (clipboard + paste)
```

## 技术栈

- Python 3.11+，`pyproject.toml` + `uv`
- STT: `mlx-audio` + Qwen3-ASR 0.6B 4bit(默认，MLX/Metal)/ `sherpa-onnx` + SenseVoice Small / `mlx-whisper`，均本地推理
- HTTP 服务器: `http.server`(标准库)
- 音频: `sounddevice` + `numpy`

## 关键文件

| 文件 | 职责 |
|------|------|
| `voicetranser/config.py` | 配置管理(stt_engine / whisper_model / port 等) |
| `voicetranser/recorder.py` | 音频录制，sounddevice 流式采集 → WAV |
| `voicetranser/watchdog.py` | CoreAudio 死锁看门狗：建流/start/stop 超时(默认5s)则 `os._exit` 由 launchd 自愈重启(2026-08-27 事故) |
| `voicetranser/transcriber.py` | STT 三引擎分派(qwen3-mlx / sensevoice / mlx-whisper)，各自懒加载、单例；qwen3-mlx 含 MLX cache_limit 内存治理与线程安全预热 |
| `voicetranser/corrector.py` | STT 误识词纠正(转写后、输出前)，纯整词匹配，词表来自 `corrections.json` |
| `voicetranser/server.py` | HTTP toggle 服务器(/toggle, /start, /stop, /status)；启动时后台线程预热当前引擎模型 |
| `voicetranser/output.py` | 剪贴板写入 + 自动粘贴(菜单点击优先，keystroke fallback) |
| `voicetranser/status.py` | macOS 系统通知反馈 |
| `voicetranser/__main__.py` | CLI 入口(守护 / 单次 / 文件处理) |
| `corrections.json` | 误识词纠正词表(用户可编辑，日常发现新误识加一行即可) |
| `download_model.py` | 下 SenseVoice 模型到 `models/sense-voice/`(hf-mirror 源，幂等)；qwen3-mlx 模型由 mlx-audio 首次运行自动拉取(HF_ENDPOINT=hf-mirror) |
| `com.voicetranser-sense.plist` | launchd 配置(端口 9877 + qwen3-mlx) |
| `voicetranser/hotkey.py` | 已废弃(pynput push-to-talk，被 HTTP server 取代，pynput 不在依赖) |

## 配置

`.env` / 环境变量(均有默认值，无需 API key)：

- `STT_ENGINE=qwen3-mlx|sensevoice|mlx-whisper`(默认 qwen3-mlx)
- `WHISPER_MODEL=large-v3`(仅 mlx-whisper 用)
- `SERVER_PORT=9876`(默认；主力实例 9877)
- `SAMPLE_RATE=16000` / `LANGUAGE=zh`
- `VT_AUDIO_WATCHDOG_TIMEOUT=5`(秒；音频流操作超时即自杀重启，勿设太小以免唤醒后冷启动误杀)

## 使用

```bash
# 首次：下 SenseVoice 模型(228MB，hf-mirror 国内源；qwen3-mlx 模型首次运行自动拉)
uv run python download_model.py

# 守护(默认 qwen3-mlx，9876)
uv run python -m voicetranser

# 临时用 sensevoice / mlx-whisper 跑
STT_ENGINE=sensevoice uv run python -m voicetranser
STT_ENGINE=mlx-whisper uv run python -m voicetranser

# 处理音频文件(对比引擎；--no-paste 只打印不粘贴)
STT_ENGINE=qwen3-mlx uv run python -m voicetranser --file recording.wav --no-paste
```

坑：uv 直连 PyPI 极慢时用清华镜像 `UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple`。
