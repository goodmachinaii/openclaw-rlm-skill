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

- **Find specific data:** "What was the API endpoint I mentioned yesterday?"
  → memory_search finds it in milliseconds
- **Remember a simple fact:** "What was the name of the library we discussed?"
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
