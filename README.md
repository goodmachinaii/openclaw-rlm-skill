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

[RLM (Recursive Language Models)](https://github.com/alexzhang13/rlm) executes Python code that reasons over your complete conversation history. It's slower (15-45s) and costs money (~$0.01-0.05/query), so it only activates when you explicitly request it.

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
│  • Root LM: kimi-k2-thinking (decides analysis strategy, 1 call)        │
│  • Sub-LMs: kimi-k2.5 (navigate context, 2-7 calls, 256K context)       │
│  • Executes Python code in local REPL                                   │
│  • Automatic fallback to kimi-k2-turbo if primary fails                 │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Moonshot API (api.moonshot.ai)                      │
│  • OpenAI-compatible endpoint                                           │
│  • Pay-as-you-go (~$0.01-0.05 per query)                                │
│  • Direct HTTPS calls (no proxy needed)                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

## When to Use

This skill uses **explicit activation only**. The user must request RLM analysis directly.

| User says | Tool used | Response Time |
|-----------|-----------|---------------|
| "What did we talk about yesterday?" | `memory_search` | ~100ms |
| "What was the API endpoint?" | `memory_search` | ~100ms |
| "/rlm how many times did we discuss Docker?" | **rlm-engine** | 15-45s |
| "Use RLM to find patterns this month" | **rlm-engine** | 15-45s |

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
| Hardware | Raspberry Pi 4 (8GB RAM) or equivalent |
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

# Set your API key
export MOONSHOT_API_KEY="sk-your-key-here"

# Or add to ~/.bashrc for persistence
echo 'export MOONSHOT_API_KEY="sk-your-key-here"' >> ~/.bashrc
source ~/.bashrc

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
- Install RLM library
- Deploy skill to `~/.openclaw/workspace/skills/rlm-engine/`

### 3. Configure API Key

Get your API key at https://platform.moonshot.ai/

```bash
# Set for current session
export MOONSHOT_API_KEY="sk-your-key-here"

# For persistence, add to your shell config
echo 'export MOONSHOT_API_KEY="sk-your-key-here"' >> ~/.bashrc
source ~/.bashrc
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
  --root-model kimi-k2-thinking \   # Main reasoning model
  --sub-model kimi-k2.5 \           # Context navigation (256K context)
  --fallback-model kimi-k2-turbo \  # Used if primary fails
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
| Root LM | kimi-k2-thinking | 1 | Main reasoning, complex analysis |
| Sub-LMs | kimi-k2.5 | 2-7 | Context navigation, 256K window |
| Fallback | kimi-k2-turbo | varies | Automatic on failure |

### Cost

| Model | Input | Output | Typical usage |
|-------|-------|--------|---------------|
| kimi-k2-thinking | ~$0.60/M | ~$2.50/M | 1 call (root) |
| kimi-k2.5 | ~$0.60/M | ~$2.50/M | 2-7 calls (sub) |
| **Per query** | | | **~$0.01-0.05** |

## Project Structure

```
openclaw-rlm-skill/
├── src/
│   └── rlm_bridge.py       # Main bridge
│                           # - find_sessions_dir(): auto-detect paths
│                           # - parse_jsonl_session(): JSONL → text
│                           # - load_workspace(): MEMORY.md, SOUL.md, etc.
│                           # - load_sessions(): up to 30 sessions
│                           # - run_rlm(): execute with fallback
├── skill/
│   └── SKILL.md            # OpenClaw skill definition
├── tests/
│   ├── test_jsonl_parsing.py  # JSONL parsing tests
│   ├── test_model_config.py   # Model configuration tests
│   └── test_fallback.py       # Fallback behavior tests
├── scripts/
│   ├── setup-rlm.sh
│   └── deploy-skill.sh
├── config/
│   └── moonshot.env.example   # API key template
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
uv run pytest tests/test_jsonl_parsing.py -v
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

### Test API Connectivity

```bash
curl -s https://api.moonshot.ai/v1/models \
  -H "Authorization: Bearer $MOONSHOT_API_KEY" | head
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| API key not set | `export MOONSHOT_API_KEY="sk-..."` |
| Rate limit (429) | Wait a few minutes or use `memory_search` |
| Invalid API key (401) | Verify key at https://platform.moonshot.ai/ |
| No sessions found | Check path: `ls ~/.openclaw/agents/*/sessions/*.jsonl` |
| Out of memory | Reduce `--max-sessions 15` |
| Connection timeout | Try alternate endpoint: `--base-url https://api.moonshot.cn/v1` |

Full troubleshooting guide: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

## Security Considerations

- **API keys** stored as environment variables (not in code)
- **Session data** stays local—only queries are sent to Moonshot API
- **No telemetry** or external data collection
- **HTTPS only** for all API communications

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
- [Moonshot AI](https://platform.moonshot.ai/) for Kimi models
- [OpenClaw](https://github.com/openclaw) ecosystem
