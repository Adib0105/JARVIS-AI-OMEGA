import tempfile
import unittest
from pathlib import Path

from jarvis.observability.health import HealthStatus, JarvisHealthSystem
from jarvis.observability.manager import ObservabilityManager
from jarvis.providers.base import AIProvider, ProviderTurn
from jarvis.providers.observed import ObservedProvider
from jarvis.providers.router import ModelRouter


class FakeProvider(AIProvider):
    name = 'fake'

    def __init__(self, *, fail=False):
        self.fail = fail

    def _turn(self, model):
        if self.fail:
            raise TimeoutError('fake timeout')
        return ProviderTurn(
            text='ok', model=model, provider='fake',
            usage={'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15, 'cost': 0.0012},
        )

    def chat(self, *, system, messages, model, timeout):
        return self._turn(model)

    def chat_with_tools(self, *, system, messages, model, tools, timeout):
        return self._turn(model)

    def continue_with_tools(self, *, previous, tool_results, system, model, tools, timeout):
        return self._turn(model)

    def vision(self, *, system, prompt, image_urls, model, timeout):
        return self._turn(model)


class V75ObservabilityTests(unittest.TestCase):
    def test_cost_is_only_reported_when_provider_explicitly_supplies_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs = ObservabilityManager(Path(tmp) / 'jarvis.db')
            no_cost = obs.record(
                category='MODEL', event_type='chat', status='SUCCESS',
                provider='fake', model='m1', usage={'total_tokens': 25},
            )
            explicit = obs.record(
                category='MODEL', event_type='chat', status='SUCCESS',
                provider='fake', model='m1', usage={'total_tokens': 25, 'cost': 0.004},
            )
            self.assertIsNone(no_cost.cost)
            self.assertIsNone(no_cost.cost_source)
            self.assertEqual(explicit.cost, 0.004)
            self.assertTrue(explicit.cost_source.startswith('provider-reported:'))
            summary = obs.usage_summary('today')
            self.assertEqual(summary['reported_cost'], 0.004)
            self.assertEqual(summary['requests'], 2)

    def test_observability_redacts_secret_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs = ObservabilityManager(Path(tmp) / 'jarvis.db')
            secret = 'sk-proj-abcdefghijklmnopqrstuvwxyz12345'
            obs.record(
                category='SECURITY', event_type='secret.test', status='BLOCKED',
                usage={'api_key': secret}, metadata={'message': f'password={secret}'},
            )
            row = obs.events(limit=1)[0]
            self.assertNotIn(secret, str(row))
            self.assertEqual(row['usage']['api_key'], '[REDACTED]')

    def test_observed_provider_persists_usage_fallback_and_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs = ObservabilityManager(Path(tmp) / 'jarvis.db')
            provider = ObservedProvider(
                FakeProvider(), obs,
                context_provider=lambda: {'session_id': 'S1', 'mission_id': 'M1', 'route': 'coding'},
                fallback=True,
            )
            turn = provider.chat(system='s', messages=[], model='model-x', timeout=5)
            self.assertEqual(turn.text, 'ok')
            summary = obs.usage_summary('today')
            self.assertEqual(summary['fallbacks'], 1)
            self.assertEqual(summary['token_usage']['total_tokens'], 15.0)
            self.assertEqual(summary['reported_cost'], 0.0012)

            failing = ObservedProvider(FakeProvider(fail=True), obs)
            with self.assertRaises(TimeoutError):
                failing.chat(system='s', messages=[], model='model-x', timeout=5)
            events = obs.events(limit=5, category='MODEL')
            self.assertTrue(any(item['status'] == 'FAILED' for item in events))

    def test_router_has_master_plan_categories(self):
        router = ModelRouter()
        self.assertEqual(router.select('inspect this Python repository', 'coding').category, 'CODING')
        self.assertEqual(router.select('make a safe plan', 'planning').category, 'PLANNING')
        self.assertEqual(router.select('verify result', 'review').category, 'REVIEW')
        self.assertEqual(router.select('summarize it', 'summary').category, 'SUMMARY')
        self.assertEqual(router.select('look at image', 'image').category, 'VISION')

    def test_health_system_runs_and_database_check_is_not_fake(self):
        with tempfile.TemporaryDirectory() as tmp:
            health = JarvisHealthSystem(Path(tmp) / 'jarvis.db')
            report = health.run()
            self.assertIn(report.status, {HealthStatus.PASS, HealthStatus.WARNING, HealthStatus.FAIL, HealthStatus.NOT_VERIFIED})
            database = next(item for item in report.checks if item.name == 'Database')
            self.assertEqual(database.status, HealthStatus.PASS)
            self.assertIn('quick_check=ok', database.detail)

    def test_configured_or_installed_external_capability_is_not_reported_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = JarvisHealthSystem(Path(tmp) / 'jarvis.db').run()
            checks = {item.name: item for item in report.checks}
            provider = checks['AI Provider']
            if 'No usable hosted API key' not in provider.detail:
                self.assertEqual(provider.status, HealthStatus.NOT_VERIFIED)
            for name in ('Vision', 'Voice', 'Microphone'):
                check = checks[name]
                if check.status not in {HealthStatus.WARNING, HealthStatus.FAIL}:
                    self.assertEqual(check.status, HealthStatus.NOT_VERIFIED, name)
            payload = report.as_dict()
            self.assertIn('NOT_VERIFIED', payload['counts'])


if __name__ == '__main__':
    unittest.main()
