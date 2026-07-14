# VoiceTranser · Mac 安装使用方案（保姆级）

> 按住一个键说话，松开自动转写成文字粘到光标。**全程本地、断网可用、中文秒出、隐私不出设备。**
> 专为 AI 编程（Claude Code / Cursor）和日常打字设计。

---

## 它解决什么问题

| 痛点 | VoiceTranser 的解法 |
|------|---------------------|
| 打字慢 / 手累了 | 按住键说话，松开就是文字 |
| 云端语音输入要联网、隐私没保障 | **本地推理**，麦克风音频不出机器 |
| 系统自带听写中文标点乱、停顿就断 | SenseVoice 引擎中文标点地道，15 秒音频 0.46 秒出结果 |
| 转写完还要手动复制粘贴 | 自动粘贴到**任何**应用的光标位置 |

---

## 前置要求

- **macOS**（仅支持 Mac，Apple Silicon 最佳，Intel 也能跑）
- **macOS 13+**（Ventura 及以上，系统设置路径以此为准）
- **Python 3.11+**（没有？下面第 1 步一起装）
- **uv**（超快的 Python 包管理器）
- 约 **500MB 磁盘**（模型 228MB + 依赖 ~200MB）

---

## 第 1 步：装 uv（Python 包管理器）

打开**终端**（Terminal.app / iTerm / Warp 都行），粘贴回车：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

装完**重开一个终端窗口**（让 PATH 生效），验证：

```bash
uv --version
# 输出类似 uv 0.x.x 就对了
```

> 如果你机器上已经有 Python 3.11+，uv 会直接用它；没有的话 uv 会自动帮你装一个，不用操心。

---

## 第 2 步：拉项目 + 装依赖

```bash
git clone https://github.com/Lumos-789/VoiceTranser.git
cd VoiceTranser
uv sync          # 自动建虚拟环境、装全部依赖
```

`uv sync` 会创建 `.venv/` 并装好 `sounddevice`、`sherpa-onnx`、`mlx-whisper` 等所有依赖。第一次约 2~3 分钟。

---

## 第 3 步：下载语音模型（228MB，一次性）

默认用 **SenseVoice**（中文场景最佳，模型小、速度快）：

```bash
uv run python download_model.py
```

走 HuggingFace 国内镜像（hf-mirror.com），国内带宽约 1~3 分钟。下载到 `models/sense-voice/`，**幂等**——已存在会跳过。

> 海外用户如果镜像慢，可以改走官方源：
> ```bash
> HF_ENDPOINT=https://huggingface.co uv run python download_model.py
> ```

---

## 第 4 步：配置（可选，默认就能跑）

项目自带 `.env.example`，默认配置已经是最佳实践。想改才需要操作：

```bash
cp .env.example .env
```

可调项（都有默认值，不动也行）：

| 变量 | 默认 | 说明 |
|------|------|------|
| `STT_ENGINE` | `sensevoice` | `sensevoice`（中文秒出）/ `mlx-whisper`（英文/小语种更强） |
| `SERVER_PORT` | `9876` | HTTP 服务端口，改了要同步改热键配置 |
| `LANGUAGE` | `zh` | 识别语言 |
| `SOUND_ENABLED` | `true` | 反馈音效开关，嫌吵设 `false` |
| `START_SOUND` / `DONE_SOUND` | `Blow` / `Glass` | 系统 Sound 名，可换 `Tink`/`Pop`/`Frog` 等 |

---

## 第 5 步：授权（关键！不授权没法用）

VoiceTranser 需要两个权限：**麦克风**（录音）和**辅助功能**（自动粘贴）。

### 5.1 麦克风权限

首次运行时系统会弹窗问你，点**允许**即可。

如果没弹或手滑点了拒绝，手动开：
**系统设置 → 隐私与安全性 → 麦克风** → 把你跑命令的终端（Terminal / iTerm / Warp）打开开关。

### 5.2 辅助功能权限（自动粘贴必需）

**系统设置 → 隐私与安全性 → 辅助功能** → 把你的终端应用拖进来 / 打开开关。

