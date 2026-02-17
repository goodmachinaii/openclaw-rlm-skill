#!/usr/bin/env python3
"""
RLM Bridge for OpenClaw — v4.1 ASYNC OPTIMIZED
Connects OpenClaw with RLM via Moonshot API (Kimi models).
Models: kimi-k2-thinking (root) + kimi-k2.5 (sub-LMs) via Moonshot API.

Usage:
  export MOONSHOT_API_KEY="sk-your-key"
  uv run python src/rlm_bridge.py --query "What did we talk about yesterday?"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Async file I/O
try:
    import aiofiles
    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False
    print("Warning: aiofiles not available, falling back to sync mode")


# === CONSTANTS ===
MAX_CHARS = 200_000         # ~50K tokens, sufficient for session analysis
MAX_SESSIONS_DEFAULT = 30
MOONSHOT_API_URL = "https://api.moonshot.ai/v1"
MOONSHOT_API_KEY = os.environ.get("MOONSHOT_API_KEY", "")
MAX_WORKERS = 4             # For ThreadPoolExecutor

# Default models (Kimi)
DEFAULT_ROOT_MODEL = "kimi-k2.5"
DEFAULT_SUB_MODEL = "kimi-k2.5"
DEFAULT_FALLBACK_MODEL = "kimi-k2-turbo"


def find_sessions_dir(openclaw_home: str = "~/.openclaw") -> str:
    """
    Auto-detects where OpenClaw stores sessions.
    """
    home = Path(openclaw_home).expanduser()
    agents_dir = home / "agents"
    if agents_dir.exists():
        for agent_dir in sorted(agents_dir.iterdir()):
            sessions_dir = agent_dir / "sessions"
            if sessions_dir.exists():
                jsonl_files = list(sessions_dir.glob("*.jsonl"))
                if jsonl_files:
                    return str(sessions_dir)

    for candidate in [home / "sessions", home / "workspace" / "sessions"]:
        if candidate.exists() and any(candidate.iterdir()):
            return str(candidate)

    return str(home / "agents" / "main" / "sessions")


def parse_jsonl_session_content(raw_content: str) -> str:
    """
    Parse JSONL content to readable text (CPU-bound operation).
    """
    lines = []
    for raw_line in raw_content.strip().split('\n'):
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            entry = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        msg = entry.get("message", {})
        role = msg.get("role", "")
        if role not in ("user", "assistant"):
            continue

        content_blocks = msg.get("content", [])
        if isinstance(content_blocks, str):
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

    return "\n".join(lines)


# === ASYNC FUNCTIONS ===

async def read_file_async(filepath: Path) -> str:
    """Read file content asynchronously."""
    if not HAS_AIOFILES:
        # Fallback to sync
        return filepath.read_text(encoding="utf-8", errors="ignore")
    
    async with aiofiles.open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return await f.read()


async def process_session_file(filepath: Path, mtime: float, fmt: str) -> tuple:
    """
    Process a single session file: read + parse.
    Returns (date_str, content) or None if failed.
    """
    try:
        if fmt == "jsonl":
            raw_content = await read_file_async(filepath)
            content = parse_jsonl_session_content(raw_content)
        else:
            content = await read_file_async(filepath)
        
        if len(content.strip()) < 50:
            return None
            
        date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        session_name = filepath.stem
        formatted = f"=== SESSION:{session_name} DATE:{date_str} FMT:{fmt} ===\n{content}"
        return (date_str, formatted)
    except (PermissionError, UnicodeDecodeError, OSError):
        return None


async def load_sessions_parallel(sessions_dir: str, max_sessions: int = MAX_SESSIONS_DEFAULT) -> str:
    """
    Load sessions using async I/O for better performance.
    """
    start_time = time.time()
    sessions = Path(sessions_dir)
    if not sessions.exists():
        return "[No sessions available]"

    # Collect all session files (sync - fast)
    session_files = []
    
    for p in sessions.glob("*.jsonl"):
        if p.name == "sessions.json":
            continue
        try:
            session_files.append((p.stat().st_mtime, p, "jsonl"))
        except OSError:
            continue

    qmd_sessions = sessions.parent / "qmd" / "sessions"
    if qmd_sessions.exists():
        for p in qmd_sessions.rglob("*.md"):
            try:
                session_files.append((p.stat().st_mtime, p, "md"))
            except OSError:
                continue

    if not session_files:
        for p in sessions.rglob("transcript.md"):
            try:
                session_files.append((p.stat().st_mtime, p, "md"))
            except OSError:
                continue

    session_files.sort(key=lambda x: x[0], reverse=True)
    session_files = session_files[:max_sessions]

    # Process files concurrently 🚀
    tasks = [
        process_session_file(filepath, mtime, fmt)
        for mtime, filepath, fmt in session_files
    ]
    results = await asyncio.gather(*tasks)
    
    # Filter valid results and assemble
    parts = []
    total_chars = 0
    
    for result in results:
        if result is None:
            continue
        _, content = result
        if total_chars >= MAX_CHARS:
            break
        if total_chars + len(content) > MAX_CHARS:
            remaining = MAX_CHARS - total_chars
            if remaining > 1000:
                content = content[:remaining] + "\n[...truncated due to memory limit]"
                parts.append(content)
            break
        parts.append(content)
        total_chars += len(content)

    elapsed = time.time() - start_time
    print(f"[Async] Loaded {len(parts)} sessions in {elapsed:.2f}s", file=sys.stderr)
    
    return "\n\n".join(parts) if parts else "[No sessions loaded]"


def load_workspace_sync(workspace_dir: str) -> str:
    """Load workspace files (sync - already fast)."""
    workspace = Path(workspace_dir)
    parts = []

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

    memory_dir = workspace / "memory"
    if memory_dir.exists():
        daily_files = sorted(
            memory_dir.glob("*.md"),
            key=lambda p: p.stem,
            reverse=True,
        )
        daily_chars = 0
        for daily_file in daily_files[:30]:
            try:
                content = daily_file.read_text(encoding="utf-8", errors="ignore")
                if not content.strip() or len(content) < 20:
                    continue
                if daily_chars + len(content) > 200_000:
                    break
                parts.append(f"=== DAILY:{daily_file.name} ===\n{content}")
                daily_chars += len(content)
            except (PermissionError, OSError):
                continue

    return "\n\n".join(parts)


# === SYNC FUNCTIONS (RLM is inherently synchronous) ===

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
        max_iterations=5,  # Professional: explore + chunk + analyze + consolidate
        max_depth=1,
        verbose=verbose,
    )

    if sub_model and sub_model != root_model:
        rlm_kwargs["other_backends"] = ["openai"]
        rlm_kwargs["other_backend_kwargs"] = [{
            "model_name": sub_model,
            "base_url": base_url,
            "api_key": api_key,
        }]

    if log_dir:
        from rlm.logger import RLMLogger
        rlm_kwargs["logger"] = RLMLogger(log_dir=log_dir)

    rlm = RLM(**rlm_kwargs)

    try:
        result = rlm.completion(prompt=context, root_prompt=query)
        
        # Extraer información de uso si está disponible
        usage_info = {}
        if result.usage_summary:
            usage_info = result.usage_summary.to_dict()
        
        return {
            "response": result.response,
            "model_used": root_model,
            "sub_model_used": sub_model,
            "execution_time": result.execution_time,
            "usage_summary": usage_info,
            "status": "ok",
        }
    except Exception as e:
        error_str = str(e).lower()
        if "429" in error_str or "rate limit" in error_str or "quota" in error_str:
            return {
                "response": "Kimi API rate limit reached. Please try again in a few minutes.",
                "status": "rate_limited",
            }
        raise


# === ASYNC MAIN ===

async def main_async():
    parser = argparse.ArgumentParser(description="RLM Bridge for OpenClaw v4.1 ASYNC")
    parser.add_argument("--query", required=True, help="User question")
    parser.add_argument("--workspace",
                        default=os.path.expanduser("~/.openclaw/workspace"),
                        help="OpenClaw workspace directory")
    parser.add_argument("--sessions-dir", default=None,
                        help="Sessions directory (auto-detected if not specified)")
    parser.add_argument("--root-model", default=DEFAULT_ROOT_MODEL,
                        help=f"Main model (default: {DEFAULT_ROOT_MODEL})")
    parser.add_argument("--sub-model", default=DEFAULT_SUB_MODEL,
                        help=f"Sub-LM model (default: {DEFAULT_SUB_MODEL})")
    parser.add_argument("--fallback-model", default=DEFAULT_FALLBACK_MODEL,
                        help=f"Fallback model (default: {DEFAULT_FALLBACK_MODEL})")
    parser.add_argument("--base-url", default=MOONSHOT_API_URL,
                        help=f"API URL (default: {MOONSHOT_API_URL})")
    parser.add_argument("--api-key", default=MOONSHOT_API_KEY,
                        help="API key (default: from MOONSHOT_API_KEY env)")
    parser.add_argument("--max-sessions", type=int, default=MAX_SESSIONS_DEFAULT,
                        help=f"Max sessions (default: {MAX_SESSIONS_DEFAULT})")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable verbose RLM output")
    parser.add_argument("--log-dir", default=None,
                        help="Directory for RLM logs")
    args = parser.parse_args()

    if not args.api_key:
        print(json.dumps({
            "response": "Error: MOONSHOT_API_KEY not set. Get key at https://platform.moonshot.ai/",
            "status": "error",
        }, ensure_ascii=False))
        sys.exit(1)

    if args.sessions_dir is None:
        args.sessions_dir = find_sessions_dir()

    # Load workspace (sync - fast)
    start_total = time.time()
    workspace_content = load_workspace_sync(args.workspace)
    
    # Load sessions (async - optimized) 🚀
    sessions_content = await load_sessions_parallel(args.sessions_dir, args.max_sessions)
    
    full_context = f"{workspace_content}\n\n{'='*60}\n\n{sessions_content}"
    context_chars = len(full_context)

    load_time = time.time() - start_total
    print(f"[Async] Total loading time: {load_time:.2f}s", file=sys.stderr)

    if context_chars < 100:
        print(json.dumps({
            "response": "Not enough history to analyze.",
            "context_chars": context_chars,
            "status": "skipped",
        }, ensure_ascii=False))
        return

    # Run RLM (sync - inherently sequential)
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
    result["load_time_seconds"] = load_time
    result.setdefault("status", "ok")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    """Entry point - runs async main."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
