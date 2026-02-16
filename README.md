# OpenClaw RLM Skill

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-skill-purple.svg)](https://github.com/openclaw)
[![Platform](https://img.shields.io/badge/platform-ARM64%20%7C%20x86__64-lightgrey.svg)]()

> **Deep programmatic reasoning over conversation history for OpenClaw.**

[Español](README.es.md)

---

## Why This Exists

OpenClaw's built-in `memory_search` is fast (milliseconds) but limited to returning short snippets. When you need to **reason** over your conversation history—cross-referencing sessions, finding patterns, or analyzing trends—you need something more powerful.

This skill integrates [RLM (Recursive Language Models)](https://github.com/alexzhang13/rlm) to execute Python code that reasons over your complete conversation history, enabling complex queries that simple search cannot answer.

## How It Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           User (Telegram)                               │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    OpenClaw Gateway (port 18789)                        │
│  • Detects question requires deep analysis                              │
│  • Reads skill/SKILL.md for invocation instructions                     │
│  • Sends "Analyzing your history..." to user                            │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         rlm_bridge.py                                   │
│  • Auto-detects OpenClaw paths (~/.openclaw/agents/*/sessions/)         │
│  • Parses JSONL sessions (extracts user + assistant, ignores tools)     │
│  • Loads workspace: MEMORY.md, SOUL.md, daily notes                     │
│  • Enforces memory limits: 30 sessions, 2M chars max                    │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              RLM                                        │
│  • Root LM decides analysis strategy (1 call)                           │
│  • Sub-LMs navigate context (2-7 calls, 4x cheaper)                     │
│  • Executes Python code in local REPL                                   │
│  • Automatic fallback if primary model fails                            │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    CLIProxyAPI (port 8317)                              │
│  • Converts API calls to OAuth (uses your ChatGPT subscription)         │
│  • $0 additional cost                                                   │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
                          OpenAI servers
```

## When to Use

| Scenario | Tool | Response Time |
|----------|------|---------------|
| Find a specific fact mentioned once | `memory_search` | ~100ms |
| Cross-reference multiple sessions | **rlm-engine** | 15-45s |
| Analyze patterns or trends | **rlm-engine** | 15-45s |
| Count occurrences across history | **rlm-engine** | 15-45s |
| Summarize everything on a topic | **rlm-engine** | 15-45s |

**Examples:**

```
✓ rlm-engine: "Compare what we discussed about the API last week vs today"
✓ rlm-engine: "What are the most frequent topics of the last month?"
✓ rlm-engine: "Find all pending decisions about infrastructure"

✗ memory_search: "What was the API endpoint I mentioned?"
✗ memory_search: "What was the command to restart the server?"
```

## Requirements

| Component | Requirement |
|-----------|-------------|
| Hardware | Raspberry Pi 4 (8GB RAM) or equivalent |
| OS | Debian 13+ ARM64 / any Linux x86_64 |
| OpenClaw | Installed and running |
| Python | 3.11+ |
| Node.js | 22+ |
| ChatGPT | Pro or Max subscription (for OAuth) |

## Quick Start

```bash
# Clone and install
git clone https://github.com/angelgalvisc/openclaw-rlm-skill.git
cd openclaw-rlm-skill
./install.sh

# Start CLIProxyAPI and authenticate
cli-proxy-api --config ~/.cli-proxy-api/config.yaml
# Open http://localhost:8317/management.html → login with ChatGPT

# Restart OpenClaw
openclaw gateway restart
```

Test from Telegram:
> "What have we talked about this week?"

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
- Install RLM library
- Compile CLIProxyAPI from source (for ARM64)
- Deploy skill to `~/.openclaw/workspace/skills/rlm-engine/`

### 3. Configure OAuth

```bash
# Start proxy
cli-proxy-api --config ~/.cli-proxy-api/config.yaml

# Open browser and authenticate
open http://localhost:8317/management.html
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
  --root-model gpt-5.3-codex \      # Main reasoning model
  --sub-model gpt-5.1-codex-mini \  # Context navigation (4x cheaper)
  --fallback-model gpt-5.2 \        # Used if primary fails
  --max-sessions 30 \               # Limit sessions loaded
  --verbose \                       # Detailed output
  --log-dir /tmp/rlm-logs           # Save execution logs
```

### Memory Limits

| Resource | Default | Purpose |
|----------|---------|---------|
| Sessions | 30 | Prevent timeout |
| Total chars | 2M | Safe for 8GB RAM (~500K tokens) |
| Daily notes | 200K chars | Cap for memory/*.md |
| Workspace files | 50K each | Skip oversized files |

### Models

| Role | Default Model | Calls/Query | Notes |
|------|---------------|-------------|-------|
| Root LM | gpt-5.3-codex | 1 | Main reasoning |
| Sub-LMs | gpt-5.1-codex-mini | 2-7 | 4x more quota efficient |
| Fallback | gpt-5.2 | varies | Automatic on failure |

## Project Structure

```
openclaw-rlm-skill/
├── src/
│   └── rlm_bridge.py       # Main bridge (382 lines)
│                           # - find_sessions_dir(): auto-detect paths
│                           # - parse_jsonl_session(): JSONL → text
│                           # - load_workspace(): MEMORY.md, SOUL.md, etc.
│                           # - load_sessions(): up to 30 sessions
│                           # - run_rlm(): execute with fallback
├── skill/
│   └── SKILL.md            # OpenClaw skill definition
├── tests/
│   ├── test_basico.py      # JSONL parsing tests
│   ├── test_modelos.py     # Model configuration tests
│   └── test_fallback.py    # Fallback behavior tests
├── scripts/
│   ├── setup-cliproxyapi.sh
│   ├── setup-rlm.sh
│   └── deploy-skill.sh
├── config/
│   ├── cliproxyapi-example.yaml
│   └── cliproxyapi.service  # systemd unit
├── docs/
│   ├── ARCHITECTURE.md
│   └── TROUBLESHOOTING.md
├── install.sh              # One-command installer
└── pyproject.toml
```

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_basico.py -v
```

Tests use mocks—no API calls required.

## Debugging

### Enable Verbose Output

```bash
uv run python src/rlm_bridge.py --query "..." --verbose
```

### Save Execution Logs

```bash
uv run python src/rlm_bridge.py --query "..." --log-dir /tmp/rlm-logs
```

Logs are saved as `.jsonl` and can be visualized with RLM's built-in visualizer:

```bash
cd ~/rlm/visualizer && npm run dev
# Open http://localhost:3001
```

### View CLIProxyAPI Logs

```bash
journalctl --user -u cliproxyapi -f
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Rate limit (429) | Wait a few minutes or use `memory_search` |
| OAuth expired (401) | Re-authenticate at http://localhost:8317/management.html |
| No sessions found | Check path: `ls ~/.openclaw/agents/*/sessions/*.jsonl` |
| Out of memory | Reduce `--max-sessions 15` |
| CLIProxyAPI won't compile | See [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for alternatives |

Full troubleshooting guide: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

## Security Considerations

- **OAuth tokens** are stored by CLIProxyAPI in `~/.cli-proxy-api/`
- **API keys** for CLIProxyAPI are placeholder strings (not real secrets)
- **Session data** stays local—only queries are sent to OpenAI
- **No telemetry** or external data collection

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

- [RLM](https://github.com/alexzhang13/rlm) by Alex Zhang
- [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) for OAuth proxy
- [OpenClaw](https://github.com/openclaw) ecosystem
