import hashlib
import io
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from jarvis.updater import validate_asset, download_installer, INSTALLER_NAME, check_latest_release
from jarvis.fast_commands import execute_fast_command, local_quick_reply
from jarvis.speech_worker import speech_segments
from jarvis.background_ui import BackgroundController


def asset(data=b'example executable'):
    return dict(name=INSTALLER_NAME, browser_download_url='https://github.com/Adib0105/JARVIS-AI-OMEGA/releases/download/v7.5.999/' + INSTALLER_NAME,
                digest='sha256:' + hashlib.sha256(data).hexdigest(), size=len(data))


class UpdateTests(unittest.TestCase):
    def test_reject_wrong_repo_missing_hash_and_size(self):
        for field, value in [('browser_download_url', 'https://evil.example/setup.exe'), ('digest', ''), ('size', 0),
                             ('browser_download_url', asset()['browser_download_url'].replace('Adib0105', 'other'))]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_asset(dict(asset(), **{field: value}))

    def test_verified_download(self):
        data = b'example executable'
        with patch('urllib.request.urlopen', return_value=io.BytesIO(data)):
            path = download_installer(asset(data))
        try:
            self.assertEqual(path.read_bytes(), data)
        finally:
            path.unlink()
            path.parent.rmdir()

    def test_corrupt_and_truncated_downloads_never_install(self):
        for data in [b'x' * len(b'example executable'), b'short']:
            with patch('urllib.request.urlopen', return_value=io.BytesIO(data)), self.assertRaises(RuntimeError):
                download_installer(asset())

    def test_latest_release_includes_verified_installer(self):
        import json
        payload = dict(tag_name='v7.5.999', assets=[asset()], html_url='https://github.com/Adib0105/JARVIS-AI-OMEGA/releases/tag/v7.5.999')
        with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(payload).encode())):
            result = check_latest_release('7.5.1')
        self.assertTrue(result['available'])
        self.assertEqual(result['asset'], asset())

    def test_failed_network_keeps_app_usable(self):
        with patch('urllib.request.urlopen', side_effect=OSError('offline')), self.assertRaisesRegex(RuntimeError, 'offline'):
            check_latest_release('7.5.1')


class LatencyLifecycleTests(unittest.TestCase):
    def test_local_greeting_and_time_never_use_tools(self):
        app = MagicMock()
        self.assertIn('Friday', execute_fast_command(app, 'Jarvis hello'))
        self.assertIn('boss', execute_fast_command(app, 'time batao'))
        app.tools.call.assert_not_called()
        self.assertIsNone(local_quick_reply('explain how weather forecasting works'))

    def test_short_audio_first_without_losing_text(self):
        text = 'Hello boss. ' + 'This is a longer sentence. ' * 100
        chunks = list(speech_segments(text))
        self.assertEqual(chunks[0], 'Hello boss.')
        self.assertEqual(' '.join(chunks), text.strip())

    def test_weather_cache_reuses_only_same_location(self):
        from jarvis.daily_briefing import weather_report, _WEATHER_CACHE
        _WEATHER_CACHE.clear()
        try:
            with patch('jarvis.daily_briefing._get_json', return_value={'current': {'temperature_2m': 25}, 'daily': {'precipitation_probability_max': [60]}}) as request:
                weather_report(dict(name='A', latitude=10, longitude=20))
                self.assertIn('cached', weather_report(dict(name='A', latitude=10, longitude=20)))
                weather_report(dict(name='B', latitude=20, longitude=30))
                self.assertEqual(request.call_count, 2)
        finally:
            _WEATHER_CACHE.clear()

    def test_tray_failure_minimizes_without_exit(self):
        desktop = MagicMock()
        with patch('jarvis.background_ui.load_preferences', return_value={}):
            controller = BackgroundController(desktop)
        with patch.object(controller, 'ensure_tray', side_effect=RuntimeError('tray unavailable')):
            controller.hide_to_tray()
        desktop.root.iconify.assert_called_once()
        desktop.root.destroy.assert_not_called()
