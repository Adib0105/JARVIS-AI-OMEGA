# Bug-fix polish — 12 September 2026

This pass changes existing behavior only. It adds no product features, providers, permissions or automatic account actions.

| Area | Confirmed defect | Fix |
| --- | --- | --- |
| Background preferences | Valid JSON with wrong field types could crash model/location controls or treat a string `false` as enabled. | Validate stored types and coordinates; enable only for boolean `true`. |
| Background pause | Disk/permission errors while saving could prevent window restoration and stop event polling. | Stop the microphone and restore the window independently of saving; display a persistence error. |
| Tray/exit | A tray cleanup exception could prevent full application shutdown. | Isolate tray cleanup and run browser/desktop cleanup through `finally` blocks. |
| Background event loop | A failed UI callback could stop all later tray/wake events. | Reschedule polling in `finally` and release pending state after errors. |
| Queued wake | A wake queued just before a typed task could interfere with that task. | Recheck busy state on the UI thread before dispatching. |
| Briefing worker | An unexpected briefing exception could leave background listening permanently pending. | Always enqueue a completion or unavailable message. |
| Weather | Null/malformed city or daily-data fields could crash the picker or discard valid temperature data. | Filter invalid locations and handle missing forecast fields independently. |
| App commands | Denied app commands fell back to the model, allowing repeated attempts; malformed tool output could produce a false success message. | Return a terminal failure for recognized commands unless the tool explicitly reports success. |
| Browser launch | A rejected browser-open request still returned a successful tool response. | Raise a handled error when the browser rejects the request. |
| YouTube lifecycle | Requests submitted around worker retirement could remain queued; shutdown did not notify waiting callers. | Retire the worker under the submission lock, cancel active work and notify pending callers. |
| YouTube verification | A nonzero but stalled playback position could pass; navigation away from the selected video was not checked. | Require position to advance and verify the final selected video ID/host; recheck cancellation before success. |
| Permission dialogs | Waiting for a dialog could hang during shutdown or when invoked from the UI thread. | Handle UI-thread requests directly, deny on closed UI, and release background waiters on shutdown. |
| Settings file | Newlines/comments/quotes in values could corrupt settings; a partial write could damage the existing file. | Reject multiline/null input, quote literal values, handle `export` assignments, and replace the file atomically. |
| Voice recovery | A failed speech attempt could leave audio in `error`, suppressing future background listening. | Emit the error, retain its diagnostic, and return to idle when playback ends. |

## Validation

- 302 local unit/regression tests pass on Python 3.12; 24 new regression cases cover the defects above.
- Python compilation and Git whitespace checks pass.
- Existing background preference round-trip fixture now includes required location coordinates.
- GitHub CI runs Python 3.11–3.14 Linux regression tests, Python 3.14 Windows tests, and a Windows package smoke check including the bundled browser driver, Vosk and tray imports.
- Hardware microphone accuracy, real tray behavior, speaker output and live YouTube consent/playback remain on-PC checks. Automated tests do not establish that every possible bug is absent.

Implementation references: [Playwright waiting API](https://playwright.dev/python/docs/api/class-page#page-wait-for-function) and [python-dotenv file format](https://bbc2.github.io/python-dotenv/#file-format).
