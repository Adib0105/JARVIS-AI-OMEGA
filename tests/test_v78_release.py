import json
import os
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import MagicMock, patch

from jarvis.daily_briefing import _WEATHER_CACHE, rich_weather_report, air_report, weather_report, wake_greeting
from jarvis.weather_details import air_text, forecast_text
from jarvis.wake_service import PartialWakeDetector
from jarvis.user_profiles import ProfileStore
from jarvis.subscription_client import SubscriptionClient, service_origin
from jarvis.voice import VoiceOutput, _SENTINEL
from jarvis.config import settings


class WeatherTests(unittest.TestCase):
    location = dict(name='Patna', latitude=25.6, longitude=85.1)
    def setUp(self):
        _WEATHER_CACHE.clear()
        self.addCleanup(_WEATHER_CACHE.clear)

    def test_rich_briefing_has_real_values_and_scale(self):
        forecast = {'current': {'temperature_2m': 28, 'apparent_temperature': 31, 'cloud_cover': 75, 'weather_code': 3},
                    'daily': {'precipitation_probability_max': [80], 'sunrise': ['2026-09-26T05:30'], 'sunset': ['2026-09-26T17:50']}}
        def fetch(url, params):
            return {'current': {'us_aqi': 120, 'pm2_5': 34}} if 'air-quality' in url else forecast
        with patch('jarvis.daily_briefing._get_json', side_effect=fetch):
            report = rich_weather_report(self.location)
        for word in ('28 degree', '31 degree', '75 percent', '80 percent', 'badal', '05:30', '17:50', 'US AQI 120', 'PM2.5 34', 'chhata'):
            self.assertIn(word, report)
        self.assertIn('Indian AQI scale nahi', report)

    def test_tomorrow_uses_second_date_and_separate_cache(self):
        data = {'daily': {'precipitation_probability_max': [10, 90]}}
        with patch('jarvis.daily_briefing._get_json', return_value=data) as fetch:
            self.assertIn('Aaj barish', weather_report(self.location))
            self.assertIn('Kal barish ya anya precipitation ka maximum chance 90', weather_report(self.location, 'tomorrow'))
            self.assertEqual(fetch.call_count, 2)

    def test_aqi_invalid_values_never_become_zero(self):
        for value in (None, True, -5, float('nan'), float('inf'), '43'):
            result = air_text({'current': {'us_aqi': value, 'pm2_5': value}})
            self.assertIn('available nahi', result)
            self.assertNotIn('US AQI 0', result)
            self.assertNotIn('PM2.5 ', result)

    def test_air_failure_preserves_weather(self):
        def fetch(url, params):
            if 'air-quality' in url:
                raise TimeoutError
            return {'current': {'temperature_2m': 28}}
        with patch('jarvis.daily_briefing._get_json', side_effect=fetch):
            report = rich_weather_report(self.location)
        self.assertIn('28 degree', report)
        self.assertIn('AQI abhi available nahi', report)

    def test_air_cache_cannot_cross_city(self):
        with patch('jarvis.daily_briefing._get_json', return_value={'current': {'us_aqi': 50}}) as fetch:
            air_report(self.location)
            air_report(self.location)
            air_report(dict(self.location, latitude=24))
        self.assertEqual(fetch.call_count, 2)

    def test_commercial_weather_fails_without_merchant_key(self):
        with patch.dict(os.environ, {'JARVIS_COMMERCIAL_WEATHER': 'true', 'OPEN_METEO_API_KEY': ''}), patch('jarvis.daily_briefing.urlopen') as request:
            with self.assertRaisesRegex(RuntimeError, 'commercial weather'):
                weather_report(self.location)
        request.assert_not_called()

    def test_alerts_are_condition_based(self):
        self.assertNotIn('Thunderstorm', forecast_text({}, 'Patna'))
        result = forecast_text({'daily': {'weather_code': [95], 'wind_gusts_10m_max': [65]}}, 'Patna')
        self.assertIn('Thunderstorm', result)
        self.assertIn('65 kilometre', result)

    def test_week_report_has_available_dates_only(self):
        result = forecast_text({'daily': {'time': ['2026-09-26', '2026-09-27'], 'precipitation_probability_max': [5, 20]}}, 'Patna', 'week')
        self.assertIn('2026-09-27', result)
        self.assertNotIn('2026-09-28', result)


