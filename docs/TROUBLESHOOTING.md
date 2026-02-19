# Troubleshooting

## Common Issues

### API key not set

Symptom: `MOONSHOT_API_KEY not set`

```bash
export MOONSHOT_API_KEY="sk-your-key-here"
```

### Rate limit (429) or quota

Symptom: status `rate_limited`

Actions:
1. Wait and retry.
2. Use `memory_search` for lightweight questions.
3. Check account usage in Moonshot console.

### Invalid API key (401)

Symptom: authentication failure.

Actions:
1. Regenerate key at Moonshot platform.
2. Update environment variable.

### Sessions not found

Symptom: `No sessions available`

Actions:
```bash
ls -la ~/.openclaw/
ls -la ~/.openclaw/agents/*/sessions/
```

Then run with explicit path:

```bash
uv run python src/rlm_bridge.py --query "test" --sessions-dir "/correct/path/sessions"
```

### Skill does not activate from chat

Symptom: normal chat question does not run RLM skill.

Actions:
1. Use explicit trigger in OpenClaw chat: `/rlm <question>`.
2. If running bridge directly from terminal, do **not** include `/rlm` in `--query`.

### Slow responses on Raspberry Pi

Likely causes:
- Iterative RLM calls dominate latency (not file loading).
- Too much context for device/network.

Use Pi profile and tighter limits:

```bash
uv run python src/rlm_bridge.py \
  --query "..." \
  --pi-profile pi4 \
  --max-sessions 6 \
  --max-context-chars 100000 \
  --max-iterations 4
```

### Timeouts / transient network errors

Bridge supports retries for transient failures.

```bash
uv run python src/rlm_bridge.py \
  --query "..." \
  --request-timeout 90 \
  --max-retries 2
```

### Install fails for RLM package

Use `rlms` package name:

```bash
uv pip install "rlms>=0.1.0,<0.2.0"
```

### `unexpected keyword argument 'compaction'`

Symptom: older bridge/code path or mismatched environment throws constructor error.

Actions:
1. Pull latest bridge code (v4.2.1+), which applies compatibility by `RLM.__init__` signature.
2. Reinstall dependencies in the skill folder:

```bash
uv venv --python 3.12 2>/dev/null || uv venv
uv pip install "rlms>=0.1.0,<0.2.0"
```

## Debugging Aids

### Verbose mode

```bash
uv run python src/rlm_bridge.py --query "..." --verbose
```

### Save trajectory logs

```bash
uv run python src/rlm_bridge.py --query "..." --log-dir /tmp/rlm-logs
```

### Validate API connectivity

```bash
curl -s https://api.moonshot.ai/v1/models \
  -H "Authorization: Bearer $MOONSHOT_API_KEY" | head
```

## Output fields to inspect

- `status`
- `timings`
- `resolved_config`
- `usage_summary`
- `cost_estimate`
