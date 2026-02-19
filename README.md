# OpenClaw RLM Skill

RLM bridge for deep, programmatic analysis of OpenClaw memory when users explicitly request `/rlm`.

This project keeps the core RLM behavior from Alex Zhang's repository:
- iterative REPL reasoning,
- recursive sub-LLM calls,
- default RLM system prompt (no custom override).

## Version

Current: `v4.2.0`

## What It Adds

- Moonshot/Kimi integration via OpenAI-compatible API.
- Async session loading for lower local I/O overhead.
- Model profiles (`cost`, `balanced`, `speed`).
- Raspberry Pi resource profiles (`pi4`, `pi8`).
- Optional compaction controls for long iterative runs (best-effort: depends on installed `rlms` API).
- Retry/timeout controls for transient API/network failures.
- Per-run cost estimate from token usage summary.

## Defaults

- Root model: `kimi-k2.5`
- Sub model: `kimi-k2.5`
- Fallback: `kimi-k2-turbo`
- Max sessions: `30`
- Max context chars: `200000`
- Max iterations: `5`
- Compaction: `off` (unless Pi profile enables it, and only if current `rlms` version supports compaction kwargs)

## Quick Start (Linux / Raspberry Pi OS)

`install.sh` uses `apt` for missing system packages, so it is intended for Debian/Ubuntu-based systems.

```bash
git clone https://github.com/goodmachinaii/openclaw-rlm-skill.git
cd openclaw-rlm-skill
./install.sh
```

Set API key:

```bash
export MOONSHOT_API_KEY="sk-your-key-here"
```

Run manually:

```bash
uv run python src/rlm_bridge.py --query "Summarize our infra decisions this week"
```

Important:
- Use `/rlm` only when triggering from OpenClaw chat.
- When you run `rlm_bridge.py` directly, pass the natural question without `/rlm` prefix.

## Recommended Invocations

### Cost-optimized (recommended)

```bash
uv run python src/rlm_bridge.py \
  --profile-model cost \
  --query "count how many times we discussed Docker"
```

### Faster sub-calls

```bash
uv run python src/rlm_bridge.py \
  --profile-model speed \
  --query "cluster all pending decisions by topic"
```

### Raspberry Pi 4GB safe profile

```bash
uv run python src/rlm_bridge.py \
  --pi-profile pi4 \
  --query "compare this week vs last week priorities"
```

### Long iterative runs with compaction

```bash
uv run python src/rlm_bridge.py \
  --compaction \
  --compaction-threshold 0.75 \
  --max-iterations 7 \
  --query "build a timeline of architecture changes"
```

## Main CLI Flags

- `--profile-model cost|balanced|speed`
- `--pi-profile off|pi4|pi8`
- `--root-model`, `--sub-model`, `--fallback-model`
- `--max-sessions`
- `--max-context-chars`
- `--max-iterations`
- `--context-format auto|string|chunks`
- `--compaction` / `--no-compaction`
- `--compaction-threshold`
- `--request-timeout`
- `--max-retries`
- `--retry-backoff-seconds`
- `--log-dir`
- `--agent-id`

## Pricing Notes (USD per 1M tokens)

As verified from Moonshot docs/forum (Feb 2026):

| Model | Input (cache miss) | Output | Cache hit |
|---|---:|---:|---:|
| `kimi-k2.5` | 0.60 | 3.00 | 0.10 |
| `kimi-k2-turbo-preview` | 1.15 | 8.00 | 0.15 |

Bridge cost estimate is conservative for input tokens when cache-hit details are unavailable.

## Output JSON Highlights

- `status`
- `response`
- `usage_summary`
- `cost_estimate`
- `timings`
- `resolved_config`

## Install / Dependency Notes

The Python package is `rlms`:

```bash
uv pip install "rlms>=0.1.0,<0.2.0"
```

## Tests

```bash
python3 -m pytest -q
```

## Project Structure

```text
src/rlm_bridge.py
skill/SKILL.md
tests/test_jsonl_parsing.py
tests/test_model_config.py
tests/test_fallback.py
tests/test_profiles.py
docs/ARCHITECTURE.md
docs/TROUBLESHOOTING.md
```

## License

MIT
