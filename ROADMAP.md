# JARVIS AI OMEGA — Roadmap

This roadmap tracks engineering reality rather than marketing claims. The current application version is defined only by `jarvis.version.APP_VERSION`.

## Current release-candidate line

- `v7-development` — active engineering/release-candidate branch for JARVIS AI OMEGA 8.0.0-rc1.
- `main` — separate stable line; this roadmap does not infer its application version.

## Automated foundations in place

- provider-neutral AI contracts, routing, timeouts, fallback and error classification;
- persisted mission orchestration with verification, retry, recovery, replanning, pause/resume/cancel;
- canonical capability permission authority and audit evidence;
- Trusted Local Mode boundaries that do not remove high-risk approval controls;
- deterministic SQLite cleanup and multi-version Linux/Windows regression coverage;
- layered memory, hybrid retrieval and document provenance/deduplication;
- semantic Computer Use with confidence/no-guess behavior, UIA-first targeting and OCR fallback controls;
- browser trust/private-target policy and prompt-injection isolation;
- evidence-based self-evaluation and deterministic benchmarks;
- observability, health and truthful provider-reported usage/cost handling;
- backup/restore with integrity and pre-restore protection;
- response-quality and provider resilience composed into the core runtime rather than startup monkey-patching;
- voice/Command Center/skill runtime composed through explicit classes with compatibility shims;
- file-root/traversal/symlink/junction/secret-content hardening;
- truthful diagnostic states that separate installation from local/device/E2E verification;
- exact-pinned direct dependencies plus release constraints;
- Windows frozen EXE and installer CI;
- canonical PE/installer version metadata derived from one application version source;
- isolated installer install/uninstall validation and post-packaging regression.

## Experimental / operator-gated systems

These remain intentionally controlled even where deterministic tests exist:

- sandboxed Self Development;
- Self Coding and bounded Self Debugging;
- optional local/offline development provider;
- skill proposal/build/activation lifecycle;
- Controlled Release;
- history-preserving Rollback.

No unrestricted autonomous production rewriting is a release goal.

## Release-candidate work still requiring external evidence

Automated CI cannot complete these on behalf of a real operator workstation. Before a stable production claim, record exact-candidate evidence using `docs/WINDOWS-E2E-CHECKLIST.md` for:

1. normal Windows GUI startup/shutdown/relaunch;
2. real keyboard/mouse/UIA interactions with post-action verification;
3. Chrome and Notepad target/focus behavior;
4. screenshot/OCR behavior on the real display;
5. 100/125/150% DPI and alternate resolution/window placement checks;
6. audible speaker TTS;
7. physical microphone capture and speech recognition;
8. real configured provider inference plus practical failure/recovery checks;
9. network disconnect/reconnect behavior;
10. clean installed first run and uninstall on a real workstation.

Optional Gmail/Calendar/local-model behavior should be validated only if included in the release claim.

## Repository policy work

Before treating a release branch as protected, enable GitHub branch protection/rulesets with required CI checks. A green workflow alone does not enforce repository policy.

## Future ideas

Subject to evidence and evaluation:

- richer mission visualization/replay;
- broader semantic accessibility adapters;
- stronger local benchmark datasets;
- additional provider adapters without core coupling;
- signed update/release metadata;
- stronger installer upgrade/migration testing;
- archival vetted wheelhouse/artifact retention for offline reproducibility;
- opt-in local model profiles and performance benchmarking;
- richer skill import/marketplace formats with strict permission manifests.

## Engineering rule

```text
IMPLEMENTED + INTEGRATED + TESTED + VERIFIED
```

Security boundaries, secret protection, audit integrity, sandbox isolation and rollback controls must not be weakened merely to make the system appear more autonomous or release-ready.
