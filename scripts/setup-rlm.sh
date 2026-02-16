#!/bin/bash
set -euo pipefail

# =============================================================================
# Instalar Python + uv + RLM
# =============================================================================

echo "RLM - Instalación de dependencias Python"
echo "========================================="

# Verificar/instalar Python
if ! command -v python3 &>/dev/null; then
    echo "Python no encontrado. Instalando..."
    sudo apt update && sudo apt install -y python3 python3-pip python3-venv
fi

PYTHON_VERSION=$(python3 --version)
echo "Python: $PYTHON_VERSION"

# Verificar/instalar uv
if ! command -v uv &>/dev/null; then
    echo ""
    echo "Instalando uv (gestor de paquetes moderno)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

UV_VERSION=$(uv --version 2>/dev/null || echo "recién instalado")
echo "uv: $UV_VERSION"

# Ir al directorio del proyecto
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "Directorio del proyecto: $SCRIPT_DIR"

# Crear venv e instalar RLM
echo ""
echo "Creando entorno virtual..."
uv venv --python 3.12 2>/dev/null || uv venv

echo ""
echo "Instalando RLM..."
uv pip install rlm

echo ""
echo "Instalación completada!"
echo ""
echo "Para verificar:"
echo "  cd $SCRIPT_DIR"
echo "  uv run python -c 'from rlm import RLM; print(\"RLM OK\")'"
