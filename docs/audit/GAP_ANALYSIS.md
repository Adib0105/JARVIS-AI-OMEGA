# Gap Analysis — V7.9 to V8 Frontier

## Priority P1 sequence
1. **Truthful autonomy gate:** finish semantic UIA/browser integration with fresh observations, secret-field exclusion and postconditions.
2. **Background runtime:** design authenticated IPC and a per-user persistent service/agent host; move durable mission scheduling there.
3. **Durable task/event model:** add BackgroundTaskQueue + EventEngine + resource locks + checkpoint/reconciliation.
4. **Native audio isolation:** subprocess capture supervision and physical Windows acceptance.
5. **Cancellation/replay safety:** adapters for cancellable work, reconciliation for ambiguous side effects.
6. **Real acceptance lab:** microphone/speaker/provider/clean install/updater/browser/UIA/multi-monitor/DPI/8h soak evidence.

## P2 sequence
7. FileSystemAgent and ApplicationAgent on top of existing safe file/Windows primitives.
8. Stateful browser session supporting click/type/select/upload/download/tabs/frames/forms.
9. WorkspaceManager profiles and user-visible mission notifications.
10. 100+ benchmark corpus, chaos suite, performance SLOs.
11. UI convergence into one command center.
12. Legacy module deprecation and architecture cleanup.

## Explicit non-goals
- No unrestricted self-modification.
- No marking imports/classes as COMPLETE.
- No claiming physical device success from hosted CI.
- No public release while explicit release gates remain open.
