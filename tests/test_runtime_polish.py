import json
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from dotenv import dotenv_values
from jarvis.background_ui import BackgroundController, load_preferences
from jarvis.daily_briefing import find_locations, weather_report
from jarvis.fast_commands import execute_fast_command
from jarvis.settings_ui import update_env_values
from jarvis import youtube_player


class SettingsRecoveryTests(unittest.TestCase):
    def test_malformed_background_preferences_do_not_enable_mic(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'prefs.json'
            for data in [{'enabled': 'false', 'model_path': 12, 'location': []}, {'enabled': 1, 'location': {'name': 'bad', 'latitude': 999, 'longitude': 0}}]:
                path.write_text(json.dumps(data))
                with patch('jarvis.background_ui.preference_path', return_value=path):
                    self.assertEqual(load_preferences(), {'enabled': False})

    def test_env_literal_values_and_other_settings_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'
            path.write_text('export WAKE_WORD=old\nOTHER_SETTING=untouched\n')
            value = "hey # jarvis's \\ model"
            with patch('jarvis.settings_ui._env_path', return_value=path):
                update_env_values({'WAKE_WORD': value, 'NOT_ALLOWLISTED': 'ignored'})
            data = dotenv_values(path)
            self.assertEqual(data['WAKE_WORD'], value)
            self.assertEqual(data['OTHER_SETTING'], 'untouched')
            self.assertNotIn('NOT_ALLOWLISTED', data)

    def test_multiline_settings_rejected_without_writing(self):
        with patch('jarvis.settings_ui._read_env_lines') as read:
            for value in ['jarvis\nREQUIRE_LOCAL_APPROVAL=false', 'jarvis\r', 'bad\0value']:
                with self.assertRaises(ValueError):
                    update_env_values({'WAKE_WORD': value})
            read.assert_not_called()

    def test_failed_atomic_replace_keeps_original_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'
            path.write_text('WAKE_WORD=original\n')
            with patch('jarvis.settings_ui._env_path', return_value=path), patch.object(Path, 'replace', side_effect=PermissionError):
                with self.assertRaises(PermissionError):
                    update_env_values({'WAKE_WORD': 'changed'})
            self.assertEqual(path.read_text(), 'WAKE_WORD=original\n')
            self.assertEqual(list(Path(folder).iterdir()), [path])


class BackgroundRecoveryTests(unittest.TestCase):
    def controller(self):
        d = MagicMock()
        d._closing = False
        d.busy = False
        d.voice.state = 'idle'
        with patch('jarvis.background_ui.load_preferences', return_value={}):
            c = BackgroundController(d)
        c.enabled = True
        c.listener = MagicMock()
        d.root.after.reset_mock()
        return c, d

    def test_save_failure_on_pause_does_not_hide_window_or_stop_polling(self):
        c, d = self.controller()
        c.events.put(('pause', None, 0))
        with patch('jarvis.background_ui.save_preferences', side_effect=PermissionError):
            c.poll()
        self.assertFalse(c.enabled)
        c.listener.stop.assert_called_once()
        d.root.deiconify.assert_called_once()
        d.root.after.assert_called_once_with(100, c.poll)
        self.assertIn('could not be saved', d._append.call_args.args[1])

    def test_tray_stop_exception_still_restores_window(self):
        c, d = self.controller()
        c.tray = MagicMock()
        c.tray.stop.side_effect = RuntimeError
        c.disable(save=False)
        self.assertFalse(c.enabled)
        self.assertIsNone(c.tray)
        d.root.deiconify.assert_called_once()

    def test_queued_wake_does_not_interrupt_new_typed_task(self):
        c, d = self.controller()
        c.heard('open chrome')
        d.busy = True
        c.poll()
        self.assertFalse(c.pending)
        d._send_text.assert_not_called()

    def test_followup_failure_releases_pending_state(self):
        c, d = self.controller()
        c.pending = True
        c.events.put(('followup', {'text': '', 'error': 'bad device', 'listener_error': ''}, c.generation))
        c.poll()
        self.assertFalse(c.pending)
        self.assertIn('Command sun nahi', d.voice.speak.call_args.args[0])

    def test_callback_error_does_not_kill_poll_loop(self):
        c, d = self.controller()
        c.events.put(('show', None, 0))
        d.root.deiconify.side_effect = RuntimeError
        c.poll()
        d.root.after.assert_called_once_with(100, c.poll)


class ResultHonestyTests(unittest.TestCase):
    def test_denied_app_command_is_terminal(self):
        j = SimpleNamespace(tools=MagicMock())
        for payload in [{'ok': False, 'error': 'permission denied'}, None, 'not json', {'ok': 'true'}]:
            j.tools.call.return_value = json.dumps(payload)
            result = execute_fast_command(j, 'open chrome')
            self.assertIsNotNone(result)
            self.assertNotIn('Done.', result)

    def test_malformed_youtube_result_is_not_a_crash(self):
        j = SimpleNamespace(tools=MagicMock())
        j.tools.call.return_value = json.dumps({'ok': True, 'result': None})
        self.assertIn('verify nahi', execute_fast_command(j, 'play song on youtube'))

    def test_rejected_browser_open_is_failure(self):
        from jarvis.system_tools import open_url
        from jarvis.automation import browser_search
        with patch('webbrowser.open', return_value=False):
            with self.assertRaises(RuntimeError):
                open_url('https://example.com')
            with self.assertRaises(RuntimeError):
                browser_search('song', 'youtube')

    def test_malformed_city_rows_filtered(self):
        valid = {'name': 'Patna', 'latitude': 25.6, 'longitude': 85.1}
        with patch('jarvis.daily_briefing._get_json', return_value={'results': [None, {}, {'name': 'bad'}, valid]}):
            self.assertEqual(find_locations('Patna'), [valid])
        with patch('jarvis.daily_briefing._get_json', return_value={'results': None}):
            self.assertEqual(find_locations('Patna'), [])

    def test_null_weather_sections_do_not_erase_other_readings(self):
        with patch('jarvis.daily_briefing._get_json', return_value={'current': {'temperature_2m': 24}, 'daily': None}):
            result = weather_report({'name': 'Patna', 'latitude': 25.6, 'longitude': 85.1})
        self.assertIn('24 degree', result)
        self.assertIn('chance abhi available nahi', result)


class YoutubeWorkerRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.patcher = patch.multiple(youtube_player, _jobs=queue.Queue(), _lock=threading.Lock(), _thread=None, _active_cancel=None, _stopping=threading.Event())
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_startup_failure_notifies_waiters_and_retires_worker(self):
        reply, cancel = queue.Queue(), threading.Event()
        youtube_player._jobs.put(('song', reply, cancel))
        youtube_player._thread = threading.current_thread()
        with patch.dict('sys.modules', {'playwright.sync_api': None}):
            youtube_player._worker()
        self.assertFalse(reply.get_nowait()['playing'])
        self.assertTrue(cancel.is_set())
        self.assertIsNone(youtube_player._thread)
        self.assertTrue(youtube_player._jobs.empty())

    def test_shutdown_cancels_active_and_notifies_queued_callers(self):
        replies = []
        for _ in range(2):
            reply, cancel = queue.Queue(), threading.Event()
            youtube_player._jobs.put(('song', reply, cancel))
            replies.append((reply, cancel))
        youtube_player._active_cancel = threading.Event()
        youtube_player.shutdown()
        self.assertTrue(youtube_player._active_cancel.is_set())
        for reply, cancel in replies:
            self.assertFalse(reply.get_nowait()['playing'])
            self.assertTrue(cancel.is_set())

    def test_worker_failure_allows_a_new_submission(self):
        with patch('jarvis.config.settings', SimpleNamespace(enable_desktop_automation=True)), patch.dict('sys.modules', {'playwright.sync_api': None}):
            for _ in range(2):
                result = youtube_player.play_first_video('song')
                self.assertFalse(result['playing'])
        # The worker clears its reference under the submission lock before returning.
        with youtube_player._lock:
            self.assertIsNone(youtube_player._thread)


class ApprovalShutdownTests(unittest.TestCase):
    def test_closing_desktop_denies_without_scheduling_dialog(self):
        from jarvis.gui import JarvisDesktop
        d = SimpleNamespace(_closing=True, root=MagicMock())
        self.assertFalse(JarvisDesktop._confirm_tool(d, 'open_app', {}))
        d.root.after.assert_not_called()

    def test_shutdown_releases_worker_waiting_for_dialog(self):
        from jarvis.gui import JarvisDesktop
        d = SimpleNamespace(_closing=False, root=MagicMock())
        scheduled = threading.Event()
        d.root.after.side_effect = lambda *_: scheduled.set()
        result = []
        worker = threading.Thread(target=lambda: result.append(JarvisDesktop._confirm_tool(d, 'open_app', {})), daemon=True)
        worker.start()
        self.assertTrue(scheduled.wait(2))
        d._closing = True
        worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result, [False])


