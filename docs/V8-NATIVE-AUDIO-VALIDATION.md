# V8 P0.3 continuation — native worker recovery

2026-10-06. **Development only; physical voice acceptance remains open.**

`jarvis/native_audio.py` moves PortAudio open/read/close into a spawned process.
Both push-to-talk/VAD and background wake use it through the existing exclusive
stream ownership path. Its bounded byte protocol reports actual device readiness,
PCM frames, overflow or errors. Stalled reads expire; cancellation only sets an
event on the caller, while the owner terminates, joins and, if necessary, kills
and reaps the child. Unconfirmed termination blocks future workers. The child
also watches parent liveness. These trusted audio workers are not OS sandboxes
for generated code.

Built-in Google/Vosk transcription and the background follow-up Vosk recognizer
also use a bounded spawned process. Custom extension/test callables retain the
existing bounded, single-owner thread contract. ASR ownership remains held through
termination; cancelled results are discarded. A fresh Vosk ASR worker loads its
model again, so real latency/soak measurement is required before promotion. The
background wake recognizer/model remains in the listener process; its native
inference is still a remaining process-recovery boundary.

Files: `jarvis/native_audio.py`, `microphone.py`, `background_ui.py`,
`desktop_app.py`, `scripts/check_windows_package.ps1`; tests in
`tests/test_v8_native_audio.py`, with the existing microphone fixtures updated in
`test_voice_updates.py` and `test_voice_reliability.py` for the process adapter.
Permissions, local-only background wake policy, wake rejection rules and the
existing controller backoff are preserved. No ambient microphone audio is sent
to a provider by this change.

Local evidence: **11 new tests passed** using real spawned/terminated processes
with synthetic device/recognizer functions. They cover stalled read, repeated
abort/restart, permission failure, process crash, malformed/oversized frames,
overflow, ASR timeout/cancel/late-result suppression and startup cleanup. The full
desktop suite passed **506 tests: 505 passed, one Windows DPAPI skip**, with
ResourceWarning as error (7.530s). The source entry-point lifecycle check passed.

The new `--jarvis-audio-worker-check` packaged smoke mode opens no microphone: it
proves that a frozen Windows executable can spawn, receive a readiness message
and terminate/reap a trusted child without reopening the GUI. Its CI result must
be assessed separately from source tests.

Not verified here: real device open/permission/Bluetooth reconnect, login/resume,
wake accuracy, barge-in, idle soak, p50/p95 latency, physical TTS interruption and
frozen capture with a real device. No voice release gate is marked complete.
Next: full semantic target integration and real Windows device acceptance.
Rollback is a normal Git revert; no persisted schema/data changes.
