#!/bin/bash
set -euo pipefail

# =============================================================================
# Deploy skill to OpenClaw workspace
# =============================================================================

echo "Deploying RLM skill to OpenClaw..."

# Project directory
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Destination directory in OpenClaw
SKILL_DIR="$HOME/.openclaw/workspace/skills/rlm-engine"

# Create directory if it doesn't exist
mkdir -p "$SKILL_DIR"

# Copy skill files
cp "$SCRIPT_DIR/skill/SKILL.md" "$SKILL_DIR/"
cp "$SCRIPT_DIR/src/rlm_bridge.py" "$SKILL_DIR/"

echo "Skill deployed to: $SKILL_DIR"
echo ""
echo "Files copied:"
ls -la "$SKILL_DIR"

echo ""
echo "To activate the skill, restart OpenClaw:"
echo "  openclaw gateway restart"
