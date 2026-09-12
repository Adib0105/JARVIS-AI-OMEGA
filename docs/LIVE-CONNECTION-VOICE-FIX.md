# Live connection and speech continuity repair

## Reported failure

In 7.5.733, a local greeting could succeed while an AI request still reported missing credentials. Saving the connection wrote `.env` but did not rebuild the running provider. X now hides the app in the tray, so closing/reopening the window is not a process restart. This combination can leave the old missing-key provider active after a key has been saved. A screenshot alone cannot prove where the user's key was saved or whether the key is valid online.

## Repairs

- **AI CONNECTION → SAVE & APPLY NOW** atomically saves provider/key/model and replaces the active provider/client immediately. It keeps the existing conversation, memory, tools, permissions and observability. Old clients are closed. Provider changes clear incompatible routing overrides; the UI explains this.
- Leaving the entry blank reuses the selected provider's saved key. The dialog shows whether the current copy's `.env` has a key and whether the running settings have one; keys are never displayed. BOM files, comments and unrelated settings are preserved. A failed write keeps the old connection and file.
- **TEST ACTIVE CONNECTION** requests one short AI response, asynchronously. Saving is not reported as successful online authentication. Test failures report categories without echoing credentials. The configured provider may charge for this explicit test.
- The header refreshes after applying provider/model changes. Missing-key guidance no longer asks for a restart.
- Both side panels are scrollable so controls are not clipped on short screens. Connection, Update and Settings come first in the module list; Ctrl+Shift+U opens updates and Ctrl+comma opens Settings.
- The screenshot's YouTube search phrasing now uses the existing permission-gated browser search tool without an AI call. It opens the default browser, not a falsely claimed Chrome instance, and does not autoplay a video.
- Speech renders the next segment while the current one plays, uses bounded subsequent segments, and selects the voice once for the whole answer. Temporary audio is isolated in a dedicated temporary directory. Network delays can still exceed the buffer; no guarantee of gapless audio is made.
- The default no longer silently replaces `openrouter/free` with a fixed large reasoning model. An explicit `OPENROUTER_STABLE_TEXT_MODEL` override is still respected. The [OpenRouter free router](https://openrouter.ai/openrouter/free) chooses among available free models, so model availability, limits and latency remain outside JARVIS's control.

## Verification scope

Regression coverage includes a real OpenAI-compatible SDK HTTP request to a local fixture immediately after save (without restart), correct authorization header, atomic-save failure recovery, BOM preservation, provider changes, search denial, concurrent speech rendering/order and text preservation. Windows packaged and installed GUI smoke tests invoke the actual Save & Apply button using an obviously synthetic CI-only key and verify provider creation, key-entry clearing and unchanged session.

No user credentials are used in tests. Paid live AI, microphone hardware and actual speaker quality still require testing on the user's PC. This is a targeted repair and broader regression check, not a claim that no undiscovered bugs remain.