class WakeLatencyTests(unittest.TestCase):
    def test_stable_partial_wake_emits_before_final_once(self):
        now = [0.0]
        detector = PartialWakeDetector('jarvis', lambda: now[0])
        self.assertIsNone(detector.feed('wake up jarvis'))
        now[0] = 0.46
        self.assertEqual(detector.feed('wake up jarvis'), '')
        self.assertIsNone(detector.feed('wake up jarvis'))
        self.assertIsNone(detector.feed('wake up jarvis', final=True))

    def test_inline_command_waits_for_final_and_is_preserved(self):
        detector = PartialWakeDetector('jarvis')
        for _ in range(5):
            self.assertIsNone(detector.feed('jarvis weather'))
        self.assertEqual(detector.feed('jarvis weather report', final=True), 'weather report')

    def test_partial_jitter_and_false_substrings_do_not_wake(self):
        now = [0.0]
        detector = PartialWakeDetector('jarvis', lambda: now[0])
        detector.feed('hey jarvis')
        now[0] = 1
        self.assertIsNone(detector.feed('jarvisian'))
        self.assertIsNone(detector.feed('hey jarvis'))

    def test_warm_model_shared_across_wake_and_transcription(self):
        from jarvis import offline_speech
        fake = MagicMock()
        fake.KaldiRecognizer.return_value.FinalResult.return_value = '{"text":"hello"}'
        with TemporaryDirectory() as folder, patch.dict('sys.modules', {'vosk': fake}), patch.object(offline_speech, '_model', None), patch.object(offline_speech, '_model_path', None):
            first = offline_speech.get_vosk_model(folder)
            self.assertIs(first, offline_speech.get_vosk_model(folder))
            self.assertEqual(offline_speech.transcribe_vosk(b'', 16000, folder), 'hello')
            fake.Model.assert_called_once()

    def test_greeting_uses_active_name(self):
        self.assertIn('Hello Soni', wake_greeting('Soni'))
        self.assertNotIn('Adib', wake_greeting('Soni'))

    def test_ack_uses_offline_engine_and_keeps_stop_behavior(self):
        with patch('jarvis.voice.settings', replace(settings, enable_voice_output=False)):
            voice = VoiceOutput()
        voice.enabled = True
        voice.acknowledge('Hello Adib')
        self.assertEqual(voice.state, 'queued')
        voice._queue.put(_SENTINEL)
        with patch.object(voice, '_speak_offline', return_value='completed') as offline, patch.object(voice, '_speak_process') as cloud:
            voice._worker()
        offline.assert_called_once_with('Hello Adib')
        cloud.assert_not_called()
        voice.shutdown()

    def test_wait_idle_does_not_skip_pending_greeting(self):
        with patch('jarvis.voice.settings', replace(settings, enable_voice_output=False)):
            voice = VoiceOutput()
        voice.enabled = True
        voice.acknowledge('Hello Adib')
        self.assertFalse(voice.wait_idle(threading.Event(), timeout=0.01))
        voice.stop()
        self.assertTrue(voice.wait_idle(threading.Event(), timeout=0.01))
        voice.shutdown()

    def test_cached_wake_briefing_and_command_run_without_weather_network(self):
        from jarvis.background_ui import BackgroundController
        import time
        desktop = MagicMock()
        desktop.busy = False
        desktop.voice.enabled = False
        desktop.voice.state = 'idle'
        with patch('jarvis.background_ui.load_preferences', return_value={}):
            controller = BackgroundController(desktop)
        controller.enabled = True
        controller.listener = MagicMock()
        controller.preferences['location'] = {'name': 'Patna', 'latitude': 25.6, 'longitude': 85.1}
        controller.weather_snapshot = (controller.preferences['location'], time.monotonic(), 'Cloud cover 70 percent.')
        with patch('jarvis.microphone.record_until_silence', return_value='time batao'), patch('jarvis.daily_briefing.rich_weather_report') as network:
            controller._followup_worker(controller.generation, threading.Event())
        network.assert_not_called()
        desktop.voice.speak.assert_called_with('Cloud cover 70 percent.')
        results = [controller.events.get_nowait(), controller.events.get_nowait()]
        self.assertEqual(results[-1][1]['text'], 'time batao')
        controller.listener.start.assert_called_once()

    def test_initial_background_start_failure_schedules_recovery(self):
        from jarvis.background_ui import BackgroundController
        desktop = MagicMock()
        desktop._closing = False
        desktop.wake_listener.running = False
        desktop._live_listening = desktop._live_voice_enabled = False
        with patch('jarvis.background_ui.load_preferences', return_value={'enabled': True}):
            controller = BackgroundController(desktop)
        controller.listener = MagicMock()
        controller.listener.start.side_effect = RuntimeError('device temporarily missing')
        with patch.object(controller, 'ensure_tray'), patch('jarvis.background_ui.settings', replace(settings, enable_mic_input=True)):
            self.assertFalse(controller.enable(show_error=False, persist_choice=False))
        self.assertTrue(any(call.args[0] == 3000 for call in desktop.root.after.call_args_list))
        self.assertTrue(controller.preferences['enabled'])

    def test_stalled_microphone_is_recovered_without_foreground_focus(self):
        from jarvis.background_ui import BackgroundController
        import time
        desktop = MagicMock()
        desktop._closing = False
        desktop.voice.state = 'idle'
        with patch('jarvis.background_ui.load_preferences', return_value={'enabled': True}):
            controller = BackgroundController(desktop)
        controller.listener = MagicMock()
        controller.listener.last_audio_at = time.monotonic() - 30
        controller.enabled = True
        controller._poll_events()
        self.assertFalse(controller.enabled)
        controller.listener.stop.assert_called_once()
        desktop.root.deiconify.assert_not_called()


