#!/bin/bash
set -euo pipefail

# =============================================================================
# OpenClaw RLM Skill — Installation Script
# =============================================================================

echo "========================================"
echo " OpenClaw RLM Skill - Installation"
echo "========================================"
echo ""

# 1. Check architecture
ARCH=$(uname -m)
if [ "$ARCH" != "aarch64" ]; then
    echo "This script is designed for ARM64 (aarch64). Detected: $ARCH"
    echo "   May work on other architectures but not tested."
    echo ""
fi

# 2. Check prerequisites
echo "[1/7] Checking prerequisites..."

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

if ! command -v docker &>/dev/null; then
    echo "  - Docker: Not found (optional, CLIProxyAPI will run as binary)"
else
    echo "  - Docker: OK"
fi

# 3. Install Python if not present
echo ""
echo "[2/7] Checking Python..."

if ! command -v python3 &>/dev/null; then
    echo "  Installing Python 3..."
    sudo apt update && sudo apt install -y python3 python3-pip python3-venv
fi

PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "  - Python: $PYTHON_VERSION"

# 4. Install uv if not present
echo ""
echo "[3/7] Checking uv (Python package manager)..."

if ! command -v uv &>/dev/null; then
    echo "  Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "  - uv: OK"

# 5. Create venv and install RLM
echo ""
echo "[4/7] Installing Python dependencies (RLM)..."

cd "$(dirname "$0")"
uv venv --python 3.12 2>/dev/null || uv venv
uv pip install rlm
echo "  - RLM: OK"

# 6. Compile CLIProxyAPI from source if not present
echo ""
echo "[5/7] Checking CLIProxyAPI..."

if ! command -v cli-proxy-api &>/dev/null && [ ! -f "$HOME/.local/bin/cli-proxy-api" ]; then
    echo "  CLIProxyAPI not found. Compiling from source for ARM64..."

    # Check/install Go
    if ! command -v go &>/dev/null; then
        echo "  Installing Go..."
        sudo apt install -y golang 2>/dev/null || {
            echo "ERROR: Could not install Go."
            echo "  See docs/TROUBLESHOOTING.md for alternatives."
            exit 1
        }
    fi

    # Compile
    TMPDIR=$(mktemp -d)
    echo "  Cloning repository..."
    git clone --depth 1 https://github.com/router-for-me/CLIProxyAPI.git "$TMPDIR/cliproxyapi"
    cd "$TMPDIR/cliproxyapi"
    echo "  Compiling..."
    mkdir -p "$HOME/.local/bin"
    go build -o "$HOME/.local/bin/cli-proxy-api" ./cmd/server
    cd - > /dev/null
    rm -rf "$TMPDIR"
    echo "  - CLIProxyAPI: Compiled to $HOME/.local/bin/cli-proxy-api"
else
    echo "  - CLIProxyAPI: OK"
fi

# Ensure ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    export PATH="$HOME/.local/bin:$PATH"
    echo '  Note: Add export PATH="$HOME/.local/bin:$PATH" to your ~/.bashrc'
fi

# 7. Deploy skill to OpenClaw
echo ""
echo "[6/7] Deploying skill to OpenClaw..."

SKILL_DIR="$HOME/.openclaw/workspace/skills/rlm-engine"
mkdir -p "$SKILL_DIR"
cp skill/SKILL.md "$SKILL_DIR/"
cp src/rlm_bridge.py "$SKILL_DIR/"
echo "  - Skill deployed to $SKILL_DIR"

# 8. Configure CLIProxyAPI
echo ""
echo "[7/7] Configuring CLIProxyAPI..."

mkdir -p "$HOME/.cli-proxy-api"
if [ ! -f "$HOME/.cli-proxy-api/config.yaml" ]; then
    cp config/cliproxyapi-example.yaml "$HOME/.cli-proxy-api/config.yaml"
    echo "  - Example config copied to ~/.cli-proxy-api/config.yaml"
    echo "  - IMPORTANT: You must do OAuth login at http://localhost:8317/management.html"
else
    echo "  - Existing config preserved"
fi

# Summary
echo ""
echo "========================================"
echo " Installation complete"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "  1. Start CLIProxyAPI:"
echo "     cli-proxy-api --config ~/.cli-proxy-api/config.yaml"
echo ""
echo "  2. Do OAuth login (in browser):"
echo "     http://localhost:8317/management.html"
echo ""
echo "  3. Restart OpenClaw:"
echo "     openclaw gateway restart"
echo ""
echo "  4. Test from Telegram:"
echo "     'What have we talked about this week?'"
echo ""
echo "To run tests:"
echo "  cd $(pwd) && uv run pytest tests/ -v"
echo ""
