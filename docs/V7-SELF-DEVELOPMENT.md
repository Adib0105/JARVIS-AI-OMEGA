# JARVIS AI OMEGA V7 / V7.5 — Controlled Self-Development

## Status

**EXPERIMENTAL** until final live integration, security review, benchmark and release gates are complete.

The self-development subsystem is intentionally not an uncontrolled “AI rewrites itself forever” loop. Its design is:

```text
OBSERVE
→ SELF-EVALUATE
→ DETECT EVIDENCE-BACKED GAP
→ CREATE PROPOSAL
→ ANALYZE / PLAN
→ CREATE ISOLATED GIT WORKTREE
→ BUILD ONLY IN SANDBOX
→ COMPILE + FULL TESTS
→ BOUNDED SELF-DEBUG (MAX ATTEMPTS)
→ POLICY / SECURITY CHECK
→ DIFF REVIEW
→ AWAITING APPROVAL
→ CONTROLLED RELEASE (separate gate)
→ POST-RELEASE TEST
→ ROLLBACK IF REQUIRED
```

## Implemented foundation

- `jarvis/evaluation/engine.py` — evidence-based self-evaluation.
- `jarvis/evaluation/gaps.py` — capability gap detection from registry, metrics, repeated failures and failed missions.
- `jarvis/self_development/proposal.py` — persisted improvement proposals.
- `jarvis/self_development/analyzer.py` — conservative extension-point analysis.
- `jarvis/self_development/planner.py` — bounded engineering plan.
- `jarvis/self_development/sandbox.py` — isolated Git worktrees.
- `jarvis/self_development/git_manager.py` — allowlisted Git operations only.
- `jarvis/self_development/builder.py` — text/code writes restricted to sandbox and allowed suffixes.
- `jarvis/self_development/tester.py` — forced compile + full unittest regression suite.
- `jarvis/self_development/debugger.py` — bounded failure classification/repair guidance.
- `jarvis/self_development/coding.py` — JSON-only generated file changes through policy-gated builder.
- `jarvis/self_development/evaluator.py` — objective before/after regression comparison.
- `jarvis/self_development/policies.py` — immutable-core and change-size policy.
- `jarvis/self_development/rollback.py` — known-good commit checkpoint persistence.
- `jarvis/self_development/release.py` — separately gated fast-forward release + history-preserving Git revert rollback.

## Immutable / protected areas

Normal self-development automation cannot modify:

- `jarvis/security/`
- the complete `jarvis/self_development/` control plane
- browser/tool/file/Git/config/runtime trust boundaries
- release-critical security/self-development tests
- `.github/workflows/`
- `.env` and secret files
- `.git/`
- runtime `data/`
- protected production workspace paths

If a change genuinely requires modifying the security/approval/rollback core, normal self-development must stop and report the proposal for deliberate human engineering review.

## No arbitrary shell

The self-development runtime does not expose arbitrary CMD/PowerShell/shell execution. The tester uses fixed Python commands and the Git manager uses a bounded Git argument allowlist.

## Production deployment

Safe defaults:

```env
SELF_DEVELOPMENT_ENABLED=true
PRODUCTION_SELF_MODIFICATION=false
REQUIRE_APPROVAL_FOR_PRODUCTION=true
AUTO_ROLLBACK_ENABLED=false
MAX_SELF_REPAIR_ATTEMPTS=3
MAX_FILES_CHANGED=20
MAX_LINES_CHANGED=1200
MAX_BUILD_TIME=300
```

`APPROVED` is not the same as `DEPLOYED`.

The controlled release engine additionally requires:

1. explicit release approval,
2. `PRODUCTION_SELF_MODIFICATION=true`,
3. proposal state `APPROVED`,
4. clean production worktree,
5. unchanged expected production HEAD,
6. fresh sandbox regression pass,
7. all changed/untracked files are regular UTF-8 text within the size limit (no symlinks, path escapes, binary payloads or NUL bytes),
8. current paths, modes, deletions and exact bytes match the SHA-256 fingerprint approved at review time,
9. immutable-core policy pass,
10. the fingerprint is rechecked after staging and immediately before commit,
11. fast-forward-only deployment,
12. post-release full regression pass.

Untracked files are included in line/file counts and review diffs. Child compilation/tests put bytecode caches outside the worktree so review evidence is not contaminated by generated `.pyc` files.

Rollback uses `git revert`, not destructive `reset --hard`, so history remains auditable.

## Skill generation

Skill proposals live in `jarvis/skills/`. Generated skills must contain manifest, implementation, tests, documentation, permissions/version/risk and evaluation metadata. Skill generation reuses the same sandbox/test/security/release gates. It does not silently create active permanent automations.

## Evidence rule

A model saying “this is better” is never proof. Improvement is accepted only from deterministic regression correction or measured before/after evaluation evidence.
