# Arquitectura

## Diagrama de flujo

```
Usuario (Telegram)
  │
  ▼
OpenClaw Gateway (Node.js, puerto 18789)
  │ Modelo: openai-codex/gpt-5.3-codex via OAuth
  │ Ya configurado y funcionando
  │
  │ [Agente detecta pregunta sobre historial]
  │ [Lee SKILL.md de rlm-engine]
  │ [Envía "Analizando tu historial..." al usuario]
  │
  ▼
bash tool: cd ~/openclaw-rlm-skill && uv run python src/rlm_bridge.py --query "..."
  │
  ▼
rlm_bridge.py
  ├─ Carga MEMORY.md, SOUL.md, transcripciones (auto-detección de rutas)
  ├─ Limita a 30 sesiones / 2M chars (seguro para 8GB RAM)
  │
  ▼
RLM (Python)
  ├─ Root LM: gpt-5.3-codex → decide cómo analizar (1 llamada)
  ├─ Sub-LMs: gpt-5.1-codex-mini → navegan contexto (2-7 llamadas, 4x más barato)
  ├─ System prompt: DEFAULT de alexzhang13 (NO override)
  ├─ REPL local: ejecuta Python generado por el modelo
  │
  ▼
CLIProxyAPI (localhost:8317)
  ├─ Compilado desde source (Go nativo ARM64)
  ├─ Convierte llamadas API en OAuth calls
  ├─ Usa la suscripción ChatGPT del usuario ($0 extra)
  │
  ▼
OpenAI servers → respuesta
  │
  ▼
JSON result → OpenClaw → Telegram → Usuario
```

## Componentes

### 1. OpenClaw Gateway

- Puerto: 18789
- Recibe mensajes de Telegram
- Detecta cuándo usar el skill rlm-engine
- Ejecuta el bridge via bash

### 2. rlm_bridge.py

Funciones principales:

| Función | Descripción |
|---------|-------------|
| `find_sessions_dir()` | Auto-detecta dónde OpenClaw guarda sesiones |
| `parse_jsonl_session()` | Convierte JSONL de OpenClaw a texto legible |
| `load_workspace()` | Carga MEMORY.md, SOUL.md, daily notes |
| `load_sessions()` | Carga hasta 30 sesiones (2M chars max) |
| `run_rlm()` | Ejecuta RLM con modelos configurados |

### 3. RLM

- Biblioteca Python de alexzhang13
- Ejecuta código Python generado por el modelo para razonar
- Usa REPL local (no Docker) para menor overhead
- max_depth=1 (único valor funcional actualmente)

### 4. CLIProxyAPI

- Proxy Go que convierte OAuth tokens en API calls
- Puerto: 8317
- Compilado desde source (no hay binarios ARM64)
- Interfaz de management: http://localhost:8317/management.html

## Flujo de datos

1. Usuario envía mensaje en Telegram
2. OpenClaw detecta que requiere análisis profundo
3. OpenClaw ejecuta rlm_bridge.py con la query
4. Bridge carga contexto (workspace + sesiones)
5. Bridge invoca RLM con el contexto
6. RLM genera y ejecuta código Python para analizar
7. RLM hace llamadas API via CLIProxyAPI
8. CLIProxyAPI usa OAuth token de ChatGPT
9. Resultado JSON se devuelve a OpenClaw
10. OpenClaw responde al usuario en Telegram

## Límites de memoria

| Recurso | Límite | Razón |
|---------|--------|-------|
| Sesiones | 30 | Evitar timeout |
| Caracteres | 2M | Seguro para 8GB RAM |
| Daily notes | 200K chars | Cap para notas diarias |
| Archivos workspace | 50K chars c/u | Evitar archivos enormes |

## Modelos y estrategia

```
Query del usuario
  │
  ▼
Root LM (gpt-5.3-codex)
  │ Decide estrategia de análisis
  │ 1 llamada
  │
  ├──────────────────┐
  │                  │
  ▼                  ▼
Sub-LM 1          Sub-LM N
(gpt-5.1-codex-mini)
  │ Navegan contexto
  │ 2-7 llamadas total
  │ 4x más eficiente en cuota
  │
  ▼
Resultado consolidado
```
