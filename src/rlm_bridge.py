#!/usr/bin/env python3
"""
RLM Bridge for OpenClaw — v3
Connects OpenClaw with RLM via CLIProxyAPI (OAuth ChatGPT).
Models: GPT-5.3-Codex (root) + GPT-5.1-Codex-Mini (sub-LMs) via CLIProxyAPI.

Usage:
  uv run python src/rlm_bridge.py --query "What did we talk about yesterday?"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


# === CONSTANTS ===
MAX_CHARS = 2_000_000       # ~500K tokens, safe for 8GB RAM
MAX_SESSIONS_DEFAULT = 30
CLIPROXYAPI_URL = "http://127.0.0.1:8317/v1"  # CLIProxyAPI default port
CLIPROXYAPI_KEY = "sk-cliproxyapi-default-key-change-me"


def find_sessions_dir(openclaw_home: str = "~/.openclaw") -> str:
    """
    Auto-detects where OpenClaw stores sessions.

    OpenClaw directory structure:
      ~/.openclaw/agents/<agentId>/sessions/*.jsonl   <- JSONL transcripts
      ~/.openclaw/agents/<agentId>/sessions/sessions.json  <- index
      ~/.openclaw/agents/<agentId>/qmd/sessions/      <- QMD exports (sanitized Markdown)
      ~/.openclaw/workspace/memory/YYYY-MM-DD.md      <- daily notes
      ~/.openclaw/workspace/MEMORY.md                 <- long-term memory
    """
    home = Path(openclaw_home).expanduser()
    # Search in agent directories (actual location)
    agents_dir = home / "agents"
    if agents_dir.exists():
        for agent_dir in sorted(agents_dir.iterdir()):
            sessions_dir = agent_dir / "sessions"
            if sessions_dir.exists():
                jsonl_files = list(sessions_dir.glob("*.jsonl"))
                if jsonl_files:
                    return str(sessions_dir)

    # Legacy fallback: some older setups
    for candidate in [home / "sessions", home / "workspace" / "sessions"]:
        if candidate.exists() and any(candidate.iterdir()):
            return str(candidate)

    # Default: first agent
    return str(home / "agents" / "main" / "sessions")


def parse_jsonl_session(filepath: Path) -> str:
    """
    Converts an OpenClaw JSONL session file to readable text.

    OpenClaw JSONL format:
      Each line is JSON with: type, timestamp, message.role, message.content[]
      message.content[] contains objects with type="text" (readable) or type="toolCall" etc.
      Roles: "user", "assistant", "toolResult"

    Only extracts readable text (user + assistant), ignores toolResult and toolCall
    to keep context clean and reduce tokens.
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
                # Only user and assistant — toolResult is noise for analysis
                if role not in ("user", "assistant"):
                    continue

                content_blocks = msg.get("content", [])
                if isinstance(content_blocks, str):
                    # Simplified format (direct string)
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
    Loads OpenClaw workspace files.
    Includes context files AND daily memory notes.

    Workspace structure:
      MEMORY.md      <- curated long-term memory
      SOUL.md        <- personality and values
      AGENTS.md      <- operational instructions
      USER.md        <- user preferences
      IDENTITY.md    <- name, vibe, emoji
      TOOLS.md       <- tool notes
      memory/YYYY-MM-DD.md  <- daily notes (recent context)
    """
    workspace = Path(workspace_dir)
    parts = []

    # 1. Main context files
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

    # 2. Daily memory notes (memory/YYYY-MM-DD.md) — most recent first
    memory_dir = workspace / "memory"
    if memory_dir.exists():
        daily_files = sorted(
            memory_dir.glob("*.md"),
            key=lambda p: p.stem,  # YYYY-MM-DD sorts chronologically
            reverse=True,
        )
        daily_chars = 0
        for daily_file in daily_files[:30]:  # last 30 days max
            try:
                content = daily_file.read_text(encoding="utf-8", errors="ignore")
                if not content.strip() or len(content) < 20:
                    continue
                if daily_chars + len(content) > 200_000:  # cap for daily notes
                    break
                parts.append(f"=== DAILY:{daily_file.name} ===\n{content}")
                daily_chars += len(content)
            except (PermissionError, OSError):
                continue

    return "\n\n".join(parts)


def load_sessions(sessions_dir: str, max_sessions: int = MAX_SESSIONS_DEFAULT) -> str:
    """
    Loads OpenClaw sessions. Supports both formats:
      - *.jsonl (native OpenClaw format — append-only JSONL)
      - *.md (sanitized QMD exports, or legacy transcript.md)

    JSONL sessions are the main format since 2025.
    MD files may exist in ~/.openclaw/agents/<id>/qmd/sessions/ as
    sanitized QMD exports.
    """
    sessions = Path(sessions_dir)
    if not sessions.exists():
        return "[No sessions available]"

    # Collect all session files (JSONL first, then MD)
    session_files = []

    # 1. JSONL files (native format — primary data source)
    for p in sessions.glob("*.jsonl"):
        if p.name == "sessions.json":  # index, not transcript
            continue
        try:
            session_files.append((p.stat().st_mtime, p, "jsonl"))
        except OSError:
            continue

    # 2. MD files in QMD exports (if they exist)
    qmd_sessions = sessions.parent / "qmd" / "sessions"
    if qmd_sessions.exists():
        for p in qmd_sessions.rglob("*.md"):
            try:
                session_files.append((p.stat().st_mtime, p, "md"))
            except OSError:
                continue

    # 3. Fallback: legacy transcript.md
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
                    content = content[:remaining] + "\n[...truncated due to memory limit]"
                else:
                    break
            session_name = filepath.stem  # name without extension
            date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            parts.append(f"=== SESSION:{session_name} DATE:{date_str} FMT:{fmt} ===\n{content}")
            total_chars += len(content)
        except (PermissionError, UnicodeDecodeError, OSError):
            continue

    return "\n\n".join(parts) if parts else "[No sessions loaded]"


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
    Executes RLM with main model (root) and cost-efficient model (sub-LMs).
    Handles rate limits (429) with user-friendly message.
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
        max_depth=1,  # Only functional value currently (RLM docs: "This is a TODO")
        verbose=verbose,
    )

    # Sub-LMs with cheaper model (4x more quota efficient)
    if sub_model and sub_model != root_model:
        rlm_kwargs["other_backends"] = ["openai"]
        rlm_kwargs["other_backend_kwargs"] = [{
            "model_name": sub_model,
            "base_url": base_url,
            "api_key": api_key,
        }]

    # Optional logging
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
                "response": "Your ChatGPT quota has been reached. "
                            "Please try again in a few minutes.",
                "status": "rate_limited",
            }
        raise  # re-raise so main() can try fallback


def main():
    parser = argparse.ArgumentParser(description="RLM Bridge for OpenClaw v3")
    parser.add_argument("--query", required=True, help="User question")
    parser.add_argument("--workspace",
                        default=os.path.expanduser("~/.openclaw/workspace"),
                        help="OpenClaw workspace directory")
    parser.add_argument("--sessions-dir", default=None,
                        help="Sessions directory (auto-detected if not specified)")
    # Models
    parser.add_argument("--root-model", default="gpt-5.3-codex",
                        help="Main model for Root LM (default: gpt-5.3-codex)")
    parser.add_argument("--sub-model", default="gpt-5.1-codex-mini",
                        help="Cost-efficient model for Sub-LMs, 4x more efficient (default: gpt-5.1-codex-mini)")
    parser.add_argument("--fallback-model", default="gpt-5.2",
                        help="Fallback model if primary fails (default: gpt-5.2)")
    # CLIProxyAPI
    parser.add_argument("--base-url", default=CLIPROXYAPI_URL,
                        help=f"CLIProxyAPI URL (default: {CLIPROXYAPI_URL})")
    parser.add_argument("--api-key", default=CLIPROXYAPI_KEY,
                        help="API key for CLIProxyAPI (any string)")
    # Options
    parser.add_argument("--max-sessions", type=int, default=MAX_SESSIONS_DEFAULT,
                        help=f"Maximum sessions to load (default: {MAX_SESSIONS_DEFAULT})")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable detailed RLM output")
    parser.add_argument("--log-dir", default=None,
                        help="Directory for RLM logs (.jsonl)")
    args = parser.parse_args()

    # Auto-detect sessions dir if not specified
    if args.sessions_dir is None:
        args.sessions_dir = find_sessions_dir()

    # Load context
    workspace_content = load_workspace(args.workspace)
    sessions_content = load_sessions(args.sessions_dir, args.max_sessions)
    full_context = f"{workspace_content}\n\n{'='*60}\n\n{sessions_content}"
    context_chars = len(full_context)

    # Verify sufficient context exists
    if context_chars < 100:
        print(json.dumps({
            "response": "Not enough history to analyze.",
            "context_chars": context_chars,
            "status": "skipped",
        }, ensure_ascii=False))
        return

    # Try: primary -> fallback
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
                "response": f"Error: Could not process. Primary: {e}, Fallback: {e2}",
                "status": "error",
            }

    result["context_chars"] = context_chars
    result["sessions_dir"] = args.sessions_dir
    result.setdefault("status", "ok")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
