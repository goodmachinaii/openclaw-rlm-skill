#!/bin/bash
set -euo pipefail

# =============================================================================
# Compile and install CLIProxyAPI from source
# For ARM64 (Raspberry Pi 4) - NO precompiled binaries available
# =============================================================================

echo "CLIProxyAPI - Compilation from source"
echo "======================================"

# Check Go
if ! command -v go &>/dev/null; then
    echo "Go not found. Installing..."
    sudo apt update && sudo apt install -y golang
fi

GO_VERSION=$(go version | cut -d' ' -f3)
echo "Go version: $GO_VERSION"

# Create temporary directory
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

# Clone repository
echo ""
echo "Cloning CLIProxyAPI..."
git clone --depth 1 https://github.com/router-for-me/CLIProxyAPI.git "$TMPDIR/cliproxyapi"

# Compile
echo ""
echo "Compiling for $(uname -m)..."
cd "$TMPDIR/cliproxyapi"
mkdir -p "$HOME/.local/bin"
go build -o "$HOME/.local/bin/cli-proxy-api" ./cmd/server

# Verify
if [ -f "$HOME/.local/bin/cli-proxy-api" ]; then
    echo ""
    echo "Compilation successful!"
    echo "Binary: $HOME/.local/bin/cli-proxy-api"
    echo ""
    echo "To start:"
    echo "  cli-proxy-api --config ~/.cli-proxy-api/config.yaml"
    echo ""
    echo "To install as systemd service:"
    echo "  cp config/cliproxyapi.service ~/.config/systemd/user/"
    echo "  systemctl --user daemon-reload"
    echo "  systemctl --user enable --now cliproxyapi"
else
    echo "ERROR: Compilation failed"
    exit 1
fi
