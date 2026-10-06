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
model again, so real latency/soak measurement is required before promotion.

Background wake now keeps its Vosk model in a separate warm worker too. Model
loading, each inference and reset have deadlines. Only one 100 ms audio request
is in flight, byte messages are bounded, reset requires acknowledgement and
cancelled transcripts cannot dispatch. Startup, inference or reset stalls cause
the owning listener to reap the worker before restart. The existing microphone
owner and controller suppression/backoff rules remain in place.

Files: `jarvis/native_audio.py`, `microphone.py`, `wake_service.py`, `background_ui.py`,
`desktop_app.py`, `scripts/check_windows_package.ps1`; tests in
`tests/test_v8_native_audio.py`, with the existing microphone fixtures updated in
`test_voice_updates.py`, `test_voice_reliability.py` and `test_background_wake.py`
for the process adapters.
Permissions, local-only background wake policy, wake rejection rules and the
existing controller backoff are preserved. No ambient microphone audio is sent
to a provider by this change.

Local evidence: **16 new tests passed** using real spawned/terminated processes
with synthetic device/recognizer functions. They cover stalled read, repeated
abort/restart, permission failure, process crash, malformed/oversized frames,
overflow, ASR timeout/cancel/late-result suppression and startup cleanup. Five
additional wake tests cover stalled model loading/inference/reset, acknowledged
resets and exact Unicode final text, malformed/oversized messages and stopping the
real listener during blocked inference without late dispatch. The native boundary
is synthetic; process creation/termination/reaping and the production byte protocol
are real. The latest focused suite passed in 2.632s. Combined-suite results are
recorded in `docs/evidence/v8-p0-continuation-20261006.json`.

The new `--jarvis-audio-worker-check` packaged smoke mode opens no microphone: it
proves that a frozen Windows executable can spawn, exchange bounded request/reply
messages and terminate/reap a trusted child without reopening the GUI.
[Run 37427755776](https://github.com/Adib0105/JARVIS-AI-OMEGA/actions/runs/37427755776)
passed all ten validation jobs on `874cfa6e96619afe2803b80adeeef5f5f2a85ff8`, including
the first one-way packaged worker check, Defender/package/installer/update lifecycle,
Linux 3.11–3.14, Windows source regressions, account services, dependency audit and
real Docker execution. Public release was skipped. This does not record a real
microphone or demonstrate physical Bluetooth/resume behavior.

Not verified here: real device open/permission/Bluetooth reconnect, login/resume,
wake accuracy, barge-in, idle soak, p50/p95 latency, physical TTS interruption and
frozen capture with a real device. No voice release gate is marked complete.
The duplex/background-wake follow-up passed all ten validation jobs in
[run 37430115582](https://github.com/Adib0105/JARVIS-AI-OMEGA/actions/runs/37430115582)
at `ced6341f8ccb07cb598376db95c38a16ef8f4985`, including the actual duplex frozen
worker check and installer/update lifecycle. Windows ran 523 ordinary tests
(521 passed, two POSIX-only skips), and 4/4 real UIA tests passed again.
The latest local desktop suite ran 523 (522 passed, one Windows DPAPI skip) in
8.592s. Public release was skipped. Physical device acceptance remains open.
Rollback is a normal Git revert; no persisted schema/data changes.
