# OpenClaw RLM Skill

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-skill-purple.svg)](https://github.com/openclaw)
[![Platform](https://img.shields.io/badge/platform-ARM64%20%7C%20x86__64-lightgrey.svg)]()

> **Razonamiento programático profundo bajo demanda sobre historial de conversaciones para OpenClaw.**
>
> Complementa `memory_search` — solo se activa cuando pides explícitamente `/rlm`.

[English](README.md)

---

## Por Qué Existe

El `memory_search` integrado de OpenClaw maneja el 90% de las consultas de memoria perfectamente—es rápido (~100ms) y gratis. **Úsalo por defecto.**

Este skill es para el 10% restante: cuando necesitas **analizar programáticamente** tu historial de conversaciones—contar ocurrencias, calcular estadísticas, o iterar sobre TODAS las sesiones en lugar de solo los mejores matches.

[RLM (Recursive Language Models)](https://github.com/alexzhang13/rlm) ejecuta código Python que razona sobre tu historial completo. Es más lento (15-45s) y cuesta dinero (~$0.01-0.05/query), así que solo se activa cuando lo pides explícitamente.

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
│  • Root LM: kimi-k2-thinking (decide estrategia, 1 llamada)             │
│  • Sub-LMs: kimi-k2.5 (navegan contexto, 2-7 llamadas, 256K contexto)   │
│  • Ejecuta código Python en REPL local                                  │
│  • Fallback automático a kimi-k2-turbo si el primario falla             │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Moonshot API (api.moonshot.ai)                      │
│  • Endpoint compatible con OpenAI                                       │
│  • Pago por uso (~$0.01-0.05 por consulta)                              │
│  • Llamadas HTTPS directas (sin proxy)                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Cuándo Usar

Este skill usa **activación explícita únicamente**. El usuario debe pedir análisis RLM directamente.

| Usuario dice | Herramienta | Tiempo |
|--------------|-------------|--------|
| "¿De qué hablamos ayer?" | `memory_search` | ~100ms |
| "¿Cuál era el endpoint de la API?" | `memory_search` | ~100ms |
| "/rlm ¿cuántas veces discutimos Docker?" | **rlm-engine** | 15-45s |
| "Usa RLM para encontrar patrones del mes" | **rlm-engine** | 15-45s |

### Frases de activación

```
/rlm <pregunta>
usa RLM para...
analiza con RLM...
análisis profundo de...
```

### Ejemplos

```
✓ "/rlm compara lo que discutimos sobre la API la semana pasada vs hoy"
✓ "Usa RLM para encontrar los temas más frecuentes del último mes"
✓ "Analiza con RLM todas las decisiones pendientes sobre infraestructura"

✗ "¿Cuál era el endpoint de la API?" → memory_search (sin trigger RLM)
✗ "Encuentra patrones en nuestras conversaciones" → memory_search (sin pedido explícito)
```

## Requisitos

| Componente | Requisito |
|------------|-----------|
| Hardware | Raspberry Pi 4 (8GB RAM) o equivalente |
| OS | Debian 13+ ARM64 / cualquier Linux x86_64 |
| OpenClaw | Instalado y funcionando |
| Python | 3.11+ |
| Node.js | 22+ |
| Moonshot API | API key de https://platform.moonshot.ai/ |

## Inicio Rápido

```bash
# Clonar e instalar
git clone https://github.com/angelgalvisc/openclaw-rlm-skill.git
cd openclaw-rlm-skill
./install.sh

# Configurar tu API key
export MOONSHOT_API_KEY="sk-your-key-here"

# O agregar a ~/.bashrc para persistencia
echo 'export MOONSHOT_API_KEY="sk-your-key-here"' >> ~/.bashrc
source ~/.bashrc

# Reiniciar OpenClaw
openclaw gateway restart
```

Probar desde Telegram:
> "/rlm ¿qué patrones ves en nuestras conversaciones de esta semana?"

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
- Despliega el skill a `~/.openclaw/workspace/skills/rlm-engine/`

### 3. Configurar API Key

Obtén tu API key en https://platform.moonshot.ai/

```bash
# Para la sesión actual
export MOONSHOT_API_KEY="sk-your-key-here"

# Para persistencia, agregar a tu shell config
echo 'export MOONSHOT_API_KEY="sk-your-key-here"' >> ~/.bashrc
source ~/.bashrc
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
  --root-model kimi-k2-thinking \   # Modelo principal de razonamiento
  --sub-model kimi-k2.5 \           # Navegación de contexto (256K contexto)
  --fallback-model kimi-k2-turbo \  # Usado si el primario falla
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
| Root LM | kimi-k2-thinking | 1 | Razonamiento principal, análisis complejo |
| Sub-LMs | kimi-k2.5 | 2-7 | Navegación de contexto, ventana 256K |
| Fallback | kimi-k2-turbo | varía | Automático al fallar |

### Costos

| Modelo | Input | Output | Uso típico |
|--------|-------|--------|------------|
| kimi-k2-thinking | ~$0.60/M | ~$2.50/M | 1 llamada (root) |
| kimi-k2.5 | ~$0.60/M | ~$2.50/M | 2-7 llamadas (sub) |
| **Por consulta** | | | **~$0.01-0.05** |

## Estructura del Proyecto

```
openclaw-rlm-skill/
├── src/
│   └── rlm_bridge.py       # Bridge principal
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
│   ├── setup-rlm.sh
│   └── deploy-skill.sh
├── config/
│   └── moonshot.env.example   # Template de API key
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

### Probar Conectividad API

```bash
curl -s https://api.moonshot.ai/v1/models \
  -H "Authorization: Bearer $MOONSHOT_API_KEY" | head
```

## Solución de Problemas

| Problema | Solución |
|----------|----------|
| API key no configurada | `export MOONSHOT_API_KEY="sk-..."` |
| Rate limit (429) | Espera unos minutos o usa `memory_search` |
| API key inválida (401) | Verifica la key en https://platform.moonshot.ai/ |
| No encuentra sesiones | Verifica ruta: `ls ~/.openclaw/agents/*/sessions/*.jsonl` |
| Sin memoria | Reduce `--max-sessions 15` |
| Timeout de conexión | Prueba endpoint alterno: `--base-url https://api.moonshot.cn/v1` |

Guía completa: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

## Consideraciones de Seguridad

- **API keys** almacenadas como variables de entorno (no en código)
- **Datos de sesión** permanecen locales—solo las queries se envían a Moonshot API
- **Sin telemetría** ni recolección de datos externa
- **Solo HTTPS** para todas las comunicaciones API

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
- [Moonshot AI](https://platform.moonshot.ai/) por los modelos Kimi
- Ecosistema [OpenClaw](https://github.com/openclaw)
