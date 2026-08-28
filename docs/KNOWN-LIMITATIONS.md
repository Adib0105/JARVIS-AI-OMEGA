# Known Limitations

- Real Windows GUI, foreground focus, UIA, OCR, multi-monitor and DPI behavior is not verified for this exact change.
- Physical microphone/STT and audible speaker/TTS behavior is not verified.
- Live hosted-provider authentication, timeout, rate-limit and recovery behavior is not verified with a real credential.
- Branch protection/required checks, signed commits/tags and Windows Authenticode are not configured by source code.
- Full Ruff reports substantial broad/silent-exception and import-order debt; only critical correctness lint is authoritative today.
- The Windows/Python 3.14 release constraint set cannot be fully resolved by Linux Python 3.12 because `audioop-lts` is version/platform constrained.
- Controlled self-development and autonomous behavior remain experimental and approval-gated; production self-modification is off by default.
- Smart planner, proactive workflows, app awareness, daily briefing and richer memory/action-history UX are not all stable release claims.

Absence of evidence stays `NOT VERIFIED`; it is not converted to PASS from implementation or test presence.

