# Voice controls and optional offline speech

## New controls

The desktop's **VOICE SETTINGS** button opens a profile chooser with Hindi, Hinglish and English previews and a local diagnostic report. All speech is AI-generated. Preview buttons save the selected profile and speak a sample; OpenAI previews use your API credit.

| Profile | Behavior |
| --- | --- |
| configured | Uses your `.env` voice settings |
| gentle | Slower, soft female Edge voice; internet required |
| bright | Slightly faster female Edge voice; internet required |
| premium | OpenAI coral voice; API key and usage credit required |
| offline | Installed pyttsx3 system voice; no online TTS |

Only the profile name is persisted, in `voice_preferences.json` beside the runtime database. API credentials are never stored in this preference file. Select **configured** to return to `.env` settings. Existing voice configuration and keys are not overwritten.

Terminal controls:

```text
/voice-profile
/voice-profile gentle
/voice-profile offline
/voice-profile configured
/voice-doctor
/voice-test hindi
/voice-test hinglish
/voice-test english
```

## Diagnose microphone and voice setup

You can run diagnostics even before configuring a chat API key:

```powershell
python -m jarvis.voice_diagnostics
```

The report checks installed packages, selected engines, configured key presence, local model folder existence and available input devices. It does not record audio, call an online service, reveal API keys or claim that synthesis/recognition is working. Provider credit, model validity and real audio quality need separate live checks.

Use a device ID or input-device name from the report:

```dotenv
MIC_DEVICE=2
```

A blank value uses the system default. Device IDs may change when hardware is reconnected; a name may be more convenient. Simultaneous recordings are blocked, so wake-word and push-to-talk cannot open overlapping microphone streams. Wait for an active recorder to stop before restarting wake-word mode.

## Offline speech recognition

Install optional dependencies from the project directory:

```powershell
.\setup_windows.ps1 -OfflineVoice
```

Or in an existing environment:

```powershell
python -m pip install -r requirements-offline-voice.txt
```

Download an appropriate language model from the [official Vosk model catalog](https://alphacephei.com/vosk/models), extract it locally, and set:

```dotenv
SPEECH_ENGINE=vosk
VOSK_MODEL_PATH=C:/JarvisModels/your-extracted-model-folder
```

The path must point to the extracted model directory, not a ZIP or its parent directory. Hindi and English use their respective language models; arbitrary Hinglish code-switching quality is not guaranteed. `SPEECH_LANGUAGE` applies to the default Google backend; Vosk's language comes from the selected model.

JARVIS does not download models automatically. Missing/invalid models or missing Vosk packages produce an error, with no automatic online transcription fallback. The model is cached in memory after first use. Recognition processes captured 16-bit mono audio using the actual capture sample rate; it preserves completed segments and the final segment.

For a local conversation pipeline, combine this with the previous local AI mode and choose the **offline** voice profile:

```dotenv
AI_PROVIDER=local
LOCAL_AI_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_AI_MODEL=your-installed-chat-model-id
SPEECH_ENGINE=vosk
VOSK_MODEL_PATH=C:/JarvisModels/your-extracted-model-folder
VOICE_ENGINE=pyttsx3
```

Select `/voice-profile configured` or `/voice-profile offline` if an online profile was saved earlier. Web searches and other online integrations remain online features; this configuration makes the conversation audio/chat paths local only when your configured AI server is local too.

For offline-capable packaged builds, install the optional dependencies before `build_windows.ps1`. The build collects Vosk and its native libraries when present. Model files remain external, so set `VOSK_MODEL_PATH` on the destination PC.

References: [Vosk overview](https://alphacephei.com/vosk/), [upstream Python recognition example](https://github.com/alphacep/vosk-api/blob/master/python/example/test_simple.py).

## Additional fixes

- Desktop chat/mission/microphone/vision error callbacks now retain the error string when the exception scope ends.
- CLI exits terminate the speech worker rather than leaving it alive.
- Rapid wake-word restart cannot clear the stop flag of a still-running listener.
- Windows setup works from another working directory and checks virtual-environment creation failures.
- Windows build compilation excludes the virtual environment.
- Fixed the missing closing quote in the prior package-check workflow and moved verification into a dedicated PowerShell script.

## Verification and limits

238 tests pass on Python 3.12/Linux, including 18 new follow-up tests. The suite uses mocked Vosk recognition and devices: model accuracy, real microphone operation, subjective voice quality, and GUI behavior on your PC remain device-dependent and are not certified by these tests. No new model was trained, no model weights were downloaded and no paid speech API was called. Refer to PR #5's GitHub Actions for Windows packaging and the Python-version matrix.
