#!/usr/bin/env python3
"""
RLM Bridge for OpenClaw — v4.2
Connects OpenClaw with RLM via Moonshot API (Kimi models).

Design goals:
- Keep Alex Zhang RLM behavior (iterative REPL, no custom system prompt override).
- Add operational controls for Raspberry Pi (context/iteration limits, optional compaction).
- Provide model profiles and estimated per-run token cost.
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
from typing import Any

# Async file I/O
try:
    import aiofiles

    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False
    print("Warning: aiofiles not available, falling back to sync mode", file=sys.stderr)


# === CONSTANTS ===
DEFAULT_MAX_CONTEXT_CHARS = 200_000
DEFAULT_MAX_SESSIONS = 30
DEFAULT_MAX_ITERATIONS = 5
MOONSHOT_API_URL = "https://api.moonshot.ai/v1"
MOONSHOT_API_KEY = os.environ.get("MOONSHOT_API_KEY", "")

# Default models (Kimi)
DEFAULT_ROOT_MODEL = "kimi-k2.5"
DEFAULT_SUB_MODEL = "kimi-k2.5"
DEFAULT_FALLBACK_MODEL = "kimi-k2-turbo"

MODEL_PROFILES: dict[str, dict[str, str]] = {
    "cost": {
        "root": "kimi-k2.5",
        "sub": "kimi-k2.5",
        "fallback": "kimi-k2-turbo",
    },
    "balanced": {
        "root": "kimi-k2.5",
        "sub": "kimi-k2.5",
        "fallback": "kimi-k2-turbo",
    },
    "speed": {
        "root": "kimi-k2.5",
        "sub": "kimi-k2-turbo-preview",
        "fallback": "kimi-k2-turbo-preview",
    },
}

PI_PROFILES: dict[str, dict[str, object]] = {
    "off": {},
    "pi4": {
        "max_sessions": 8,
        "max_context_chars": 120_000,
        "max_iterations": 4,
        "compaction": True,
        "compaction_threshold": 0.70,
    },
    "pi8": {
        "max_sessions": 15,
        "max_context_chars": 180_000,
        "max_iterations": 5,
        "compaction": True,
        "compaction_threshold": 0.80,
    },
}

# Official public pricing references (USD per 1M tokens)
# Updated from Moonshot docs/forum in Feb 2026.
MODEL_PRICING_USD_PER_1M: dict[str, dict[str, float]] = {
    "kimi-k2.5": {"prompt": 0.60, "completion": 3.00, "caching": 0.10},
    "kimi-k2-turbo-preview": {"prompt": 1.15, "completion": 8.00, "caching": 0.15},
    "kimi-k2-turbo": {"prompt": 1.15, "completion": 8.00, "caching": 0.15},
    "kimi-k2-thinking-turbo": {"prompt": 1.15, "completion": 8.00, "caching": 0.15},
}


def _resolve_openclaw_home_from_sessions_dir(sessions_dir: str | Path) -> Path | None:
    path = Path(sessions_dir).expanduser().resolve()
    parts = list(path.parts)
    if ".openclaw" in parts:
        idx = parts.index(".openclaw")
        return Path(*parts[: idx + 1])
    return None


def _extract_agent_id_from_payload(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("agentId", "agent_id", "id", "currentAgentId", "activeAgentId"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    nested = payload.get("agent")
    if isinstance(nested, dict):
        return _extract_agent_id_from_payload(nested)
    return None


def _discover_active_agent_id(openclaw_home: str = "~/.openclaw") -> str | None:
    explicit = os.environ.get("OPENCLAW_AGENT_ID", "").strip()
    if explicit:
        return explicit

    home = Path(openclaw_home).expanduser()
    candidates = [
        home / "active-agent.json",
        home / "runtime" / "active-agent.json",
        home / "state" / "active-agent.json",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8", errors="ignore"))
            found = _extract_agent_id_from_payload(payload)
            if found:
                return found
        except (json.JSONDecodeError, OSError):
            continue

    return None


def _safe_text_from_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("text", "summary", "content", "message"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    return ""


def _parse_timestamp_like(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            pass
        try:
            normalized = raw.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized).timestamp()
        except ValueError:
            return None

    return None


def _load_sessions_index_map(sessions_dir: str) -> dict[str, dict[str, Any]]:
    index_path = Path(sessions_dir) / "sessions.json"
    if not index_path.exists():
        return {}

    try:
        payload = json.loads(index_path.read_text(encoding="utf-8", errors="ignore"))
    except (json.JSONDecodeError, OSError):
        return {}

    out: dict[str, dict[str, Any]] = {}

    # Format A: {"sessions": [...]} or {"items": [...]}.
    if isinstance(payload, dict):
        list_entries = payload.get("sessions", payload.get("items"))
        if isinstance(list_entries, list):
            for item in list_entries:
                if not isinstance(item, dict):
                    continue
                session_id = str(
                    item.get("id") or item.get("sessionId") or item.get("uuid") or ""
                ).strip()
                if session_id:
                    out[session_id] = item

        # Format B (current in OpenClaw docs): map sessionKey -> sessionEntry.
        for value in payload.values():
            if not isinstance(value, dict):
                continue
            session_id = str(value.get("sessionId") or value.get("id") or "").strip()
            if session_id and session_id not in out:
                out[session_id] = value

    # Format C: raw list.
    elif isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            session_id = str(item.get("id") or item.get("sessionId") or item.get("uuid") or "").strip()
            if session_id:
                out[session_id] = item

    return out


def find_sessions_dir(openclaw_home: str = "~/.openclaw", agent_id: str | None = None) -> str:
    """Auto-detect where OpenClaw stores sessions."""
    home = Path(openclaw_home).expanduser()
    agents_dir = home / "agents"
    preferred_agent_raw = agent_id or _discover_active_agent_id(openclaw_home)
    preferred_agent = preferred_agent_raw.strip() if isinstance(preferred_agent_raw, str) else ""
    if agents_dir.exists():
        ordered_dirs: list[Path] = []
        if preferred_agent:
            ordered_dirs.append(agents_dir / preferred_agent)
        ordered_dirs.extend(sorted(agents_dir.iterdir()))

        seen: set[Path] = set()
        for agent_dir in ordered_dirs:
            if agent_dir in seen or not agent_dir.exists():
                continue
            seen.add(agent_dir)
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
    """Parse OpenClaw JSONL content to readable text."""
    lines: list[str] = []
    for raw_line in raw_content.strip().split("\n"):
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        try:
            entry = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        entry_type = str(entry.get("type") or "").strip().lower()
        if entry_type in ("compaction", "branch_summary"):
            summary_text = (
                _safe_text_from_value(entry.get("summary"))
                or _safe_text_from_value(entry.get("content"))
                or _safe_text_from_value(entry.get("message"))
            )
            if summary_text:
                lines.append(f"[memory-summary]: {summary_text}")
            continue

        msg = entry.get("message", {})
        role = msg.get("role", "")
        if role not in ("user", "assistant"):
            continue

        content_blocks = msg.get("content", [])
        if isinstance(content_blocks, str):
            lines.append(f"[{role}]: {content_blocks}")
            continue

        text_parts: list[str] = []
        for block in content_blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "").strip()
                if text:
                    text_parts.append(text)
        if text_parts:
            lines.append(f"[{role}]: {' '.join(text_parts)}")

    return "\n".join(lines)


def parse_jsonl_session(filepath: str | Path) -> str:
    """
    Backward-compatible sync helper used by tests and docs.
    """
    path = Path(filepath)
    raw_content = path.read_text(encoding="utf-8", errors="ignore")
    return parse_jsonl_session_content(raw_content)


def _collect_session_files(sessions_dir: str, max_sessions: int) -> list[tuple[float, Path, str]]:
    sessions = Path(sessions_dir)
    if not sessions.exists():
        return []

    index_map = _load_sessions_index_map(sessions_dir)
    session_files: list[tuple[float, Path, str]] = []

    for p in sessions.glob("*.jsonl"):
        if p.name == "sessions.json":
            continue
        try:
            mtime = p.stat().st_mtime
            meta = index_map.get(p.stem, {})
            indexed_ts = _parse_timestamp_like(
                meta.get("updatedAt")
                or meta.get("lastMessageAt")
                or meta.get("timestamp")
                or meta.get("createdAt")
            )
            session_files.append((indexed_ts if indexed_ts is not None else mtime, p, "jsonl"))
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
    return session_files[:max_sessions]


def _assemble_session_parts(parts: list[str], max_chars: int) -> str:
    total_chars = 0
    assembled: list[str] = []

    for content in parts:
        if total_chars >= max_chars:
            break

        if total_chars + len(content) > max_chars:
            remaining = max_chars - total_chars
            if remaining > 1000:
                assembled.append(content[:remaining] + "\n[...truncated due to memory limit]")
            break

        assembled.append(content)
        total_chars += len(content)

    return "\n\n".join(assembled) if assembled else "[No sessions loaded]"


# === ASYNC FUNCTIONS ===


async def read_file_async(filepath: Path) -> str:
    """Read file content asynchronously."""
    if not HAS_AIOFILES:
        return filepath.read_text(encoding="utf-8", errors="ignore")

    async with aiofiles.open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return await f.read()


async def process_session_file(
    filepath: Path,
    mtime: float,
    fmt: str,
    index_map: dict[str, dict[str, Any]] | None = None,
) -> str | None:
    """Process one session file and return formatted text or None."""
    try:
        if fmt == "jsonl":
            raw_content = await read_file_async(filepath)
            content = parse_jsonl_session_content(raw_content)
        else:
            content = await read_file_async(filepath)

        if len(content.strip()) < 50:
            return None

        map_for_file = index_map if isinstance(index_map, dict) else {}
        meta = map_for_file.get(filepath.stem, {}) if fmt == "jsonl" else {}
        branch_id = str(meta.get("branchId") or meta.get("branch_id") or "").strip()
        parent_id = str(meta.get("parentId") or meta.get("parent_id") or "").strip()
        title = str(meta.get("title") or "").strip()
        date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        session_name = filepath.stem
        header = f"=== SESSION:{session_name} DATE:{date_str} FMT:{fmt}"
        if title:
            header += f" TITLE:{title[:120]}"
        if branch_id:
            header += f" BRANCH:{branch_id}"
        if parent_id:
            header += f" PARENT:{parent_id}"
        header += " ==="
        return f"{header}\n{content}"
    except (PermissionError, UnicodeDecodeError, OSError):
        return None


async def load_sessions_parallel(
    sessions_dir: str,
    max_sessions: int = DEFAULT_MAX_SESSIONS,
    max_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
) -> str:
    """Load sessions using async I/O for better performance."""
    start_time = time.perf_counter()
    session_files = _collect_session_files(sessions_dir, max_sessions)
    if not session_files:
        return "[No sessions available]"

    index_map = _load_sessions_index_map(sessions_dir)
    tasks = [
        process_session_file(filepath, mtime, fmt, index_map=index_map)
        for mtime, filepath, fmt in session_files
    ]
    results = await asyncio.gather(*tasks)
    parts = [item for item in results if item]

    elapsed = time.perf_counter() - start_time
    print(f"[Async] Loaded {len(parts)} sessions in {elapsed:.2f}s", file=sys.stderr)

    return _assemble_session_parts(parts, max_chars)


def load_sessions(
    sessions_dir: str,
    max_sessions: int = DEFAULT_MAX_SESSIONS,
    max_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
) -> str:
    """
    Backward-compatible sync loader used by tests.
    """
    session_files = _collect_session_files(sessions_dir, max_sessions)
    if not session_files:
        return "[No sessions available]"

    parts: list[str] = []
    index_map = _load_sessions_index_map(sessions_dir)
    for mtime, filepath, fmt in session_files:
        try:
            if fmt == "jsonl":
                content = parse_jsonl_session(filepath)
            else:
                content = filepath.read_text(encoding="utf-8", errors="ignore")

            if len(content.strip()) < 50:
                continue

            meta = index_map.get(filepath.stem, {}) if fmt == "jsonl" else {}
            branch_id = str(meta.get("branchId") or meta.get("branch_id") or "").strip()
            parent_id = str(meta.get("parentId") or meta.get("parent_id") or "").strip()
            title = str(meta.get("title") or "").strip()
            date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            session_name = filepath.stem
            header = f"=== SESSION:{session_name} DATE:{date_str} FMT:{fmt}"
            if title:
                header += f" TITLE:{title[:120]}"
            if branch_id:
                header += f" BRANCH:{branch_id}"
            if parent_id:
                header += f" PARENT:{parent_id}"
            header += " ==="
            parts.append(f"{header}\n{content}")
        except (PermissionError, UnicodeDecodeError, OSError):
            continue

    return _assemble_session_parts(parts, max_chars)


def build_context_payload(
    workspace_content: str,
    sessions_content: str,
    context_format: str,
    pi_profile_name: str,
) -> tuple[str | list[str], str]:
    full_context = f"{workspace_content}\n\n{'=' * 60}\n\n{sessions_content}"
    sessions_available = sessions_content.strip() not in (
        "",
        "[No sessions available]",
        "[No sessions loaded]",
    )
    if context_format == "auto":
        context_chars = len(full_context)
        # On constrained devices, list chunks reduce single-prompt overload.
        if pi_profile_name != "off" or context_chars >= 120_000:
            context_format = "chunks"
        else:
            context_format = "string"

    if context_format == "chunks":
        chunks: list[str] = []
        if workspace_content.strip():
            chunks.append(f"=== WORKSPACE ===\n{workspace_content}")
        if sessions_available:
            for block in sessions_content.split("\n\n=== SESSION:"):
                block = block.strip()
                if not block:
                    continue
                if block.startswith("=== SESSION:"):
                    chunks.append(block)
                else:
                    chunks.append(f"=== SESSION:{block}")
        return (chunks if chunks else [full_context]), context_format

    return full_context, "string"


def load_workspace_sync(workspace_dir: str, daily_chars_limit: int = 200_000) -> str:
    """Load workspace files (sync)."""
    workspace = Path(workspace_dir)
    parts: list[str] = []
    seen_paths: set[Path] = set()

    workspace_file_aliases = [
        ("MEMORY.md", ("MEMORY.md", "memory.md")),
        ("SOUL.md", ("SOUL.md",)),
        ("AGENTS.md", ("AGENTS.md",)),
        ("USER.md", ("USER.md",)),
        ("IDENTITY.md", ("IDENTITY.md",)),
        ("TOOLS.md", ("TOOLS.md",)),
    ]

    for display_name, aliases in workspace_file_aliases:
        filepath = None
        for name in aliases:
            candidate = workspace / name
            if candidate.exists():
                filepath = candidate.resolve()
                break
        if filepath is None or filepath in seen_paths:
            continue
        seen_paths.add(filepath)

        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
            if content.strip() and len(content) < 50_000:
                parts.append(f"=== {display_name} ===\n{content}")
        except (PermissionError, OSError) as error:
            parts.append(f"=== {display_name} === [Error: {error}]")

    memory_dir = workspace / "memory"
    if memory_dir.exists():
        daily_files = sorted(memory_dir.glob("*.md"), key=lambda p: p.stem, reverse=True)
        daily_chars = 0
        for daily_file in daily_files[:30]:
            try:
                content = daily_file.read_text(encoding="utf-8", errors="ignore")
                if not content.strip() or len(content) < 20:
                    continue
                if daily_chars + len(content) > daily_chars_limit:
                    break
                parts.append(f"=== DAILY:{daily_file.name} ===\n{content}")
                daily_chars += len(content)
            except (PermissionError, OSError):
                continue

    return "\n\n".join(parts)


def _create_rlm(**kwargs):
    """Small seam for tests to patch RLM construction."""
    from rlm import RLM

    return RLM(**kwargs)


def _is_rate_limited_error(error_text: str) -> bool:
    return "429" in error_text or "rate limit" in error_text or "quota" in error_text


def _is_retryable_error(error_text: str) -> bool:
    retryable_markers = (
        "timeout",
        "timed out",
        "connection reset",
        "temporarily unavailable",
        "temporary",
        "502",
        "503",
        "504",
    )
    return any(marker in error_text for marker in retryable_markers)


def _extract_usage_summary(result_obj) -> dict:
    usage_obj = getattr(result_obj, "usage_summary", None)
    if usage_obj is None:
        return {}

    to_dict = getattr(usage_obj, "to_dict", None)
    if callable(to_dict):
        return to_dict()

    if isinstance(usage_obj, dict):
        return usage_obj

    return {}


def _resolve_model_pricing(model_name: str) -> dict[str, float] | None:
    if model_name in MODEL_PRICING_USD_PER_1M:
        return MODEL_PRICING_USD_PER_1M[model_name]

    for known_name, prices in MODEL_PRICING_USD_PER_1M.items():
        if model_name.startswith(known_name):
            return prices

    return None


def estimate_usage_cost(usage_summary: dict) -> dict:
    """
    Estimate token cost from usage summary.

    Notes:
    - Uses published per-token prices.
    - Uses non-cached input token pricing (conservative when cache hits are unknown).
    """
    model_usage = usage_summary.get("model_usage_summaries", {}) if usage_summary else {}
    if not isinstance(model_usage, dict):
        return {}

    per_model: dict[str, dict[str, float | int | str]] = {}
    total_usd = 0.0

    for model_name, stats in model_usage.items():
        if not isinstance(stats, dict):
            continue

        input_tokens = int(
            stats.get("total_input_tokens")
            or stats.get("prompt_tokens")
            or stats.get("input_tokens")
            or 0
        )
        output_tokens = int(
            stats.get("total_output_tokens")
            or stats.get("completion_tokens")
            or stats.get("output_tokens")
            or 0
        )

        pricing = _resolve_model_pricing(model_name)
        if not pricing:
            per_model[model_name] = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_usd": 0.0,
                "pricing_source": "unknown_model",
            }
            continue

        model_cost = (
            (input_tokens / 1_000_000.0) * pricing["prompt"]
            + (output_tokens / 1_000_000.0) * pricing["completion"]
        )

        per_model[model_name] = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "usd_per_1m_prompt": pricing["prompt"],
            "usd_per_1m_completion": pricing["completion"],
            "estimated_usd": round(model_cost, 6),
            "pricing_source": "moonshot_docs_forum_feb_2026",
        }
        total_usd += model_cost

    if not per_model:
        return {}

    return {
        "total_estimated_usd": round(total_usd, 6),
        "estimated_input_pricing_mode": "cache_miss",
        "by_model": per_model,
    }


# === RUN RLM ===

def run_rlm(
    query: str,
    context: str | list[str],
    root_model: str,
    sub_model: str,
    base_url: str,
    api_key: str,
    verbose: bool = False,
    log_dir: str | None = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    compaction: bool = False,
    compaction_threshold: float = 0.85,
    request_timeout: float = 120.0,
    max_retries: int = 1,
    retry_backoff_seconds: float = 2.0,
) -> dict:
    """Execute RLM with retries for transient failures."""
    attempt = 0

    while True:
        attempt += 1

        backend_kwargs = {
            "model_name": root_model,
            "base_url": base_url,
            "api_key": api_key,
        }
        if request_timeout > 0:
            backend_kwargs["timeout"] = request_timeout

        rlm_kwargs = {
            "backend": "openai",
            "backend_kwargs": backend_kwargs,
            "environment": "local",
            "max_iterations": max_iterations,
            "max_depth": 1,
            "verbose": verbose,
            "compaction": compaction,
            "compaction_threshold_pct": compaction_threshold,
        }

        if sub_model and sub_model != root_model:
            other_backend_kwargs = {
                "model_name": sub_model,
                "base_url": base_url,
                "api_key": api_key,
            }
            if request_timeout > 0:
                other_backend_kwargs["timeout"] = request_timeout

            rlm_kwargs["other_backends"] = ["openai"]
            rlm_kwargs["other_backend_kwargs"] = [other_backend_kwargs]

        if log_dir:
            from rlm.logger import RLMLogger

            rlm_kwargs["logger"] = RLMLogger(log_dir=log_dir)

        rlm = _create_rlm(**rlm_kwargs)

        try:
            result = rlm.completion(prompt=context, root_prompt=query)
            usage_info = _extract_usage_summary(result)
            cost_estimate = estimate_usage_cost(usage_info)

            return {
                "response": result.response,
                "model_used": root_model,
                "sub_model_used": sub_model,
                "execution_time": getattr(result, "execution_time", None),
                "usage_summary": usage_info,
                "cost_estimate": cost_estimate,
                "attempts": attempt,
                "status": "ok",
            }
        except Exception as error:
            error_text = str(error).lower()
            if _is_rate_limited_error(error_text):
                return {
                    "response": "Kimi API rate limit reached. Please try again in a few minutes.",
                    "attempts": attempt,
                    "status": "rate_limited",
                }

            can_retry = attempt <= max_retries and _is_retryable_error(error_text)
            if can_retry:
                sleep_seconds = retry_backoff_seconds * attempt
                print(
                    f"[RLM] transient error on attempt {attempt}: {error}. "
                    f"Retrying in {sleep_seconds:.1f}s...",
                    file=sys.stderr,
                )
                time.sleep(sleep_seconds)
                continue

            raise


# === ASYNC MAIN ===


async def main_async():
    parser = argparse.ArgumentParser(description="RLM Bridge for OpenClaw v4.2")
    parser.add_argument("--query", required=True, help="User question")
    parser.add_argument(
        "--workspace",
        default=os.path.expanduser("~/.openclaw/workspace"),
        help="OpenClaw workspace directory",
    )
    parser.add_argument(
        "--sessions-dir",
        default=None,
        help="Sessions directory (auto-detected if not specified)",
    )
    parser.add_argument(
        "--agent-id",
        default=None,
        help="OpenClaw agent id to resolve sessions directory deterministically",
    )

    parser.add_argument(
        "--profile-model",
        choices=sorted(MODEL_PROFILES.keys()),
        default="cost",
        help="Model profile (default: cost)",
    )
    parser.add_argument("--root-model", default=None, help="Override root model")
    parser.add_argument("--sub-model", default=None, help="Override sub model")
    parser.add_argument("--fallback-model", default=None, help="Override fallback model")

    parser.add_argument(
        "--pi-profile",
        choices=sorted(PI_PROFILES.keys()),
        default="off",
        help="Resource profile for Raspberry Pi",
    )

    parser.add_argument(
        "--max-sessions",
        type=int,
        default=None,
        help=f"Max sessions (default: {DEFAULT_MAX_SESSIONS})",
    )
    parser.add_argument(
        "--max-context-chars",
        type=int,
        default=None,
        help=f"Max chars in aggregated context (default: {DEFAULT_MAX_CONTEXT_CHARS})",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help=f"Max RLM iterations (default: {DEFAULT_MAX_ITERATIONS})",
    )
    parser.add_argument(
        "--context-format",
        choices=["auto", "string", "chunks"],
        default="auto",
        help="How to pass context to RLM (default: auto)",
    )

    parser.add_argument("--compaction", dest="compaction", action="store_true")
    parser.add_argument("--no-compaction", dest="compaction", action="store_false")
    parser.set_defaults(compaction=None)

    parser.add_argument(
        "--compaction-threshold",
        type=float,
        default=None,
        help="Compaction threshold pct in (0,1], default 0.85",
    )

    parser.add_argument(
        "--request-timeout",
        type=float,
        default=120.0,
        help="Per-request timeout in seconds for API calls",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="Retries for transient model/API errors",
    )
    parser.add_argument(
        "--retry-backoff-seconds",
        type=float,
        default=2.0,
        help="Backoff base for retries",
    )

    parser.add_argument("--base-url", default=MOONSHOT_API_URL, help="API URL")
    parser.add_argument(
        "--api-key",
        default=MOONSHOT_API_KEY,
        help="API key (default: from MOONSHOT_API_KEY env)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose RLM output")
    parser.add_argument("--log-dir", default=None, help="Directory for RLM logs")
    args = parser.parse_args()

    if not args.api_key:
        print(
            json.dumps(
                {
                    "response": "Error: MOONSHOT_API_KEY not set. Get key at https://platform.moonshot.ai/",
                    "status": "error",
                },
                ensure_ascii=False,
            )
        )
        sys.exit(1)

    model_profile = MODEL_PROFILES[args.profile_model]
    root_model = args.root_model or model_profile["root"]
    sub_model = args.sub_model or model_profile["sub"]
    fallback_model = args.fallback_model or model_profile["fallback"]

    pi_profile = PI_PROFILES[args.pi_profile]
    max_sessions = int(args.max_sessions or pi_profile.get("max_sessions", DEFAULT_MAX_SESSIONS))
    max_context_chars = int(
        args.max_context_chars or pi_profile.get("max_context_chars", DEFAULT_MAX_CONTEXT_CHARS)
    )
    max_iterations = int(
        args.max_iterations or pi_profile.get("max_iterations", DEFAULT_MAX_ITERATIONS)
    )

    compaction = args.compaction
    if compaction is None:
        compaction = bool(pi_profile.get("compaction", False))

    compaction_threshold = args.compaction_threshold
    if compaction_threshold is None:
        compaction_threshold = float(pi_profile.get("compaction_threshold", 0.85))
    if compaction_threshold <= 0 or compaction_threshold > 1:
        compaction_threshold = 0.85

    if args.sessions_dir is None:
        args.sessions_dir = find_sessions_dir(agent_id=args.agent_id)
    openclaw_home = _resolve_openclaw_home_from_sessions_dir(args.sessions_dir)
    active_agent_id = args.agent_id or (
        _discover_active_agent_id(str(openclaw_home)) if openclaw_home else None
    )

    total_start = time.perf_counter()

    workspace_start = time.perf_counter()
    workspace_content = load_workspace_sync(args.workspace)
    workspace_time = time.perf_counter() - workspace_start

    sessions_start = time.perf_counter()
    sessions_content = await load_sessions_parallel(
        args.sessions_dir,
        max_sessions=max_sessions,
        max_chars=max_context_chars,
    )
    sessions_time = time.perf_counter() - sessions_start

    context_payload, resolved_context_format = build_context_payload(
        workspace_content=workspace_content,
        sessions_content=sessions_content,
        context_format=args.context_format,
        pi_profile_name=args.pi_profile,
    )
    if isinstance(context_payload, list):
        full_context = "\n\n".join(context_payload)
        context_chunk_count = len(context_payload)
    else:
        full_context = context_payload
        context_chunk_count = 1
    context_chars = len(full_context)

    load_time = workspace_time + sessions_time
    print(
        f"[Async] Workspace load: {workspace_time:.2f}s | "
        f"Sessions load: {sessions_time:.2f}s | Total load: {load_time:.2f}s",
        file=sys.stderr,
    )

    if context_chars < 100:
        result = {
            "response": "Not enough history to analyze.",
            "status": "skipped",
        }
    else:
        rlm_start = time.perf_counter()
        try:
            result = run_rlm(
                query=args.query,
                context=context_payload,
                root_model=root_model,
                sub_model=sub_model,
                base_url=args.base_url,
                api_key=args.api_key,
                verbose=args.verbose,
                log_dir=args.log_dir,
                max_iterations=max_iterations,
                compaction=compaction,
                compaction_threshold=compaction_threshold,
                request_timeout=args.request_timeout,
                max_retries=max(0, args.max_retries),
                retry_backoff_seconds=max(0.0, args.retry_backoff_seconds),
            )
        except Exception as error:
            try:
                result = run_rlm(
                    query=args.query,
                    context=context_payload,
                    root_model=fallback_model,
                    sub_model=fallback_model,
                    base_url=args.base_url,
                    api_key=args.api_key,
                    verbose=args.verbose,
                    log_dir=args.log_dir,
                    max_iterations=max_iterations,
                    compaction=compaction,
                    compaction_threshold=compaction_threshold,
                    request_timeout=args.request_timeout,
                    max_retries=max(0, args.max_retries),
                    retry_backoff_seconds=max(0.0, args.retry_backoff_seconds),
                )
                result["fallback_reason"] = str(error)
            except Exception as fallback_error:
                result = {
                    "response": f"Error: Could not process. Primary: {error}, Fallback: {fallback_error}",
                    "status": "error",
                }

        rlm_time = time.perf_counter() - rlm_start
        result["rlm_time_seconds"] = round(rlm_time, 4)

    total_time = time.perf_counter() - total_start

    result["context_chars"] = context_chars
    result["context_chunks"] = context_chunk_count
    result["sessions_dir"] = args.sessions_dir
    result["workspace_dir"] = args.workspace
    result["timings"] = {
        "workspace_load_seconds": round(workspace_time, 4),
        "sessions_load_seconds": round(sessions_time, 4),
        "load_total_seconds": round(load_time, 4),
        "total_seconds": round(total_time, 4),
    }
    result["resolved_config"] = {
        "model_profile": args.profile_model,
        "pi_profile": args.pi_profile,
        "root_model": root_model,
        "sub_model": sub_model,
        "fallback_model": fallback_model,
        "max_sessions": max_sessions,
        "max_context_chars": max_context_chars,
        "max_iterations": max_iterations,
        "context_format": resolved_context_format,
        "compaction": compaction,
        "compaction_threshold": compaction_threshold,
        "request_timeout": args.request_timeout,
        "max_retries": max(0, args.max_retries),
        "retry_backoff_seconds": max(0.0, args.retry_backoff_seconds),
        "api_base_url": args.base_url,
        "agent_id": active_agent_id,
    }
    result.setdefault("status", "ok")

    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
