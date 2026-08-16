# JARVIS AI OMEGA — Roadmap

This roadmap tracks engineering reality, not marketing promises.

## Branches

- `main` — stable V6 baseline until final V7 release
- `v7-development` — V7/V7.5 engineering and release-candidate work

## Completed / verified foundations

- provider-neutral AI abstraction
- typed error/configuration foundations
- persisted mission state machine
- retry, recovery, replanning and verification
- capability-based security and audit
- Trusted Local Mode for allowlisted ordinary local actions
- deterministic SQLite cleanup and Windows regression coverage
- layered working/episodic/semantic/procedural memory
- hybrid retrieval and document provenance/deduplication
- semantic Computer Use with confidence/no-guess behavior
- UIA-first OCR fallback integration
- Browser V2 trust and prompt-injection isolation
- Capability Registry
- evidence-based Self Evaluation
- Capability Gap Detection
- deterministic evaluation benchmarks
- observability, health and truthful provider-reported cost handling
- backup/restore with integrity and pre-restore protection
- voice playback stop/pause/speed controls
- Agent Command Center
- expanded Linux/Windows CI gates
- Windows PyInstaller package smoke and secret-exclusion checks

## Experimental / operator-gated systems

These have implementation and deterministic tests but remain intentionally controlled:

- sandboxed Self Development
- Self Coding
- bounded Self Debugging
- optional offline/local development model
- Skill Build Pipeline
- Skill Activation
- Controlled Release
- history-preserving Rollback

Target lifecycle:

```text
Discover → Propose → Sandbox → Build → Test → Security/Evaluation
→ Diff → Approval → Controlled Release → Post-test → Rollback if needed
```

No unrestricted autonomous production rewriting is planned.

## Release-candidate work remaining

Before V7 becomes the stable `main` line:

1. run full workstation smoke tests on the operator Windows machine;
2. validate real microphone/voice behavior;
3. validate real provider chat/vision/tool paths;
4. validate browser/app control against installed applications;
5. validate optional OCR on real screens if configured;
6. validate optional Gmail/Calendar only if included in the release claim;
7. compile and test the Inno Setup installer locally;
8. perform install/launch/uninstall smoke testing;
9. sync status/changelog/release notes;
10. make the final merge/tag/release decision.

## Post-V7 ideas

Possible future work, subject to evidence and evaluation:

- richer mission visualization and replay
- broader semantic accessibility adapters
- stronger local benchmark datasets
- more provider adapters without core coupling
- signed update/release metadata
- improved installer upgrade/migration experience
- opt-in local model profiles and performance benchmarking
- richer skill marketplace/import format with strict permission manifests

## Engineering rules

A feature is not complete merely because code exists.

```text
IMPLEMENTED + INTEGRATED + TESTED + VERIFIED
```

Security boundaries, secret protection, audit integrity, sandbox isolation and rollback controls must not be weakened to make a feature appear more autonomous.
