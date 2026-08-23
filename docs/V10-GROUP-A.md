# JARVIS OMEGA V10 — Group A (Features 1–25)

Group A is the first delivery slice of the V10 master list. The rule is strict: `implemented` means code already exists in the repository; `foundation` means the control contract/state/safety boundary exists but the feature still needs subsystem integration and/or real Windows validation.

## Group A

1. Live Companion Mode — foundation
2. Instant Barge-In — foundation
3. Ultra-Low-Latency Voice — foundation
4. Natural Hinglish + English — implemented
5. Human-like Conversation Style — implemented
6. Multiple Voice Personalities — foundation
7. Wake Word V2 — foundation
8. Windows Auto-Start — foundation
9. Smart Greeting Engine — implemented
10. Background Companion Service — foundation
11. System Tray JARVIS — foundation
12. Screen Awareness — foundation
13. Current Context Understanding — foundation
14. Computer Use V3 — foundation
15. Visual Computer Control — foundation
16. Multi-Monitor Awareness — foundation
17. Application Control — implemented
18. Advanced File Agent — foundation
19. Browser Agent V3 — foundation
20. Research Agent — foundation
21. Document Intelligence V3 — foundation
22. Coding Agent V3 — foundation
23. Personal Memory V3 — foundation
24. Memory Control Center — foundation
25. Routine Learning — foundation

## New Group-A control layer

`jarvis/v10_group_a.py` provides an exact 1–25 feature manifest, Live Companion coordination, screen-awareness modes, privacy-aware current-context state, contextual reference resolution, routine learning primitives and root-scoped file target validation.

It intentionally does not bypass the existing permission system. Screen capture, browser control, file writes, desktop control, credentials, messages and other sensitive operations must continue through their established security/approval gates.

## Completion gates

A foundation item can move to `implemented` only when its actual subsystem is wired into the desktop runtime and deterministic tests pass. Features involving Windows startup/service/tray, microphone echo/barge-in, multi-monitor control or visual computer control also require a real Windows test before release-ready status.

Group B will cover master-list features 26–50 after Group A integration is advanced and regression-tested.