class AdditionalRecoveryTests(unittest.TestCase):
    def guarded_confirm(self):
        from jarvis.runtime_guard import _install_security_gui_hooks
        class Desktop:
            def _build_right_panel(self, parent):
                pass
        _install_security_gui_hooks(SimpleNamespace(JarvisDesktop=Desktop))
        return Desktop._confirm_tool

    def test_v7_dialog_failure_denies_without_name_error(self):
        import tkinter as tk
        confirm = self.guarded_confirm()
        d = SimpleNamespace(_closing=False, root=MagicMock())
        with patch('tkinter.messagebox.askyesno', side_effect=tk.TclError):
            self.assertEqual(confirm(d, 'open_app', {}), 'deny')

    def test_v7_shutdown_releases_pending_permission(self):
        confirm = self.guarded_confirm()
        d = SimpleNamespace(_closing=False, root=MagicMock())
        scheduled = threading.Event()
        d.root.after.side_effect = lambda *_: scheduled.set()
        answers = []
        worker = threading.Thread(target=lambda: answers.append(confirm(d, 'open_app', {})), daemon=True)
        worker.start()
        self.assertTrue(scheduled.wait(2))
        d._closing = True
        worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(answers, ['deny'])

    def test_full_exit_survives_cleanup_errors(self):
        from jarvis.background_ui import install_background_ui
        class Desktop:
            def __init__(self, root):
                pass
            def _close(self):
                self.closed = True
        with patch('jarvis.gui.JarvisDesktop', Desktop):
            install_background_ui()
        d = object.__new__(Desktop)
        d.background = MagicMock()
        d.background.disable.side_effect = RuntimeError('tray')
        with patch('jarvis.youtube_player.shutdown', side_effect=RuntimeError('browser')):
            with self.assertRaises(RuntimeError):
                d._exit_completely()
        self.assertTrue(d.closed)

    def test_failed_voice_returns_idle_without_shutdown(self):
        from jarvis.voice import VoiceOutput
        idle, failed = threading.Event(), threading.Event()
        def state(value):
            if value == 'error':
                failed.set()
            if value == 'idle':
                idle.set()
        with patch('jarvis.voice.settings', SimpleNamespace(enable_voice_output=True, db_path=Path('/unused/test.db'))), patch('jarvis.voice.load_profile', return_value='configured'), patch.object(VoiceOutput, '_play_text', return_value='failed'):
            voice = VoiceOutput(state)
            try:
                voice.speak('hello')
                self.assertTrue(failed.wait(2))
                self.assertTrue(idle.wait(2))
                self.assertEqual(voice.state, 'idle')
                self.assertFalse(voice._shutdown)
            finally:
                voice.shutdown()

    def test_playback_check_requires_progress_and_selected_video(self):
        page = MagicMock()
        first = page.locator.return_value.first
        first.get_attribute.return_value = '/watch?v=selected'
        first.evaluate.return_value = 5.0
        page.url = 'https://www.youtube.com/watch?v=different'
        with patch.object(youtube_player, '_stopping', threading.Event()):
            with self.assertRaisesRegex(RuntimeError, 'selected video'):
                youtube_player.play_on_page(page, 'song')
        expression = page.wait_for_function.call_args.args[0]
        self.assertIn('startedAt + 0.15', expression)
        self.assertEqual(page.wait_for_function.call_args.kwargs['arg'], 5.0)


if __name__ == '__main__':
    unittest.main()
