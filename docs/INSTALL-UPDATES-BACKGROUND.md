# Install once, then update inside JARVIS

Download `JARVIS-AI-OMEGA-V7-Setup.exe` from this repository's latest GitHub Release. Run Setup once; it installs for your Windows user and creates Desktop and Start Menu shortcuts. No Python installation or administrator access is required. Keep the old portable folder until you have moved any wanted settings/history into the installed folder; a new installation does not automatically search your computer for old copies.

Open **UPDATE APP**, then **UPDATE AND RESTART**. The app downloads only this repository's published Windows installer, verifies its GitHub SHA-256 digest and size, waits for the current JARVIS process to exit, installs into the same folder and reopens. The installer does not bundle or remove `.env`, databases or runtime data. Network/download errors keep the running version intact; installer failures create an `update-result.txt` file beside the downloaded installer in `%TEMP%/jarvis-update-*`. This is not a transactional full-version rollback mechanism. Windows policy or antivirus can still prevent unsigned installers from running; do not disable them.

Future main-branch changes are built, tested and published automatically only after all CI gates pass. Merely committing a file does not make an untested update available. The Windows version includes the increasing CI run number. Public release assets supply the SHA-256 digest used by the updater ([GitHub documentation](https://docs.github.com/en/rest/releases/assets)); installation uses the documented [Inno Setup silent/no-restart parameters](https://jrsoftware.org/ishelp/topic_setupcmdline.htm).

## Background and weather

Switching windows leaves JARVIS running. **X** hides it to the Windows tray, independently of microphone mode. If the tray is unavailable, it minimizes to the taskbar instead. Use the tray menu or the Desktop shortcut to reopen; **EXIT COMPLETELY** stops it. In **BACKGROUND / WEATHER**, choose your city and optionally enable Windows sign-in startup. This starts JARVIS when you sign in, not while the PC is shut down or asleep.

Background listening still requires microphone permission and a selected extracted Vosk model. Existing Live/Wake modes can continue when minimized; only one microphone mode can own the device at a time. Pausing background listening stops microphone capture. Weather is also available through **WEATHER NOW**, `weather report` or `mausam batao`. Forecasts are cached for five minutes with a cache label; the city is never inferred silently.

## Responsiveness and verification

Greetings, time and system status avoid AI network requests; weather uses Open-Meteo directly. Neural speech renders a short first sentence before longer sections. Live recording's default end-of-speech silence is 0.55 seconds (an explicit existing setting is preserved). Detailed AI replies still depend on your provider, model, network and any requested tool operations.

CI covers Linux/Windows regressions, real packaged GUI focus switching/minimize/tray restore, offline local replies, installer-created Desktop shortcut, the actual update helper, settings/data preservation during reinstall, and launching the installed app. Physical microphone quality, real provider response times, third-party browser focus behavior and Windows security policy on your PC still need local testing. General desktop tools remain available; sensitive actions retain their permission checks.
