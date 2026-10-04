# Isolated audit reproductions

Date: **2026-10-04**. Runtime baseline: [`main@83b7f34`](https://github.com/Adib0105/JARVIS-AI-OMEGA/commit/83b7f34b67c0aca444c1139cd7db700364bc554c). Documentation branch: `v8/frontier-audit-2026-09-28` / PR #24.

This is the audit-first deliverable requested by section 59 of the supplied brief. No runtime code, security policy, production data, dependency pins or release settings are changed. The 2026-09-28 audit is retained in Git history; this refresh adds direct source checks and six executable reproductions.

All six experiments ran on Linux Python 3.12.14 against the pinned runtime source using disposable SQLite data. They used no live provider, mailbox, browser, payment or desktop. Only the semantic-typing case used a fake UI backend/no-op keyboard adapter. The replay case used the real RecordingToolRegistry, MemoryStore, MissionStore and MissionOrchestrator, with an injected verifier timeout.

| Finding | Stimulus | Observed incorrect behavior |
|---|---|---|
| V8-001 | Complete todo 999999 in an empty temporary database | Handler completed=false; final verifier VERIFIED |
| V8-002 | Explicit verification with verified="false" and no evidence | verified=true |
| V8-003 | Request one real local todo; verifier times out after dispatch | Two handler calls, two rows, one retry, mission COMPLETED |
| V8-004 | Benchmark function returns {success: false} | success=true |
| V8-005 | Add one equally successful/fast scenario to after cohort | scenario_count alone yields successful_improvement=true |
| V8-006 | No-op typing; readback already contains requested substring | semantic_type reports VERIFIED |

The semantic and malformed-contract findings are not demonstrations of a live attacker-controlled path. General semantic tools are not exposed in the ordinary registry. The todo/replay findings exercise current runtime paths. No fix is included in this audit-only commit.

## Reproduction procedure

Create a disposable virtual environment, install `requirements.txt` with `constraints/linux.txt`, place the following script outside the checkout and execute it with the repository on PYTHONPATH. It creates/removes its own temporary database. Set microphone and Google integration off. Do not run against a real profile database. The tool configuration must permit local memory writes; the script supplies an explicit fixture confirmer.

```python
import json, sys, tempfile, types
from pathlib import Path
from unittest.mock import patch
from jarvis.memory import MemoryStore
from jarvis.security.audit import AuditStore
from jarvis.agent.tool_runtime import RecordingToolRegistry
from jarvis.agent.verification import VerificationEngine
from jarvis.agent.mission_store import MissionStore
from jarvis.agent.orchestrator import MissionOrchestrator
from jarvis.evaluation.benchmark import AgentEvaluationBenchmark, ScenarioResult
from jarvis.computer_use.action_engine import ComputerActionEngine
from jarvis.computer_use.targets import UITarget
from jarvis.computer_use.windows_ui import BackendStatus

results = {}
with tempfile.TemporaryDirectory(prefix='jarvis-audit-') as tmp:
    db = Path(tmp) / 'audit.db'
    memory = MemoryStore(db)
    registry = RecordingToolRegistry(memory, lambda *_: True, audit_store=AuditStore(db))
    output = json.loads(registry.call('complete_todo', {'todo_id': 999999}))
    event = registry.drain_events()[0]
    check = VerificationEngine().verify_tool_event(event)
    results['V8-001'] = {'case': 'complete nonexistent todo', 'tool_result': output, 'verified': check['verified'], 'status': check['status']}

    results['V8-002'] = {'case': 'truthy false verification flag', 'result': VerificationEngine().verify_tool_event({'name': 'semantic_type', 'output': {'ok': True, 'verification': {'status': 'VERIFIED', 'verified': 'false'}}})}

    class Core:
        session_id = 'audit-fixture'
        last_provider_used = 'fixture-no-network'
        last_plan = ['Create one todo']
        calls = 0
        tools = registry
        def plan_mission(self, _goal): return self.last_plan
        def chat(self, _prompt):
            self.calls += 1
            self.tools.call('add_todo', {'title': 'Exactly one audit todo'})
            return 'Tool returned.'
        def _one_shot_text(self, *_args): return '[]'
        @staticmethod
        def _extract_plan(*_args): return []
    core = Core()
    orchestrator = MissionOrchestrator(core, MissionStore(db))
    original_verify = orchestrator.verifier.verify_step
    checks = [0]
    def verify_once_timeout(*args):
        checks[0] += 1
        if checks[0] == 1: raise TimeoutError('Injected verification timeout after tool dispatch')
        return original_verify(*args)
    orchestrator.verifier.verify_step = verify_once_timeout
    orchestrator.retry.wait = lambda *_a, **_k: True
    mission = orchestrator.run('Create exactly one todo')
    results['V8-003'] = {'case': 'verification failure after effect', 'handler_calls': core.calls, 'todo_count': len(memory.list_todos()), 'retries': mission.retry_count, 'mission_status': mission.status.value}

    b = AgentEvaluationBenchmark.run_case('false-dict', 'verification', lambda: {'success': False})
    results['V8-004'] = {'case': 'failed benchmark dict', 'success_reported': b.success}
    bench = AgentEvaluationBenchmark(db)
    before = bench.record('before', [ScenarioResult('one', 'task', True, 10)])
    after = bench.record('after', [ScenarioResult('one', 'task', True, 10), ScenarioResult('two', 'task', True, 10)])
    results['V8-005'] = {'case': 'extra benchmark scenario only', 'comparison': bench.compare(before.as_dict(), after.as_dict())}

    target = UITarget('Name', 'Edit', 'Audit fixture', automation_id='Name')
    class Backend:
        def status(self): return BackendStatus(True, 'fixture', 'ready')
        def enumerate_targets(self, **kw): return [target]
        def focus(self, target): return self.observe(target)
        def observe(self, target): return {'observed': True, 'exists': True, 'focused': True, 'value': 'hello already here'}
    with patch.dict(sys.modules, {'pyautogui': types.SimpleNamespace(write=lambda *a, **kw: None)}):
        result = ComputerActionEngine(Backend()).semantic_type('Name', 'hello', window_hint='Audit fixture')
    results['V8-006'] = {'case': 'no-op typing with preexisting substring', 'verification': result['verification']}

print(json.dumps(results, indent=2))
```

Machine-readable observations: [reproduction-results.json](reproduction-results.json). These record failing behavior at the audited runtime commit, not post-fix results.
