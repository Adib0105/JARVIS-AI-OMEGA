# Audit coverage and evidence

Date: **2026-10-04**. Runtime baseline: [`main@83b7f34`](https://github.com/Adib0105/JARVIS-AI-OMEGA/commit/83b7f34b67c0aca444c1139cd7db700364bc554c). Documentation branch: `v8/frontier-audit-2026-09-28` / PR #24.

This is the audit-first deliverable requested by section 59 of the supplied brief. No runtime code, security policy, production data, dependency pins or release settings are changed. The 2026-09-28 audit is retained in Git history; this refresh adds direct source checks and six executable reproductions.

Repository inventory on the audit branch: 328 tracked files, 239 Python files, 31,938 Python lines, 70 desktop test files and two service test files. Inventory is a scope description, not a completeness score. Source review followed the main entrypoints and trust/effect boundaries; no claim is made that every line or possible runtime path was exhaustively proved.

| Area | Representative inspected paths | Evidence boundary |
|---|---|---|
| Entrypoints/UI/background | `desktop_app.py; main.py; gui.py; background_ui.py; ui_command_center.py; wake_service.py` | Source + existing lifecycle regressions; no fresh Windows visual check |
| Core/provider/planning | `core.py; core_v7.py; providers/; intelligence/; agent/` | Source + mission/provider tests; no live model call |
| Tools/capabilities/security | `tools.py; capability_registry.py; security/; agent/tool_runtime.py; agent/effects.py` | Source + policy/audit tests + malformed-evidence/replay reproductions |
| Memory/RAG/documents/database | `memory.py; memory_v7.py; memory_lifecycle.py; document_index.py; retrieval.py; documents.py; storage/` | Source + parser/retrieval/backup/migration regressions; large-corpus/source lifecycle acceptance open |
| Voice/vision/computer/browser | `microphone.py; wake_service.py; speech_worker.py; vision.py; computer_use/; youtube_player.py` | Source + fixture tests; real device/UI/browser acceptance open |
| Coding/Git/skills/self-development | `coding_tools.py; git_tools.py; coding_agent.py; skills/; self_development/` | Source + policy/worktree/release regressions; untrusted execution stays blocked |
| Account/billing/recovery | `server/app.py; store.py; billing.py; recovery.py; backup.py; worker.py; subscription_client.py` | Source + 30 isolated service tests; no deployed merchant or SMTP |
| Configuration/logging/telemetry | `config.py; config_validation.py; logging_utils.py; observability/; readiness.py` | Source + current tests; performance/live readiness unknown |
| Build/install/update/deployment/CI | `requirements*.txt; constraints/; .github/workflows/ci.yml; build scripts; installer; updater.py; scripts/; docs/` | Source + live GitHub jobs/governance; no fresh local Windows installer run |

## Verification commands

```bash
python -m pip install -r requirements.txt -c constraints/linux.txt
PYTHONWARNINGS=error::ResourceWarning python -m unittest discover -s tests -v
python -m compileall -q jarvis server desktop_app.py main.py
python -m pip check
# In a separate service virtual environment:
python -m pip install -r requirements-server.txt -c constraints/linux.txt
PYTHONWARNINGS=error::ResourceWarning python -m unittest discover -s tests_server -v
python -m pip check
```

The desktop run used test-key-not-used, microphone/Google disabled, self-development enabled with production self-modification disabled. Provider-specific tests use fixtures; the placeholder is not a credential. See [evidence.json](evidence.json) for counts and boundaries.

[Historical main CI](https://github.com/Adib0105/JARVIS-AI-OMEGA/actions/runs/36313850691) is successful for `83b7f34b67c0aca444c1139cd7db700364bc554c`. Current documentation changes require their own CI status; the old run must not be relabelled as the new commit result.
