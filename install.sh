#!/usr/bin/env bash
set -euo pipefail

# VoiceTranser — 一键安装脚本
# 用法: curl -fsSL https://raw.githubusercontent.com/Lumos-789/VoiceTranser/main/install.sh | bash

REPO_URL="https://github.com/Lumos-789/VoiceTranser.git"
DIR_NAME="VoiceTranser"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[VoiceTranser]${NC} $*"; }
ok()    { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }

# ── 1. 平台检测 ──
info "检测运行环境..."
if [[ "$(uname)" != "Darwin" ]]; then
    warn "VoiceTranser 目前仅支持 macOS。"
    exit 1
fi
ok "macOS 环境"

# ── 2. 安装 uv ──
if command -v uv &>/dev/null; then
    ok "uv 已安装 ($(uv --version))"
else
    info "安装 uv 包管理器..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    ok "uv 安装完成 ($(uv --version))"
fi

# ── 3. 克隆仓库 ──
if [[ -d "$DIR_NAME" ]]; then
    ok "目录 $DIR_NAME 已存在，跳过克隆"
else
    info "克隆仓库..."
    git clone "$REPO_URL" "$DIR_NAME"
    ok "仓库克隆完成"
fi
cd "$DIR_NAME"

# ── 4. 安装依赖 ──
info "安装 Python 依赖..."
uv sync
ok "依赖安装完成"

# ── 5. 配置 .env ──
if [[ -f ".env" ]]; then
    ok ".env 已存在，跳过"
else
    cp .env.example .env
    ok "已创建 .env 配置文件"
fi

# ── 6. 打印后续步骤 ──
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}  安装完成！接下来需要 3 步：${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${YELLOW}1. 填写 API Key${NC}"
echo "   编辑 .env 文件，将 MINIMAX_API_KEY 改为你的 key："
echo "   $ cd $DIR_NAME && nano .env"
echo ""
echo -e "${YELLOW}2. 授予辅助功能权限${NC}"
echo "   系统设置 → 隐私与安全性 → 辅助功能 → 勾选你的终端应用"
echo ""
echo -e "${YELLOW}3. 启动${NC}"
echo "   $ uv run python -m voicetranser"
echo ""
echo -e "首次运行会自动下载 Whisper 模型（~488MB），请耐心等待。"
echo -e "按住 ${CYAN}右 Cmd 键${NC} 说话，松开即自动转写、精炼、粘贴。"
echo ""
