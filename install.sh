#!/bin/bash
set -euo pipefail

# =============================================================================
# OpenClaw RLM Skill — Script de Instalación
# =============================================================================

echo "========================================"
echo " OpenClaw RLM Skill - Instalación"
echo "========================================"
echo ""

# 1. Verificar arquitectura
ARCH=$(uname -m)
if [ "$ARCH" != "aarch64" ]; then
    echo "Este script está diseñado para ARM64 (aarch64). Detectado: $ARCH"
    echo "   Puede funcionar en otras arquitecturas pero no está testeado."
    echo ""
fi

# 2. Verificar prerequisites
echo "[1/7] Verificando prerequisites..."

if ! command -v openclaw &>/dev/null; then
    echo "ERROR: OpenClaw no encontrado. Instálalo primero."
    exit 1
fi
echo "  - OpenClaw: OK"

if ! command -v node &>/dev/null; then
    echo "ERROR: Node.js no encontrado."
    exit 1
fi
echo "  - Node.js: OK"

if ! command -v docker &>/dev/null; then
    echo "  - Docker: No encontrado (opcional, CLIProxyAPI correrá como binario)"
else
    echo "  - Docker: OK"
fi

# 3. Instalar Python si no existe
echo ""
echo "[2/7] Verificando Python..."

if ! command -v python3 &>/dev/null; then
    echo "  Instalando Python 3..."
    sudo apt update && sudo apt install -y python3 python3-pip python3-venv
fi

PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "  - Python: $PYTHON_VERSION"

# 4. Instalar uv si no existe
echo ""
echo "[3/7] Verificando uv (gestor de paquetes Python)..."

if ! command -v uv &>/dev/null; then
    echo "  Instalando uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "  - uv: OK"

# 5. Crear venv e instalar RLM
echo ""
echo "[4/7] Instalando dependencias Python (RLM)..."

cd "$(dirname "$0")"
uv venv --python 3.12 2>/dev/null || uv venv
uv pip install rlm
echo "  - RLM: OK"

# 6. Compilar CLIProxyAPI desde source si no existe
echo ""
echo "[5/7] Verificando CLIProxyAPI..."

if ! command -v cli-proxy-api &>/dev/null && [ ! -f "$HOME/.local/bin/cli-proxy-api" ]; then
    echo "  CLIProxyAPI no encontrado. Compilando desde source para ARM64..."

    # Verificar/instalar Go
    if ! command -v go &>/dev/null; then
        echo "  Instalando Go..."
        sudo apt install -y golang 2>/dev/null || {
            echo "ERROR: No se pudo instalar Go."
            echo "  Ver docs/TROUBLESHOOTING.md para alternativas."
            exit 1
        }
    fi

    # Compilar
    TMPDIR=$(mktemp -d)
    echo "  Clonando repositorio..."
    git clone --depth 1 https://github.com/router-for-me/CLIProxyAPI.git "$TMPDIR/cliproxyapi"
    cd "$TMPDIR/cliproxyapi"
    echo "  Compilando..."
    mkdir -p "$HOME/.local/bin"
    go build -o "$HOME/.local/bin/cli-proxy-api" ./cmd/server
    cd - > /dev/null
    rm -rf "$TMPDIR"
    echo "  - CLIProxyAPI: Compilado en $HOME/.local/bin/cli-proxy-api"
else
    echo "  - CLIProxyAPI: OK"
fi

# Asegurar que ~/.local/bin está en PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    export PATH="$HOME/.local/bin:$PATH"
    echo '  Nota: Añade export PATH="$HOME/.local/bin:$PATH" a tu ~/.bashrc'
fi

# 7. Deploy skill a OpenClaw
echo ""
echo "[6/7] Desplegando skill a OpenClaw..."

SKILL_DIR="$HOME/.openclaw/workspace/skills/rlm-engine"
mkdir -p "$SKILL_DIR"
cp skill/SKILL.md "$SKILL_DIR/"
cp src/rlm_bridge.py "$SKILL_DIR/"
echo "  - Skill desplegado en $SKILL_DIR"

# 8. Config CLIProxyAPI
echo ""
echo "[7/7] Configurando CLIProxyAPI..."

mkdir -p "$HOME/.cli-proxy-api"
if [ ! -f "$HOME/.cli-proxy-api/config.yaml" ]; then
    cp config/cliproxyapi-example.yaml "$HOME/.cli-proxy-api/config.yaml"
    echo "  - Config ejemplo copiada a ~/.cli-proxy-api/config.yaml"
    echo "  - IMPORTANTE: Debes hacer OAuth login en http://localhost:8317/management.html"
else
    echo "  - Config existente preservada"
fi

# Test rápido (opcional)
echo ""
echo "========================================"
echo " Instalación completada"
echo "========================================"
echo ""
echo "Próximos pasos:"
echo ""
echo "  1. Iniciar CLIProxyAPI:"
echo "     cli-proxy-api --config ~/.cli-proxy-api/config.yaml"
echo ""
echo "  2. Hacer OAuth login (en navegador):"
echo "     http://localhost:8317/management.html"
echo ""
echo "  3. Reiniciar OpenClaw:"
echo "     openclaw gateway restart"
echo ""
echo "  4. Probar desde Telegram:"
echo "     '¿De qué hemos hablado esta semana?'"
echo ""
echo "Para ejecutar tests:"
echo "  cd $(pwd) && uv run pytest tests/ -v"
echo ""
