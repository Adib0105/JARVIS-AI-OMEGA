## Summary

Describe what changed and why.

## Change type

- [ ] Bug fix
- [ ] Reliability / recovery
- [ ] Security
- [ ] Memory / RAG
- [ ] Computer use / browser
- [ ] Provider / model routing
- [ ] UI / voice
- [ ] Self-development / skills
- [ ] Tests / CI
- [ ] Documentation
- [ ] Packaging / release

## Evidence

- [ ] I tested the changed behavior.
- [ ] I added or updated deterministic tests when behavior changed.
- [ ] `python -m compileall -f -q .` passes.
- [ ] `python -m unittest discover -s tests -v` passes locally, or I explained why it cannot run locally.
- [ ] I did not delete/skip tests to make CI green.

## Security checklist

- [ ] No `.env`, API keys, passwords, OAuth tokens, recovery codes or private credentials are included.
- [ ] New tools have explicit capability/risk behavior.
- [ ] Unknown/high-risk behavior is not silently auto-approved.
- [ ] Web/external content remains untrusted data.
- [ ] Self-development changes do not weaken security/audit/secret/sandbox/rollback controls.
- [ ] No unrestricted arbitrary shell or credential-scraping path was added.

## Verification / real-world effects

If this change performs a real-world action, explain how success is independently verified. Do not equate a successful tool return with a verified external outcome.

## Screenshots / logs

Add safe screenshots or redacted logs if useful. Never upload secrets.

## Rollback

Explain the safest rollback/revert path for non-trivial changes.
