# JARVIS OMEGA V8 — Home AI Product Architecture

This document is a product contract, not a claim that every physical integration is already verified.

## Target architecture

```text
JARVIS OMEGA
├── CORE
│   ├── Reasoning
│   ├── Planning
│   ├── Memory
│   ├── Context
│   ├── Recovery
│   └── Verification
├── VOICE
│   ├── STT
│   ├── TTS
│   ├── Wake Word
│   ├── Interruption
│   └── Continuous Conversation
├── VISION
│   ├── Screenshot
│   ├── OCR
│   ├── Camera Adapter
│   └── Visual Reasoning
├── COMPUTER
│   ├── Mouse
│   ├── Keyboard
│   ├── Apps
│   ├── Windows
│   ├── Media Controls
│   └── Semantic UIA/OCR
├── BROWSER
│   ├── Search
│   ├── Research
│   ├── Safe Read
│   └── Web Automation
├── PRODUCTIVITY
│   ├── Tasks
│   ├── Calendar
│   ├── Reminders
│   ├── Notes
│   └── Focus
├── HOME
│   ├── Smart Home Connectors
│   ├── Scenes
│   ├── Sensors
│   ├── Shopping
│   └── Household
├── OFFICE
│   ├── Email
│   ├── Meetings
│   ├── Documents
│   └── Projects
├── DEVELOPER
│   ├── Coding
│   ├── Testing
│   ├── Git
│   └── Debugging
├── SECURITY
│   ├── Permissions
│   ├── Audit
│   ├── Sandbox
│   ├── Secrets
│   └── Recovery
├── ANALYTICS
│   ├── Performance
│   ├── Usage
│   ├── Tests
│   ├── Diagnostics
│   └── Reliability
└── COMMERCIAL
    ├── Onboarding
    ├── Activation/Licensing
    ├── Updates/Rollback
    ├── Backup/Restore
    └── Support Diagnostics
```

## Execution priorities 1–9

1. **Real-PC stabilization** — P0/P1 defects first. Interactive Windows, mic, speaker, browser and installer behavior must not be inferred from CI.
2. **Windows Control 4.0** — Siri-like direct commands plus multi-step tool execution. Semantic UIA/OCR is preferred over coordinate guessing. Every consequential step must retain permission and evidence.
3. **Voice Agent 4.0** — natural Hinglish/Hindi/English, wake-word path, silence-aware STT, barge-in and continuous conversation. Free Edge voice remains the default test path; premium realtime providers are optional adapters.
4. **Screen Vision** — screenshot/image reasoning, OCR-assisted targeting and confidence-gated action. Ambiguous target means stop/ask, never guess.
5. **Browser Agent** — safe search/read/research plus permission-gated navigation. Web content is untrusted. No CAPTCHA bypass or fabricated submission success.
6. **Home AI Core** — Home Assistant/MQTT-style connector layer, device registry, scenes/routines and sensor state. Physical device success requires connector evidence and real-home E2E.
7. **Automation Engine** — recurring and conditional routines, resumable jobs, bounded retries, idempotency and condition evidence.
8. **Commercial Layer** — onboarding, customer profiles, activation/licensing, update channels, rollback, backup/restore and support diagnostics. Secrets are never bundled in the EXE.
9. **Home Lab / Release Gate** — Windows 10/11, sleep/wake, restart/crash recovery, offline/slow network, Chrome/Edge, different DPI/resolutions, mic/speaker and smart-home devices. Release requires P0=0 and P1=0.

## Windows Control 4.0 contract

Direct computer requests should act like an assistant rather than a tutorial. Current safe controls include app launch, semantic click/type, keyboard/mouse, browser search, volume, media play/pause/next/previous, active-window minimize/maximize/close, Task View and standard browser/editing shortcuts.

Compound requests use the agent/mission path: plan the smallest safe sequence, execute each tool through permissions, inspect result evidence, recover/re-plan on failure, and never report the whole sequence as successful when a step is unverified.

Exact numeric system volume is **not yet guaranteed** by media-key control and must not be claimed as exact until a verified Windows audio API is integrated.

## Truthful maturity

Automated tests can verify logic and packaging. They do not prove physical microphone output, audible speaker output, real browser state, camera behavior, multi-monitor targeting, sleep/wake recovery or smart-home hardware. Those remain `NOT VERIFIED` until tested on real hardware.

A feature is considered product-complete only when:

`Implementation + regression + packaged build + real customer scenario + failure/recovery evidence`
