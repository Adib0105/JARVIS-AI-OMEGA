# JARVIS OMEGA V7 — Computer Use

## Objective

V7 moves desktop control away from “guess an x/y coordinate” toward:

```text
Semantic request
  -> visible UI discovery
  -> target ranking
  -> confidence check
  -> capability approval
  -> action
  -> post-action observation
  -> verification status
```

The old PyAutoGUI coordinate tools remain available as an explicit/manual fallback. They are not the preferred semantic path.

## Semantic UI backend

On Windows, V7 can optionally use the UI Automation accessibility tree through `pywinauto` with the UIA backend.

The backend extracts safe target metadata such as:

- visible label/name
- control type
- window title
- automation ID
- bounding rectangle
- enabled/visible state

No OCR is required for normal accessibility-labeled controls.

If the optional backend is unavailable, V7 reports that semantic targeting is unavailable. It does **not** fabricate a target.

## Confidence

Target ranking combines:

- exact name match
- substring match
- fuzzy text similarity
- token overlap
- automation ID similarity
- optional window-title hint

Default semantic confidence threshold: **0.82**.

A target is rejected when:

- best confidence is below threshold
- top candidates are too close/ambiguous
- no visible target matches

The returned error explicitly says JARVIS cannot confidently identify the target and will not guess.

## Semantic actions

V7 adds model-callable tools:

- `computer_ui_status`
- `list_ui_targets`
- `semantic_click`
- `semantic_type`

`semantic_click` and `semantic_type` are high-risk capability-gated actions.

### Click verification

After a semantic click, V7 re-observes the accessibility target. Focus/selection changes can provide verified evidence. If the UIA state does not prove the higher-level outcome, the action remains `PARTIAL` rather than falsely `VERIFIED`.

### Type verification

After focusing a semantic target, text is typed through the existing PyAutoGUI layer. When UI Automation exposes a readable value, V7 compares the resulting value. If value readback is unavailable, the result remains `PARTIAL`.

## Browser abstraction

V7 adds:

- `browser_agent_open`
- `browser_agent_search`
- `browser_agent_read`
- `browser_agent_extract`

Opening/searching uses the user's default browser and returns process-level evidence. Browser process detection does not prove a page loaded, so browser open/search remains `PARTIAL` unless stronger evidence is available.

Reading/extraction uses a separate HTTP page reader and explicitly tags returned webpage data:

```json
{"untrusted_content": true}
```

Webpage text is data, not system instructions. JARVIS must not follow malicious instructions embedded in fetched pages.

## Security

Relevant capabilities:

- `SCREEN_READ`
- `SCREEN_CONTROL`
- `MOUSE_CONTROL`
- `KEYBOARD_CONTROL`
- `BROWSER_READ`
- `BROWSER_CONTROL`

Semantic click/type always passes through the V7 capability policy and Approval Center before execution.

The mission audit trail persists sanitized argument summaries and verification evidence, not raw typed/file/email content.

## Fallback philosophy

Preferred order:

1. semantic UI Automation target
2. ask user when target confidence is low
3. exact coordinate action only when the user/tool context deliberately supplies coordinates

V7 does not silently invent coordinates.

## Known limitations

- UI Automation quality depends on the target Windows application exposing accessible control metadata.
- Games, custom-rendered canvases and some Chromium/web content may expose incomplete accessibility trees.
- Browser DOM automation is not silently installed or enabled. Visible browser controls may be driven through the same UIA semantic layer when confidently discoverable; public page reading uses HTTP extraction.
- Screen-vision-assisted target detection is not automatically invoked by semantic click; image/screen upload remains an explicit user-permission path.
