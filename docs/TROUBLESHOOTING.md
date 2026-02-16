# Troubleshooting

## Problemas comunes

### Rate limits (429)

**Síntoma:** Mensaje "Tu cuota de ChatGPT está alcanzada"

**Causa:** Has excedido el límite de requests de tu suscripción ChatGPT.

**Solución:**
1. Espera unos minutos y vuelve a intentar
2. Usa `memory_search` para preguntas simples (no consume cuota RLM)
3. Considera usar menos el skill durante períodos de alto uso

### CLIProxyAPI no compila en ARM64

**Síntoma:** Error al ejecutar `go build`

**Causa:** Problemas con dependencias de Go en ARM64.

**Soluciones:**

1. Verificar versión de Go:
   ```bash
   go version
   # Debe ser >= 1.20
   ```

2. Actualizar Go:
   ```bash
   sudo apt update && sudo apt install -y golang
   ```

3. **Alternativa: 9Router (JavaScript)**
   Si Go no funciona, puedes usar 9Router que corre con Node.js:
   https://github.com/mqa8668/9router-ha

### OAuth token expirado

**Síntoma:** Error 401 al hacer requests

**Causa:** El token OAuth ha expirado.

**Solución:**
1. Abrir http://localhost:8317/management.html
2. Re-autenticarte con tu cuenta ChatGPT
3. El proxy guarda el nuevo token automáticamente

> TODO: Verificar en la Pi los pasos exactos del flujo OAuth. Depende de la versión de CLIProxyAPI instalada.

### Rutas de OpenClaw no encontradas

**Síntoma:** "No hay sesiones disponibles" pero sabes que tienes sesiones.

**Causa:** El bridge no encuentra el directorio de sesiones.

**Diagnóstico:**
```bash
# Verificar estructura de OpenClaw
ls -la ~/.openclaw/
ls -la ~/.openclaw/agents/
ls -la ~/.openclaw/agents/*/sessions/
```

**Solución:**
Especificar la ruta manualmente:
```bash
uv run python src/rlm_bridge.py \
  --query "test" \
  --sessions-dir "/ruta/correcta/sessions"
```

### Memoria insuficiente

**Síntoma:** El proceso se mata o el Pi se congela.

**Causa:** Intentando cargar demasiadas sesiones en 8GB RAM.

**Solución:**
1. Reducir número de sesiones:
   ```bash
   uv run python src/rlm_bridge.py \
     --query "..." \
     --max-sessions 15
   ```

2. El bridge ya tiene límites seguros (30 sesiones, 2M chars), pero si tienes sesiones muy largas, reduce más.

### RLM no responde (timeout)

**Síntoma:** El comando se queda colgado sin respuesta.

**Causas posibles:**
1. CLIProxyAPI no está corriendo
2. Problema de red con OpenAI
3. Sesión OAuth inválida

**Diagnóstico:**
```bash
# Verificar que CLIProxyAPI está corriendo
curl http://localhost:8317/health

# Ver logs de CLIProxyAPI
journalctl --user -u cliproxyapi -f
```

### Tests fallan

**Síntoma:** `pytest` reporta errores.

**Solución:**
```bash
# Instalar dependencias de desarrollo
uv pip install pytest

# Ejecutar tests con verbose
uv run pytest tests/ -v --tb=short
```

## Logs y debugging

### Activar verbose en RLM

```bash
uv run python src/rlm_bridge.py \
  --query "..." \
  --verbose
```

### Guardar logs de RLM

```bash
uv run python src/rlm_bridge.py \
  --query "..." \
  --log-dir /tmp/rlm-logs
```

Los logs se guardan en formato `.jsonl` y pueden visualizarse con el visualizador de RLM.

### Ver logs de CLIProxyAPI

```bash
# Si corre como servicio systemd
journalctl --user -u cliproxyapi -f

# Si corre en terminal
# Los logs aparecen directamente en stdout
```

## Verificación de instalación

```bash
# 1. Python y RLM
uv run python -c "from rlm import RLM; print('RLM OK')"

# 2. CLIProxyAPI
curl -s http://localhost:8317/health && echo "CLIProxyAPI OK"

# 3. OpenClaw
openclaw status

# 4. Skill desplegado
ls ~/.openclaw/workspace/skills/rlm-engine/
```
