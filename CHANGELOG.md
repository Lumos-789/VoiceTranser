# Changelog

## 1.0.2 — 2026-11-05

### 修复

- **诊断脚本不再挂死、不再等麦克风授权框** (`tests/diagnose.py`)
  - 音频检查改为「授权预检 + 子进程硬超时」：先只读查询 TCC 麦克风授权状态
    (AVFoundation `authorizationStatusForMediaType:`，不触发授权框)；未授权时
    绝不打开 `InputStream`，而是报 `audio device unavailable` /
    `microphone permission not granted` 并给出授权与跳过提示。
  - 已授权时才在独立子进程里开流，硬超时 3s；超时强杀子进程并报 finding。
  - 新增 `--skip-audio` 逃生口：麦克风不可碰时跳过音频项，其余检查照常执行。
  - 汇总改为三态（通过 / 失败 / 跳过）：跳过项计入「跳过(未验证)」，退出码非 0，
    不再把未执行的检查冒充成全绿。
- **诊断端口按实际运行的实例解析** (`tests/diagnose.py`)
  - 删除写死的 `9877`，改为按实际运行实例解析：`--port` > `SERVER_PORT`
    环境变量 > 已安装 launchd plist 的 `SERVER_PORT` > 项目 `.env` > 默认端口。
  - plist 端口与默认值不一致时打印 WARNING 并列出两个数字（这正是健康服务
    被诊断成“死了”的原因）。
- **端口单一事实源统一为 9877**
  - `config.DEFAULT_SERVER_PORT` 为唯一常量（9876 → 9877），`Config`、
    `server.py`、`install_launchd.py`、`diagnose.py` 全部派生，launchd 模块
    删除重复的 `DEFAULT_PORT`。
  - 未设置 `SERVER_PORT` 的安装从 9876 移到 9877，与 launchd 一直写入的值一致；
    已有 launchd plist 因显式 pin 了 `SERVER_PORT`，继续按原端口运行。
  - `load_config` 延迟导入 `dotenv`，缺依赖时仍能解析默认端口。

### 测试与文档

- 新增 `tests/test_diagnose.py`（18 项）：端口解析（launchd plist / 优先级 /
  不一致告警）、未授权不碰设备、跳过语义、子进程超时强杀、汇总不把跳过当通过；
  新增 `tests/test_metadata.py`（3 项）；`tests/test_launchd.py` 增加默认端口
  必须来自 `config.DEFAULT_SERVER_PORT` 的断言。
- 文档测试命令改为可复现的 `.venv/bin/python -m unittest discover -s tests -v`；
  `README.md` / `PACKAGE.md` / skill 补充端口解析顺序与 `--skip-audio` 用法。
- 版本号统一：`pyproject.toml` 0.1.0、`voicetranser/__init__.py` 0.1.0、
  `package.json` 1.0.1 → 全部 1.0.2（`uv.lock` 同步）。

### 精简

- **删除 `com.voicetranser-sense.plist`**：作者本机路径快照，无任何代码引用
  （`install_launchd.py` 按当前 checkout 生成），照抄会给用户装出指向别人目录的服务。
- **删除 `voicetranser/hotkey.py`**：pynput push-to-talk 时代的死模块，全仓零引用、
  `pynput` 早已不在依赖里，两份文档各写一行「已废弃别用」。
- **`PACKAGE.md`（466 行）拆解**：其中的用户手册部分（安装 5 步、跑起来、热键三方案、
  开机自启、HTTP 速查、技术栈）与 `README.md` / skill 逐段重复，删掉；只保留唯一
  独有的架构图、状态机与模块职责表，移到 `docs/architecture.md`。README 补上原先只在
  PACKAGE 里有的「故障排查」与「卸载」，并明确单元测试命令。
- **`AGENTS.md` 收窄到项目事实**：本机实例状态、老实例收尾迁移到本地 `.agents/`
  （已加进 `.gitignore`）；架构图补上默认引擎 qwen3-mlx（原先只写 sense/whisper）。
- `.env.example` 的 `SERVER_PORT` 示例从 9876 改为 9877（与端口单一事实源一致）；
  移除误提交的 `.DS_Store`。
