import json
import queue
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from jarvis.wake_service import BackgroundWakeListener, split_wake
from jarvis.daily_briefing import build_briefing, weather_report, find_locations
from jarvis.fast_commands import parse_fast_command, execute_fast_command
from jarvis.youtube_player import play_on_page
from jarvis.background_ui import BackgroundController, load_preferences, save_preferences
from jarvis.permissions import Decision
from jarvis.tools import ToolRegistry
from jarvis.agent.verification import VerificationEngine


class WakeTests(unittest.TestCase):
    def test_wake_aliases_and_preserved_query(self):
        for word in ['Jarvis', 'jarves', 'जार्विस', 'जारविस', 'Hey Jarvis']:
            self.assertEqual(split_wake(word + ', Play Tum Hi Ho'), 'Play Tum Hi Ho')
        self.assertEqual(split_wake('Jarvis'), '')
        self.assertEqual(split_wake('hello omega play', 'hello omega'), 'play')

    def test_not_a_substring(self):
        for text in ['superjarvis open', 'jarvisian', 'hello world']:
            self.assertIsNone(split_wake(text))

    def test_missing_model_fails_before_thread(self):
        listener = BackgroundWakeListener('', MagicMock(), MagicMock())
        with self.assertRaisesRegex(RuntimeError, 'model folder'):
            listener.start()
        self.assertFalse(listener.running)

    def test_stream_cancellation_and_suppression(self):
        listener = BackgroundWakeListener('model', MagicMock(), MagicMock())
        recog = MagicMock()
        recog.AcceptWaveform.return_value = True
        recog.Result.return_value = json.dumps({'text': 'Jarvis play music'})
        stream = MagicMock()
        reads = [0]
        def read(_):
            reads[0] += 1
            if reads[0] == 3:
                listener.stop()
            return b'\0\0' * 1600, False
        stream.read.side_effect = read
        listener.suspended = lambda: reads[0] == 1
        context = MagicMock()
        context.__enter__.return_value = stream
        vosk = MagicMock()
        vosk.KaldiRecognizer.return_value = recog
        with patch.dict('sys.modules', {'vosk': vosk, 'sounddevice': MagicMock()}), patch('jarvis.microphone._exclusive_stream', return_value=context):
            listener._loop()
        listener.on_wake.assert_called_once_with('play music')
        listener.on_error.assert_not_called()
        self.assertTrue(listener._stop.is_set())
        self.assertGreaterEqual(recog.Reset.call_count, 2)


class BriefingTests(unittest.TestCase):
    location = {'name': 'Patna', 'latitude': 25.6, 'longitude': 85.1}

    def test_no_location_does_not_network(self):
        with patch('jarvis.daily_briefing._get_json') as request:
            self.assertIn('shehar', weather_report(None))
        request.assert_not_called()

    def test_weather_uses_local_day_and_probability(self):
        with patch('jarvis.daily_briefing._get_json', return_value={'current': {'temperature_2m': 29}, 'daily': {'precipitation_probability_max': [70]}}) as request:
            result = weather_report(self.location)
        self.assertIn('70 percent', result)
        self.assertIn('29 degree', result)
        self.assertIn('guarantee nahi', result)
        self.assertEqual(request.call_args.args[1]['timezone'], 'auto')

    def test_missing_weather_is_not_zero(self):
        with patch('jarvis.daily_briefing._get_json', return_value={'daily': {'precipitation_probability_max': [None]}}):
            result = weather_report(self.location)
        self.assertNotIn('0 percent', result)
        self.assertIn('available nahi', result)

    def test_invalid_coordinates_rejected_before_network(self):
        with patch('jarvis.daily_briefing._get_json') as request:
            with self.assertRaises(ValueError):
                weather_report(dict(self.location, latitude=float('nan')))
        request.assert_not_called()

    def test_failed_weather_still_reads_real_metrics(self):
        with patch('jarvis.daily_briefing.weather_report', side_effect=OSError), patch('psutil.cpu_percent', return_value=17) as cpu, patch('psutil.virtual_memory', return_value=SimpleNamespace(percent=45)), patch('psutil.sensors_battery', return_value=None):
            result = build_briefing(self.location, datetime(2026, 9, 12, 14))
        self.assertIn('Yes boss, good afternoon', result)
        self.assertIn('CPU 17 percent', result)
        self.assertIn('RAM 45 percent', result)
        self.assertIn('confirm nahi', result)
        cpu.assert_called_once_with(interval=0.25)

    def test_greeting_boundaries(self):
        with patch('jarvis.daily_briefing.weather_report', return_value=''), patch('psutil.cpu_percent', side_effect=OSError):
            for hour, period in [(5, 'morning'), (11, 'morning'), (12, 'afternoon'), (16, 'afternoon'), (17, 'evening'), (0, 'evening')]:
                self.assertIn('good ' + period, build_briefing(now=datetime(2026, 1, 1, hour)))

    def test_city_search_validated(self):
        with patch('jarvis.daily_briefing._get_json') as request:
            with self.assertRaises(ValueError):
                find_locations('')
        request.assert_not_called()


