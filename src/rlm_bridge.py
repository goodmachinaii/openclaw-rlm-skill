#!/usr/bin/env python3
"""
RLM Bridge para OpenClaw — v3
Conecta OpenClaw con RLM via CLIProxyAPI (OAuth ChatGPT).
Modelos: GPT-5.3-Codex (root) + GPT-5.1-Codex-Mini (sub-LMs) via CLIProxyAPI.

Uso:
  uv run python src/rlm_bridge.py --query "¿De qué hablamos ayer?"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


# === CONSTANTES ===
MAX_CHARS = 2_000_000       # ~500K tokens, seguro para 8GB RAM
MAX_SESSIONS_DEFAULT = 30
CLIPROXYAPI_URL = "http://127.0.0.1:8317/v1"  # Puerto default de CLIProxyAPI
CLIPROXYAPI_KEY = "sk-cliproxyapi-default-key-change-me"


def find_sessions_dir(openclaw_home: str = "~/.openclaw") -> str:
    """
    Auto-detecta dónde OpenClaw guarda las sesiones.

    Estructura real de OpenClaw:
      ~/.openclaw/agents/<agentId>/sessions/*.jsonl   ← transcripciones JSONL
      ~/.openclaw/agents/<agentId>/sessions/sessions.json  ← índice
      ~/.openclaw/agents/<agentId>/qmd/sessions/      ← exportaciones QMD (Markdown sanitizado)
      ~/.openclaw/workspace/memory/YYYY-MM-DD.md      ← daily notes
      ~/.openclaw/workspace/MEMORY.md                 ← memoria largo plazo
    """
    home = Path(openclaw_home).expanduser()
    # Buscar en directorios de agentes (la ubicación real)
    agents_dir = home / "agents"
    if agents_dir.exists():
        for agent_dir in sorted(agents_dir.iterdir()):
            sessions_dir = agent_dir / "sessions"
            if sessions_dir.exists():
                jsonl_files = list(sessions_dir.glob("*.jsonl"))
                if jsonl_files:
                    return str(sessions_dir)

    # Fallback legacy: algunos setups antiguos
    for candidate in [home / "sessions", home / "workspace" / "sessions"]:
        if candidate.exists() and any(candidate.iterdir()):
            return str(candidate)

    # Default: primer agente
    return str(home / "agents" / "main" / "sessions")


def parse_jsonl_session(filepath: Path) -> str:
    """
    Convierte un archivo de sesión JSONL de OpenClaw a texto legible.

    Formato JSONL de OpenClaw:
      Cada línea es JSON con: type, timestamp, message.role, message.content[]
      message.content[] contiene objetos con type="text" (legible) o type="toolCall" etc.
      Roles: "user", "assistant", "toolResult"

    Solo extrae texto legible (user + assistant), ignora toolResult y toolCall
    para mantener el contexto limpio y reducir tokens.
    """
    lines = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    entry = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                msg = entry.get("message", {})
                role = msg.get("role", "")
                # Solo user y assistant — toolResult es ruido para análisis
                if role not in ("user", "assistant"):
                    continue

                content_blocks = msg.get("content", [])
                if isinstance(content_blocks, str):
                    # Formato simplificado (string directo)
                    lines.append(f"[{role}]: {content_blocks}")
                    continue

                text_parts = []
                for block in content_blocks:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text:
                            text_parts.append(text)
                if text_parts:
                    lines.append(f"[{role}]: {' '.join(text_parts)}")

    except (PermissionError, OSError):
        return ""

    return "\n".join(lines)


def load_workspace(workspace_dir: str) -> str:
    """
    Carga archivos del workspace de OpenClaw.
    Incluye archivos de contexto Y daily memory notes.

    Estructura workspace:
      MEMORY.md      ← memoria largo plazo curada
      SOUL.md        ← personalidad y valores
      AGENTS.md      ← instrucciones operativas
      USER.md        ← preferencias del usuario
      IDENTITY.md    ← nombre, vibe, emoji
      TOOLS.md       ← notas sobre herramientas
      memory/YYYY-MM-DD.md  ← daily notes (contexto reciente)
    """
    workspace = Path(workspace_dir)
    parts = []

    # 1. Archivos de contexto principales
    for filename in ["MEMORY.md", "SOUL.md", "AGENTS.md", "USER.md",
                     "IDENTITY.md", "TOOLS.md"]:
        filepath = workspace / filename
        if filepath.exists():
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
                if content.strip() and len(content) < 50_000:
                    parts.append(f"=== {filename} ===\n{content}")
            except (PermissionError, OSError) as e:
                parts.append(f"=== {filename} === [Error: {e}]")

    # 2. Daily memory notes (memory/YYYY-MM-DD.md) — más recientes primero
    memory_dir = workspace / "memory"
    if memory_dir.exists():
        daily_files = sorted(
            memory_dir.glob("*.md"),
            key=lambda p: p.stem,  # YYYY-MM-DD ordena cronológicamente
            reverse=True,
        )
        daily_chars = 0
        for daily_file in daily_files[:30]:  # últimos 30 días máximo
            try:
                content = daily_file.read_text(encoding="utf-8", errors="ignore")
                if not content.strip() or len(content) < 20:
                    continue
                if daily_chars + len(content) > 200_000:  # cap para daily notes
                    break
                parts.append(f"=== DAILY:{daily_file.name} ===\n{content}")
                daily_chars += len(content)
            except (PermissionError, OSError):
                continue

    return "\n\n".join(parts)


def load_sessions(sessions_dir: str, max_sessions: int = MAX_SESSIONS_DEFAULT) -> str:
    """
    Carga sesiones de OpenClaw. Soporta ambos formatos:
      - *.jsonl (formato nativo de OpenClaw — append-only JSONL)
      - *.md (exportaciones QMD sanitizadas, o legacy transcript.md)

    Las sesiones JSONL son el formato principal desde 2025.
    Los .md pueden existir en ~/.openclaw/agents/<id>/qmd/sessions/ como
    exportaciones sanitizadas de QMD.
    """
    sessions = Path(sessions_dir)
    if not sessions.exists():
        return "[No hay sesiones disponibles]"

    # Recoger todos los archivos de sesión (JSONL primero, luego MD)
    session_files = []

    # 1. Archivos JSONL (formato nativo — principal fuente de datos)
    for p in sessions.glob("*.jsonl"):
        if p.name == "sessions.json":  # índice, no transcripción
            continue
        try:
            session_files.append((p.stat().st_mtime, p, "jsonl"))
        except OSError:
            continue

    # 2. Archivos MD en QMD exports (si existen)
    qmd_sessions = sessions.parent / "qmd" / "sessions"
    if qmd_sessions.exists():
        for p in qmd_sessions.rglob("*.md"):
            try:
                session_files.append((p.stat().st_mtime, p, "md"))
            except OSError:
                continue

    # 3. Fallback: transcript.md legacy
    if not session_files:
        for p in sessions.rglob("transcript.md"):
            try:
                session_files.append((p.stat().st_mtime, p, "md"))
            except OSError:
                continue

    session_files.sort(key=lambda x: x[0], reverse=True)
    session_files = session_files[:max_sessions]

    parts = []
    total_chars = 0

    for mtime, filepath, fmt in session_files:
        if total_chars >= MAX_CHARS:
            break
        try:
            if fmt == "jsonl":
                content = parse_jsonl_session(filepath)
            else:
                content = filepath.read_text(encoding="utf-8", errors="ignore")

            if len(content.strip()) < 50:
                continue
            if total_chars + len(content) > MAX_CHARS:
                remaining = MAX_CHARS - total_chars
                if remaining > 1000:
                    content = content[:remaining] + "\n[...truncado por límite de memoria]"
                else:
                    break
            session_name = filepath.stem  # nombre sin extensión
            date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            parts.append(f"=== SESSION:{session_name} DATE:{date_str} FMT:{fmt} ===\n{content}")
            total_chars += len(content)
        except (PermissionError, UnicodeDecodeError, OSError):
            continue

    return "\n\n".join(parts) if parts else "[Sin sesiones cargadas]"


def run_rlm(
    query: str,
    context: str,
    root_model: str,
    sub_model: str,
    base_url: str,
    api_key: str,
    verbose: bool = False,
    log_dir: str | None = None,
) -> dict:
    """
    Ejecuta RLM con modelo principal (root) y modelo económico (sub-LMs).
    Maneja rate limits (429) con mensaje amigable.
    """
    from rlm import RLM

    rlm_kwargs = dict(
        backend="openai",
        backend_kwargs={
            "model_name": root_model,
            "base_url": base_url,
            "api_key": api_key,
        },
        environment="local",
        max_iterations=20,
        max_depth=1,  # Único valor funcional actualmente (RLM docs: "This is a TODO")
        verbose=verbose,
    )

    # Sub-LMs con modelo más barato (4x más eficiente en cuota)
    if sub_model and sub_model != root_model:
        rlm_kwargs["other_backends"] = ["openai"]
        rlm_kwargs["other_backend_kwargs"] = [{
            "model_name": sub_model,
            "base_url": base_url,
            "api_key": api_key,
        }]

    # Logging opcional
    if log_dir:
        from rlm.logger import RLMLogger
        rlm_kwargs["logger"] = RLMLogger(log_dir=log_dir)

    rlm = RLM(**rlm_kwargs)

    try:
        result = rlm.completion(query, context=context)
        return {
            "response": result.response,
            "model_used": root_model,
            "sub_model_used": sub_model,
            "status": "ok",
        }
    except Exception as e:
        error_str = str(e).lower()
        if "429" in error_str or "rate limit" in error_str or "quota" in error_str:
            return {
                "response": "Tu cuota de ChatGPT está alcanzada. "
                            "Intenta de nuevo en unos minutos.",
                "status": "rate_limited",
            }
        raise  # re-raise para que main() intente el fallback


def main():
    parser = argparse.ArgumentParser(description="RLM Bridge para OpenClaw v3")
    parser.add_argument("--query", required=True, help="Pregunta del usuario")
    parser.add_argument("--workspace",
                        default=os.path.expanduser("~/.openclaw/workspace"),
                        help="Directorio del workspace de OpenClaw")
    parser.add_argument("--sessions-dir", default=None,
                        help="Directorio de sesiones (auto-detectado si no se especifica)")
    # Modelos
    parser.add_argument("--root-model", default="gpt-5.3-codex",
                        help="Modelo principal para Root LM (default: gpt-5.3-codex)")
    parser.add_argument("--sub-model", default="gpt-5.1-codex-mini",
                        help="Modelo económico para Sub-LMs, 4x más eficiente (default: gpt-5.1-codex-mini)")
    parser.add_argument("--fallback-model", default="gpt-5.2",
                        help="Modelo fallback si el principal falla (default: gpt-5.2)")
    # CLIProxyAPI
    parser.add_argument("--base-url", default=CLIPROXYAPI_URL,
                        help=f"URL de CLIProxyAPI (default: {CLIPROXYAPI_URL})")
    parser.add_argument("--api-key", default=CLIPROXYAPI_KEY,
                        help="API key para CLIProxyAPI (cualquier string)")
    # Opciones
    parser.add_argument("--max-sessions", type=int, default=MAX_SESSIONS_DEFAULT,
                        help=f"Máximo de sesiones a cargar (default: {MAX_SESSIONS_DEFAULT})")
    parser.add_argument("--verbose", action="store_true",
                        help="Activar output detallado de RLM")
    parser.add_argument("--log-dir", default=None,
                        help="Directorio para logs RLM (.jsonl)")
    args = parser.parse_args()

    # Auto-detectar sessions dir si no se especificó
    if args.sessions_dir is None:
        args.sessions_dir = find_sessions_dir()

    # Cargar contexto
    workspace_content = load_workspace(args.workspace)
    sessions_content = load_sessions(args.sessions_dir, args.max_sessions)
    full_context = f"{workspace_content}\n\n{'='*60}\n\n{sessions_content}"
    context_chars = len(full_context)

    # Verificar que hay suficiente contexto
    if context_chars < 100:
        print(json.dumps({
            "response": "No hay suficiente historial para analizar.",
            "context_chars": context_chars,
            "status": "skipped",
        }, ensure_ascii=False))
        return

    # Intentar: principal → fallback
    try:
        result = run_rlm(
            args.query, full_context,
            args.root_model, args.sub_model,
            args.base_url, args.api_key,
            args.verbose, args.log_dir,
        )
    except Exception as e:
        try:
            result = run_rlm(
                args.query, full_context,
                args.fallback_model, args.fallback_model,
                args.base_url, args.api_key,
                args.verbose, args.log_dir,
            )
            result["fallback_reason"] = str(e)
        except Exception as e2:
            result = {
                "response": f"Error: No se pudo procesar. Principal: {e}, Fallback: {e2}",
                "status": "error",
            }

    result["context_chars"] = context_chars
    result["sessions_dir"] = args.sessions_dir
    result.setdefault("status", "ok")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
