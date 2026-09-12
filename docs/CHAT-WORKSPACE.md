# Chat workspace

- **Ctrl+K / QUICK COMMANDS:** search common actions and Python, SQL, Excel, study or code-review prompt starters. Enter or double-click chooses an action. Draft starters fill the input without sending it and will not overwrite an existing draft.
- **Ctrl+H / SAVED CHATS:** search conversation titles and message text, rename chats, or resume them. Searches are local, run off the UI thread, and display up to 100 conversations sorted by last activity. Percent and underscore characters are literal text, not search wildcards.
- Resuming uses the selected session's stored history and continuity summary. The desktop shows the latest 100 messages; model context still follows the existing configured history limit. It does not resend/replay old messages or resume an old mission.
- Switching chats stops speech and listening and clears image attachments. Switching is blocked while a task is running. Input drafts remain in the entry box.
- Terminal: `/sessions`, `/resume <session-id>`, `/rename <new title>`.

Existing confirmations for missions, screen capture, document access and tools remain active. The command palette invokes the same desktop controls; it does not grant additional tool permissions. Templates are editable text, not trained models or automatic tool runs.

Validation covers database search/rename/resume, literal search, prompt insertion, busy-state guards, preserved drafts, and stopping audio when switching conversations. Real desktop layout and device behavior still need an on-PC check.

The full local regression suite passes: 251 tests on Python 3.12, including 13 new workspace tests. Compilation and whitespace checks pass.
