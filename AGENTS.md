# VoiceTranser

语音输入 → 转写 → 自动粘贴。全局热键触发 HTTP 端点录音，本地 STT 转写，自动粘贴到当前应用。完全本地运行，零外部 API 依赖。

## 双引擎(2026-07-04 起)

两个 STT 引擎可切换，默认 SenseVoice：

- **SenseVoice**(sherpa-onnx，默认)：非自回归并行解码，中文秒出。15s 音频纯推理 ~0.46s(RTF 0.03)，中文标点地道，模型 228MB / 常驻 ~400MB。
- **mlx-whisper large-v3**(fallback)：自回归，MLX/Metal 优化，英文/小语种更强。15s 音频 ~1.08s(RTF 0.07)，长音频易丢标点，常驻 ~3GB。

实测对比(15.18s 中文)：sense 0.46s + 标点完整；whisper 1.08s + 丢标点。中文场景 sense 全面更优。

引擎由 `STT_ENGINE` 环境变量切换：`sensevoice`(默认)/ `mlx-whisper`。

## 当前实例（2026-07-13 起）

sense 引擎测好后转正为主力，老 mlx-whisper 实例 2026-08-23 已彻底移除：

| 实例 | launchd Label | 端口 | 引擎 | 热键 | 状态 |
|------|---------------|------|------|------|------|
| 主力 | `com.voicetranser-sense` | 9877 | sensevoice | `right_option` 按下录/松开停 | ✅ 已 load，开机自启 + KeepAlive |

热键由 Karabiner-Elements complex_modifications 配置：`right_option` 按下 → `curl localhost:9877/start`，松开 → `curl localhost:9877/stop`（见 `~/.config/karabiner/karabiner.json`）。

主力 plist：`com.voicetranser-sense.plist`(项目根)，同步装到 `~/Library/LaunchAgents/`，日志 `~/Library/Logs/VoiceTranser-sense.log`。**路径已修正为 `/Users/black-wood/IdeaProjects/myProjects/VoiceTranser`**（之前写错少一层 `myProjects`，导致重启后 launchd 找不到 python、`EX_CONFIG` 反复崩）。

**老实例收尾（2026-08-23 完成）**：已删 `~/Library/LaunchAgents/com.voicetranser.plist` 并 bootout（其路径仍指向旧 `/IdeaProjects/VoiceTranser`，每次开机以 exit 78 空转）；`.env` 去掉 `STT_ENGINE=mlx-whisper` 锁定；Karabiner 删 `right_command`→9876 规则（删前备份 `.zcode/tmp/karabiner.json.bak-20260823`）。如需恢复 mlx-whisper：改用 `STT_ENGINE=mlx-whisper` 起新实例或临时命令行运行。

## 架构

```
External Hotkey → HTTP /toggle → Recorder (sounddevice) → Transcriber (sensevoice/mlx-whisper) → Output (clipboard + paste)
```

## 技术栈

- Python 3.11+，`pyproject.toml` + `uv`
- STT: `sherpa-onnx` + SenseVoice Small(默认)/ `mlx-whisper`(fallback)，均本地推理
- HTTP 服务器: `http.server`(标准库)
- 音频: `sounddevice` + `numpy`

## 关键文件

| 文件 | 职责 |
|------|------|
| `voicetranser/config.py` | 配置管理(stt_engine / whisper_model / port 等) |
| `voicetranser/recorder.py` | 音频录制，sounddevice 流式采集 → WAV |
| `voicetranser/transcriber.py` | STT 双引擎分派(sensevoice / mlx-whisper)，各自懒加载、单例 |
| `voicetranser/corrector.py` | STT 误识词纠正(转写后、输出前)，纯整词匹配，词表来自 `corrections.json` |
| `voicetranser/server.py` | HTTP toggle 服务器(/toggle, /start, /stop, /status) |
| `voicetranser/output.py` | 剪贴板写入 + 自动粘贴(菜单点击优先，keystroke fallback) |
| `voicetranser/status.py` | macOS 系统通知反馈 |
| `voicetranser/__main__.py` | CLI 入口(守护 / 单次 / 文件处理) |
| `corrections.json` | 误识词纠正词表(用户可编辑，日常发现新误识加一行即可) |
| `download_model.py` | 下 SenseVoice 模型到 `models/sense-voice/`(hf-mirror 源，幂等) |
| `com.voicetranser-sense.plist` | 新实例 launchd 配置(端口 9877 + sensevoice) |
| `voicetranser/hotkey.py` | 已废弃(pynput push-to-talk，被 HTTP server 取代，pynput 不在依赖) |

## 配置

`.env` / 环境变量(均有默认值，无需 API key)：

- `STT_ENGINE=sensevoice|mlx-whisper`(默认 sensevoice)
- `WHISPER_MODEL=large-v3`(仅 mlx-whisper 用)
- `SERVER_PORT=9876`(默认；新实例用 9877)
- `SAMPLE_RATE=16000` / `LANGUAGE=zh`

## 使用

```bash
# 首次：下 SenseVoice 模型(228MB，hf-mirror 国内源)
uv run python download_model.py

# 守护(默认 sensevoice，9876)
uv run python -m voicetranser

# 用 mlx-whisper 跑
STT_ENGINE=mlx-whisper uv run python -m voicetranser

# 第二实例(sense，9877)—— 等价于 com.voicetranser-sense plist
SERVER_PORT=9877 STT_ENGINE=sensevoice uv run python -m voicetranser

# 处理音频文件(对比两引擎)
STT_ENGINE=sensevoice uv run python -m voicetranser --file recording.wav --no-paste
```
