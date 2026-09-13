# Twenty reliability improvements

This release addresses the user's repeated voice, wake and updater failures.
These are scoped improvements, not a claim of zero remaining defects.

1. Fix Windows SAPI argument parsing: use a UTF-8 PowerShell file with named parameters instead of appending arguments to `-Command`.
2. Resolve Windows PowerShell from the system installation rather than a PATH-selected executable.
3. Add a packaged real SAPI-to-WAV release gate; reject empty/silent output without needing a speaker or API key.
4. Pass the selected voice profile explicitly after configuration loading so `.env` cannot undo the UI choice.
5. Bound each Edge synthesis request to 20 seconds before existing offline fallback.
6. Revalidate downloaded installer size and SHA-256 before starting the helper.
7. Require an explicit helper-ready handshake before closing JARVIS; validate the target folder and installer in the helper first.
8. Run the staged helper with a process-local execution-policy setting, leaving Windows policy unchanged.
9. Prepare the update on a worker thread so the UI remains responsive during verification.
10. Reserve the assistant while preparing installation so a new action cannot race with shutdown; release it on failure.
11. Bound release JSON responses and reject malformed release records and invalid boolean asset sizes.
12. Check releases after startup and every six hours; offer optional automatic installation while idle.
13. Download/setup the official small Indian English wake model inside Background / Weather, with progress and offline failure handling.
14. Limit model download/extraction size and time, reject archive path traversal/symlinks, validate required files and remove partial staging files.
15. Reuse and automatically discover the installed wake model after restart.
16. Apply microphone enablement immediately when the user explicitly enables background listening; no restart required.
17. Preserve background preference after a listener/device error and retry after 30 seconds; normal pause still disables it.
18. Use the same bounded wake aliases in both listeners, including Jarvis, Jarves and Hindi spelling; prevent substring false triggers.
19. Improve weather validation, explicit units, humidity/wind readings and labeled stale-cache fallback capped at 30 minutes.
20. Improve setup access: visible Background / Weather sidebar button, installer sign-in startup option, smaller settings minimum height, and BOM/duplicate-key-safe settings saves.

## First setup

Install the new Setup and launch the desktop shortcut. Close any older portable
copy through its tray menu first. In Background / Weather, download the wake
model, enable the background microphone, and choose sign-in startup. Select a
weather city. To allow unattended app restarts for updates, enable the automatic
update checkbox. Regular update checks run without this opt-in.

Wake requires an awake PC, a signed-in Windows session and an available microphone.
Exit completely stops listening; closing the window leaves the tray running.
The model is downloaded from [Vosk's official model catalog](https://alphacephei.com/vosk/models).
Recognition accuracy and physical speaker/microphone behavior require a test on
the user's machine. Existing desktop tool permission checks remain in effect.

## Verification

Local regression tests cover malformed weather/releases, stale forecast expiry,
unsafe/partial model archives, settings migration, voice lifecycle and existing
AI/tool behaviors. Windows CI additionally builds the frozen app, generates real
speech audio, checks no-key GUI startup and verifies installer/upgrade data
preservation. A passed WAV test proves synthesis, not audible speaker playback.
