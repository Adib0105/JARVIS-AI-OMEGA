# V8 P0.2 continuation — observed semantic dispatch

2026-10-06. **Opt-in experimental; release HOLD.**

The existing `ComputerActionEngine` now provides an inspection/action path through
the normal tool registry, capability permission, effect ledger, audit and mission
verification. Enable only for development with `ENABLE_SEMANTIC_COMPUTER_USE=true`
and the pinned Windows UIA dependency. It is disabled by default pending physical
acceptance. This is a personal desktop capability, not a SaaS entitlement or a
replacement for the future server plan enforcement.

## Pipeline and safety behavior

`inspect_computer_target` requires an explicit target and window hint. UIA matching
retains the confidence threshold and ambiguity rejection. A resolved element must
have a process ID **and process creation time**, executable path, top-level window
handle/title, UIA runtime identity, visible/enabled state and known non-sensitive
field status. The engine returns an opaque, single-use observation ID that expires
after 30 seconds, plus the exact application/window/target to show for approval.
At most 32 observations are retained in that runtime instance.

`semantic_click` / `semantic_type` require those identity fields to match the
observation. After approval, the engine enumerates again, rejects missing/duplicate/
moved/renamed/replaced/protected targets, rechecks expiry and performs one action.
UIA references are refreshed inside the action thread's COM session rather than
carried between calls. Failures consume the observation; no automatic retargeting
or side-effect retry occurs.

Click uses UIA InvokePattern, not screen coordinates. Literal Unicode replacement
uses ValuePattern on an editable non-sensitive Edit control with before/after
readback. Credential-like input and password/sensitive/unknown protection state
are blocked. Password values are never read by observation. Unsupported UIA
patterns fail closed. The Windows adapter is pinned as `pywinauto==0.6.9` and
included in Windows dependency auditing/packaging.

Exact changed value plus stable post-action identity can verify only the scope
`field_value_replacement`. An invocation acknowledgement remains **UNKNOWN** for
the higher-level workflow. OCR fallback can report a possible location, but cannot
issue an actionable observation ID or perform an action in the guarded dispatcher.
The older experimental direct engine APIs remain separate from normal dispatch.

## Files and test evidence

Changed `jarvis/computer_use/{targets,windows_ui,action_engine}.py`, `tools.py`,
`config.py`, capability records, legacy/V7 permission registration and `.env.example`.
Added `requirements-computer-use.txt`; extended Windows pins/build collection and
CI. `tests/test_v8_semantic_dispatch.py` adds **12 regressions** for identity/PID
reuse, expiry including slow revalidation, geometry/state changes, ambiguity,
password privacy, exact Unicode values, single use, uncertain outcomes, OCR
information-only behavior and real SQLite permission/audit/verification integration.

Those 12 local tests pass. UIA itself is simulated in them. A new
`tests_windows/test_semantic_uia.py` suite opens a disposable WinForms application
and exercises actual UIA replacement, invocation, password protection, stale
application handling and normal registry/audit/verification. No user application,
private account or network service is targeted. All **4 real Windows UIA tests
passed in 4.652s** in [run 37428735356](https://github.com/Adib0105/JARVIS-AI-OMEGA/actions/runs/37428735356)
at `ced58e414b61ae47db908a1556433b4d4e9b4065`. Its ordinary Windows suite ran
518 tests: 516 passed and two POSIX-only cases skipped. The Linux local suite
ran 518: 517 passed and one Windows DPAPI case skipped. All ten CI validation
jobs passed, including the updated packaged UIA dependency, frozen audio worker,
installer/update lifecycle, real Docker, dependency audit and account services.
Public release was skipped. These disposable-application CI results do not replace
physical Windows acceptance in real user applications.

## Remaining limits and next gate

Physical Windows, Chrome/Explorer and varied accessibility providers still require
acceptance. UIA providers/process identity are trusted OS/application observations;
custom applications can expose incomplete or misleading accessibility semantics.
Secret-like labels plus IsPassword are conservative protection, not a universal
sensitive-data classifier. UIA COM calls execute off Tk but are not yet in a
killable process; a wedged provider can retain the single operation slot. Fresh
inspection and explicit user review are required after uncertainty.

Full Computer Use / voice release gates therefore remain open. The next product
phases remain the existing SaaS architecture/account/plan/gateway/quota work after
P0 acceptance, followed by the requested UI/admin/security/release sequence.
No database migration or mainline/release publication is involved. Rollback is a
normal Git revert; disabling the experimental flag also removes the three schemas
and rejects direct dispatch without weakening other capabilities.

Primary adapter references: [UIA element identity](https://pywinauto.readthedocs.io/en/latest/code/pywinauto.uia_element_info.html),
[Invoke/Value controls](https://pywinauto.readthedocs.io/en/latest/code/pywinauto.controls.uia_controls.html),
[Microsoft accessibility properties](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-automation-element-propids).
