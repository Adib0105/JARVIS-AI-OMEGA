# JARVIS OMEGA V10 — implementation contract

V10 is developed on `v10-development`; `main` remains the stable release line until V10 passes release gates.

## Product rule
V10 is a personal AI operating companion, not an unrestricted background controller. Screen, microphone, files, browser, credentials, messages, purchases and destructive actions remain visible, revocable and policy-gated. Self-development must use sandbox/test/diff/rollback and may not silently rewrite production.

## 100-feature scope
The V10 scope is the approved master list: Live Companion; Barge-In; low-latency streaming voice; Hindi/Hinglish/English; conversational personality; voice profiles; Wake Word V2; Windows startup; greetings; background companion; tray controls; screen modes; context understanding; Computer Use V3; visual fallback; multi-monitor; apps; files; Browser V3; research; Document V3; Coding V3; Memory V3; memory control; routine learning; skills; Mission V3; multi-agent brain; verification; recovery; Router V3; local AI; hybrid AI; offline mode; RAG V3; capability registry; self-evaluation; gap detection; controlled self-development; sandbox coding; self-debugging; before/after evaluation; reviewable diff; controlled deployment; rollback; command center; V10 HUD; mission timeline; health; cost; notifications; kill switch; privacy mode; permissions; trusted local mode; sensitive-action protection; credential vault; audit; prompt-injection defense; isolation; signed updates; backup/restore; crash recovery; accounts; devices; onboarding; personalization; plans; licensing; payments; offline grace; entitlements; admin; analytics; updater; installer; code signing; Store package; crash reports; support diagnostics; Gmail; Calendar; Contacts; daily briefing; reminders; automation; proactive assistance; DND; performance modes; hardware awareness; streaming progress; cancellation; fast commands; contextual commands; multimodal input; personal knowledge; evaluation suite; hardware matrix; release certification; and creator identity (`Adib Azam`).

## Delivery gates
### Gate A — V10 foundation
Version/config migration, capability registry, runtime state machine, privacy/kill/cancel primitives, compatibility with V7.5 tests.

### Gate B — conversation
Full-duplex-capable architecture, VAD, streaming STT/TTS where provider supports it, barge-in, wake word, language routing, graceful fallbacks. Acoustic echo cancellation is required before claiming hands-free full duplex.

### Gate C — computer companion
Screen modes, context resolver, UIA-first computer use with OCR/vision fallback, multi-monitor, fast local commands, browser/files/documents.

### Gate D — intelligence
Memory/RAG, missions, specialist agents, verifier/recovery, local/cloud routing, skills and controlled self-development.

### Gate E — security and reliability
Credential vault, prompt-injection boundaries, audit, backup, crash recovery, emergency stop, privacy center and permission tests.

### Gate F — commercial product
Accounts, device licensing, plans, payment-provider abstraction, updater/installer/signing, onboarding, admin and privacy-respecting telemetry. Payment secrets never ship in the desktop client.

### Gate G — release
Regression/security/evaluation suites, real Windows/DPI/hardware matrix, installer/uninstaller tests, signed build verification and documented release evidence.

## Definition of done
A feature is not marked complete because a button/module exists. It needs implementation, deterministic tests where possible, failure handling, documentation, and integration evidence. Hardware/provider-dependent features require real-device validation before release certification.
