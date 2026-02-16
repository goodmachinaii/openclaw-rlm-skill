# OpenClaw RLM Skill

OpenClaw skill that integrates [RLM](https://github.com/alexzhang13/rlm) (Recursive Language Models) for programmatic reasoning over complete conversation history.

## What it does

This skill complements OpenClaw's `memory_search`. While `memory_search` quickly finds snippets, `rlm-engine` can:

- Cross-reference information across multiple sessions
- Analyze patterns and trends in history
- Execute Python code to reason over large volumes of data
- Answer questions that require reading complete sessions

## Requirements

| Component | Version |
|-----------|---------|
| Raspberry Pi 4 | 8GB RAM recommended |
| OS | Debian 13 (Trixie) ARM64 |
| OpenClaw | Installed and running |
| Node.js | >= 22 |
| Python | >= 3.11 |
| ChatGPT subscription | Pro or Max (for OAuth) |

## Installation

### 1. Clone the repository

```bash
cd ~
git clone https://github.com/angelgalvisc/openclaw-rlm-skill.git
cd openclaw-rlm-skill
```

### 2. Run automatic installation

```bash
chmod +x install.sh
./install.sh
```

This will:
- Install Python and uv if not present
- Install RLM
- Compile CLIProxyAPI from source (for ARM64)
- Deploy the skill to OpenClaw

### 3. Configure CLIProxyAPI

```bash
# Start CLIProxyAPI
cli-proxy-api --config ~/.cli-proxy-api/config.yaml
```

### 4. OAuth login

Open in browser: http://localhost:8317/management.html

Authenticate with your ChatGPT account.

### 5. Restart OpenClaw

```bash
openclaw gateway restart
```

### 6. Test

From Telegram:
> "What have we talked about this week?"

## Usage

The skill activates automatically when OpenClaw detects questions requiring deep history analysis.

### Examples of questions that trigger rlm-engine

- "Compare what we discussed about project X last week with today"
- "What are the most frequent topics of the last month?"
- "Find all pending decisions about infrastructure"
- "Summarize EVERYTHING we've worked on in the migration project"

### Questions that DON'T need rlm-engine (use memory_search)

- "What was the WiFi password?"
- "Do you remember the restaurant name?"

## Models

| Role | Model | Description |
|------|-------|-------------|
| Root LM | gpt-5.3-codex | Main reasoning (1 call/query) |
| Sub-LMs | gpt-5.1-codex-mini | Context navigation (2-7 calls, 4x more efficient) |
| Fallback | gpt-5.2 | If primary fails |

## Project structure

```
openclaw-rlm-skill/
├── src/rlm_bridge.py      # Main RLM ↔ OpenClaw bridge
├── skill/SKILL.md         # Skill definition
├── tests/                 # Unit tests
├── scripts/               # Installation scripts
├── config/                # Configuration files
└── docs/                  # Additional documentation
```

## Tests

```bash
uv run pytest tests/ -v
```

## Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common issues.

## License

MIT

---

# Español

## Qué hace

Este skill complementa `memory_search` de OpenClaw. Mientras `memory_search` busca snippets rápidamente, `rlm-engine` puede:

- Cruzar información entre múltiples sesiones
- Analizar patrones y tendencias en el historial
- Ejecutar código Python para razonar sobre grandes volúmenes de datos
- Responder preguntas que requieren leer sesiones completas

## Requisitos

| Componente | Versión |
|------------|---------|
| Raspberry Pi 4 | 8GB RAM recomendado |
| OS | Debian 13 (Trixie) ARM64 |
| OpenClaw | Instalado y funcionando |
| Node.js | >= 22 |
| Python | >= 3.11 |
| Suscripción ChatGPT | Pro o Max (para OAuth) |

## Instalación

### 1. Clonar el repositorio

```bash
cd ~
git clone https://github.com/angelgalvisc/openclaw-rlm-skill.git
cd openclaw-rlm-skill
```

### 2. Ejecutar instalación automática

```bash
chmod +x install.sh
./install.sh
```

### 3. Configurar CLIProxyAPI

```bash
cli-proxy-api --config ~/.cli-proxy-api/config.yaml
```

### 4. OAuth login

Abrir en navegador: http://localhost:8317/management.html

### 5. Reiniciar OpenClaw

```bash
openclaw gateway restart
```

### 6. Probar

Desde Telegram:
> "¿De qué hemos hablado esta semana?"

## Uso

El skill se activa automáticamente cuando OpenClaw detecta preguntas que requieren análisis profundo del historial.

### Ejemplos de preguntas que activan rlm-engine

- "Compara lo que discutimos sobre el proyecto X la semana pasada con hoy"
- "¿Cuáles son los temas más frecuentes del último mes?"
- "Encuentra todas las decisiones pendientes sobre infraestructura"
- "Resume TODO lo que hemos trabajado en el proyecto de migración"

### Preguntas que NO necesitan rlm-engine (usa memory_search)

- "¿Cuál era la contraseña del WiFi?"
- "¿Recuerdas el nombre del restaurante?"
