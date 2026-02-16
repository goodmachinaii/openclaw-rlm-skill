#!/bin/bash
set -euo pipefail

# =============================================================================
# Desplegar skill a OpenClaw workspace
# =============================================================================

echo "Desplegando RLM skill a OpenClaw..."

# Directorio del proyecto
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Directorio destino en OpenClaw
SKILL_DIR="$HOME/.openclaw/workspace/skills/rlm-engine"

# Crear directorio si no existe
mkdir -p "$SKILL_DIR"

# Copiar archivos del skill
cp "$SCRIPT_DIR/skill/SKILL.md" "$SKILL_DIR/"
cp "$SCRIPT_DIR/src/rlm_bridge.py" "$SKILL_DIR/"

echo "Skill desplegado en: $SKILL_DIR"
echo ""
echo "Archivos copiados:"
ls -la "$SKILL_DIR"

echo ""
echo "Para activar el skill, reinicia OpenClaw:"
echo "  openclaw gateway restart"
