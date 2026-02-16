#!/bin/bash
set -euo pipefail

# =============================================================================
# Compilar e instalar CLIProxyAPI desde source
# Para ARM64 (Raspberry Pi 4) - NO hay binarios precompilados
# =============================================================================

echo "CLIProxyAPI - Compilación desde source"
echo "======================================="

# Verificar Go
if ! command -v go &>/dev/null; then
    echo "Go no encontrado. Instalando..."
    sudo apt update && sudo apt install -y golang
fi

GO_VERSION=$(go version | cut -d' ' -f3)
echo "Go version: $GO_VERSION"

# Crear directorio temporal
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

# Clonar repositorio
echo ""
echo "Clonando CLIProxyAPI..."
git clone --depth 1 https://github.com/router-for-me/CLIProxyAPI.git "$TMPDIR/cliproxyapi"

# Compilar
echo ""
echo "Compilando para $(uname -m)..."
cd "$TMPDIR/cliproxyapi"
mkdir -p "$HOME/.local/bin"
go build -o "$HOME/.local/bin/cli-proxy-api" ./cmd/server

# Verificar
if [ -f "$HOME/.local/bin/cli-proxy-api" ]; then
    echo ""
    echo "Compilación exitosa!"
    echo "Binario: $HOME/.local/bin/cli-proxy-api"
    echo ""
    echo "Para iniciar:"
    echo "  cli-proxy-api --config ~/.cli-proxy-api/config.yaml"
    echo ""
    echo "Para instalar como servicio systemd:"
    echo "  cp config/cliproxyapi.service ~/.config/systemd/user/"
    echo "  systemctl --user daemon-reload"
    echo "  systemctl --user enable --now cliproxyapi"
else
    echo "ERROR: Compilación falló"
    exit 1
fi
