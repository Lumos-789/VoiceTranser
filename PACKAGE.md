# VoiceTranser · 使用说明（拆包文档）

> 按住一个键说话,松开自动转写成文字粘到光标。**全程本地、断网可用、中文秒出、隐私不出设备。**
> 专为 AI 编程(Claude Code / Cursor)和日常打字设计。

本文是给「想拿去用的人」看的完整说明:它是什么、怎么装、怎么配、怎么跑、怎么排障。读完能独立把它跑起来。

---

## 1. 它是什么

VoiceTranser 是一个 macOS 本地语音输入工具。核心流程:

```
按住热键 ──▶ 录音 ──▶ 本地 STT 转写 ──▶ 自动粘贴到当前光标
```

**特点**:

| 特性 | 说明 |
|------|------|
| 🎙️ 全局热键录音 | 通过外部快捷键工具(Karabiner/Raycast)触发 HTTP 端点,按住说话、松开出字 |
| 🧠 本地 STT,双引擎 | 默认 [SenseVoice](https://github.com/FunAudioLLM/SenseVoice)(中文秒出);[mlx-whisper](https://github.com/ml-explore/mlx-whisper) large-v3 作 fallback(英文/小语种更强)。均离线,无需网络 |
| 📋 自动粘贴 | 转写完自动粘到当前光标位置(任何应用都行) |
| 🔔 系统通知 | 每个阶段 macOS 通知 + 音效反馈 |
| 🍎 macOS 原生 | 菜单点击粘贴 + 系统通知,深度系统集成 |
| 🔒 隐私安全 | 麦克风音频不出设备,零外部 API 依赖 |

**适用场景**:Claude Code 终端、微信、备忘录、邮件、浏览器 —— 任何能打字的地方。

---

## 2. 架构与数据流

### 2.1 整体架构

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
│  │(HTTP API)│  │(sounddevice)│ │(sense/whisper)│ │(剪贴板+粘贴)│  │
│  └─────────┘  └───────────┘  └─────────────┘  └───────────┘  │
│       │                              │              │         │
│       ▼                              ▼              ▼         │
│   状态机锁           引擎懒加载单例         osascript 模拟 Cmd+V  │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 状态机

Server 维护一个三态状态机,所有请求加锁串行化:

```
        /start 或 /toggle            录音 ≥0.5s,/stop 或 /toggle
  ┌──────────────────────┐         ┌──────────────────────┐
  │                      ▼         │                      ▼
idle ◄───────────────── recording ◄────────────────── processing
  │   (录音太短/异常回 idle)                                  │
  └──────────────────────────────────────────────────────────┘
                  转写+粘贴完成,后台线程回 idle
```

- `idle` → `recording`:调用 `/start` 或 `/toggle`(空闲时)
- `recording` → `processing`:调用 `/stop` 或 `/toggle`(录音中),录音 <0.5s 直接回 `idle`
- `processing` → `idle`:后台转写线程完成后自动回 `idle`
- 处理中再次请求 → 返回 `409 busy`,拒绝

### 2.3 模块职责

| 文件 | 职责 |
|------|------|
| `voicetranser/__main__.py` | CLI 入口(守护 / 单次 / 文件处理 / 查配置),含 `process_audio` 全流水线函数 |
| `voicetranser/config.py` | 配置管理。读 `.env` + 环境变量,产出不可变 `Config` dataclass |
| `voicetranser/recorder.py` | 音频录制。`sounddevice` 流式采集 → WAV bytes。长连接 stream 复用,省每次开设备 ~160ms |
| `voicetranser/transcriber.py` | STT 双引擎分派(sensevoice / mlx-whisper),各自懒加载、单例,互不 import |
| `voicetranser/server.py` | HTTP toggle 服务器。`/toggle` `/start` `/stop` `/status`,状态机 + 后台转写线程 |
| `voicetranser/output.py` | 剪贴板写入 + 自动粘贴。菜单点击优先(Edit>Paste),失败回退 keystroke 模拟 Cmd+V |
| `voicetranser/status.py` | macOS 系统通知 + 音效反馈(afplay 异步,不阻塞 handler) |
| `voicetranser/hotkey.py` | ⚠️ **已废弃**(pynput push-to-talk,被 HTTP server 取代,`pynput` 不在依赖里,别用) |
| `download_model.py` | 下 SenseVoice 模型到 `models/sense-voice/`(hf-mirror 源,幂等) |
| `com.voicetranser-sense.plist` | launchd 配置示例(作者本机用,端口 9877 + sensevoice) |
| `tests/diagnose.py` | 诊断脚本,逐层检查 8 项健康状态,支持 `--fix` 自动重启 |
| `VoiceTranser.app/` | .app bundle 壳(仅授权用,内部 `cd` 到项目目录跑 `python -m voicetranser`) |

---

## 3. 双引擎说明

两个 STT 引擎可切换,**默认 SenseVoice**:

| 引擎 | 适合语种 | 模型大小 | 常驻内存 | 15 秒中文推理 | 切换方式 |
|------|----------|----------|----------|---------------|----------|
| **SenseVoice**(默认) | 中文为主、中英日韩粤 | 228MB | ~400MB | **~0.46 秒**(RTF 0.03) | `STT_ENGINE=sensevoice` |
| **mlx-whisper large-v3** | 英文/小语种、长音频 | 3GB | ~3GB | ~1.08 秒(RTF 0.07) | `STT_ENGINE=mlx-whisper` |

**怎么选**:中文场景默认 SenseVoice 就对了(速度快 2 倍 + 标点地道 + 内存省 7 倍)。英文为主再切 mlx-whisper。

**技术差异**:
- SenseVoice:非自回归并行解码,sherpa-onnx + int8 量化模型,初始化时 `language="auto"` 自动判语种
- mlx-whisper:自回归,MLX/Metal 优化,代码里已设 `mx.set_cache_limit(1GB)` 防止 Metal buffer 缓存无限增长(否则长期运行能涨到 14GB)

两个引擎各自懒加载、单例,互不 import —— 只用其中一个的实例不必装另一个的依赖。

---

## 4. 前置要求

- **macOS**(仅支持 Mac,Apple Silicon 最佳,Intel 也能跑)
- **macOS 13+**(Ventura 及以上)
- **Python 3.11+**(没有的话,uv 会自动帮你装,不用操心)
- **[uv](https://docs.astral.sh/uv/)** —— 超快的 Python 包管理器
- 约 **500MB 磁盘**(SenseVoice 模型 228MB + 依赖 ~200MB;用 mlx-whisper 还要再下 3GB 模型)

> Windows / Linux 不支持(依赖 macOS 的 `osascript`、`afplay`、`pyperclip` 的 Mac 后端)。

---

## 5. 安装(5 步)

### 第 1 步:装 uv

打开**终端**(Terminal.app / iTerm / Warp),粘贴回车:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

装完**重开一个终端窗口**(让 PATH 生效),验证:

```bash
uv --version
# 输出类似 uv 0.x.x 就对了
```

### 第 2 步:拉项目 + 装依赖

```bash
git clone https://github.com/Lumos-789/VoiceTranser.git
cd VoiceTranser
uv sync          # 自动建虚拟环境、装全部依赖
```

`uv sync` 会创建 `.venv/` 并装好 `sounddevice`、`sherpa-onnx`、`mlx-whisper`、`pyperclip`、`python-dotenv` 等。第一次约 2~3 分钟。

> ⚠️ `sherpa-onnx` 锁定在 `==1.10.46`(自包含 wheel)。1.13.x 的 PyPI 瘦版缺 onnxruntime dylib,会崩。别擅自升级。

### 第 3 步:下载语音模型(228MB,一次性)

默认用 **SenseVoice**(中文场景最佳):

```bash
uv run python download_model.py
```

走 HuggingFace 国内镜像(hf-mirror.com),国内带宽约 1~3 分钟。下载到 `models/sense-voice/`,**幂等** —— 已存在会跳过。

> 海外用户如果镜像慢,改走官方源:
> ```bash
> HF_ENDPOINT=https://huggingface.co uv run python download_model.py
> ```

> 用 mlx-whisper 的话不用这步,首次转写时自动从 HuggingFace 下模型(走 `HF_ENDPOINT` 镜像)。

### 第 4 步:配置(可选,默认就能跑)

项目自带 `.env.example`,默认配置已是最佳实践。想改才需要操作:

```bash
cp .env.example .env
```

可调项(都有默认值,不动也行):

| 变量 | 默认 | 说明 |
|------|------|------|
| `STT_ENGINE` | `sensevoice` | `sensevoice`(中文秒出)/ `mlx-whisper`(英文/小语种更强) |
| `WHISPER_MODEL` | `large-v3` | 仅 `STT_ENGINE=mlx-whisper` 时生效。可选 `tiny`/`base`/`small`/`medium`/`large-v3` |
| `SERVER_PORT` | `9876` | HTTP 服务端口,改了要同步改热键配置 |
| `SAMPLE_RATE` | `16000` | 采样率,别动 |
| `LANGUAGE` | `zh` | 识别语言(sensevoice 用 auto 自动判,这个主要给 whisper) |
| `HF_ENDPOINT` | `https://hf-mirror.com` | 模型下载源,海外可改 `https://huggingface.co` |
| `SOUND_ENABLED` | `true` | 反馈音效开关,嫌吵设 `false` |
| `START_SOUND` / `DONE_SOUND` | `Blow` / `Glass` | 系统 Sound 名,可换 `Tink`/`Pop`/`Frog`/`Submarine` 等(见 `/System/Library/Sounds/`) |

### 第 5 步:授权(关键!不授权没法用)

VoiceTranser 需要两个权限:**麦克风**(录音)和**辅助功能**(自动粘贴)。

**5.1 麦克风权限** —— 首次运行时系统会弹窗,点**允许**即可。没弹或手滑点了拒绝,手动开:
**系统设置 → 隐私与安全性 → 麦克风** → 把你跑命令的终端(Terminal / iTerm / Warp)打开开关。

**5.2 边助功能权限**(自动粘贴必需) —— **系统设置 → 隐私与安全性 → 辅助功能** → 把你的终端应用拖进来 / 打开开关。

> 这个权限让 VoiceTranser 能模拟 `Cmd+V` 把转写结果粘到当前窗口。没这个权限 = 转写能成功但不会自动粘贴。

> ⚠️ 授权后**重启一次终端**再继续。
>
> ⚠️ 用 launchd 开机自启的话,launchd 启动的进程要**单独再授一次**辅助功能权限 —— 在「辅助功能」列表里会出现一个 `python` 或 `Python` 条目,把它打开。不做这步,launchd 实例无法自动粘贴。

---

## 6. 跑起来

### 6.1 手动试跑

```bash
uv run python -m voicetranser
```

看到类似输出就成功了:

```
[VoiceTranser] STT 引擎: sensevoice
[VoiceTranser] HTTP server listening on 127.0.0.1:9876
  GET /start   — start recording
  GET /stop    — stop recording & process
  GET /toggle  — toggle start/stop
  GET /status  — current state
```

**手动测试**(新开一个终端窗口):

```bash
curl http://localhost:9876/start     # 开始录音,对着麦克风说几句话
curl http://localhost:9876/stop      # 停止 → 自动转写 → 自动粘贴到当前光标
```

转写结果会自动粘到你当前光标所在的输入框。按 `Ctrl+C` 停掉服务。

### 6.2 其他运行模式

```bash
# 守护模式(默认,HTTP 服务器,日常使用)
uv run python -m voicetranser

# 单次录制(交互式调试,回车开始/停止)
uv run python -m voicetranser --once

# 处理音频文件(不粘贴,只输出到 stderr)
uv run python -m voicetranser --file recording.wav --no-paste

# 查看当前配置
uv run python -m voicetranser --config

# 指定引擎/端口跑
STT_ENGINE=mlx-whisper uv run python -m voicetranser
SERVER_PORT=9877 STT_ENGINE=sensevoice uv run python -m voicetranser
```

---

## 7. 绑定热键(核心体验)

手敲 curl 太蠢了。真正的用法是**按住一个物理键说话,松开自动出字**。三种方案选一:

### 方案 A:Karabiner-Elements(⭐ 推荐,体验最丝滑)

[Karabiner-Elements](https://karabiner-elements.pqrs.org/)(免费)是 macOS 键盘改造神器,支持「按住/松开」两种事件。

1. 下载安装 Karabiner-Elements,打开后授予它需要的权限
2. 编辑 `~/.config/karabiner/assets/complex_modifications/voicetranser.json`,粘贴:

```json
{
  "title": "VoiceTranser: 右 Option 按住说话",
  "rules": [
    {
      "description": "右 Option 按下开始录音,松开停止并转写",
      "manipulators": [
        {
          "type": "basic",
          "from": { "key_code": "right_option" },
          "to": [
            { "shell_command": "curl -s http://localhost:9876/start >/dev/null 2>&1 &" }
          ],
          "to_after_key_up": [
            { "shell_command": "curl -s http://localhost:9876/stop >/dev/null 2>&1 &" }
          ]
        }
      ]
    }
  ]
}
```

3. 保存后回到 Karabiner Settings → Complex Modifications → **Add rule**,启用「右 Option 按住说话」

> 端口不是 9876?把 JSON 里的 `9876` 全换成你的 `SERVER_PORT`。
> 想换键?`right_option` 可改成 `right_command` / `fn` / `caps_lock` 等。

### 方案 B:Raycast(免费,不想装 Karabiner 的选这个)

[Raycast](https://www.raycast.com/) 是个启动器。**Commands → Create Script Command**,建两条(各绑一个快捷键,如 `Cmd+Shift+1` 开始、`Cmd+Shift+2` 停止):

```bash
#!/bin/bash
# 开始录音
curl -s http://localhost:9876/start

#!/bin/bash
# 停止转写
curl -s http://localhost:9876/stop
```

> 局限:Raycast 不支持「按住/松开」,只能两个命令各绑一个快捷键,体验不如 Karabiner 的按住式。

### 方案 C:系统快捷指令(最简,macOS 自带)

1. 打开「快捷指令」→ 新建快捷指令
2. 动作选「运行 Shell 脚本」,内容填 `curl -s http://localhost:9876/toggle`
3. 右侧 ⚙️ → 添加键盘快捷键 → 按一个组合键(如 `F5`)

> 这是 toggle 模式(按一下开始,再按一下停止),不是按住式。

---

## 8. 开机自启(一劳永逸)

用 macOS 原生的 **launchd** 让 VoiceTranser 开机自动后台运行、崩溃自动重启。

### 8.1 生成 plist

先查你的用户名和项目绝对路径:

```bash
whoami        # 用户名,如 sarah
pwd           # 项目绝对路径,如 /Users/sarah/VoiceTranser
```

创建 `~/Library/LaunchAgents/com.voicetranser.plist`(**替换两处 `<...>`**):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.voicetranser</string>
    <key>ProgramArguments</key>
    <array>
        <string><YOUR_PROJECT_PATH>/.venv/bin/python3</string>
        <string>-m</string>
        <string>voicetranser</string>
    </array>
    <key>WorkingDirectory</key>
    <string><YOUR_PROJECT_PATH></string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>STT_ENGINE</key>
        <string>sensevoice</string>
        <key>SERVER_PORT</key>
        <string>9876</string>
        <key>HF_ENDPOINT</key>
        <string>https://hf-mirror.com</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/<YOUR_USERNAME>/Library/Logs/VoiceTranser.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/<YOUR_USERNAME>/Library/Logs/VoiceTranser.log</string>
</dict>
</plist>
```

> 项目根的 `com.voicetranser-sense.plist` 是作者本机用的示例(端口 9877 + sensevoice,路径硬编码),可参考但别直接用 —— 路径是别人的。

### 8.2 加载并启动

```bash
# 加载(立即启动,因为 RunAtLoad=true)
launchctl load ~/Library/LaunchAgents/com.voicetranser.plist

# 验证在跑
curl http://localhost:9876/status
# 期望: {"status": "idle"}
```

### 8.3 launchd 常用命令

```bash
launchctl load ~/Library/LaunchAgents/com.voicetranser.plist      # 启用
launchctl unload ~/Library/LaunchAgents/com.voicetranser.plist    # 停用
launchctl kickstart -k gui/$(id -u)/com.voicetranser               # 重启服务
tail -f ~/Library/Logs/VoiceTranser.log                            # 看日志
```

> ⚠️ **路径是最大的坑**。launchd 启动失败 99% 是 plist 里路径写错。验证:
> ```bash
> ls <YOUR_PROJECT_PATH>/.venv/bin/python3   # 必须真实存在
> ```
> 作者曾因路径少写一层 `myProjects`,导致 launchd 找不到 python、`EX_CONFIG` 反复崩。

---

## 9. HTTP API 速查

守护模式启动后监听 `http://127.0.0.1:<SERVER_PORT>`(默认 9876):

| 端点 | 方法 | 说明 | 返回 |
|------|------|------|------|
| `/toggle` | GET | 切换录音状态(空闲→录 / 录→停转写) | `{"status": "recording"}` / `{"status": "processing"}` |
| `/start` | GET | 开始录音(空闲时) | `{"status": "recording"}`;非空闲 `409 {"status": ..., "message": "busy"}` |
| `/stop` | GET | 停止录音并触发转写+粘贴(录音中) | `{"status": "processing"}`;录音太短 `{"status": "idle", "message": "too short"}`;非录音中 `409` |
| `/status` | GET | 查当前状态 | `{"status": "idle"}` / `recording` / `processing` |

所有响应都是 JSON,`Content-Type: application/json`。转写在后台线程执行,`/stop` 立即返回 `processing`,不阻塞。

---

## 10. 日常使用

配好后,日常就是:

1. **开机** → VoiceTranser 自动后台启动(launchd),你看不见它
2. **想语音输入** → 在任何输入框里**按住右 Option 键**(或你设的键),说话,**松开**
3. 文字自动出现在光标位置,带正确的中文标点

适用于:Claude Code 终端、微信、备忘录、邮件、浏览器、任何能打字的地方。

---

## 11. 故障排查

跑 `tests/diagnose.py` 一键体检 8 项(Python 依赖 / 进程 / HTTP / 音频设备 / 模型 / 剪贴板 / 外部工具 / 日志):

```bash
uv run python tests/diagnose.py          # 全量检查
uv run python tests/diagnose.py --fix    # 检查 + 自动重启修复
```

### 常见问题

**转写成功但不自动粘贴** → **辅助功能权限没授**。系统设置 → 隐私与安全性 → 辅助功能,把终端/python 打开。launchd 启动的实例要单独授一次(列表里会出现 `python`/`Python` 条目)。

**没反应 / curl 报连接拒绝** → 服务没起来。`tail -f ~/Library/Logs/VoiceTranser.log` 看报错。常见:端口被占(改 `SERVER_PORT`)、模型没下(跑 `download_model.py`)。

**麦克风没声音 / 录到空白** → 麦克风权限没授。系统设置 → 隐私与安全性 → 麦克风。

**开机自启不生效 / launchd 反复崩** → 99% 是 plist 里的**路径写错了**。检查 `<YOUR_PROJECT_PATH>` 和 `.venv/bin/python3` 是否真实存在:`ls <YOUR_PROJECT_PATH>/.venv/bin/python3`。

**音频报错 `-9986` / PortAudio 异常** → macOS 休眠后音频子系统状态损坏、蓝牙耳机切换、虚拟音频驱动冲突。`launchctl kickstart -k gui/$(id -u)/com.voicetranser` 重启进程。

**内存占用高(mlx-whisper 引擎)** → mlx-whisper large-v3 常驻 ~3GB 属正常(SenseVoice 只占 400MB)。代码里已设 `mx.set_cache_limit(1GB)` 防止 Metal 缓存无限增长。中文场景换 SenseVoice 即可。

---

## 12. 卸载

```bash
launchctl unload ~/Library/LaunchAgents/com.voicetranser.plist
rm ~/Library/LaunchAgents/com.voicetranser.plist
rm -rf ~/VoiceTranser                       # 项目目录
rm ~/Library/Logs/VoiceTranser.log
```

到系统设置里手动移除辅助功能 / 麦克风权限里的相关条目即可。

---

## 13. 技术栈

| 组件 | 技术 |
|------|------|
| STT | [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) + SenseVoice(默认)/ [mlx-whisper](https://github.com/ml-explore/mlx-whisper)(fallback) |
| 音频录制 | [sounddevice](https://python-sounddevice.readthedocs.io/) + numpy |
| HTTP 服务器 | Python 标准库 `http.server`(`ThreadingHTTPServer`) |
| 剪贴板 | [pyperclip](https://github.com/asweigart/pyperclip) |
| 配置 | [python-dotenv](https://github.com/theskumar/python-dotenv) |
| 系统集成 | `osascript`(通知 / 菜单点击粘贴)、`afplay`(音效) |
| 包管理 | [uv](https://docs.astral.sh/uv/) + `pyproject.toml` |
| Python | 3.11+ |

## License

MIT