class AccountTests(unittest.TestCase):
    def test_password_change_rotates_session_and_old_password_fails(self):
        with TemporaryDirectory() as folder:
            store = ProfileStore(Path(folder))
            original = store.create('adib', 'Adib', 'old-password')
            old_session = store.session_path.read_text()
            updated = store.update_profile('adib', 'old-password', display_name='Adib Azam', new_password='new-password')
            self.assertEqual(updated.profile_id, original.profile_id)
            self.assertEqual(store.resume_session().display_name, 'Adib Azam')
            with self.assertRaises(PermissionError):
                store.authenticate('adib', 'old-password')
            store.session_path.write_text(old_session)
            self.assertIsNone(store.resume_session())
            self.assertEqual(store.authenticate('adib', 'new-password').display_name, 'Adib Azam')

    def test_wrong_password_cannot_rename_another_profile(self):
        with TemporaryDirectory() as folder:
            store = ProfileStore(Path(folder))
            store.create('user1', 'First', 'password-one')
            store.create('user2', 'Second', 'password-two')
            with self.assertRaises(PermissionError):
                store.update_profile('user2', 'password-one', display_name='attacker')
            self.assertEqual(store.authenticate('user2', 'password-two').display_name, 'Second')

    def test_client_requires_secure_origin_and_payment_host(self):
        for origin in ('http://example.com', 'https://user:password@example.com', 'https://example.com/path', 'https://example.com?token=foo'):
            with self.assertRaises(ValueError):
                service_origin(origin)
        api = SubscriptionClient('https://accounts.example.com')
        with patch.object(api, 'request', return_value={'url': 'https://checkout.stripe.com.evil.example/'}):
            with self.assertRaises(RuntimeError):
                api.payment_link('monthly')

    def test_client_logout_forgets_token_even_if_network_fails(self):
        api = SubscriptionClient('https://accounts.example.com')
        api._token = 'temporary-session'
        with patch.object(api, 'request', side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                api.sign_out()
        self.assertEqual(api._token, '')

    def test_billing_secrets_blocked_from_memory_and_redacted(self):
        from jarvis.security.secrets import contains_secret
        from jarvis.security.redaction import redact_text
        for secret in ('sk_test_' + 'a' * 24, 'rk_live_' + 'b' * 24, 'whsec_' + 'c' * 24):
            self.assertTrue(contains_secret(secret))
            self.assertNotIn(secret, redact_text(secret))
