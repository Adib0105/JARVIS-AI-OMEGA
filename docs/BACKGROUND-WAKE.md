# Background wake, daily briefing and YouTube

## One-time Windows setup

1. Update the project and run `./setup_windows.ps1 -OfflineVoice`. Packaged Windows builds include Vosk, tray and browser automation dependencies; Microsoft Edge must be installed separately.
2. Download and extract a suitable English or Hindi model from [Vosk models](https://alphacephei.com/vosk/models). In **BACKGROUND / WEATHER**, click **Choose Vosk model folder** and select the extracted folder. Existing `VOSK_MODEL_PATH` is also supported. Recognition quality and the recognized spelling depend on the model, microphone and accent. No model is silently downloaded or trained.
3. Turn off the older **WAKE WORD** and **LIVE** modes. Open **BACKGROUND / WEATHER**, search for your city, select the correct region/country and save it. City search and coordinates are sent to [Open-Meteo](https://open-meteo.com/en/docs); ambient microphone audio stays local in this background mode. Your normal AI/TTS provider settings still apply to commands and spoken replies.
4. Click **Enable always-on mode (wake + tray + sign-in)**, or enable the microphone and sign-in shortcut separately. READY is shown only after the Vosk model loads and the real microphone stream opens.
5. Close the main window: the process remains running in the tray. Say **Wake up Jarvis**, **Hey Jarvis**, **Jarvis**, **Jarves**, **Jervis**, **जार्विस** or your configured phrase. With the default follow-up option, Friday says **“Yes boss, kya chahiye?”**, listens for one offline command, then resumes hotword listening.
6. Keep **Bring the JARVIS window forward** off for background use while Chrome or another app stays in front. Enable it only if you want the full window on wake.
7. The script `./setup_background_startup.ps1` remains available for source/portable installs; undo it with `./setup_background_startup.ps1 -Remove`.

The PC must be powered on, awake and signed in. A fully terminated app cannot listen. **EXIT COMPLETELY** (or tray Exit) stops listening; closing with X keeps it running in the tray. A device error does not steal foreground focus: the tray stays alive and retries with bounded backoff. Setup errors remain visible when the user explicitly enables the feature. Pause background listening before push-to-talk, Live conversation, or the older wake listener. Only one Windows desktop instance can run per sign-in session.

## Say a command

- “Jarvis, YouTube par Tum Hi Ho chalao.”
- “Jarvis, play Kesariya on YouTube.”
- “Jarvis YouTube jao aur Arijit Singh search karo aur pehla video chala do.”

You may say the wake name and command in one utterance, or use the two-turn flow: “Wake up Jarvis” → “Yes boss, kya chahiye?” → your command. Listening is suppressed while Friday speaks or an active task runs, reducing self-triggering. Use headphones when other media repeatedly contains the wake name.

YouTube commands use the existing browser permission gate and audit trail. Desktop automation must be enabled. A visible, separate Microsoft Edge session searches YouTube, chooses the first ordinary video result (excluding ad/channel/playlist cards), starts playback and checks the video element. Results may differ from your signed-in browser. No account cookies are imported, media downloaded, or consent/sign-in buttons automatically accepted. Consent, age restrictions, browser policies, unavailable videos or site changes may require manual action; JARVIS reports unverified playback instead of claiming success. A playing advertisement is identified separately. Full app Exit also closes this automation browser.

Weather comes from Open-Meteo, with no API key required for its non-commercial free service. Forecast probability is not certainty; precipitation includes rain, showers and snow. Missing city, missing readings or network failure are spoken explicitly. Location is selected by you, never guessed; the forecast uses that location's day, while greeting uses the PC's local time. Data attribution: [Open-Meteo](https://open-meteo.com/) / CC BY 4.0; [geocoding docs](https://open-meteo.com/en/docs/geocoding-api). Commercial deployments should review Open-Meteo's service terms.

## Validation and limits

Automated tests cover wake boundaries, readiness/error handshakes, cancellation, speech suppression, follow-up routing, close/exit lifecycle, weather failure, command routing and permission denial. Windows CI packages the dependencies. Real microphone recognition, tray rendering, focus retention, account UI and browser playback still require an on-PC check; devices, network services and browser layouts can change.
