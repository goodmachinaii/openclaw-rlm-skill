# OpenClaw RLM Skill

Bridge RLM para análisis profundo y programático de memoria en OpenClaw cuando el usuario pide explícitamente `/rlm`.

Mantiene la esencia del repositorio original de Alex Zhang:
- razonamiento iterativo en REPL,
- sub-llamadas recursivas a LLM,
- sin override del system prompt de RLM.

## Versión

Actual: `v4.2.1`

## Qué agrega esta versión

- Integración Moonshot/Kimi (API compatible con OpenAI).
- Carga asíncrona de sesiones.
- Perfiles de modelo (`cost`, `balanced`, `speed`).
- Perfiles Raspberry Pi (`pi4`, `pi8`).
- Compaction opcional para corridas largas (best-effort: depende de la API de `rlms` instalada).
- Reintentos y timeout configurables.
- Estimación de costo por corrida usando uso real de tokens.

## Defaults

- Root model: `kimi-k2.5`
- Sub model: `kimi-k2.5`
- Fallback: `kimi-k2-turbo`
- Sesiones máximas: `30`
- Contexto máximo: `200000` chars
- Iteraciones máximas: `5`
- Compaction: `off` (salvo que el perfil Pi lo active, y solo si la versión actual de `rlms` soporta esos kwargs)

## Inicio rápido (Linux / Raspberry Pi OS)

`install.sh` usa `apt` para paquetes del sistema, así que está orientado a Debian/Ubuntu.

```bash
git clone https://github.com/goodmachinaii/openclaw-rlm-skill.git
cd openclaw-rlm-skill
./install.sh
```

Configura API key:

```bash
export MOONSHOT_API_KEY="sk-your-key-here"
```

Ejecución básica:

```bash
uv run python src/rlm_bridge.py --query "Resume decisiones de infraestructura de esta semana"
```

Importante:
- Usa `/rlm` solo cuando activas el skill desde el chat de OpenClaw.
- Si ejecutas `rlm_bridge.py` directo, pasa la pregunta normal sin prefijo `/rlm`.

## Comandos recomendados

### Costo optimizado (recomendado)

```bash
uv run python src/rlm_bridge.py \
  --profile-model cost \
  --query "cuántas veces hablamos de Docker"
```

### Menor latencia en sub-llamadas

```bash
uv run python src/rlm_bridge.py \
  --profile-model speed \
  --query "agrupa decisiones pendientes por tema"
```

### Raspberry Pi 4GB

```bash
uv run python src/rlm_bridge.py \
  --pi-profile pi4 \
  --query "compara prioridades de esta semana vs la pasada"
```

### Corridas largas con compaction

```bash
uv run python src/rlm_bridge.py \
  --compaction \
  --compaction-threshold 0.75 \
  --max-iterations 7 \
  --query "construye una línea de tiempo de cambios de arquitectura"
```

## Flags principales

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

## Precios (USD por 1M tokens)

Verificados en docs/foro Moonshot (febrero 2026):

| Modelo | Input (cache miss) | Output | Cache hit |
|---|---:|---:|---:|
| `kimi-k2.5` | 0.60 | 3.00 | 0.10 |
| `kimi-k2-turbo-preview` | 1.15 | 8.00 | 0.15 |

La estimación de costo del bridge es conservadora para input cuando no hay detalle de cache hit.

## Salida JSON clave

- `status`
- `response`
- `usage_summary`
- `cost_estimate`
- `timings`
- `resolved_config`

## Dependencias

El paquete correcto es `rlms`:

```bash
uv pip install "rlms>=0.1.0,<0.2.0"
```

## Tests

```bash
python3 -m pytest -q
```

## Licencia

MIT
