# JARVIS AI OMEGA 8.0.0-rc1 — Windows E2E Evidence Checklist

This checklist separates automated software/package evidence from real-device evidence. A CI smoke check never upgrades a physical-device or live-service item to verified.

## Status vocabulary

- **AUTOMATED** — exercised by an automated test/job; the exact run/commit must be recorded as evidence.
- **MANUAL** — requires a real Windows operator/device interaction.
- **NOT TESTED** — no qualifying evidence has been recorded for the release candidate being evaluated.

For a release candidate, record the exact commit SHA, workflow run ID, Windows machine/OS build for manual checks, application version, installer SHA-256, date, tester, and result. Never reuse evidence from an older commit after code or packaging changes.

## Application

| Check | Method | Release evidence before an exact-RC run |
|---|---|---|
| Fresh packaged startup/bootstrap path | AUTOMATED | NOT TESTED |
| Installed EXE package-healthcheck | AUTOMATED | NOT TESTED |
| Normal GUI launch to usable window | MANUAL | NOT TESTED |
| Normal shutdown without orphaned JARVIS process | MANUAL | NOT TESTED |
| Re-launch after shutdown | MANUAL | NOT TESTED |

## Computer use

| Check | Method | Release evidence before an exact-RC run |
|---|---|---|
| UIA target resolution logic | AUTOMATED | NOT TESTED |
| UIA action on real Windows application | MANUAL | NOT TESTED |
| Keyboard typing in intended focused window | MANUAL | NOT TESTED |
| Mouse action hits intended target | MANUAL | NOT TESTED |
| Screenshot capture returns current display | MANUAL | NOT TESTED |
| OCR configured and reads an actual on-screen target | MANUAL | NOT TESTED |
| Chrome launch and visible-window verification | MANUAL | NOT TESTED |
| Notepad launch and visible-window verification | MANUAL | NOT TESTED |
| Focus loss/wrong-window protection | MANUAL | NOT TESTED |
| Post-action expected-state verification | MANUAL | NOT TESTED |
| Wrong target is rejected | AUTOMATED | NOT TESTED |
| Missing UI element fails safely | AUTOMATED | NOT TESTED |
| Low-confidence OCR is rejected | AUTOMATED | NOT TESTED |
| UIA unavailable falls back/stops safely | AUTOMATED | NOT TESTED |

Important: OS input acceptance is not success evidence. For an important action use **ACT → OBSERVE → EXPECTED STATE CHANGE → VERIFY**. If the expected state cannot be observed, report an unverified/acknowledged outcome rather than success.

## Voice

| Check | Method | Release evidence before an exact-RC run |
|---|---|---|
| TTS worker starts in frozen package | AUTOMATED | NOT TESTED |
| Audible TTS reaches real speakers | MANUAL | NOT TESTED |
| Microphone captures real speech | MANUAL | NOT TESTED |
| Speech recognition returns intended utterance | MANUAL | NOT TESTED |
| Stop TTS | MANUAL | NOT TESTED |
| Pause/resume TTS | MANUAL | NOT TESTED |
| Closing app terminates playback | MANUAL | NOT TESTED |

Package import/worker success does not prove microphone or audible speaker output.

## Providers

| Check | Method | Release evidence before an exact-RC run |
|---|---|---|
| Missing/invalid configuration handled safely | AUTOMATED | NOT TESTED |
| Real configured provider returns a response | MANUAL | NOT TESTED |
| Invalid real key produces truthful auth failure | MANUAL | NOT TESTED |
| Provider timeout respects configured deadline | AUTOMATED + MANUAL | NOT TESTED |
| Real rate-limit response is classified correctly | MANUAL | NOT TESTED |
| Unavailable model error is surfaced truthfully | MANUAL | NOT TESTED |
| Network/provider recovery does not fabricate success | MANUAL | NOT TESTED |

A live API must not be marked `INTEGRATION_TESTED`/`E2E_VERIFIED` without an actual live request for the exact release candidate.

## Files

| Check | Method | Release evidence before an exact-RC run |
|---|---|---|
| Normal file inside allowed root | AUTOMATED | NOT TESTED |
| Absolute path outside allowed root blocked | AUTOMATED | NOT TESTED |
| `../` traversal blocked | AUTOMATED | NOT TESTED |
| Symlink escape blocked | AUTOMATED | NOT TESTED |
| Windows junction/reparse escape blocked | AUTOMATED | NOT TESTED |
| Nested secret-like path blocked | AUTOMATED | NOT TESTED |
| Renamed secret content blocked | AUTOMATED | NOT TESTED |
| Sensitive extension blocked | AUTOMATED | NOT TESTED |

## Display

| Check | Method | Release evidence before an exact-RC run |
|---|---|---|
| 100% DPI | MANUAL | NOT TESTED |
| 125% DPI | MANUAL | NOT TESTED |
| 150% DPI | MANUAL | NOT TESTED |
| 1920×1080 | MANUAL | NOT TESTED |
| Alternate supported resolution | MANUAL | NOT TESTED |
| Window moved after target discovery | MANUAL | NOT TESTED |
| Coordinate fallback does not trust stale coordinates | MANUAL | NOT TESTED |

## Network

| Check | Method | Release evidence before an exact-RC run |
|---|---|---|
| Disconnect during provider request | MANUAL | NOT TESTED |
| Reconnect and retry/recovery behavior | MANUAL | NOT TESTED |
| Provider failure classification | AUTOMATED | NOT TESTED |
| Request deadline/cancellation cleanup | AUTOMATED | NOT TESTED |

## Installer / clean install

| Check | Method | Release evidence before an exact-RC run |
|---|---|---|
| EXE build succeeds | AUTOMATED | NOT TESTED |
| Release bundle secret exclusion | AUTOMATED | NOT TESTED |
| Installer compiles | AUTOMATED | NOT TESTED |
| Installer installs without repository/Python present | AUTOMATED | NOT TESTED |
| Installed first-run bootstrap healthcheck | AUTOMATED | NOT TESTED |
| Installed package healthcheck | AUTOMATED | NOT TESTED |
| Installed TTS worker healthcheck | AUTOMATED | NOT TESTED |
| Start Menu/desktop shortcuts created as requested | AUTOMATED | NOT TESTED |
| Uninstall removes application binaries | AUTOMATED | NOT TESTED |
| Uninstall preserves per-user data | AUTOMATED | NOT TESTED |
| Human clean-machine GUI first run | MANUAL | NOT TESTED |
| Human configuration with real API key | MANUAL | NOT TESTED |
| Human first real AI response from installed build | MANUAL | NOT TESTED |

## Exact-release evidence record

Fill this section only after the exact release candidate has been exercised.

```text
Commit SHA: NOT TESTED
Application version: 8.0.0-rc1
CI workflow run ID: NOT TESTED
Installer filename: NOT TESTED
Installer SHA-256: NOT TESTED
Windows edition/build: NOT TESTED
Display/DPI: NOT TESTED
Tester: NOT TESTED
Date: NOT TESTED

Automated gate: NOT TESTED
Manual application E2E: NOT TESTED
Computer-use device verification: NOT TESTED
Microphone verification: NOT TESTED
Audible TTS verification: NOT TESTED
Live-provider verification: NOT TESTED
Overall device/E2E status: NOT TESTED
```

Do not convert any `NOT TESTED` entry to verified from inference, package import success, an older workflow run, or documentation alone.
