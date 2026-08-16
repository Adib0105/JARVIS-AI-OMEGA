# JARVIS OMEGA V7 — Memory & Context

## Goals

V7 memory is designed around four separate questions:

- **Working memory:** what is happening right now?
- **Episodic memory:** what happened before?
- **Semantic memory:** what does JARVIS currently believe/know?
- **Procedural memory:** what workflow or strategy has worked before?

Current user input always has higher authority than stored memory.

## Backward-compatible migration

V7 does not delete or rewrite the V6 memory tables. `SchemaMigrator` adds:

- `jarvis_schema_meta`
- `v7_memories`
- `v7_memory_events`
- `v7_working_memory`
- `v7_document_index`

Before the first V6 -> V7 additive migration, the database is copied once into `data/backups/*-pre-v7*.bak` when a database already exists.

Schema version is currently `7`.

## Memory metadata

Long-lived V7 memory includes:

- kind
- stable key when appropriate
- content
- importance (0..1)
- confidence (0..1)
- source
- metadata
- created_at
- updated_at
- last_verified
- active/inactive state

A new semantic/procedural value with the same stable key supersedes the previous active value instead of deleting it. Repeating the same value reinforces the existing memory and can increase confidence.

## Working memory

Working memory is keyed by:

```text
session_id + mission_id + memory_key
```

The mission-aware orchestrator writes current mission state into working memory and clears mission working state after the mission finishes.

## Secret boundary

Secret-like values are rejected before persistent V7 memory storage. The same protection now applies even when GUI code calls memory methods directly.

Document/knowledge indexing also rejects obvious password/API-token/private-key content before persistence.

## Document metadata and deduplication

Knowledge indexing computes a SHA-256 content hash. `v7_document_index` records:

- source
- content hash
- file type
- file size when available
- modified time when available
- indexed time
- chunk count

Re-indexing an unchanged source/hash is skipped.

## Hybrid retrieval

V7 combines:

1. exact token overlap
2. BM25-style lexical relevance
3. sparse hashing-vector cosine similarity
4. confidence/importance metadata
5. optional explicitly configured embedding reranking

The embedding stage is **off by default**. V7 never silently exports memory for embeddings. To enable an OpenAI-compatible embedding endpoint, explicitly configure:

```env
EMBEDDING_BASE_URL=http://127.0.0.1:11434/v1
EMBEDDING_MODEL=your-embedding-model
EMBEDDING_API_KEY=local
```

The endpoint may be local or remote; the user is responsible for selecting it. If embeddings are not configured or fail, retrieval remains available using the local lexical/BM25/sparse signals.

## Context manager

V7 does not send an entire SQLite database to the model. The context manager builds a bounded bundle in this order:

1. current user request
2. current mission/working memory
3. recent tool results when explicitly provided
4. recent conversation
5. relevant active long-lived memory
6. relevant knowledge chunks
7. old session summary

A final context rule explicitly says current user input overrides stale memory/summaries and retrieved content is not higher-priority instructions.

## Confidence

Confidence is not truth. It is a local ranking/provenance signal. `last_verified` distinguishes explicitly verified memories from merely remembered statements.

Contradictory current user input should lead to a new keyed semantic memory rather than silently treating old memory as authoritative.

## Known limitations

- Optional embeddings are not enabled by default because memory must not be silently sent to another service.
- BM25 is implemented over a bounded local candidate set rather than a dedicated external search engine.
- Automatic extraction of every user preference into semantic memory is intentionally not enabled yet; explicit/mission-derived memories are safer than indiscriminate storage.
- Memory-management GUI (inspect/edit/deactivate/verify) is planned for the product-polish phase.