> 这个权限让 VoiceTranser 能模拟 `Cmd+V` 把转写结果粘到当前窗口。没这个权限 = 转写能成功但不会自动粘贴。

> ⚠️ 授权后**重启一次终端**再继续。

---

## 第 6 步：跑起来试试

```bash
uv run python -m voicetranser
```

看到类似输出就成功了：

```
[VoiceTranser] STT 引擎: sensevoice
[VoiceTranser] 服务器监听 http://127.0.0.1:9876
[VoiceTranser] 等待热键触发 /toggle 或 /start ...
```

**手动测试**（新开一个终端窗口）：

```bash
# 开始录音
curl http://localhost:9876/start

# 对着麦克风说几句话……

# 停止录音 → 自动转写 → 自动粘贴到你当前光标
curl http://localhost:9876/stop
```

转写结果会自动粘贴到你当前光标所在的输入框。按 `Ctrl+C` 停掉服务。

---

## 第 7 步：绑定热键（核心体验）

手敲 curl 太蠢了。真正的用法是**按住一个物理键说话，松开自动出字**。选一个方案：

### 方案 A：Karabiner-Elements（⭐ 推荐，体验最丝滑）

[Karabiner-Elements](https://karabiner-elements.pqrs.org/)（免费）是 macOS 键盘改造神器。VoiceTranser 用它实现「按住右 Option 录音、松开转写」。

1. 下载安装 Karabiner-Elements，打开后授予它需要的权限
2. 打开 **Karabiner-Elements Settings → Complex Modifications → Rules**
3. 把下面的规则导入（方法见下方）

**导入方法**：编辑 `~/.config/karabiner/assets/complex_modifications/voicetranser.json`，粘贴：

```json
{
  "title": "VoiceTranser: 右 Option 按住说话",
  "rules": [
    {
      "description": "右 Option 按下开始录音，松开停止并转写",
      "manipulators": [
        {
          "type": "basic",
          "from": { "key_code": "right_option" },
          "to": [
            {
              "shell_command": "curl -s http://localhost:9876/start >/dev/null 2>&1 &"
            }
          ],
          "to_after_key_up": [
            {
              "shell_command": "curl -s http://localhost:9876/stop >/dev/null 2>&1 &"
            }
          ]
        }
      ]
    }
  ]
}
```

保存后回到 Karabiner Settings → Complex Modifications → **Add rule**，启用「右 Option 按住说话」。

> 端口不是 9876？把 JSON 里的 `9876` 全换成你的 `SERVER_PORT`。
> 想换键？`right_option` 可改成 `right_command` / `fn` / `caps_lock` 等。

### 方案 B：Raycast（免费，不想装 Karabiner 的选这个）

[Raycast](https://www.raycast.com/) 是个启动器。用它做两个快捷命令：

1. 装 Raycast
2. **Commands → Create Script Command**，建两条：

**开始录音**（快捷键设为你想按住的键之一）：
```bash
#!/bin/bash
curl -s http://localhost:9876/start
```

**停止转写**：
```bash
#!/bin/bash
curl -s http://localhost:9876/stop
```

> Raycast 的局限：它不支持「按住/松开」两种事件，只能给两个命令各绑一个快捷键（比如 `Cmd+Shift+1` 开始、`Cmd+Shift+2` 停止）。体验不如 Karabiner 的按住式，但零额外学习成本。

### 方案 C：系统快捷键绑定（最简，macOS 自带）

用 macOS 自带的「快捷指令 (Shortcuts)」app：

1. 打开「快捷指令」→ 新建快捷指令
2. 动作选「运行 Shell 脚本」，内容填 `curl -s http://localhost:9876/toggle`
3. 右侧 ⚙️ → 添加键盘快捷键 → 按一个组合键（如 `F5`）

> 这种是 toggle 模式（按一下开始，再按一下停止），不是按住式。

---

## 第 8 步：开机自启（一劳永逸）

用 macOS 原生的 **launchd** 让 VoiceTranser 开机自动后台运行、崩溃自动重启。

### 8.1 生成 plist 配置

在项目目录下，把 `USERNAME` 换成你的用户名（终端输入 `whoami` 查看）：

```bash
# 查你的用户名
whoami
# 查项目绝对路径
pwd
```

创建 `~/Library/LaunchAgents/com.voicetranser.plist`，内容如下（**替换三处 `<...>`**）：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
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

> 三个要替换的占位符：
> - `<YOUR_PROJECT_PATH>`：项目绝对路径，如 `/Users/sarah/VoiceTranser`
> - `<YOUR_USERNAME>`：你的 Mac 用户名，如 `sarah`

### 8.2 加载并启动

```bash
# 加载（立即启动，因为 RunAtLoad=true）
launchctl load ~/Library/LaunchAgents/com.voicetranser.plist

# 验证在跑
curl http://localhost:9876/status
```

### 8.3 launchd 常用命令

```bash
launchctl load ~/Library/LaunchAgents/com.voicetranser.plist      # 启用
launchctl unload ~/Library/LaunchAgents/com.voicetranser.plist    # 停用
launchctl kickstart -k gui/$(id -u)/com.voicetranser               # 重启服务
tail -f ~/Library/Logs/VoiceTranser.log                            # 看日志
```

> ⚠️ launchd 启动的进程需要重新授权一次**辅助功能权限**——在「辅助功能」列表里会出现一个 `python` 或 `Python` 条目，把它打开。这一步不做的话，launchd 启动的实例无法自动粘贴。

---

## 日常使用

配好后，日常就是：

1. **开机** → VoiceTranser 自动后台启动（launchd），你看不见它
2. **想语音输入** → 在任何输入框里**按住右 Option 键**，说话，**松开**
3. 文字自动出现在光标位置，带正确的中文标点

适用于：Claude Code 终端、微信、备忘录、邮件、浏览器、任何能打字的地方。

---

## 双引擎说明

| 引擎 | 适合 | 模型大小 | 常驻内存 | 15 秒中文 | 切换方式 |
|------|------|----------|----------|-----------|----------|
| **SenseVoice**（默认） | 中文为主、中英日韩粤 | 228MB | ~400MB | **0.46 秒** | `STT_ENGINE=sensevoice` |
| **mlx-whisper large-v3** | 英文/小语种、长音频 | 3GB | ~3GB | 1.08 秒 | `STT_ENGINE=mlx-whisper` |

默认 SenseVoice 就对了。英文为主想切 mlx-whisper，改 `.env` 或环境变量。

---

## 故障排查

### 转写成功但不自动粘贴
→ **辅助功能权限没授**。系统设置 → 隐私与安全性 → 辅助功能，把终端/python 打开。launchd 启动的实例要单独授一次。

### 没反应 / curl 报连接拒绝
→ 服务没起来。`tail -f ~/Library/Logs/VoiceTranser.log` 看报错。常见：端口被占（改 `SERVER_PORT`）、模型没下（跑 `download_model.py`）。

### 麦克风没声音 / 录到空白
→ 麦克风权限没授。系统设置 → 隐私与安全性 → 麦克风。

### 开机自启不生效
→ 99% 是 plist 里的**路径写错了**。检查 `<YOUR_PROJECT_PATH>` 和 `.venv/bin/python3` 是否真实存在：`ls <YOUR_PROJECT_PATH>/.venv/bin/python3`。

### 内存占用高（mlx-whisper 引擎）
→ mlx-whisper large-v3 常驻 ~3GB 属正常（SenseVoice 只占 400MB）。代码里已设 `mx.set_cache_limit(1GB)` 防止 Metal 缓存无限增长。

---

## HTTP 端点速查

| 端点 | 作用 |
|------|------|
| `GET /toggle` | 切换录音状态（闲→录 / 录→停转写） |
| `GET /start` | 开始录音 |
| `GET /stop` | 停止录音，触发转写 + 粘贴 |
| `GET /status` | 查当前状态（idle / recording / processing） |

---

## 卸载

```bash
launchctl unload ~/Library/LaunchAgents/com.voicetranser.plist
rm ~/Library/LaunchAgents/com.voicetranser.plist
rm -rf ~/VoiceTranser          # 项目目录
rm ~/Library/Logs/VoiceTranser.log
```
到系统设置里手动移除辅助功能 / 麦克风权限里的条目即可。
