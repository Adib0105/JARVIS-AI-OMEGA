# JARVIS AI OMEGA — Computer Use 3.0

## Objective

The current computer-use path moves desktop control away from “guess an x/y coordinate” toward:

```text
Semantic request
  -> visible UI discovery (UIA first)
  -> target ranking
  -> confidence / ambiguity check
  -> capability approval
  -> target/window readiness + focus recovery
  -> action
  -> bounded post-action observation
  -> VERIFIED / PARTIAL / FAILED evidence
```

The historical PyAutoGUI coordinate/focused-input tools remain available as explicit compatibility tools. They are not the preferred semantic path.

## Windows semantic UI backend

Windows releases install and package the pinned `pywinauto` UIA runtime. The semantic backend reads safe accessibility metadata such as:

- visible label/name
- control type
- window title
- automation ID
- bounding rectangle
- enabled/visible state
- focus/selection/value observations when exposed
- per-window DPI when Windows exposes it

If UIA is unavailable, JARVIS reports that state. It does **not** fabricate a semantic target.

## Display and DPI context

`computer_status` reports the current Windows virtual-desktop geometry, monitor count, primary dimensions, system DPI and derived scale percentage when available.

OCR fallback uses virtual-desktop coordinates, including negative coordinates for monitors positioned left/above the primary display. This avoids assuming that screen origin is always `(0, 0)` on a multi-monitor workstation.

Physical multi-monitor and 100/125/150% DPI behavior still requires real Windows E2E evidence for the exact packaged candidate.

## Confidence and ambiguity

Target ranking combines exact/substring/fuzzy text, token overlap, automation ID similarity and an optional window-title hint. Default semantic confidence threshold is **0.82**.

A target is rejected rather than guessed when:

- confidence is below threshold
- top candidates are too close/ambiguous
- no visible target matches
- a previously resolved UIA target becomes stale and cannot be safely re-resolved
- the target window cannot be restored/focused safely

OCR fallback uses a stricter default threshold (**0.88**). An ambiguous UIA result is not silently bypassed by OCR.

## Runtime tools

When desktop automation is enabled, the main ToolRegistry exposes:

- `computer_status`
- `list_ui_targets`
- `semantic_click`
- `semantic_type`

The older `type_text`, `press_key`, `hotkey`, and `click_screen` tools remain compatibility paths.

`semantic_click` and `semantic_type` are explicitly classified as **HIGH** risk and capability-gated. They require screen-read plus the relevant screen/mouse/keyboard capabilities.

## Focus recovery

Before a UIA semantic action, JARVIS re-checks that the resolved target exists, is visible and enabled. It then attempts to restore a minimized top-level window and focus that window.

If the wrapper became stale, the engine performs one bounded UIA refresh/re-resolution. It does not silently switch to an OCR click during stale-target recovery.

## Post-action verification

### Click

After a semantic click the engine performs bounded re-observation. Focus, selection or a readable value change can provide `VERIFIED` evidence. A disappearing target or an observed click without proof of the higher-level outcome remains `PARTIAL` rather than being promoted to success evidence.

### Type

After focus recovery, typing uses the existing local input layer. When UIA exposes a readable value, JARVIS polls briefly for the typed text and returns `VERIFIED` or `FAILED`. If value readback is unavailable, the action remains `PARTIAL`.

OCR-based click/type can establish target-location confidence, but without an independent semantic outcome observation it remains `PARTIAL`.

## Security

Relevant capabilities include:

- `SCREEN_READ`
- `SCREEN_CONTROL`
- `MOUSE_CONTROL`
- `KEYBOARD_CONTROL`
- `APP_CONTROL`

Semantic actions pass through the same canonical capability permission gate and audited tool runtime as the rest of JARVIS. A semantic engine result with `ok: false` is preserved as a tool failure; it is not wrapped in a fake outer success result.

## Preferred fallback order

1. semantic UI Automation target
2. local OCR fallback when UIA cannot resolve a target and OCR confidence is sufficiently high
3. ask/stop when target identity is low-confidence or ambiguous
4. explicit coordinate action only when a deliberate workflow supplies coordinates

JARVIS does not invent coordinates.

## Still requires real-machine evidence

Repository tests and Windows CI can validate dependency packaging, policy behavior, scoring, stale-target recovery logic and evidence contracts. They cannot prove real physical interaction.

Before final release, validate the exact packaged build on a real Windows workstation for Chrome/Notepad (or equivalent targets), focus loss, minimized/moved windows, wrong/missing targets, keyboard/mouse effects, OCR, multiple displays and common DPI scales. Use `docs/WINDOWS-E2E-CHECKLIST.md` and record the exact build SHA.

## Known limitations

- UI Automation quality depends on applications exposing useful accessibility metadata.
- Games, custom-rendered canvases and some web surfaces may expose incomplete UIA trees.
- OCR fallback remains optional and reports unavailable if its local OCR runtime is not installed.
- This layer does not claim DOM-level browser control, browser-profile introspection or login-session extraction.
