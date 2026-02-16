---
name: rlm-engine
description: >
  Análisis profundo y razonamiento programático sobre historial completo de conversaciones.
  Complementa memory_search: usa RLM cuando necesites RAZONAR sobre muchas sesiones,
  no solo encontrar un snippet. Tarda 15-45 segundos y consume cuota.
version: 3.1.0
---

# RLM Engine — Razonamiento profundo sobre historial

## Diferencia con memory_search

OpenClaw ya tiene `memory_search` (búsqueda semántica + BM25) que es rápida y eficiente.
NO uses rlm-engine como reemplazo de memory_search. Son herramientas complementarias:

| | memory_search (nativo) | rlm-engine (este skill) |
|---|---|---|
| Velocidad | Milisegundos | 15-45 segundos |
| Resultado | Snippets cortos (~700 chars) | Análisis completo con razonamiento |
| Tipo | Buscar y devolver fragmentos | Razonar ejecutando código Python sobre el historial |
| Costo | 1 embedding call (barato) | 3-8 llamadas LLM (consume cuota ChatGPT) |
| Alcance | Chunks indexados de MEMORY.md y memory/*.md | Transcripciones completas de hasta 30 sesiones |

**Regla de oro:** Usa primero `memory_search`. Solo escala a `rlm-engine` si memory_search
no puede resolver la pregunta porque requiere cruzar datos, analizar patrones, o razonar
sobre grandes volúmenes de historial.

## Cuándo usar rlm-engine

Usa este skill SOLO cuando la pregunta requiera algo que memory_search NO puede hacer:

- **Cruzar información entre múltiples sesiones:** "Compara lo que discutimos sobre el proyecto X
  la semana pasada con lo que dijimos hoy"
- **Analizar patrones o tendencias:** "¿Cuáles son los temas más frecuentes del último mes?"
  "¿Cómo ha evolucionado mi opinión sobre Y?"
- **Razonamiento complejo sobre historial extenso:** "Encuentra todas las decisiones que tomamos
  sobre infraestructura y evalúa cuáles siguen pendientes"
- **Conteo, estadísticas o agregación:** "¿Cuántas veces hemos hablado de Kubernetes?"
  "¿En qué porcentaje de sesiones mencioné temas de trabajo vs personales?"
- **Preguntas que requieren leer sesiones completas**, no solo snippets:
  "Resume TODO lo que hemos trabajado en el proyecto de migración"

## Cuándo NO usar (usa memory_search en su lugar)

- **Buscar un dato puntual:** "¿Cuál era la contraseña del WiFi que mencioné?"
  → memory_search lo encuentra en milisegundos
- **Recordar un hecho simple:** "¿Recuerdas el nombre del restaurante que recomendé?"
  → memory_search es suficiente
- **Contexto de la sesión actual** → ya lo tienes en el contexto, no necesitas ninguna herramienta
- **Saludos, chat casual, tareas en tiempo real** → no requieren historial
- **Búsquedas web** → usa herramientas de navegación, no historial

## Flujo de decisión

```
Usuario hace pregunta sobre historial
  │
  ├─ ¿Puedo responder con el contexto actual? → Sí → Responde directo
  │
  ├─ ¿Es un dato puntual o snippet? → Sí → Usa memory_search
  │
  ├─ ¿memory_search ya devolvió resultado suficiente? → Sí → Responde con eso
  │
  └─ ¿Requiere cruzar sesiones, analizar patrones, o razonar
      sobre grandes volúmenes? → Sí → Usa rlm-engine (este skill)
```

## Invocación

1. Envía primero al usuario:
   "Analizando tu historial con RLM... esto puede tardar 15-45 segundos."

2. Ejecuta:

```bash
cd ~/openclaw-rlm-skill && uv run python src/rlm_bridge.py \
  --query "PREGUNTA EXACTA DEL USUARIO" \
  --root-model gpt-5.3-codex \
  --sub-model gpt-5.1-codex-mini \
  --fallback-model gpt-5.2
```

3. El resultado es JSON:
   - `status: "ok"` → responde con el campo `response`
   - `status: "rate_limited"` → comunica que la cuota ChatGPT está alcanzada, sugiere esperar
   - `status: "skipped"` → no hay suficiente historial, responde con lo que tengas en MEMORY.md
   - `status: "error"` → informa el problema, ofrece usar memory_search como alternativa

## Modelos y costos

- Root LM: gpt-5.3-codex (razonamiento principal, 1 llamada por query)
- Sub-LMs: gpt-5.1-codex-mini (navegación de contexto, 2-7 llamadas, 4x más eficiente en cuota)
- Fallback: gpt-5.2 (si el modelo principal no está disponible o rate limited)
- Costo: $0 adicional — usa la suscripción ChatGPT existente via CLIProxyAPI
- Consumo estimado: ~7-12 créditos por query (vs ~15-40 sin la optimización de sub-LMs)
- Advertencia: usar este skill frecuentemente consume cuota más rápido que memory_search
