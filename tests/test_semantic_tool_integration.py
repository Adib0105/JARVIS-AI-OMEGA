from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from jarvis.config import settings
from jarvis.memory import MemoryStore
from jarvis.tools import ToolRegistry


class AllowAll:
    def check(self, _name: str, _args: dict):
        return SimpleNamespace(allowed=True, reason='allowed for test')


class FakeComputer:
    def status(self):
        return {'available': True, 'backend': 'fake-uia', 'display': {'monitor_count': 2, 'scale_percent': 125}}

    def list_targets(self, query: str = '', *, window_hint: str = '', limit: int = 20):
        return {'count': 1, 'targets': [{'name': query or 'Search', 'window_title': window_hint or 'Chrome'}], 'limit': limit}

    def semantic_click(self, target: str, *, window_hint: str = ''):
        return {
            'ok': False,
            'error': 'target changed before click',
            'target_name': target,
            'window_hint': window_hint,
            'verification': {'status': 'FAILED', 'verified': False},
        }

    def semantic_type(self, target: str, text: str, *, window_hint: str = '', interval: float = 0.01):
        return {
            'ok': True,
            'action': 'type',
            'target_name': target,
            'characters': len(text),
            'window_hint': window_hint,
            'interval': interval,
            'verification': {'status': 'VERIFIED', 'verified': True},
        }


class FakeBrowser:
    def trust(self, url: str):
        return {'allowed': True, 'hostname': 'example.test', 'transport': 'https', 'trust': 'PUBLIC_HTTPS', 'reasons': []}

    def open(self, url: str):
        return {'ok': False, 'error': 'DNS policy blocked navigation', 'url': url, 'verification': {'status': 'FAILED', 'verified': False}}

    def search(self, engine: str, query: str):
        return {'ok': True, 'engine': engine, 'query': query, 'verification': {'status': 'PARTIAL', 'verified': False}}

    def read(self, url: str, max_chars: int = 14000):
        return {'ok': False, 'error': 'redirect target blocked', 'url': url, 'max_chars': max_chars, 'verification': {'status': 'FAILED', 'verified': False}}

    def extract(self, url: str, keyword: str = '', max_chars: int = 18000):
        return {'ok': True, 'url': url, 'keyword': keyword, 'content': 'safe excerpt', 'max_chars': max_chars, 'verification': {'status': 'VERIFIED', 'verified': True}}


class SemanticToolIntegrationTests(unittest.TestCase):
    def _registry(self, tmp: str) -> ToolRegistry:
        memory = MemoryStore(Path(tmp) / 'memory.db')
        registry = ToolRegistry(memory, permission_checker=AllowAll())
        registry.computer = FakeComputer()
        registry.browser = FakeBrowser()
        return registry

    def test_desktop_schemas_expose_semantic_tools_and_keep_compatibility_tools(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings, 'enable_desktop_automation', True):
            registry = self._registry(tmp)
            names = {row['name'] for row in registry.schemas(include_local=True)}
        for name in ('computer_status', 'list_ui_targets', 'semantic_click', 'semantic_type'):
            self.assertIn(name, names)
        for name in ('type_text', 'click_screen', 'press_key', 'hotkey'):
            self.assertIn(name, names)

    def test_public_web_schemas_expose_safe_browser_read_tools(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings, 'enable_public_web_tools', True):
            registry = self._registry(tmp)
            names = {row['name'] for row in registry.schemas(include_local=False)}
        for name in ('browser_trust', 'browser_read_safe', 'browser_extract_safe'):
            self.assertIn(name, names)

    def test_semantic_click_failure_is_not_wrapped_as_tool_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = self._registry(tmp)
            payload = json.loads(registry.call('semantic_click', {'target': 'Submit', 'window_hint': 'Browser'}))
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['verification']['status'], 'FAILED')
        self.assertNotIn('result', payload)

    def test_semantic_type_preserves_verification_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = self._registry(tmp)
            payload = json.loads(registry.call('semantic_type', {
                'target': 'Search', 'text': 'hello', 'window_hint': 'Chrome', 'interval': 0.01,
            }))
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['verification']['status'], 'VERIFIED')
        self.assertEqual(payload['characters'], 5)

    def test_safe_browser_failure_is_not_wrapped_as_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = self._registry(tmp)
            payload = json.loads(registry.call('browser_read_safe', {'url': 'https://example.test', 'max_chars': 2000}))
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['verification']['status'], 'FAILED')
        self.assertNotIn('result', payload)

    def test_open_url_uses_safe_browser_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = self._registry(tmp)
            payload = json.loads(registry.call('open_url', {'url': 'https://example.test'}))
        self.assertFalse(payload['ok'])
        self.assertIn('DNS policy', payload['error'])

    def test_read_only_semantic_status_keeps_standard_result_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = self._registry(tmp)
            payload = json.loads(registry.call('computer_status', {}))
        self.assertTrue(payload['ok'])
        self.assertTrue(payload['result']['available'])
        self.assertEqual(payload['result']['display']['monitor_count'], 2)


if __name__ == '__main__':
    unittest.main()
