#!/bin/bash
set -euo pipefail

# =============================================================================
# OpenClaw RLM Skill — Installation Script (v4 - Kimi API)
# =============================================================================

echo "========================================"
echo " OpenClaw RLM Skill - Installation"
echo "========================================"
echo ""

# 1. Check prerequisites
echo "[1/5] Checking prerequisites..."

if ! command -v openclaw &>/dev/null; then
    echo "ERROR: OpenClaw not found. Install it first."
    exit 1
fi
echo "  - OpenClaw: OK"

if ! command -v node &>/dev/null; then
    echo "ERROR: Node.js not found."
    exit 1
fi
echo "  - Node.js: OK"

# 2. Install Python if not present
echo ""
echo "[2/5] Checking Python..."

if ! command -v python3 &>/dev/null; then
    echo "  Installing Python 3..."
    sudo apt update && sudo apt install -y python3 python3-pip python3-venv
fi

PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "  - Python: $PYTHON_VERSION"

# 3. Install uv if not present
echo ""
echo "[3/5] Checking uv (Python package manager)..."

if ! command -v uv &>/dev/null; then
    echo "  Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "  - uv: OK"

# 4. Create venv and install rlms
echo ""
echo "[4/5] Installing Python dependencies (rlms)..."

cd "$(dirname "$0")"
uv venv --python 3.12 2>/dev/null || uv venv
uv pip install "rlms>=0.1.0,<0.2.0"
echo "  - rlms: OK"

# 5. Deploy skill to OpenClaw
echo ""
echo "[5/5] Deploying skill to OpenClaw..."

SKILL_DIR="$HOME/.openclaw/workspace/skills/rlm-engine"
mkdir -p "$SKILL_DIR"
mkdir -p "$SKILL_DIR/src"
cp skill/SKILL.md "$SKILL_DIR/"
cp src/rlm_bridge.py "$SKILL_DIR/src/rlm_bridge.py"
echo "  - Skill deployed to $SKILL_DIR"

# Summary
echo ""
echo "========================================"
echo " Installation complete"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "  1. Get your Moonshot API key at:"
echo "     https://platform.moonshot.ai/"
echo ""
echo "  2. Set the environment variable:"
echo "     export MOONSHOT_API_KEY=\"sk-your-key-here\""
echo ""
echo "     Or add to your ~/.bashrc:"
echo "     echo 'export MOONSHOT_API_KEY=\"sk-...\"' >> ~/.bashrc"
echo ""
echo "  3. Restart OpenClaw:"
echo "     openclaw gateway restart"
echo ""
echo "  4. Test from Telegram:"
echo "     '/rlm What have we talked about this week?'"
echo ""
echo "To run tests:"
echo "  cd $(pwd) && uv run pytest tests/ -v"
echo ""
