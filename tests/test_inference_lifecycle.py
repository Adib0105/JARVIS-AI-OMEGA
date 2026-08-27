from __future__ import annotations

import queue
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from jarvis.errors import ErrorCategory, classify_exception
from jarvis.gui import JarvisDesktop
from jarvis.providers.deadline import (
    RequestCancelledError,
    call_with_deadline,
    request_deadline_seconds,
    request_lifecycle,
    transport_timeout_seconds,
)
from jarvis.providers.openrouter_provider import OpenRouterProvider
from jarvis.providers.openai_provider import OpenAIProvider
from jarvis.tools import ToolRegistry


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

    def test_request_deadline_contract_enforces_one_second_minimum(self):
        self.assertEqual(request_deadline_seconds(0), 1.0)
        self.assertEqual(request_deadline_seconds(0.05), 1.0)
        self.assertEqual(request_deadline_seconds(1.0), 1.0)
        self.assertEqual(request_deadline_seconds(2.5), 2.5)
        self.assertEqual(request_deadline_seconds('invalid'), 60.0)

    def test_hard_request_deadline_returns_control_at_production_floor(self):
        blocker = threading.Event()
        with patch('jarvis.providers.deadline.queue.Queue.get', side_effect=queue.Empty) as queue_get:
            with self.assertRaisesRegex(TimeoutError, 'exceeded the 1s request deadline'):
                call_with_deadline(lambda: blocker.wait(30.0), 0.05, operation='test request')
        self.assertEqual(queue_get.call_args.kwargs['timeout'], 1.0)

    def test_transport_timeout_is_finite_and_shorter_than_long_request_budget(self):
        self.assertEqual(transport_timeout_seconds(60), 30.0)
        self.assertEqual(transport_timeout_seconds(10), 10.0)
        self.assertEqual(transport_timeout_seconds(0.05), 1.0)
        self.assertEqual(transport_timeout_seconds(0), 1.0)

    def test_one_request_budget_is_shared_across_multiple_slow_operations(self):
        started = time.monotonic()
        blocker = threading.Event()
        with request_lifecycle(1.0, operation='test lifecycle'):
            self.assertEqual(call_with_deadline(lambda: (time.sleep(0.35), 'ok')[1], 60), 'ok')
            with self.assertRaisesRegex(TimeoutError, 'request deadline'):
                call_with_deadline(lambda: blocker.wait(30), 60, operation='second provider turn')
        elapsed = time.monotonic() - started
        self.assertGreaterEqual(elapsed, 0.85)
        self.assertLess(elapsed, 1.4)

    def test_cancellation_returns_control_during_blocking_provider_call(self):
        cancel = threading.Event()
        blocker = threading.Event()
        threading.Timer(0.1, cancel.set).start()
        started = time.monotonic()
        with request_lifecycle(10, operation='test request', cancel_event=cancel):
            with self.assertRaisesRegex(RequestCancelledError, 'cancelled'):
                call_with_deadline(lambda: blocker.wait(30), 10)
        self.assertLess(time.monotonic() - started, 0.6)

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

    def test_openrouter_request_timeout_is_finite_and_enforced(self):
        blocker = threading.Event()
        provider, completions = self._provider(lambda **_kwargs: blocker.wait(30.0))
        with patch('jarvis.providers.deadline.queue.Queue.get', side_effect=queue.Empty) as queue_get:
            with self.assertRaisesRegex(TimeoutError, 'OpenRouter chat completion exceeded the 1s request deadline'):
                provider.chat(
                    system='system',
                    messages=[{'role': 'user', 'content': 'Hello'}],
                    model='openrouter/free',
                    timeout=0.05,
                )
        self.assertEqual(queue_get.call_args.kwargs['timeout'], 1.0)
        self.assertEqual(completions.last_kwargs['timeout'], 1.0)
        self.assertIs(completions.last_kwargs['stream'], False)

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
        self.assertEqual(kwargs['max_retries'], 2)

    def test_openai_success_is_non_persistent_and_uses_finite_timeout(self):
        provider = OpenAIProvider(api_key='test-key-not-used', reasoning_effort='high', max_retries=0)
        response = SimpleNamespace(output=[], output_text='OpenAI response', model='gpt-test', usage=None)
        captured = {}

        def create(**kwargs):
            captured.update(kwargs)
            return response

        provider.client = SimpleNamespace(responses=SimpleNamespace(create=create))
        turn = provider.chat(system='system', messages=[{'role': 'user', 'content': 'Hi'}], model='gpt-test', timeout=2)
        self.assertEqual(turn.text, 'OpenAI response')
        self.assertIs(captured['store'], False)
        self.assertGreater(captured['timeout'], 0)
        self.assertLessEqual(captured['timeout'], 2)

    def test_openai_malformed_response_is_rejected(self):
        provider = OpenAIProvider(api_key='test-key-not-used', max_retries=0)
        provider.client = SimpleNamespace(
            responses=SimpleNamespace(create=lambda **_kwargs: SimpleNamespace(output=None, output_text='')),
        )
        with self.assertRaisesRegex(ValueError, 'malformed response'):
            provider.chat(system='system', messages=[], model='gpt-test', timeout=1)

    def test_connection_and_read_timeout_failures_are_classified(self):
        connection = classify_exception(ConnectionError('connection reset by peer'))
        read_timeout = classify_exception(TimeoutError('provider read timeout'))
        self.assertEqual(connection.category, ErrorCategory.NETWORK_ERROR)
        self.assertTrue(connection.retryable)
        self.assertEqual(read_timeout.category, ErrorCategory.TIMEOUT)
        self.assertTrue(read_timeout.retryable)

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
        self.assertTrue(any('timeout' in text.lower() for _speaker, text in appended))

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
        self.assertTrue(any('ERROR:' in text for _speaker, text in appended))
        self.assertTrue(any('request deadline exceeded' in text for _speaker, text in appended))

    def test_deferred_ui_callback_preserves_original_failure(self):
        callbacks = []

        class DeferredRoot:
            def after(self, _delay, callback):
                callbacks.append(callback)

        desktop = JarvisDesktop.__new__(JarvisDesktop)
        desktop.busy = True
        desktop.hud = None
        desktop.root = DeferredRoot()
        desktop.jarvis = SimpleNamespace(chat=lambda _text: (_ for _ in ()).throw(TimeoutError('provider read timeout')))
        appended = []
        desktop._append = lambda speaker, text: appended.append((speaker, text))
        desktop._answer_worker('Hello', [])
        self.assertEqual(len(callbacks), 1)
        callbacks.pop()()
        self.assertFalse(desktop.busy)
        self.assertTrue(any('provider read timeout' in text for _speaker, text in appended))

    def test_permission_dialog_wait_is_bounded_by_active_request(self):
        desktop = JarvisDesktop.__new__(JarvisDesktop)
        desktop.root = SimpleNamespace(after=lambda _delay, _callback: None)
        desktop.jarvis = SimpleNamespace(
            _active_request=SimpleNamespace(remaining=lambda: 0.02),
        )
        started = time.monotonic()
        self.assertFalse(desktop._confirm_tool('type_text', {'text': 'hello'}))
        self.assertLess(time.monotonic() - started, 0.2)

    def test_long_typing_action_is_rejected_before_side_effect_when_budget_is_too_short(self):
        registry = ToolRegistry.__new__(ToolRegistry)
        registry.permissions = SimpleNamespace(check=lambda *_args: self.fail('permission prompt should not run'))
        with request_lifecycle(1, operation='typing test'):
            output = registry.call('type_text', {'text': 'x' * 5000, 'interval': 0.2})
        self.assertIn('Typing would need', output)
        self.assertIn('only', output)


if __name__ == '__main__':
    unittest.main()