class YoutubeTests(unittest.TestCase):
    def test_supported_commands(self):
        for command in ['Jarvis play Kesariya on YouTube', 'YouTube par Kesariya chalao', 'youtube pe kesariya chala do', 'youtube jao aur kesariya search karo aur pehla video chala do']:
            self.assertEqual(parse_fast_command(command), ('youtube_play_first', {'query': 'kesariya'}))
        self.assertIsNone(parse_fast_command('YouTube par music kaise banate hain?'))

    def test_denial_does_not_fall_back_to_llm(self):
        jarvis = SimpleNamespace(tools=MagicMock())
        jarvis.tools.call.return_value = json.dumps({'ok': False, 'error': 'permission denied'})
        result = execute_fast_command(jarvis, 'play Kesariya on YouTube')
        self.assertIn('permission denied', result)
        jarvis.tools.call.assert_called_once()

    def test_tool_gate_runs_before_browser(self):
        registry = object.__new__(ToolRegistry)
        registry.permissions = MagicMock()
        registry.permissions.check.return_value = Decision(False, 'denied')
        with patch('jarvis.tools.play_first_video') as player:
            result = json.loads(registry.call('youtube_play_first', {'query': 'song'}))
        player.assert_not_called()
        self.assertFalse(result['ok'])

    def test_playback_failure_is_not_success(self):
        registry = MagicMock(spec=ToolRegistry)
        registry.permissions = MagicMock()
        registry.permissions.check.return_value = Decision(True)
        # Handlers are lambdas, so unused registry collaborators need not be created.
        with patch('jarvis.tools.play_first_video', return_value={'playing': False, 'message': 'blocked'}):
            result = json.loads(ToolRegistry.call(registry, 'youtube_play_first', {'query': 'song'}))
        self.assertFalse(result['ok'])
        self.assertEqual(result['error'], 'blocked')

    def make_page(self):
        page = MagicMock()
        first, video, button, ads = [MagicMock() for _ in range(4)]
        first.get_attribute.return_value = '/watch?v=abc123'
        video.evaluate.return_value = True
        ads.count.return_value = 0
        page.url = 'https://www.youtube.com/watch?v=abc123'
        def locator(selector):
            return {'ytd-video-renderer a#video-title:visible': SimpleNamespace(first=first), 'video': SimpleNamespace(first=video), 'button.ytp-play-button': SimpleNamespace(first=button), '.html5-video-player.ad-showing': ads}[selector]
        page.locator.side_effect = locator
        return page, first, video, button, ads

    def test_first_video_and_actual_playback_check(self):
        page, first, _, button, _ = self.make_page()
        result = play_on_page(page, 'song & name')
        self.assertTrue(result['playing'])
        self.assertIn('song+%26+name', page.goto.call_args.args[0])
        first.click.assert_called_once()
        button.click.assert_called_once()
        page.wait_for_function.assert_called_once()

    def test_ad_reported_separately(self):
        page, _, _, _, ads = self.make_page()
        ads.count.return_value = 1
        self.assertTrue(play_on_page(page, 'song')['ad_playing'])

    def test_external_first_link_not_clicked(self):
        page, first, *_ = self.make_page()
        first.get_attribute.return_value = 'https://evil.example/watch?v=x'
        with self.assertRaises(RuntimeError):
            play_on_page(page, 'song')
        first.click.assert_not_called()

    def test_no_false_success_when_playback_blocked(self):
        page, *_ = self.make_page()
        page.wait_for_function.side_effect = TimeoutError
        with self.assertRaises(TimeoutError):
            play_on_page(page, 'song')

    def test_verification_does_not_mark_ad_as_selected_video(self):
        event = {'name': 'youtube_play_first', 'args': {}, 'output': json.dumps({'ok': True, 'verification': {'status': 'PARTIAL', 'verified': False, 'evidence': 'ad playing'}})}
        result = VerificationEngine().verify_tool_event(event)
        self.assertTrue(result['side_effecting'])
        self.assertFalse(result['verified'])


