import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from jarvis.daily_briefing import weather_report, valid_location, _WEATHER_CACHE
from jarvis.wake_model import install_model, MODEL_NAME, model_valid
from jarvis.updater import check_latest_release, validate_asset
from jarvis.settings_ui import update_env_values


class WeatherHardeningTests(unittest.TestCase):
    location = dict(name='Patna', latitude=25.6, longitude=85.1)

    def setUp(self):
        _WEATHER_CACHE.clear()
        self.addCleanup(_WEATHER_CACHE.clear)

    def test_boolean_coordinates_are_not_locations(self):
        self.assertFalse(valid_location(dict(self.location, latitude=True)))

    def test_malformed_payload_has_clear_failure(self):
        for payload in ([], None, {'error': True}):
            with patch('jarvis.daily_briefing._get_json', return_value=payload):
                with self.assertRaises(ValueError):
                    weather_report(self.location)

    def test_boolean_weather_values_are_missing(self):
        with patch('jarvis.daily_briefing._get_json', return_value={'current': {'temperature_2m': True}, 'daily': {'precipitation_probability_max': [False]}}):
            report = weather_report(self.location)
        self.assertNotIn('0 percent', report)
        self.assertNotIn('1 degree', report)

    def test_stale_weather_is_labeled_and_bounded(self):
        payload = {'current': {'temperature_2m': 30}}
        with patch('jarvis.daily_briefing.time.monotonic', return_value=100), patch('jarvis.daily_briefing._get_json', return_value=payload):
            weather_report(self.location)
        with patch('jarvis.daily_briefing.time.monotonic', return_value=450), patch('jarvis.daily_briefing._get_json', side_effect=OSError):
            self.assertIn('purana forecast', weather_report(self.location))
        with patch('jarvis.daily_briefing.time.monotonic', return_value=2000), patch('jarvis.daily_briefing._get_json', side_effect=OSError):
            with self.assertRaises(OSError):
                weather_report(self.location)

    def test_weather_units_and_extra_readings(self):
        with patch('jarvis.daily_briefing._get_json', return_value={'current': {'relative_humidity_2m': 60, 'wind_speed_10m': 12}}) as request:
            report = weather_report(self.location)
        self.assertIn('Humidity 60 percent', report)
        self.assertIn('12 kilometre per hour', report)
        self.assertEqual(request.call_args.args[1]['temperature_unit'], 'celsius')


class ModelSetupTests(unittest.TestCase):
    def archive(self, names):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as bundle:
            for name in names:
                bundle.writestr(name, b'model fixture')
        return io.BytesIO(data.getvalue())

    def test_complete_model_installs_and_is_reused(self):
        names = [MODEL_NAME + '/am/final.mdl', MODEL_NAME + '/conf/model.conf']
        with tempfile.TemporaryDirectory() as folder, patch('jarvis.wake_model.urlopen', return_value=self.archive(names)) as request:
            destination = install_model(folder)
            self.assertTrue(model_valid(destination))
            self.assertEqual(install_model(folder), destination)
            request.assert_called_once()
            self.assertEqual(len(list(Path(folder).iterdir())), 1)

    def test_unsafe_archive_and_partial_model_leave_no_install(self):
        for name in ('../outside.txt', MODEL_NAME + '/../../outside.txt', '/absolute', MODEL_NAME + '/conf/missing'):
            with tempfile.TemporaryDirectory() as folder, patch('jarvis.wake_model.urlopen', return_value=self.archive([name])):
                with self.assertRaises(RuntimeError):
                    install_model(folder)
                self.assertEqual(list(Path(folder).iterdir()), [])

    def test_download_failure_is_cleaned_up(self):
        with tempfile.TemporaryDirectory() as folder, patch('jarvis.wake_model.urlopen', side_effect=OSError):
            with self.assertRaises(OSError):
                install_model(folder)
            self.assertEqual(list(Path(folder).iterdir()), [])


class SettingsAndReleaseTests(unittest.TestCase):
    def test_helper_must_acknowledge_before_app_can_exit(self):
        import sys
        from unittest.mock import MagicMock
        from jarvis.updater import start_installer_update, INSTALLER_NAME
        from test_desktop_updates import asset
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            package = root / 'app'
            package.mkdir()
            (package / 'apply-update.ps1').write_text('# fixture')
            installer = root / INSTALLER_NAME
            installer.write_bytes(b'example executable')
            process = MagicMock()
            def acknowledge():
                (root / 'helper-ready.txt').write_text('ready')
                return None
            process.poll.side_effect = acknowledge
            with patch.object(sys, 'frozen', True, create=True), patch('jarvis.config.ROOT', package), patch('jarvis.windows_integration.powershell_path', return_value='powershell.exe'), patch('subprocess.Popen', return_value=process):
                start_installer_update(installer, asset())
            self.assertTrue((root / 'helper-ready.txt').exists())

    def test_changed_installer_never_starts_helper(self):
        import sys
        from jarvis.updater import start_installer_update, INSTALLER_NAME
        from test_desktop_updates import asset
        with tempfile.TemporaryDirectory() as folder:
            installer = Path(folder) / INSTALLER_NAME
            installer.write_bytes(b'changed')
            with patch.object(sys, 'frozen', True, create=True), patch('subprocess.Popen') as launch:
                with self.assertRaisesRegex(RuntimeError, 'changed'):
                    start_installer_update(installer, asset())
            launch.assert_not_called()

    def test_bom_and_duplicate_settings_do_not_override_saved_choice(self):
        from dotenv import dotenv_values
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'
            path.write_text('\ufeffENABLE_MIC_INPUT=false\nENABLE_MIC_INPUT=false\n# preserve\n', encoding='utf-8')
            with patch('jarvis.settings_ui._env_path', return_value=path):
                update_env_values({'ENABLE_MIC_INPUT': 'true'})
            self.assertEqual(dotenv_values(path)['ENABLE_MIC_INPUT'], 'true')
            self.assertEqual(path.read_text().count('ENABLE_MIC_INPUT='), 1)
            self.assertIn('# preserve', path.read_text())

    def test_malformed_release_and_oversized_response(self):
        for raw in (b'[]', b'x' * (1024 * 1024 + 1)):
            with patch('urllib.request.urlopen', return_value=io.BytesIO(raw)):
                with self.assertRaises(RuntimeError):
                    check_latest_release('7.5.1')

    def test_non_object_asset_entries_are_ignored(self):
        payload = {'tag_name': 'v7.5.999', 'assets': [None, 'wrong']}
        with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(payload).encode())):
            self.assertIsNone(check_latest_release('7.5.1')['asset'])

    def test_boolean_size_is_rejected(self):
        from test_desktop_updates import asset
        with self.assertRaises(ValueError):
            validate_asset(dict(asset(), size=True))
