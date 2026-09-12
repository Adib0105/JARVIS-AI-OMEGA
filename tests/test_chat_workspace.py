import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from jarvis.memory import MemoryStore
from jarvis.core_v7 import JarvisOmega
from jarvis.workspace_commands import apply_command, search_commands
from jarvis.chat_workspace_ui import resume_chat


class ChatWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.memory = MemoryStore(Path(self.directory.name) / 'memory.db')
        self.first = self.memory.new_session('SQL practice')
        self.second = self.memory.new_session('Python')
        self.memory.add_message(self.first, 'user', 'Sales rose 20% in July')
        self.memory.add_message(self.second, 'assistant', 'Use customer_id here')

    def test_title_and_content_search(self):
        self.assertEqual(self.memory.find_sessions('SQL')[0]['id'], self.first)
        self.assertEqual(self.memory.find_sessions('july')[0]['id'], self.first)
        self.assertEqual(self.memory.find_sessions('customer_id')[0]['message_count'], 1)

    def test_search_wildcards_are_literal(self):
        self.assertEqual([r['id'] for r in self.memory.find_sessions('%')], [self.first])
        self.assertEqual([r['id'] for r in self.memory.find_sessions('_')], [self.second])
        self.assertEqual(self.memory.find_sessions("' OR 1=1 --"), [])

    def test_rename_preserves_messages_and_is_persistent(self):
        self.memory.rename_session(self.first, 'Analytics revision')
        reopened = MemoryStore(self.memory.db_path)
        self.assertEqual(reopened.get_session(self.first)['title'], 'Analytics revision')
        self.assertEqual(reopened.message_count(self.first), 1)

    def test_invalid_rename_leaves_title_intact(self):
        for title in ['', '  ', 'x' * 101]:
            with self.assertRaises(ValueError):
                self.memory.rename_session(self.first, title)
        self.assertEqual(self.memory.get_session(self.first)['title'], 'SQL practice')
        with self.assertRaises(ValueError):
            self.memory.rename_session('missing', 'Valid title')

    def test_resume_retains_history_and_clears_old_mission_marker(self):
        core = SimpleNamespace(memory=self.memory, session_id=self.second, last_plan=['old'], last_mission_id='old')
        self.assertEqual(JarvisOmega.resume_session(core, self.first), self.first)
        self.assertEqual(self.memory.recent_messages(core.session_id)[0][1], 'Sales rose 20% in July')
        self.assertEqual(core.last_plan, [])
        self.assertIsNone(core.last_mission_id)

    def test_invalid_resume_does_not_change_current_chat(self):
        core = SimpleNamespace(memory=self.memory, session_id=self.first)
        with self.assertRaises(ValueError):
            JarvisOmega.resume_session(core, 'missing')
        self.assertEqual(core.session_id, self.first)

    def test_library_limit(self):
        self.assertEqual(len(self.memory.find_sessions('', 1)), 1)

    def test_prompt_starter_never_sends_or_calls_tools(self):
        desktop = MagicMock()
        desktop.busy = False
        desktop.entry.get.return_value = ''
        self.assertFalse(apply_command(desktop, 'sql'))
        self.assertIn('Hinglish', desktop.entry.insert.call_args.args[1])
        desktop._send_text.assert_not_called()
        desktop.jarvis.tools.call.assert_not_called()

    def test_prompt_starter_preserves_existing_draft(self):
        desktop = MagicMock()
        desktop.busy = False
        desktop.entry.get.return_value = 'my draft'
        with self.assertRaises(ValueError):
            apply_command(desktop, 'python')
        desktop.entry.insert.assert_not_called()

    def test_busy_and_unknown_commands_do_not_execute(self):
        desktop = MagicMock()
        desktop.busy = True
        with self.assertRaises(RuntimeError):
            apply_command(desktop, 'new')
        with self.assertRaises(ValueError):
            apply_command(desktop, 'run arbitrary shell')
        desktop._new_chat.assert_not_called()

    def test_command_search(self):
        self.assertEqual(search_commands('SQL')[0].id, 'sql')
        self.assertEqual(search_commands('purani')[0].id, 'chats')
        self.assertEqual(search_commands('no such command xyz'), [])

    def test_resume_ui_stops_audio_and_does_not_respeak_history(self):
        desktop = MagicMock()
        desktop.busy = False
        desktop.jarvis.memory = self.memory
        resume_chat(desktop, self.first)
        desktop.jarvis.resume_session.assert_called_once_with(self.first)
        desktop.voice.stop.assert_called_once()
        desktop.wake_listener.stop.assert_called_once()
        desktop.voice.speak.assert_not_called()
        self.assertFalse(desktop._live_voice_enabled)

    def test_busy_resume_leaves_ui_intact(self):
        desktop = MagicMock()
        desktop.busy = True
        with self.assertRaises(RuntimeError):
            resume_chat(desktop, self.first)
        desktop.chat.delete.assert_not_called()
