#!/bin/bash
set -euo pipefail

# =============================================================================
# Install Python + uv + RLM
# =============================================================================

echo "RLM - Python dependencies installation"
echo "======================================="

# Check/install Python
if ! command -v python3 &>/dev/null; then
    echo "Python not found. Installing..."
    sudo apt update && sudo apt install -y python3 python3-pip python3-venv
fi

PYTHON_VERSION=$(python3 --version)
echo "Python: $PYTHON_VERSION"

# Check/install uv
if ! command -v uv &>/dev/null; then
    echo ""
    echo "Installing uv (modern package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

UV_VERSION=$(uv --version 2>/dev/null || echo "just installed")
echo "uv: $UV_VERSION"

# Go to project directory
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "Project directory: $SCRIPT_DIR"

# Create venv and install rlms
echo ""
echo "Creating virtual environment..."
uv venv --python 3.12 2>/dev/null || uv venv

echo ""
echo "Installing rlms..."
uv pip install "rlms>=0.1.0,<0.2.0"

echo ""
echo "Installation complete!"
echo ""
echo "To verify:"
echo "  cd $SCRIPT_DIR"
echo "  uv run python -c 'from rlm import RLM; print(\"rlms OK\")'"
