# Voice and AI reliability update

## What was checked

Audit base: `36fc6f37c0b87b64f2ea69383b1b0d54050df376` on `main`.
Reviewed voice playback/lifecycle, microphone and wake-word capture, desktop voice wiring, provider configuration/factory/routing, speech formatting, Windows packaging and CI. Ran the complete existing regression suite, including its security, memory, tool and self-development tests. This is not a claim that every function or real device has been exhaustively verified.

Baseline: 194 tests passed on Python 3.12/Linux after installing the declared dependencies.
Updated: 220 tests passed, including 26 new regression/integration tests. Compilation and `git diff --check` passed. Tests use mock AI providers: no paid API requests, external messages or real desktop actions were executed.

## Confirmed issues and changes

| Finding | Change |
| --- | --- |
| Frozen desktop tried `sys.executable -m edge_playback`, which launches the application EXE instead of Python | Dedicated `--jarvis-speech-worker` dispatch before GUI imports; same helper supports source installs |
| STOP could miss a child launched immediately after cancellation | Cancellation check and process registration share a lock; queued utterances carry generation IDs |
| Rapid pause/resume erased the interruption reason and could drop speech | Preserve interruption until worker observes it, then replay the utterance |
| Offline TTS ran in-process and could block shutdown | Offline and neural speech both run in a killable child process |
| Voice error state immediately became idle; neural failure silently switched voice | Persistent error state, fallback indication and actionable system messages |
| Mic/wake results could arrive after disabling listening | Cancellation events and result checks; wake commands preserve original case |
| Delayed live-listening callbacks could reopen the microphone after LIVE was disabled | Recheck live state, mute, busy, closing and playback status when callback runs |
| A silent live-listening window never restarted capture | Reschedule while LIVE remains enabled |
| `latest`, `planet`, `classical` triggered `test`, `plan`, `class` model routes | Match whole terms instead of substrings |
| Local inference existed only as fallback and primary startup still required a cloud provider | `AI_PROVIDER=local` with the existing OpenAI-compatible local provider |
| Long alphabetic words could be hidden as IDs when a later word contained a digit | Restrict identifier lookaheads to the same token |
| Conda workflow referenced absent `environment.yml` | Remove redundant broken workflow; retain the full Linux/Windows CI |
| Windows package smoke environment omitted optional microphone dependencies | Install Windows dependencies for packaging; collect offline voice drivers; test frozen worker startup |

## Warm female speech

All voices are AI-generated. This is a configurable voice profile, not a reproduction of a particular ChatGPT voice or real person.

### Existing Edge female voices (default)

In your local `.env`:

```dotenv
VOICE_ENGINE=edge
VOICE_HINDI=hi-IN-SwaraNeural
VOICE_HINGLISH=en-IN-NeerjaNeural
VOICE_ENGLISH=en-IN-NeerjaNeural
```

Requires internet. Windows uses native media playback. Linux/macOS source installs require `mpv` or `ffplay`. Voice availability and pronunciation depend on the service.

### Optional expressive OpenAI voice

```dotenv
VOICE_ENGINE=openai
OPENAI_API_KEY=your_private_api_key
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_VOICE=coral
OPENAI_TTS_INSTRUCTIONS=Speak in a warm, gentle, affectionate female voice. Use natural conversational pacing and clear Hindi, Hinglish or English pronunciation. Sound caring and relaxed, without exaggerated pitch or breathiness.
```

Keep the key only in your private `.env`; do not commit it or paste it into public issues. This engine requires an API account with available credit and sends spoken text to OpenAI. It is opt-in and has separate API usage costs. Your chat provider can still be OpenRouter or local.

Speech input is split into bounded chunks. Each chunk is synthesized before playback. This is not streaming, full-duplex ChatGPT Voice; pause/speed changes replay the current utterance and may synthesize it again. A failed online engine falls back to the installed offline voice and displays a fallback message. It does not silently switch between online providers.

Implementation reference: [official OpenAI text-to-speech documentation](https://developers.openai.com/api/docs/guides/text-to-speech). The guide documents `gpt-4o-mini-tts`, `coral`, style instructions and supported output formats. The application omits style instructions for legacy `tts-1` models.

### Offline speech

```dotenv
VOICE_ENGINE=pyttsx3
OFFLINE_VOICE_ID=
```

Automatically prefers an installed female voice when recognizable; otherwise uses the system default. Set `OFFLINE_VOICE_ID` to an installed voice ID to override. Offline quality depends on installed Windows speech packs and is not equivalent to neural cloud speech.

## Local AI without a cloud chat key

Start an OpenAI-compatible local inference server and load a model supported by your PC. Then set:

```dotenv
AI_PROVIDER=local
LOCAL_AI_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_AI_MODEL=your-exact-installed-model-id
VOICE_ENGINE=pyttsx3
```

Use the exact model ID exposed by your local server. Clear any cloud-specific `FAST_MODEL`, `SMART_MODEL`, `VISION_MODEL`, `CODING_MODEL`, `PLANNING_MODEL`, `REVIEW_MODEL` or `SUMMARY_MODEL` overrides unless the local server also exposes those IDs. Tool calling and vision require a model/server supporting those capabilities; a text-only model does not gain vision automatically.

Local chat does not require a cloud key. The existing microphone transcription still uses Google's online recognition service. Web tools and configured integrations also use the network. Selecting local chat does not make every feature offline.

This uses pretrained models plus the project's existing memory/retrieval. No new foundation model, ML training run, autonomous production self-modification or full-duplex audio system was created. Existing tool approvals and security checks remain in force.

## Run and check on Windows

1. Check out the update branch, then run `setup_windows.ps1` from PowerShell.
2. Edit your private `.env` with one voice configuration above and a valid AI provider.
3. Run `run_desktop.bat` or `run_jarvis.bat`.
4. In the CLI, try `/voice-test hindi`, `/voice-test english` and `/voice-test hinglish`.
5. In the desktop, check STOP, rapid pause/resume, speed adjustment, LIVE on/off, and closing while speaking/listening.
6. For a packaged build, run `build_windows.ps1`; the CI package check exercises the speech worker dispatcher without audio hardware.

Local verification:

```powershell
python -m compileall -q jarvis tests desktop_app.py main.py
python -m unittest discover -s tests -v
```

Not verified here: live paid speech synthesis, subjective female voice quality, real Windows speakers/microphone, Windows native MP3 playback, local model inference quality or on-device latency. The PR's GitHub Actions results show the separate Windows/Python matrix and packaging status.
