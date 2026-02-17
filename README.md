# OpenClaw RLM Skill

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-skill-purple.svg)](https://github.com/openclaw)
[![Platform](https://img.shields.io/badge/platform-ARM64%20%7C%20x86__64-lightgrey.svg)]()

> **On-demand deep programmatic reasoning over conversation history for OpenClaw.**
>
> Complements `memory_search` — only activates when you explicitly request `/rlm`.

[Español](README.es.md)

---

## Why This Exists

OpenClaw's built-in `memory_search` handles 90% of memory queries perfectly—it's fast (~100ms) and free. **Use it by default.**

This skill is for the remaining 10%: when you need to **programmatically analyze** your conversation history—counting occurrences, calculating statistics, or iterating over ALL sessions instead of just top matches.

[RLM (Recursive Language Models)](https://github.com/alexzhang13/rlm) executes Python code that reasons over your complete conversation history. It's slower (15-60s) and costs money (~$0.01-0.05/query), so it only activates when you explicitly request it.

## How It Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           User (Telegram)                               │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    OpenClaw Gateway                                     │
│  • Detects /rlm trigger                                                 │
│  • Reads skill/SKILL.md for invocation instructions                     │
│  • Sends "Analyzing your history..." to user                            │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         rlm_bridge.py                                   │
│  • Async loading: 0.1-0.2s (vs 3s sync)                                 │
│  • Auto-detects OpenClaw paths                                          │
│  • Parses JSONL sessions (extracts user + assistant)                    │
│  • Loads workspace: MEMORY.md, SOUL.md, daily notes                     │
│  • Enforces limits: 30 sessions, 200K chars                             │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              RLM                                        │
│  • Model: kimi-k2.5 (reasoning + execution, 256K context)               │
│  • 5 iterations: explore → chunk → analyze → consolidate                │
│  • Executes Python code in local REPL                                   │
│  • Automatic fallback to kimi-k2-turbo if primary fails                 │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Moonshot API                                        │
│  • OpenAI-compatible endpoint                                           │
│  • Pay-as-you-go (~$0.01-0.05 per query)                                │
│  • Direct HTTPS calls                                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

## Key Optimizations (v4.1)

| Feature | Before | After | Improvement |
|---------|--------|-------|-------------|
| **Session loading** | 3-5s (sync) | **0.1-0.2s (async)** | **20-30x faster** |
| **Iterations** | 20 (default) | **5 (optimized)** | **4x faster** |
| **Model** | kimi-k2-thinking + kimi-k2.5 | **kimi-k2.5 only** | Simpler, faster |
| **Context handling** | Load all at once | **Smart chunking** | Better for large history |

### Async Loading

Uses `aiofiles` and `asyncio.gather()` to read multiple session files in parallel:

```python
# Load 30 sessions in parallel
tasks = [read_session(file) for file in session_files]
results = await asyncio.gather(*tasks)  # ~0.15s total
```

### 5-Iteration Strategy

Following the [RLM paper](https://arxiv.org/abs/2512.24601), 5 iterations provide:

1. **Exploration** — Map the context structure
2. **Strategy** — Decide how to chunk and analyze
3. **Execution** — Generate code to process data
4. **Analysis** — Run code and collect results
5. **Consolidation** — Combine results into final answer

## When to Use

This skill uses **explicit activation only**. The user must request RLM analysis directly.

| User says | Tool used | Response Time |
|-----------|-----------|---------------|
| "What did we talk about yesterday?" | `memory_search` | ~100ms |
| "What was the API endpoint?" | `memory_search` | ~100ms |
| "/rlm how many times did we discuss Docker?" | **rlm-engine** | **20-60s** |
| "Use RLM to find patterns this month" | **rlm-engine** | **20-60s** |

### Trigger phrases

```
/rlm <question>
use RLM to...
analyze with RLM...
deep analysis of...
```

### Examples

```
✓ "/rlm compare what we discussed about the API last week vs today"
✓ "Use RLM to find the most frequent topics of the last month"
✓ "Analyze with RLM all pending decisions about infrastructure"

✗ "What was the API endpoint I mentioned?" → memory_search (no RLM trigger)
✗ "Find patterns in our chats" → memory_search (no explicit RLM request)
```

## Requirements

| Component | Requirement |
|-----------|-------------|
| Hardware | Raspberry Pi 4 (4GB+ RAM) or equivalent |
| OS | Debian 13+ ARM64 / any Linux x86_64 |
| OpenClaw | Installed and running |
| Python | 3.11+ |
| Node.js | 22+ |
| Moonshot API | API key from https://platform.moonshot.ai/ |

## Quick Start

```bash
# Clone and install
git clone https://github.com/angelgalvisc/openclaw-rlm-skill.git
cd openclaw-rlm-skill
./install.sh

# Configure API key (choose one method)
# Method 1: Environment variable
export MOONSHOT_API_KEY="sk-your-key-here"

# Method 2: Config file (recommended)
echo 'MOONSHOT_API_KEY="sk-your-key-here"' > config/moonshot.env
chmod 600 config/moonshot.env

# Restart OpenClaw
openclaw gateway restart
```

Test from Telegram:
> "/rlm what patterns do you see in our conversations this week?"

## Installation (Detailed)

### 1. Clone Repository

```bash
cd ~
git clone https://github.com/angelgalvisc/openclaw-rlm-skill.git
cd openclaw-rlm-skill
```

### 2. Run Installer

```bash
chmod +x install.sh
./install.sh
```

The installer will:
- Install Python 3.11+ and uv (if missing)
- Install RLM library and dependencies (incl. aiofiles)
- Deploy skill to `~/.openclaw/workspace/skills/rlm-engine/`

### 3. Configure API Key

Get your API key at https://platform.moonshot.ai/

**Option A: Environment variable (simple)**
```bash
export MOONSHOT_API_KEY="sk-your-key-here"
echo 'export MOONSHOT_API_KEY="sk-your-key-here"' >> ~/.bashrc
```

**Option B: Config file (recommended, more secure)**
```bash
# Create config file
echo 'MOONSHOT_API_KEY="sk-your-key-here"' > config/moonshot.env
# Set restrictive permissions (only owner can read)
chmod 600 config/moonshot.env
```

### 4. Restart OpenClaw

```bash
openclaw gateway restart
```

## Configuration

### CLI Options

```bash
uv run python src/rlm_bridge.py \
  --query "Your question" \
  --root-model kimi-k2.5 \         # Main model (reasoning + execution)
  --sub-model kimi-k2.5 \          # Same model for sub-calls
  --fallback-model kimi-k2-turbo \ # Backup if primary fails
  --max-sessions 30 \              # Limit sessions loaded
  --max-sessions 5 \               # Async: 30, Sync: 10-15
  --verbose \                      # Detailed output
  --log-dir /tmp/rlm-logs          # Save execution logs
```

### Memory Limits

| Resource | Default | Purpose |
|----------|---------|---------|
| Sessions | 30 | Safe for most queries |
| Total chars | 200K | ~50K tokens, safe for 4GB RAM |
| Daily notes | 200K chars | Cap for memory/*.md |
| Workspace files | 50K each | Skip oversized files |

**For Raspberry Pi with 4GB RAM:**
- Use `--max-sessions 10` for complex queries
- Use `--max-sessions 5` if you experience OOM kills

### Models

| Role | Default Model | Calls/Query | Notes |
|------|---------------|-------------|-------|
| Root LM | kimi-k2.5 | 5 | Unified reasoning + execution |
| Sub-LMs | kimi-k2.5 | (same) | Simplified architecture |
| Fallback | kimi-k2-turbo | varies | Automatic on failure |

**Why kimi-k2.5 only?**
- Simpler architecture (no separate thinking model)
- Faster on resource-constrained devices (Raspberry Pi)
- 256K context window sufficient for most analyses
- Better cost/performance ratio

### Cost

| Model | Input | Output | Typical usage |
|-------|-------|--------|---------------|
| kimi-k2.5 | ~$0.60/M | ~$2.50/M | 5 calls × ~2K tokens |
| **Per query** | | | **~$0.01-0.05** |

## Project Structure

```
openclaw-rlm-skill/
├── src/
│   └── rlm_bridge.py       # Main bridge (async-optimized)
│                           # - load_sessions_parallel(): async I/O
│                           # - parse_jsonl_session(): JSONL → text
│                           # - load_workspace(): MEMORY.md, etc.
│                           # - run_rlm(): execute with fallback
├── skill/
│   └── SKILL.md            # OpenClaw skill definition
├── config/
│   └── moonshot.env.example   # API key template (chmod 600)
├── tests/
│   ├── test_jsonl_parsing.py
│   ├── test_async_loading.py  # Async performance tests
│   └── test_model_config.py
├── scripts/
│   ├── setup-rlm.sh
│   └── deploy-skill.sh
├── install.sh              # One-command installer
├── pyproject.toml
└── README.md
```

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_async_loading.py -v

# Test async performance
uv run pytest tests/test_async_loading.py::test_load_sessions_speed -v
```

Tests use mocks—no API calls required.

## Debugging

### Enable Verbose Output

```bash
uv run python src/rlm_bridge.py --query "..." --verbose
```

### Monitor Performance

```bash
# Time the execution
time uv run python src/rlm_bridge.py --query "..." --max-sessions 10

# Expected output:
# [Async] Loaded 10 sessions in 0.15s
# [Async] Total loading time: 0.18s
# real    0m25.234s
```

### Save Execution Logs

```bash
uv run python src/rlm_bridge.py --query "..." --log-dir /tmp/rlm-logs
```

Logs are saved as `.jsonl` with full execution traces.

### Test API Connectivity

```bash
curl -s https://api.moonshot.ai/v1/models \
  -H "Authorization: Bearer $MOONSHOT_API_KEY" | head
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| API key not set | Set `MOONSHOT_API_KEY` env var or create `config/moonshot.env` |
| Rate limit (429) | Wait a few minutes or use `memory_search` |
| Invalid API key (401) | Verify key at https://platform.moonshot.ai/ |
| No sessions found | Check path: `ls ~/.openclaw/agents/*/sessions/*.jsonl` |
| Out of memory (OOM kill) | Reduce `--max-sessions 5` or `--max-sessions 3` |
| Slow loading (>1s) | Verify async: check `aiofiles` is installed |
| Connection timeout | Try alternate endpoint: `--base-url https://api.moonshot.cn/v1` |

### Raspberry Pi Specific Notes

**Expected performance on Pi 4 (4GB):**
- Loading: ~0.15s (async)
- Analysis: ~25-60s (depends on query complexity)
- Memory usage: ~100-200MB peak

**If you get SIGKILL/OOM:**
1. Reduce sessions: `--max-sessions 5`
2. Close other applications
3. Enable swap: `sudo dphys-swapfile setup && sudo dphys-swapfile swapon`

**If Gateway times out:**
The OpenClaw Gateway may have a shorter timeout than RLM needs. In this case, run RLM directly:
```bash
cd ~/openclaw-rlm-skill
source config/moonshot.env
uv run python src/rlm_bridge.py --query "your question"
```

## Security Considerations

- **API keys** stored in environment variables OR `config/moonshot.env` (chmod 600)
- **Session data** stays local—only queries are sent to Moonshot API
- **No telemetry** or external data collection
- **HTTPS only** for all API communications
- **File permissions**: Config files should be `600` (owner read-only)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`uv run pytest tests/ -v`)
4. Commit changes (`git commit -m 'Add amazing feature'`)
5. Push to branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## License

MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgments

- [RLM](https://github.com/alexzhang13/rlm) by Alex Zhang, Tim Kraska, Omar Khattab (MIT)
- [Moonshot AI](https://platform.moonshot.ai/) for Kimi models
- [OpenClaw](https://github.com/openclaw) ecosystem
- [aiofiles](https://github.com/Tinche/aiofiles) for async file I/O

## Changelog

### v4.1 (2026-02-17)
- **Added**: Async session loading (~0.15s vs 3s)
- **Changed**: Simplified to single model (kimi-k2.5)
- **Changed**: Optimized to 5 iterations (vs 20 default)
- **Added**: Secure config file support (`config/moonshot.env`)
- **Improved**: Better memory limits for Raspberry Pi
- **Added**: Detailed timing metrics in output
