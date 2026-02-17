# Troubleshooting

## Common issues

### API key not set

**Symptom:** Error "MOONSHOT_API_KEY environment variable not set"

**Cause:** The API key is not configured.

**Solution:**
```bash
# Set for current session
export MOONSHOT_API_KEY="sk-your-key-here"

# Or add to ~/.bashrc for persistence
echo 'export MOONSHOT_API_KEY="sk-your-key-here"' >> ~/.bashrc
source ~/.bashrc
```

Get your key at: https://platform.moonshot.ai/

### Rate limits (429)

**Symptom:** Message "Kimi API rate limit reached"

**Cause:** You've exceeded the Moonshot API rate limit.

**Solution:**
1. Wait a few minutes and try again
2. Use `memory_search` for simple questions (doesn't use RLM)
3. Check your usage at https://platform.moonshot.ai/

### Invalid API key (401)

**Symptom:** Authentication error on API calls

**Cause:** API key is invalid or expired.

**Solution:**
1. Verify your key at https://platform.moonshot.ai/
2. Generate a new key if needed
3. Update the environment variable:
   ```bash
   export MOONSHOT_API_KEY="sk-new-key-here"
   ```

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

**Symptom:** Process gets killed or system freezes.

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
1. Network issue with Moonshot API
2. Invalid API key
3. API service down

**Diagnosis:**
```bash
# Test API connectivity
curl -s https://api.moonshot.ai/v1/models \
  -H "Authorization: Bearer $MOONSHOT_API_KEY" | head
```

### Connection timeout to China endpoint

**Symptom:** Timeout errors on API calls

**Cause:** Network issues reaching Moonshot servers

**Solution:**
Try the alternate endpoint:
```bash
uv run python src/rlm_bridge.py \
  --query "..." \
  --base-url "https://api.moonshot.cn/v1"
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

### Check API key is set

```bash
echo $MOONSHOT_API_KEY
# Should show sk-... (not empty)
```

## Installation verification

```bash
# 1. Python and RLM
uv run python -c "from rlm import RLM; print('RLM OK')"

# 2. API key set
[ -n "$MOONSHOT_API_KEY" ] && echo "API key OK" || echo "API key NOT SET"

# 3. API connectivity
curl -s https://api.moonshot.ai/v1/models \
  -H "Authorization: Bearer $MOONSHOT_API_KEY" | grep -q "kimi" && echo "API OK"

# 4. OpenClaw
openclaw status

# 5. Skill deployed
ls ~/.openclaw/workspace/skills/rlm-engine/
```
