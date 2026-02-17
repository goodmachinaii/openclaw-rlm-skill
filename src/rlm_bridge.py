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


def find_sessions_dir(openclaw_home: str = "~/.openclaw") -> str:
    """Auto-detect where OpenClaw stores sessions."""
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
    """Parse JSONL content to readable text."""
    lines: list[str] = []
    for raw_line in raw_content.strip().split("\n"):
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

    session_files: list[tuple[float, Path, str]] = []

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


async def process_session_file(filepath: Path, mtime: float, fmt: str) -> str | None:
    """Process one session file and return formatted text or None."""
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
        return f"=== SESSION:{session_name} DATE:{date_str} FMT:{fmt} ===\n{content}"
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

    tasks = [process_session_file(filepath, mtime, fmt) for mtime, filepath, fmt in session_files]
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
    for mtime, filepath, fmt in session_files:
        try:
            if fmt == "jsonl":
                content = parse_jsonl_session(filepath)
            else:
                content = filepath.read_text(encoding="utf-8", errors="ignore")

            if len(content.strip()) < 50:
                continue

            date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            session_name = filepath.stem
            parts.append(f"=== SESSION:{session_name} DATE:{date_str} FMT:{fmt} ===\n{content}")
        except (PermissionError, UnicodeDecodeError, OSError):
            continue

    return _assemble_session_parts(parts, max_chars)


def load_workspace_sync(workspace_dir: str, daily_chars_limit: int = 200_000) -> str:
    """Load workspace files (sync)."""
    workspace = Path(workspace_dir)
    parts: list[str] = []

    for filename in [
        "MEMORY.md",
        "SOUL.md",
        "AGENTS.md",
        "USER.md",
        "IDENTITY.md",
        "TOOLS.md",
    ]:
        filepath = workspace / filename
        if filepath.exists():
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
                if content.strip() and len(content) < 50_000:
                    parts.append(f"=== {filename} ===\n{content}")
            except (PermissionError, OSError) as error:
                parts.append(f"=== {filename} === [Error: {error}]")

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
    context: str,
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
        args.sessions_dir = find_sessions_dir()

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

    full_context = f"{workspace_content}\n\n{'=' * 60}\n\n{sessions_content}"
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
                context=full_context,
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
                    context=full_context,
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
        "compaction": compaction,
        "compaction_threshold": compaction_threshold,
        "request_timeout": args.request_timeout,
        "max_retries": max(0, args.max_retries),
        "retry_backoff_seconds": max(0.0, args.retry_backoff_seconds),
        "api_base_url": args.base_url,
    }
    result.setdefault("status", "ok")

    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
