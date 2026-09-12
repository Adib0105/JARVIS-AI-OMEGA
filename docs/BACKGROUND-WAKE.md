# Background wake, daily briefing and YouTube

## One-time Windows setup

1. Update the project and run `./setup_windows.ps1 -OfflineVoice`. Packaged Windows builds include Vosk, tray and browser automation dependencies; Microsoft Edge must be installed separately.
2. Download and extract a suitable English or Hindi model from [Vosk models](https://alphacephei.com/vosk/models). In **BACKGROUND / WEATHER**, click **Choose Vosk model folder** and select the extracted folder. Existing `VOSK_MODEL_PATH` is also supported. Recognition quality and the recognized spelling depend on the model, microphone and accent. No model is silently downloaded or trained.
3. Turn off the older **WAKE WORD** and **LIVE** modes. Open **BACKGROUND / WEATHER**, search for your city, select the correct region/country and save it. City search and coordinates are sent to [Open-Meteo](https://open-meteo.com/en/docs); ambient microphone audio stays local in this background mode. Your normal AI/TTS provider settings still apply to commands and spoken replies.
4. Click **Enable / pause background microphone**. The tray icon means listening is enabled. Close the main window: the process remains running in the tray. Say **Jarvis**, **Jarves**, **जार्विस** or your configured wake phrase to reveal it and hear “Yes boss, good morning/afternoon/evening”, temperature, today's maximum precipitation probability and measured CPU/RAM/battery use.
5. To start at Windows sign-in, deliberately run `./setup_background_startup.ps1`. Undo with `./setup_background_startup.ps1 -Remove`. Keep the installation folder in place. This creates only a current-user Startup shortcut. Enable background listening once before using it.

The PC must be powered on, awake and signed in. A fully terminated app cannot listen. **EXIT COMPLETELY** (or tray Exit) stops listening; closing with X keeps it running only when background mode is active. Missing model/microphone/tray errors restore the window. Pause background listening before push-to-talk, Live conversation, or the older wake listener. Resuming a saved chat pauses background listening. Only one Windows desktop instance can run per sign-in session.

## Say a command

- “Jarvis, YouTube par Tum Hi Ho chalao.”
- “Jarvis, play Kesariya on YouTube.”
- “Jarvis YouTube jao aur Arijit Singh search karo aur pehla video chala do.”

Say the wake name and song in one utterance. Saying only “Jarvis” gives the briefing; after it finishes, say “Jarvis” plus your command. Listening is suppressed during speech, briefings and active tasks to reduce self-triggering. Use headphones to reduce wake triggers from other media.

YouTube commands use the existing browser permission gate and audit trail. Desktop automation must be enabled. A visible, separate Microsoft Edge session searches YouTube, chooses the first ordinary video result (excluding ad/channel/playlist cards), starts playback and checks the video element. Results may differ from your signed-in browser. No account cookies are imported, media downloaded, or consent/sign-in buttons automatically accepted. Consent, age restrictions, browser policies, unavailable videos or site changes may require manual action; JARVIS reports unverified playback instead of claiming success. A playing advertisement is identified separately. Full app Exit also closes this automation browser.

Weather comes from Open-Meteo, with no API key required for its non-commercial free service. Forecast probability is not certainty; precipitation includes rain, showers and snow. Missing city, missing readings or network failure are spoken explicitly. Location is selected by you, never guessed; the forecast uses that location's day, while greeting uses the PC's local time. Data attribution: [Open-Meteo](https://open-meteo.com/) / CC BY 4.0; [geocoding docs](https://open-meteo.com/en/docs/geocoding-api). Commercial deployments should review Open-Meteo's service terms.

## Validation and limits

Automated tests cover wake boundaries, cancellation, speech suppression, close/exit lifecycle, weather missing data/failure, YouTube command routing and permission denial, first-video selection and playback verification. Windows CI packages the dependencies. Real microphone recognition, tray rendering, foreground behavior and YouTube playback still require an on-PC check; network services and browser layouts can change.
