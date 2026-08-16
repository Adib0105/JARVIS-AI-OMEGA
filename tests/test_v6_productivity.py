import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jarvis.memory import MemoryStore


class V6ProductivityTests(unittest.TestCase):
    def test_todo_reminder_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / 'v6.db')
            todo = store.add_todo('Ship V6')
            self.assertEqual(store.list_todos()[0]['title'], 'Ship V6')
            self.assertTrue(store.complete_todo(todo['id'])['completed'])
            self.assertEqual(store.list_todos(), [])

            due = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
            reminder = store.add_reminder('Test reminder', due)
            due_rows = store.due_reminders()
            self.assertEqual(due_rows[0]['id'], reminder['id'])
            store.mark_reminder_done(reminder['id'])
            self.assertEqual(store.due_reminders(), [])

            sid = store.new_session('history')
            store.add_message(sid, 'user', 'unique-v6-history-token')
            hits = store.search_messages('unique-v6-history-token')
            self.assertEqual(hits[0]['session_id'], sid)

    def test_stats_include_v6_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp) / 'stats.db')
            store.add_todo('one')
            future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            store.add_reminder('later', future)
            stats = store.stats()
            self.assertEqual(stats['open_todos'], 1)
            self.assertEqual(stats['pending_reminders'], 1)


if __name__ == '__main__':
    unittest.main()