class BackgroundLifecycleTests(unittest.TestCase):
    def controller(self):
        desktop = MagicMock()
        desktop._closing = False
        desktop.busy = False
        desktop.voice.state = 'idle'
        with patch('jarvis.background_ui.load_preferences', return_value={}):
            controller = BackgroundController(desktop)
        controller.listener = MagicMock()
        controller.enabled = True
        return controller, desktop

    def test_speech_and_busy_suppress_wake(self):
        controller, desktop = self.controller()
        for field in ['speech', 'busy', 'pending']:
            desktop.voice.state = 'speaking' if field == 'speech' else 'idle'
            desktop.busy = field == 'busy'
            controller.pending = field == 'pending'
            controller.heard('play music')
            self.assertTrue(controller.events.empty())

    def test_inline_command_restores_window_and_sends_once(self):
        controller, desktop = self.controller()
        controller.heard('play music')
        controller.heard('play music')
        controller.poll()
        desktop.root.deiconify.assert_called_once()
        desktop._send_text.assert_called_once_with('play music', from_voice=True)

    def test_stale_result_after_pause_does_not_speak(self):
        controller, desktop = self.controller()
        controller.events.put(('brief', 'stale briefing', controller.generation))
        controller.disable(save=False)
        controller.poll()
        desktop.voice.speak.assert_not_called()
        controller.listener.stop.assert_called_once()

    def test_listener_error_restores_window(self):
        controller, desktop = self.controller()
        controller.events.put(('error', 'device lost', controller.generation))
        with patch('jarvis.background_ui.save_preferences'):
            controller.poll()
        self.assertFalse(controller.enabled)
        desktop.root.deiconify.assert_called_once()
        self.assertIn('device lost', desktop._append.call_args.args[1])

    def test_preferences_round_trip_and_corruption(self):
        with tempfile.TemporaryDirectory() as folder, patch('jarvis.background_ui.preference_path', return_value=Path(folder) / 'background.json'):
            data = {'enabled': True, 'model_path': 'my model', 'location': {'name': 'Patna', 'latitude': 25.6, 'longitude': 85.1}}
            save_preferences(data)
            self.assertEqual(load_preferences(), data)
            (Path(folder) / 'background.json').write_text('broken')
            self.assertEqual(load_preferences(), {})


class DesktopCloseTests(unittest.TestCase):
    def desktop_class(self):
        from jarvis.background_ui import install_background_ui
        class Desktop:
            def __init__(self, root):
                pass
            def _close(self):
                self.closed = True
        with patch('jarvis.gui.JarvisDesktop', Desktop):
            install_background_ui()
        return Desktop

    def test_x_hides_only_with_active_listener_and_tray(self):
        cls = self.desktop_class()
        desktop = object.__new__(cls)
        desktop.root = MagicMock()
        desktop.background = MagicMock()
        desktop.background.enabled = True
        desktop.background.listener.running = True
        desktop._exit_completely = MagicMock()
        desktop._close()
        desktop.root.withdraw.assert_called_once()
        desktop._exit_completely.assert_not_called()
        desktop.background.listener.running = False
        desktop._close()
        desktop._exit_completely.assert_called_once()

    def test_full_exit_stops_background_and_browser(self):
        cls = self.desktop_class()
        desktop = object.__new__(cls)
        desktop.background = MagicMock()
        with patch('jarvis.youtube_player.shutdown') as shutdown:
            desktop._exit_completely()
        desktop.background.disable.assert_called_once_with(save=False)
        shutdown.assert_called_once()
        self.assertTrue(desktop.closed)


if __name__ == '__main__':
    unittest.main()
