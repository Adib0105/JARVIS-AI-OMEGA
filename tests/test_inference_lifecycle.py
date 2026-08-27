from __future__ import annotations

import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from jarvis.errors import ErrorCategory, classify_exception
from jarvis.gui import JarvisDesktop
from jarvis.providers.deadline import call_with_deadline, transport_timeout_seconds
from jarvis.providers.openrouter_provider import OpenRouterProvider


class _StatusError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


class _Completions:
    def __init__(self, behavior):
        self.behavior = behavior
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = dict(kwargs)
        return self.behavior(**kwargs)


class _Root:
    def after(self, _delay, callback):
        callback()


class InferenceLifecycleTests(unittest.TestCase):
    def _provider(self, behavior):
        provider = OpenRouterProvider(
            api_key='test-key-not-used',
            base_url='https://openrouter.ai/api/v1',
            app_url='https://example.invalid/jarvis',
            app_title='JARVIS AI OMEGA TEST',
            max_retries=0,
        )
        completions = _Completions(behavior)
        provider.client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        return provider, completions

    def test_hard_request_deadline_returns_control(self):
        blocker = threading.Event()
        started = time.perf_counter()
        with self.assertRaisesRegex(TimeoutError, 'request deadline'):
            call_with_deadline(lambda: blocker.wait(1.0), 0.05, operation='test request')
        self.assertLess(time.perf_counter() - started, 0.5)

    def test_transport_timeout_is_finite_and_shorter_than_long_request_budget(self):
        self.assertEqual(transport_timeout_seconds(60), 30.0)
        self.assertEqual(transport_timeout_seconds(10), 10.0)
        self.assertEqual(transport_timeout_seconds(0), 1.0)

    def test_openrouter_success_uses_expected_endpoint_payload_model_and_non_streaming(self):
        message = SimpleNamespace(content='JARVIS ONLINE AND OPERATIONAL', tool_calls=[])
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=message)],
            model='openrouter/free',
            usage=None,
        )
        provider, completions = self._provider(lambda **_kwargs: response)
        turn = provider.chat(
            system='system',
            messages=[{'role': 'user', 'content': 'Hello'}],
            model='openrouter/free',
            timeout=2,
        )
        self.assertEqual(turn.text, 'JARVIS ONLINE AND OPERATIONAL')
        self.assertEqual(turn.model, 'openrouter/free')
        self.assertEqual(completions.last_kwargs['model'], 'openrouter/free')
        self.assertIs(completions.last_kwargs['stream'], False)
        self.assertGreater(completions.last_kwargs['timeout'], 0)
        self.assertEqual(completions.last_kwargs['messages'][0]['role'], 'system')

    def test_openrouter_request_timeout_is_finite(self):
        blocker = threading.Event()
        provider, _completions = self._provider(lambda **_kwargs: blocker.wait(2.0))
        started = time.perf_counter()
        with self.assertRaises(TimeoutError):
            provider.chat(
                system='system',
                messages=[{'role': 'user', 'content': 'Hello'}],
                model='openrouter/free',
                timeout=0.05,
            )
        self.assertLess(time.perf_counter() - started, 0.5)

    def test_openrouter_authentication_failure_propagates_status(self):
        provider, _ = self._provider(lambda **_kwargs: (_ for _ in ()).throw(_StatusError(401, 'Unauthorized')))
        with self.assertRaises(_StatusError) as caught:
            provider.chat(system='system', messages=[], model='openrouter/free', timeout=1)
        self.assertEqual(caught.exception.status_code, 401)
        failure = classify_exception(caught.exception, provider='openrouter', operation='chat')
        self.assertEqual(failure.category, ErrorCategory.AUTH_ERROR)

    def test_openrouter_http_failures_are_classified_explicitly(self):
        expected = {
            403: ErrorCategory.PERMISSION_ERROR,
            429: ErrorCategory.RATE_LIMIT,
            500: ErrorCategory.NETWORK_ERROR,
            502: ErrorCategory.NETWORK_ERROR,
            503: ErrorCategory.NETWORK_ERROR,
        }
        for status, category in expected.items():
            with self.subTest(status=status):
                failure = classify_exception(_StatusError(status, f'HTTP {status}'))
                self.assertEqual(failure.category, category)

    def test_openrouter_malformed_response_is_rejected(self):
        provider, _ = self._provider(lambda **_kwargs: SimpleNamespace(choices=[], model='openrouter/free'))
        with self.assertRaisesRegex(ValueError, 'malformed response'):
            provider.chat(system='system', messages=[], model='openrouter/free', timeout=1)

    def test_openrouter_constructor_uses_official_attribution_headers_without_exposing_key(self):
        with patch('jarvis.providers.openrouter_provider.OpenAI') as constructor:
            OpenRouterProvider(
                api_key='secret-test-value',
                base_url='https://openrouter.ai/api/v1',
                app_url='https://example.invalid/jarvis',
                app_title='JARVIS AI OMEGA',
                max_retries=2,
            )
        kwargs = constructor.call_args.kwargs
        self.assertEqual(kwargs['base_url'], 'https://openrouter.ai/api/v1')
        self.assertEqual(kwargs['default_headers']['HTTP-Referer'], 'https://example.invalid/jarvis')
        self.assertEqual(kwargs['default_headers']['X-Title'], 'JARVIS AI OMEGA')
        self.assertNotIn('secret-test-value', repr(kwargs['default_headers']))

    def test_ui_error_completion_always_clears_thinking_busy_state(self):
        desktop = JarvisDesktop.__new__(JarvisDesktop)
        desktop.busy = True
        desktop.hud = None
        desktop.root = _Root()
        appended = []
        desktop._append = lambda speaker, text: appended.append((speaker, text))
        desktop._answer_done('', 'AI provider response timeout hua.', False)
        self.assertFalse(desktop.busy)
        self.assertTrue(any('ERROR:' in text for _speaker, text in appended))

    def test_worker_timeout_path_reaches_ui_cleanup(self):
        desktop = JarvisDesktop.__new__(JarvisDesktop)
        desktop.busy = True
        desktop.hud = None
        desktop.root = _Root()
        desktop.jarvis = SimpleNamespace(chat=lambda _text: (_ for _ in ()).throw(TimeoutError('request deadline exceeded')))
        appended = []
        desktop._append = lambda speaker, text: appended.append((speaker, text))
        desktop._answer_worker('Hello', [])
        self.assertFalse(desktop.busy)
        self.assertTrue(any('request deadline exceeded' in text for _speaker, text in appended))


if __name__ == '__main__':
    unittest.main()
