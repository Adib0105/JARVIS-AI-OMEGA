# JARVIS AI OMEGA V7 / V7.5 — Offline Development

## Status

**OPTIONAL / EXPERIMENTAL.**

Offline development uses an explicitly configured local OpenAI-compatible reasoning endpoint. It does not hard-code Ollama, LM Studio or one vendor. Any compatible local server may be used.

## Configuration

```env
OFFLINE_DEVELOPMENT_ENABLED=true
LOCAL_MODEL_PROVIDER=openai-compatible
LOCAL_AI_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_AI_MODEL=<your-local-model>
LOCAL_AI_API_KEY=local
```

The local API key field is only for compatibility with OpenAI-style clients; local runtimes commonly ignore it.

## Truthful availability

If no local model is configured, JARVIS reports:

```text
Offline development is unavailable because no local reasoning model is configured.
```

It must not pretend that offline reasoning exists.

## Offline self-build resources

When configured, the self-development loop can use:

- local repository checkout
- local Git
- local Python
- installed Python packages
- local tests
- local SQLite data/evaluation evidence
- local OpenAI-compatible model
- optional local embeddings when deliberately configured

No external dependency installation or model download happens silently.

## Same safety policy

Offline mode does not weaken sandbox, permission, immutable-core, diff, test, approval or release policies. Local reasoning output is still treated as untrusted generated text and must pass the same JSON/file/path/test/security gates before it can become an approved proposal.
