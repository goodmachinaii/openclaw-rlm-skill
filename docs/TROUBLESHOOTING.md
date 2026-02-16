# Troubleshooting

## Common issues

### Rate limits (429)

**Symptom:** Message "Your ChatGPT quota is reached"

**Cause:** You've exceeded your ChatGPT subscription request limit.

**Solution:**
1. Wait a few minutes and try again
2. Use `memory_search` for simple questions (doesn't consume RLM quota)
3. Consider using the skill less during high-usage periods

### CLIProxyAPI doesn't compile on ARM64

**Symptom:** Error when running `go build`

**Cause:** Go dependency issues on ARM64.

**Solutions:**

1. Verify Go version:
   ```bash
   go version
   # Should be >= 1.20
   ```

2. Update Go:
   ```bash
   sudo apt update && sudo apt install -y golang
   ```

3. **Alternative: 9Router (JavaScript)**
   If Go doesn't work, you can use 9Router which runs on Node.js:
   https://github.com/mqa8668/9router-ha

### OAuth token expired

**Symptom:** 401 error on requests

**Cause:** OAuth token has expired.

**Solution:**
1. Open http://localhost:8317/management.html
2. Re-authenticate with your ChatGPT account
3. The proxy saves the new token automatically

> TODO: Verify exact OAuth flow steps on the Pi. Depends on installed CLIProxyAPI version.

### OpenClaw paths not found

**Symptom:** "No sessions available" but you know you have sessions.

**Cause:** Bridge can't find sessions directory.

**Diagnosis:**
```bash
# Verify OpenClaw structure
ls -la ~/.openclaw/
ls -la ~/.openclaw/agents/
ls -la ~/.openclaw/agents/*/sessions/
```

**Solution:**
Specify path manually:
```bash
uv run python src/rlm_bridge.py \
  --query "test" \
  --sessions-dir "/correct/path/sessions"
```

### Insufficient memory

**Symptom:** Process gets killed or Pi freezes.

**Cause:** Trying to load too many sessions in 8GB RAM.

**Solution:**
1. Reduce number of sessions:
   ```bash
   uv run python src/rlm_bridge.py \
     --query "..." \
     --max-sessions 15
   ```

2. Bridge already has safe limits (30 sessions, 2M chars), but if you have very long sessions, reduce further.

### RLM not responding (timeout)

**Symptom:** Command hangs without response.

**Possible causes:**
1. CLIProxyAPI not running
2. Network issue with OpenAI
3. Invalid OAuth session

**Diagnosis:**
```bash
# Verify CLIProxyAPI is running
curl http://localhost:8317/health

# View CLIProxyAPI logs
journalctl --user -u cliproxyapi -f
```

### Tests fail

**Symptom:** `pytest` reports errors.

**Solution:**
```bash
# Install dev dependencies
uv pip install pytest

# Run tests with verbose
uv run pytest tests/ -v --tb=short
```

## Logs and debugging

### Enable verbose in RLM

```bash
uv run python src/rlm_bridge.py \
  --query "..." \
  --verbose
```

### Save RLM logs

```bash
uv run python src/rlm_bridge.py \
  --query "..." \
  --log-dir /tmp/rlm-logs
```

Logs are saved in `.jsonl` format and can be viewed with RLM visualizer.

### View CLIProxyAPI logs

```bash
# If running as systemd service
journalctl --user -u cliproxyapi -f

# If running in terminal
# Logs appear directly on stdout
```

## Installation verification

```bash
# 1. Python and RLM
uv run python -c "from rlm import RLM; print('RLM OK')"

# 2. CLIProxyAPI
curl -s http://localhost:8317/health && echo "CLIProxyAPI OK"

# 3. OpenClaw
openclaw status

# 4. Skill deployed
ls ~/.openclaw/workspace/skills/rlm-engine/
```
