---
name: rlm-engine
description: >
  Deep analysis and programmatic reasoning over complete conversation history.
  Complements memory_search: use RLM when you need to REASON over many sessions,
  not just find a snippet. Takes 15-45 seconds and consumes quota.
version: 3.1.0
---

# RLM Engine — Deep reasoning over history

## Difference with memory_search

OpenClaw already has `memory_search` (semantic search + BM25) which is fast and efficient.
DO NOT use rlm-engine as a replacement for memory_search. They are complementary tools:

| | memory_search (native) | rlm-engine (this skill) |
|---|---|---|
| Speed | Milliseconds | 15-45 seconds |
| Result | Short snippets (~700 chars) | Complete analysis with reasoning |
| Type | Search and return fragments | Reason by executing Python code over history |
| Cost | 1 embedding call (cheap) | 3-8 LLM calls (consumes ChatGPT quota) |
| Scope | Indexed chunks from MEMORY.md and memory/*.md | Complete transcripts from up to 30 sessions |

**Golden rule:** Use `memory_search` first. Only scale to `rlm-engine` if memory_search
can't resolve the question because it requires cross-referencing data, analyzing patterns,
or reasoning over large volumes of history.

## When to use rlm-engine

Use this skill ONLY when the question requires something memory_search CANNOT do:

- **Cross-reference information across multiple sessions:** "Compare what we discussed about project X
  last week with what we said today"
- **Analyze patterns or trends:** "What are the most frequent topics of the last month?"
  "How has my opinion about Y evolved?"
- **Complex reasoning over extensive history:** "Find all decisions we made
  about infrastructure and evaluate which are still pending"
- **Counting, statistics or aggregation:** "How many times have we talked about Kubernetes?"
  "What percentage of sessions mentioned work topics vs personal?"
- **Questions that require reading complete sessions**, not just snippets:
  "Summarize EVERYTHING we've worked on in the migration project"

## When NOT to use (use memory_search instead)

- **Find specific data:** "What was the WiFi password I mentioned?"
  → memory_search finds it in milliseconds
- **Remember a simple fact:** "Do you remember the restaurant name I recommended?"
  → memory_search is enough
- **Current session context** → you already have it in context, no tool needed
- **Greetings, casual chat, real-time tasks** → don't require history
- **Web searches** → use navigation tools, not history

## Decision flow

```
User asks question about history
  │
  ├─ Can I answer with current context? → Yes → Answer directly
  │
  ├─ Is it specific data or snippet? → Yes → Use memory_search
  │
  ├─ Did memory_search return sufficient result? → Yes → Answer with that
  │
  └─ Does it require cross-referencing sessions, analyzing patterns, or reasoning
      over large volumes? → Yes → Use rlm-engine (this skill)
```

## Invocation

1. Send to user first:
   "Analyzing your history with RLM... this may take 15-45 seconds."

2. Execute:

```bash
cd ~/openclaw-rlm-skill && uv run python src/rlm_bridge.py \
  --query "EXACT USER QUESTION" \
  --root-model gpt-5.3-codex \
  --sub-model gpt-5.1-codex-mini \
  --fallback-model gpt-5.2
```

3. Result is JSON:
   - `status: "ok"` → respond with `response` field
   - `status: "rate_limited"` → communicate ChatGPT quota reached, suggest waiting
   - `status: "skipped"` → not enough history, respond with what you have in MEMORY.md
   - `status: "error"` → inform the problem, offer using memory_search as alternative

## Models and costs

- Root LM: gpt-5.3-codex (main reasoning, 1 call per query)
- Sub-LMs: gpt-5.1-codex-mini (context navigation, 2-7 calls, 4x more quota efficient)
- Fallback: gpt-5.2 (if primary unavailable or rate limited)
- Cost: $0 additional — uses existing ChatGPT subscription via CLIProxyAPI
- Estimated consumption: ~7-12 credits per query (vs ~15-40 without sub-LM optimization)
- Warning: using this skill frequently consumes quota faster than memory_search

---

# Español

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

## Cuándo NO usar (usa memory_search en su lugar)

- **Buscar un dato puntual:** "¿Cuál era la contraseña del WiFi que mencioné?"
- **Recordar un hecho simple:** "¿Recuerdas el nombre del restaurante que recomendé?"
- **Contexto de la sesión actual** → ya lo tienes en el contexto
- **Saludos, chat casual, tareas en tiempo real** → no requieren historial

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
   - `status: "rate_limited"` → comunica que la cuota ChatGPT está alcanzada
   - `status: "skipped"` → no hay suficiente historial
   - `status: "error"` → informa el problema
