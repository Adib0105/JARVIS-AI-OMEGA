"""Observed-identity guard and full permission/audit dispatch, simulated UIA.

Real UI Automation fixture checks live separately in tests_windows.
"""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from jarvis.agent.tool_runtime import RecordingToolRegistry
from jarvis.agent.verification import VerificationEngine
from jarvis.computer_use.action_engine import ComputerActionEngine
from jarvis.computer_use.targets import UITarget, TargetMatch
from jarvis.computer_use.windows_ui import WindowsUIBackend
from jarvis.config import settings
from jarvis.memory import MemoryStore
from jarvis.security.audit import AuditStore


class TargetBackend:
    def __init__(self):
        self.target = UITarget('Draft', 'Edit', 'JARVIS Fixture', automation_id='Draft',
                               left=10, top=10, right=200, bottom=40, process_id=41,
                               process_started=123.5, application='C:/Test/fixture.exe',
                               window_handle=77, runtime_id=(42, 7), protected=False)
        self.targets = None
        self.value = 'before'
        self.actions = []

    def enumerate_targets(self, **_):
        return [self.target] if self.targets is None else self.targets

    def observe(self, target):
        return {'exists': True, 'value': self.value}

    def refresh(self, target):
        return self.target

    def replace_text(self, target, text):
        self.actions.append(('type', text))
        self.value = text

    def invoke(self, target):
        self.actions.append(('click', None))


