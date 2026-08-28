# JARVIS AI OMEGA — Capability Matrix

`Implemented` means a real code path exists. `Tested` means deterministic automated coverage exists. Neither column proves a live provider, physical device or real Windows action.

| Capability | Implemented | Tested | Verified on Windows | Risk | Status |
|---|---:|---:|---:|---|---|
| Provider text chat | Yes | Yes | No | Medium | TESTED / LIVE NOT VERIFIED |
| Model routing/fallback/deadline | Yes | Yes | No | Medium | TESTED |
| Persisted mission orchestration | Yes | Yes | No | High | TESTED |
| Execution vs verification outcomes | Yes | Yes | No | High | TESTED |
| Capability permissions/approval | Yes | Yes | No | Critical | TESTED |
| Tamper-evident audit chain | Yes | Yes | No | Critical | TESTED |
| Local profiles/authentication | Yes | Yes | No | High | TESTED |
| Password recovery/profile migration | Yes | Yes | No | High | TESTED; recovery is one-time |
| Profile avatar normalization | Yes | Yes | No | Low | TESTED |
| Memory/RAG lifecycle | Yes | Yes | No | High | TESTED |
| Document/PDF/DOCX/XLSX/CSV handling | Yes | Yes | No | Medium | TESTED |
| Local file-root/traversal protection | Yes | Yes | Partial CI | Critical | TESTED; junction case Windows-only |
| Browser public-target security | Yes | Yes | No | Critical | TESTED |
| Computer-use semantic targeting | Yes | Yes | No | Critical | TESTED / DEVICE NOT VERIFIED |
| OCR fallback policy | Yes | Yes | No | High | TESTED / DEVICE NOT VERIFIED |
| Windows app/media/window commands | Yes | Yes | No | High | TESTED / DEVICE NOT VERIFIED |
| Voice cleanup/prosody/barge-in logic | Yes | Yes | No | Medium | TESTED |
| TTS packaged worker | Yes | Yes | Automated CI only | Medium | TESTED / AUDIBLE NOT VERIFIED |
| Microphone/STT | Yes | Partial | No | High | LIMITED / DEVICE NOT VERIFIED |
| Observability/resource sampling | Yes | Yes | No | Medium | TESTED; optional sensors degrade independently |
| Backup/integrity/restore gates | Yes | Yes | No | High | TESTED |
| Controlled self-development | Yes | Yes | No | Critical | EXPERIMENTAL / SAFE-OFF FOR PRODUCTION |
| Skill lifecycle | Yes | Yes | No | High | TESTED / CONTROLLED |
| Windows EXE build | Yes | Yes | Automated CI only | High | CI-GATED |
| Inno installer/repair/uninstall | Yes | Yes | Automated CI only | High | CI-GATED / HUMAN UX NOT VERIFIED |
| Updater/checksum verification | Yes | Yes | Automated CI only | Critical | TESTED / REAL RESTART NOT VERIFIED |
| Smart planner/proactive/workflow center | Partial | Partial | No | High | NOT A STABLE RELEASE CLAIM |
| Daily briefing/smart reminders | Partial | Partial | No | Medium | NOT A STABLE RELEASE CLAIM |

