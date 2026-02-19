# Architecture

## Flow Diagram

```text
User (Telegram)
  |
  v
OpenClaw Gateway
  | Reads rlm-engine SKILL.md
  | Executes bridge command
  v
rlm_bridge.py
  |- Loads workspace docs (MEMORY.md, SOUL.md, etc.)
  |- Loads recent sessions (JSONL/MD)
  |- Applies limits (default: 30 sessions, 200K chars)
  |- Resolves model profile (cost/balanced/speed)
  |- Runs RLM with iterative REPL loop
  v
RLM (rlms)
  |- Root model: kimi-k2.5 (default)
  |- Sub model: kimi-k2.5 (default)
  |- Optional sub-model override (e.g., turbo-preview)
  |- Optional compaction for long iterative runs (best-effort by rlms version)
  v
Moonshot API (OpenAI-compatible)
  |- https://api.moonshot.ai/v1
  v
JSON result -> OpenClaw -> Telegram
```

## Core Components

### 1. OpenClaw Gateway
- Detects explicit `/rlm` requests.
- Invokes bridge through shell command.

### 2. `src/rlm_bridge.py`
- Session discovery: `find_sessions_dir()`
- JSONL parsing: `parse_jsonl_session_content()`
- Async session loading: `load_sessions_parallel()`
- Workspace loading: `load_workspace_sync()`
- RLM execution + retries: `run_rlm()`

### 3. RLM Runtime (`rlms`)
- Keeps default RLM system prompt behavior.
- Uses local REPL environment (`environment="local"`).
- Uses `max_depth=1` (current practical depth).
- Uses compatibility checks to pass optional kwargs (like compaction) only when supported by installed `rlms`.

### 4. Moonshot API
- OpenAI-compatible API endpoint.
- Auth via `MOONSHOT_API_KEY`.

## Runtime Controls

### Model profiles
- `cost` (default): root/sub `kimi-k2.5`, fallback `kimi-k2-turbo`
- `balanced`: same as `cost`
- `speed`: root `kimi-k2.5`, sub/fallback `kimi-k2-turbo-preview`

### Raspberry Pi profiles
- `off`: standard defaults
- `pi4`: smaller context/session limits + compaction preferred when available
- `pi8`: medium limits + compaction preferred when available

### Performance/safety flags
- `--max-sessions`
- `--max-context-chars`
- `--max-iterations`
- `--context-format auto|string|chunks`
- `--compaction` / `--no-compaction`
- `--compaction-threshold`
- `--agent-id`
- `--max-retries`
- `--request-timeout`

## Cost Estimation

Bridge output includes an estimated cost based on token usage summary and published per-model prices.
When cache-hit data is unavailable, input tokens are estimated with cache-miss pricing (conservative).