class SemanticDispatchTests(unittest.TestCase):
    def setUp(self):
        self.backend = TargetBackend()
        self.engine = ComputerActionEngine(self.backend)

    def inspect(self):
        result = self.engine.inspect_target('Draft', window_hint='JARVIS Fixture')
        self.assertTrue(result['ok'], result)
        self.assertTrue(result['actionable'])
        return {'observation_id': result['observation_id'], 'app': result['target']['application'],
                'window_title': result['target']['window_title'], 'target': result['target']['name']}

    def test_typed_value_is_exact_verified_and_observation_is_single_use(self):
        args = self.inspect()
        result = self.engine.act_observed('type', **args, text='literal {ENTER} नमस्ते')
        self.assertTrue(result['verification']['verified'], result)
        self.assertEqual(self.backend.value, 'literal {ENTER} नमस्ते')
        self.assertFalse(self.engine.act_observed('type', **args, text='twice')['ok'])
        self.assertEqual(len(self.backend.actions), 1)

    def test_changed_application_pid_lifetime_window_element_geometry_or_state_is_blocked(self):
        original = self.backend.target
        for changed in ({'process_id': 99}, {'process_started': 124.}, {'application': 'C:/other.exe'},
                        {'window_handle': 999}, {'runtime_id': (123,)}, {'window_title': 'Other'},
                        {'left': 11}, {'right': 300}, {'name': 'Other'}, {'automation_id': 'Other'},
                        {'protected': True}, {'protected': None}, {'visible': False}, {'enabled': False}):
            self.backend.target = original
            args = self.inspect()
            self.backend.target = replace(original, **changed)
            with self.subTest(change=changed):
                self.assertFalse(self.engine.act_observed('type', **args, text='unsafe')['ok'])
                self.assertEqual(self.backend.actions, [])

    def test_expiry_before_and_during_revalidation_denies(self):
        now = [100.]
        self.engine._clock = lambda: now[0]
        args = self.inspect()
        now[0] = 131.
        self.assertFalse(self.engine.act_observed('click', **args)['ok'])
        args = self.inspect()
        previous = self.backend.observe
        def observe(target):
            now[0] += 31
            return previous(target)
        self.backend.observe = observe
        self.assertFalse(self.engine.act_observed('click', **args)['ok'])
        self.assertFalse(self.backend.actions)

    def test_ambiguous_identity_after_approval_is_rejected(self):
        args = self.inspect()
        self.backend.targets = [self.backend.target, self.backend.target]
        self.assertFalse(self.engine.act_observed('click', **args)['ok'])
        self.assertFalse(self.backend.actions)

    def test_wrong_approval_arguments_cannot_retarget(self):
        args = self.inspect(); args['app'] = 'C:/Different.exe'
        self.assertFalse(self.engine.act_observed('click', **args)['ok'])
        self.assertFalse(self.backend.actions)

    def test_protected_or_missing_identity_never_yields_actionable_observation(self):
        original = self.backend.target
        for change in ({'protected': None}, {'protected': True}, {'process_started': 0}, {'runtime_id': ()}):
            self.backend.target = replace(original, **change)
            self.assertFalse(self.engine.inspect_target('Draft', window_hint='JARVIS Fixture')['ok'])

    def test_ocr_fallback_is_information_only_in_guarded_dispatch(self):
        visual = replace(self.backend.target, control_type='OCRText')
        with patch.object(self.engine, 'resolve', return_value=TargetMatch(visual, .99, 'ocr')):
            result = self.engine.inspect_target('Draft', window_hint='JARVIS Fixture')
        self.assertTrue(result['ok'])
        self.assertFalse(result['actionable'])
        self.assertNotIn('observation_id', result)
        self.assertFalse(self.backend.actions)

    def test_unknown_action_outcome_consumes_observation_without_replay(self):
        args = self.inspect()
        def crash(target):
            self.backend.actions.append(('click', None))
            raise TimeoutError('observation failed after invocation')
        self.backend.invoke = crash
        result = self.engine.act_observed('click', **args)
        self.assertFalse(result['ok'])
        self.assertEqual(result['verification']['status'], 'UNKNOWN')
        self.assertFalse(self.engine.act_observed('click', **args)['ok'])
        self.assertEqual(len(self.backend.actions), 1)

    def test_click_acknowledgement_is_not_workflow_verification(self):
        result = self.engine.act_observed('click', **self.inspect())
        self.assertTrue(result['ok'])
        self.assertFalse(result['verification']['verified'])

    def test_secret_text_and_noop_value_never_write(self):
        for value in ('sk-sensitive-fixture-key', 'before'):
            self.assertFalse(self.engine.act_observed('type', **self.inspect(), text=value)['ok'])
            self.assertFalse(self.backend.actions)

    def test_password_value_is_never_read_even_if_wrapper_exposes_it(self):
        wrapper = MagicMock()
        wrapper.element_info.element.CurrentIsPassword = True
        target = replace(self.backend.target, backend_ref=wrapper)
        result = WindowsUIBackend.observe(target)
        wrapper.get_value.assert_not_called()
        self.assertIsNone(result['value'])

    def test_full_registry_denial_approval_audit_and_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.db'
            registry = RecordingToolRegistry(MemoryStore(path), confirmer=lambda *_: 'deny', audit_store=AuditStore(path))
            registry.computer = self.engine
            configured = replace(settings, enable_local_tools=True, enable_desktop_automation=True,
                                 enable_semantic_computer_use=True)
            with patch('jarvis.tools.settings', configured):
                denied = json.loads(registry.call('inspect_computer_target', {'target': 'Draft', 'window_hint': 'JARVIS Fixture'}))
                self.assertFalse(denied['ok'])
                self.assertFalse(self.engine._observations)
                registry.permissions.confirmer = lambda *_: 'allow_once'
                result = json.loads(registry.call('inspect_computer_target', {'target': 'Draft', 'window_hint': 'JARVIS Fixture'}))['result']
                args = {'observation_id': result['observation_id'], 'app': result['target']['application'],
                        'window_title': result['target']['window_title'], 'target': result['target']['name'], 'text': 'after'}
                registry.clear_events()
                acted = json.loads(registry.call('semantic_type', args))
                self.assertTrue(acted['ok'], acted)
                events = registry.drain_events()
                self.assertTrue(events[0]['audit_id'])
                self.assertTrue(VerificationEngine().verify_step('updated field', events).verified)
                self.assertNotEqual(events[0]['args']['text'], 'after')
            with patch('jarvis.tools.settings', replace(configured, enable_semantic_computer_use=False)):
                self.assertNotIn('semantic_type', {x['name'] for x in registry.schemas()})
                self.assertFalse(json.loads(registry.call('semantic_type', args))['ok'])
