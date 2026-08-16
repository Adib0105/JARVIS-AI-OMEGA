import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from jarvis.agent.event_safety import sanitize_tool_event
from jarvis.agent.mission import Mission, MissionStep
from jarvis.agent.mission_store import MissionStore
from jarvis.agent.verification import VerificationEngine


class V75EventPrivacyTests(unittest.TestCase):
    def test_sanitize_tool_event_removes_private_text_and_keeps_hashes(self):
        secret = 'sk-or-v1-abcdefghijklmnopqrstuvwxyz1234567890'
        body = 'Private email body with customer details.'
        event = sanitize_tool_event({
            'name': 'gmail_send',
            'args': {'to': 'person@example.com', 'body': body, 'api_key': secret},
            'output': json.dumps({'ok': True, 'result': {'id': 'msg-1', 'body': body, 'token': secret}}),
            'audit_id': 7,
        })
        serialized = json.dumps(event, ensure_ascii=False)
        self.assertNotIn(secret, serialized)
        self.assertNotIn(body, serialized)
        self.assertIn('PRIVATE_TEXT', serialized)
        self.assertEqual(len(event['arguments_hash']), 64)
        self.assertEqual(event['audit_id'], 7)

    def test_write_verification_uses_hash_hint_without_raw_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'generated.py'
            content = 'print("privacy-safe verification")\n'
            path.write_text(content, encoding='utf-8')
            event = {
                'name': 'write_local_text_file',
                'args': {'file_path': str(path), 'content': '[PRIVATE_TEXT:35 chars]'},
                'output': json.dumps({'ok': True, 'result': {'path': str(path)}}),
                'verification_hints': {
                    'content_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
                    'content_characters': len(content),
                },
            }
            check = VerificationEngine().verify_tool_event(event)
            self.assertTrue(check['verified'])
            self.assertEqual(check['status'], 'VERIFIED')
            self.assertTrue(check['evidence']['content_hash_match'])
            self.assertNotIn(content, json.dumps(check, ensure_ascii=False))

    def test_mission_store_can_persist_sanitized_tool_event_without_raw_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'mission.db'
            store = MissionStore(db)
            body = 'Highly private email text that must not be persisted in tool events.'
            safe_event = sanitize_tool_event({
                'name': 'gmail_send',
                'args': {'to': 'person@example.com', 'body': body},
                'output': json.dumps({'ok': True, 'result': {'id': 'msg-2', 'body': body}}),
            })
            mission = Mission(goal='Send approved message', session_id='S1')
            mission.plan = [MissionStep(index=1, description='send message', tool_events=[safe_event])]
            store.save(mission)
            with store._connect() as conn:
                raw = conn.execute('SELECT state_json FROM v7_missions WHERE id=?', (mission.id,)).fetchone()[0]
            self.assertNotIn(body, raw)
            self.assertIn('PRIVATE_TEXT', raw)


if __name__ == '__main__':
    unittest.main()
