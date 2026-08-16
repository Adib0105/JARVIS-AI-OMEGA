import tempfile
import unittest
from pathlib import Path

from jarvis.errors import ErrorCategory, classify_exception
from jarvis.observability.manager import ObservabilityManager
from jarvis.providers.base import AIProvider, ProviderTurn
from jarvis.providers.circuit_breaker import CircuitOpenError, ProviderCircuitBreaker
from jarvis.providers.observed import ObservedProvider


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += float(seconds)


class CountingProvider(AIProvider):
    name = 'counting'

    def __init__(self, *, fail=True):
        self.fail = fail
        self.calls = 0

    def _turn(self, model):
        self.calls += 1
        if self.fail:
            raise TimeoutError('provider timed out')
        return ProviderTurn(text='ok', model=model, provider=self.name)

    def chat(self, *, system, messages, model, timeout):
        return self._turn(model)

    def chat_with_tools(self, *, system, messages, model, tools, timeout):
        return self._turn(model)

    def continue_with_tools(self, *, previous, tool_results, system, model, tools, timeout):
        return self._turn(model)

    def vision(self, *, system, prompt, image_urls, model, timeout):
        return self._turn(model)


class V75ProviderCircuitBreakerTests(unittest.TestCase):
    def test_retryable_failure_budget_opens_and_half_open_probe_recovers(self):
        clock = FakeClock()
        breaker = ProviderCircuitBreaker(
            'fake', failure_threshold=2, recovery_seconds=10, clock=clock
        )
        breaker.before_call()
        breaker.record_failure(retryable=True)
        self.assertEqual(breaker.snapshot().state, 'CLOSED')
        breaker.before_call()
        breaker.record_failure(retryable=True)
        self.assertEqual(breaker.snapshot().state, 'OPEN')
        with self.assertRaises(CircuitOpenError):
            breaker.before_call()
        clock.advance(11)
        breaker.before_call()
        self.assertEqual(breaker.snapshot().state, 'HALF_OPEN')
        breaker.record_success()
        snapshot = breaker.snapshot()
        self.assertEqual(snapshot.state, 'CLOSED')
        self.assertEqual(snapshot.consecutive_retryable_failures, 0)

    def test_non_retryable_failure_does_not_poison_provider_health(self):
        breaker = ProviderCircuitBreaker('fake', failure_threshold=1, recovery_seconds=10)
        breaker.before_call()
        breaker.record_failure(retryable=False)
        self.assertEqual(breaker.snapshot().state, 'CLOSED')
        breaker.before_call()  # still allowed

    def test_observed_provider_blocks_calls_after_repeated_timeouts(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs = ObservabilityManager(Path(tmp) / 'obs.db')
            raw = CountingProvider(fail=True)
            breaker = ProviderCircuitBreaker('counting', failure_threshold=2, recovery_seconds=60)
            provider = ObservedProvider(raw, obs, circuit_breaker=breaker)
            for _ in range(2):
                with self.assertRaises(TimeoutError):
                    provider.chat(system='s', messages=[], model='m', timeout=1)
            self.assertEqual(raw.calls, 2)
            with self.assertRaises(CircuitOpenError):
                provider.chat(system='s', messages=[], model='m', timeout=1)
            self.assertEqual(raw.calls, 2, 'open circuit must block before hitting provider')
            self.assertEqual(provider.circuit_status()['state'], 'OPEN')
            events = obs.events(limit=10, category='MODEL')
            self.assertTrue(any(
                row['status'] == 'BLOCKED'
                and row['metadata'].get('error_category') == 'CIRCUIT_OPEN'
                for row in events
            ))

    def test_circuit_open_error_is_retryable_network_failure_with_retry_after(self):
        exc = CircuitOpenError('fake', 12.5)
        failure = classify_exception(exc, provider='fake', operation='chat')
        self.assertEqual(failure.category, ErrorCategory.NETWORK_ERROR)
        self.assertTrue(failure.retryable)
        self.assertEqual(failure.retry_after, 12.5)


if __name__ == '__main__':
    unittest.main()
