# OpenClaw RLM Skill

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-skill-purple.svg)](https://github.com/openclaw)
[![Platform](https://img.shields.io/badge/platform-ARM64%20%7C%20x86__64-lightgrey.svg)]()

> **Razonamiento programático profundo sobre historial de conversaciones para OpenClaw.**

[English](README.md)

---

## Por Qué Existe

El `memory_search` integrado de OpenClaw es rápido (milisegundos) pero está limitado a devolver fragmentos cortos. Cuando necesitas **razonar** sobre tu historial de conversaciones—cruzar sesiones, encontrar patrones o analizar tendencias—necesitas algo más potente.

Este skill integra [RLM (Recursive Language Models)](https://github.com/alexzhang13/rlm) para ejecutar código Python que razona sobre tu historial completo de conversaciones, habilitando consultas complejas que la búsqueda simple no puede responder.

## Cómo Funciona

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Usuario (Telegram)                             │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    OpenClaw Gateway (puerto 18789)                      │
│  • Detecta que la pregunta requiere análisis profundo                   │
│  • Lee skill/SKILL.md para instrucciones de invocación                  │
│  • Envía "Analizando tu historial..." al usuario                        │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         rlm_bridge.py                                   │
│  • Auto-detecta rutas de OpenClaw (~/.openclaw/agents/*/sessions/)      │
│  • Parsea sesiones JSONL (extrae user + assistant, ignora tools)        │
│  • Carga workspace: MEMORY.md, SOUL.md, notas diarias                   │
│  • Aplica límites de memoria: 30 sesiones, 2M chars máx                 │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              RLM                                        │
│  • Root LM decide estrategia de análisis (1 llamada)                    │
│  • Sub-LMs navegan contexto (2-7 llamadas, 4x más barato)               │
│  • Ejecuta código Python en REPL local                                  │
│  • Fallback automático si el modelo primario falla                      │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    CLIProxyAPI (puerto 8317)                            │
│  • Convierte llamadas API a OAuth (usa tu suscripción ChatGPT)          │
│  • $0 costo adicional                                                   │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
                          Servidores OpenAI
```

## Cuándo Usar

| Escenario | Herramienta | Tiempo de Respuesta |
|-----------|-------------|---------------------|
| Buscar un dato específico mencionado una vez | `memory_search` | ~100ms |
| Cruzar información de múltiples sesiones | **rlm-engine** | 15-45s |
| Analizar patrones o tendencias | **rlm-engine** | 15-45s |
| Contar ocurrencias en el historial | **rlm-engine** | 15-45s |
| Resumir todo sobre un tema | **rlm-engine** | 15-45s |

**Ejemplos:**

```
✓ rlm-engine: "Compara lo que discutimos sobre la API la semana pasada vs hoy"
✓ rlm-engine: "¿Cuáles son los temas más frecuentes del último mes?"
✓ rlm-engine: "Encuentra todas las decisiones pendientes sobre infraestructura"

✗ memory_search: "¿Cuál era el endpoint de la API que mencioné?"
✗ memory_search: "¿Cuál era el comando para reiniciar el servidor?"
```

## Requisitos

| Componente | Requisito |
|------------|-----------|
| Hardware | Raspberry Pi 4 (8GB RAM) o equivalente |
| OS | Debian 13+ ARM64 / cualquier Linux x86_64 |
| OpenClaw | Instalado y funcionando |
| Python | 3.11+ |
| Node.js | 22+ |
| ChatGPT | Suscripción Pro o Max (para OAuth) |

## Inicio Rápido

```bash
# Clonar e instalar
git clone https://github.com/angelgalvisc/openclaw-rlm-skill.git
cd openclaw-rlm-skill
./install.sh

# Iniciar CLIProxyAPI y autenticarse
cli-proxy-api --config ~/.cli-proxy-api/config.yaml
# Abrir http://localhost:8317/management.html → login con ChatGPT

# Reiniciar OpenClaw
openclaw gateway restart
```

Probar desde Telegram:
> "¿De qué hemos hablado esta semana?"

## Instalación (Detallada)

### 1. Clonar Repositorio

```bash
cd ~
git clone https://github.com/angelgalvisc/openclaw-rlm-skill.git
cd openclaw-rlm-skill
```

### 2. Ejecutar Instalador

```bash
chmod +x install.sh
./install.sh
```

El instalador:
- Instala Python 3.11+ y uv (si faltan)
- Instala la biblioteca RLM
- Compila CLIProxyAPI desde source (para ARM64)
- Despliega el skill a `~/.openclaw/workspace/skills/rlm-engine/`

### 3. Configurar OAuth

```bash
# Iniciar proxy
cli-proxy-api --config ~/.cli-proxy-api/config.yaml

# Abrir navegador y autenticarse
open http://localhost:8317/management.html
```

### 4. Reiniciar OpenClaw

```bash
openclaw gateway restart
```

## Configuración

### Opciones CLI

```bash
uv run python src/rlm_bridge.py \
  --query "Tu pregunta" \
  --root-model gpt-5.3-codex \      # Modelo principal de razonamiento
  --sub-model gpt-5.1-codex-mini \  # Navegación de contexto (4x más barato)
  --fallback-model gpt-5.2 \        # Usado si el primario falla
  --max-sessions 30 \               # Límite de sesiones cargadas
  --verbose \                       # Salida detallada
  --log-dir /tmp/rlm-logs           # Guardar logs de ejecución
```

### Límites de Memoria

| Recurso | Default | Propósito |
|---------|---------|-----------|
| Sesiones | 30 | Prevenir timeout |
| Chars totales | 2M | Seguro para 8GB RAM (~500K tokens) |
| Notas diarias | 200K chars | Límite para memory/*.md |
| Archivos workspace | 50K c/u | Omitir archivos muy grandes |

### Modelos

| Rol | Modelo Default | Llamadas/Query | Notas |
|-----|----------------|----------------|-------|
| Root LM | gpt-5.3-codex | 1 | Razonamiento principal |
| Sub-LMs | gpt-5.1-codex-mini | 2-7 | 4x más eficiente en cuota |
| Fallback | gpt-5.2 | varía | Automático al fallar |

## Estructura del Proyecto

```
openclaw-rlm-skill/
├── src/
│   └── rlm_bridge.py       # Bridge principal (382 líneas)
│                           # - find_sessions_dir(): auto-detecta rutas
│                           # - parse_jsonl_session(): JSONL → texto
│                           # - load_workspace(): MEMORY.md, SOUL.md, etc.
│                           # - load_sessions(): hasta 30 sesiones
│                           # - run_rlm(): ejecuta con fallback
├── skill/
│   └── SKILL.md            # Definición del skill para OpenClaw
├── tests/
│   ├── test_jsonl_parsing.py  # Tests de parsing JSONL
│   ├── test_model_config.py   # Tests de configuración de modelos
│   └── test_fallback.py       # Tests de comportamiento fallback
├── scripts/
│   ├── setup-cliproxyapi.sh
│   ├── setup-rlm.sh
│   └── deploy-skill.sh
├── config/
│   ├── cliproxyapi-example.yaml
│   └── cliproxyapi.service  # unidad systemd
├── docs/
│   ├── ARCHITECTURE.md
│   └── TROUBLESHOOTING.md
├── install.sh              # Instalador de un comando
└── pyproject.toml
```

## Tests

```bash
# Ejecutar todos los tests
uv run pytest tests/ -v

# Ejecutar archivo de test específico
uv run pytest tests/test_jsonl_parsing.py -v
```

Los tests usan mocks—no requieren llamadas API.

## Debugging

### Habilitar Salida Verbose

```bash
uv run python src/rlm_bridge.py --query "..." --verbose
```

### Guardar Logs de Ejecución

```bash
uv run python src/rlm_bridge.py --query "..." --log-dir /tmp/rlm-logs
```

Los logs se guardan como `.jsonl` y pueden visualizarse con el visualizador de RLM:

```bash
cd ~/rlm/visualizer && npm run dev
# Abrir http://localhost:3001
```

### Ver Logs de CLIProxyAPI

```bash
journalctl --user -u cliproxyapi -f
```

## Solución de Problemas

| Problema | Solución |
|----------|----------|
| Rate limit (429) | Espera unos minutos o usa `memory_search` |
| OAuth expirado (401) | Re-autentícate en http://localhost:8317/management.html |
| No encuentra sesiones | Verifica ruta: `ls ~/.openclaw/agents/*/sessions/*.jsonl` |
| Sin memoria | Reduce `--max-sessions 15` |
| CLIProxyAPI no compila | Ver [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) para alternativas |

Guía completa: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

## Consideraciones de Seguridad

- **Tokens OAuth** se almacenan por CLIProxyAPI en `~/.cli-proxy-api/`
- **API keys** para CLIProxyAPI son strings placeholder (no secretos reales)
- **Datos de sesión** permanecen locales—solo las queries se envían a OpenAI
- **Sin telemetría** ni recolección de datos externa

## Contribuir

1. Fork del repositorio
2. Crear rama de feature (`git checkout -b feature/amazing-feature`)
3. Ejecutar tests (`uv run pytest tests/ -v`)
4. Commit de cambios (`git commit -m 'Add amazing feature'`)
5. Push a la rama (`git push origin feature/amazing-feature`)
6. Abrir un Pull Request

## Licencia

Licencia MIT. Ver [LICENSE](LICENSE) para detalles.

## Agradecimientos

- [RLM](https://github.com/alexzhang13/rlm) por Alex Zhang
- [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) para proxy OAuth
- Ecosistema [OpenClaw](https://github.com/openclaw)
