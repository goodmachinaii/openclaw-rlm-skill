# OpenClaw RLM Skill

Skill de OpenClaw que integra [RLM](https://github.com/alexzhang13/rlm) (Recursive Language Models) para razonamiento programático sobre historial completo de conversaciones.

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
git clone https://github.com/TU_USUARIO/openclaw-rlm-skill.git
cd openclaw-rlm-skill
```

### 2. Ejecutar instalación automática

```bash
chmod +x install.sh
./install.sh
```

Esto:
- Instala Python y uv si no existen
- Instala RLM
- Compila CLIProxyAPI desde source (para ARM64)
- Despliega el skill a OpenClaw

### 3. Configurar CLIProxyAPI

```bash
# Iniciar CLIProxyAPI
cli-proxy-api --config ~/.cli-proxy-api/config.yaml
```

### 4. Hacer OAuth login

Abre en el navegador: http://localhost:8317/management.html

Autentícate con tu cuenta ChatGPT.

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

## Modelos

| Rol | Modelo | Descripción |
|-----|--------|-------------|
| Root LM | gpt-5.3-codex | Razonamiento principal (1 llamada/query) |
| Sub-LMs | gpt-5.1-codex-mini | Navegación de contexto (2-7 llamadas, 4x más eficiente) |
| Fallback | gpt-5.2 | Si el principal falla |

## Estructura del proyecto

```
openclaw-rlm-skill/
├── src/rlm_bridge.py      # Bridge principal RLM ↔ OpenClaw
├── skill/SKILL.md         # Definición del skill
├── tests/                 # Tests unitarios
├── scripts/               # Scripts de instalación
├── config/                # Archivos de configuración
└── docs/                  # Documentación adicional
```

## Tests

```bash
uv run pytest tests/ -v
```

## Troubleshooting

Ver [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) para solución de problemas comunes.

## Licencia

MIT
