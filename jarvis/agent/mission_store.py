from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from .mission import Mission, utc_now
from ..config import settings


class MissionStore:
    """Backward-compatible additive V7 mission storage.

    V6 tables are never modified or deleted here. Versioned global migrations are a
    later V7 storage phase; these isolated `v7_*` tables can coexist with V6 data.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS v7_missions (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                goal TEXT NOT NULL,
                status TEXT NOT NULL,
                state_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )''')
            conn.execute('''CREATE INDEX IF NOT EXISTS idx_v7_missions_session
                            ON v7_missions(session_id, updated_at)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS v7_mission_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mission_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )''')
            conn.execute('''CREATE INDEX IF NOT EXISTS idx_v7_mission_events
                            ON v7_mission_events(mission_id, id)''')
            conn.commit()

    def save(self, mission: Mission) -> None:
        mission.touch()
        payload = json.dumps(mission.to_dict(), ensure_ascii=False, default=str)
        with self._lock, self._connect() as conn:
            conn.execute(
                '''INSERT INTO v7_missions(id, session_id, goal, status, state_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     session_id=excluded.session_id,
                     goal=excluded.goal,
                     status=excluded.status,
                     state_json=excluded.state_json,
                     updated_at=excluded.updated_at''',
                (
                    mission.id, mission.session_id, mission.goal, mission.status.value,
                    payload, mission.created_at, mission.updated_at,
                ),
            )
            conn.commit()

    def add_event(self, mission_id: str, event_type: str, payload: dict | None = None) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                'INSERT INTO v7_mission_events(mission_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?)',
                (mission_id, event_type, json.dumps(payload or {}, ensure_ascii=False, default=str), utc_now()),
            )
            conn.commit()

    def get(self, mission_id: str) -> Mission | None:
        with self._lock, self._connect() as conn:
            row = conn.execute('SELECT state_json FROM v7_missions WHERE id=?', (mission_id,)).fetchone()
        if not row:
            return None
        return Mission.from_dict(json.loads(row['state_json']))

    def list_recent(self, limit: int = 20) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                '''SELECT id, session_id, goal, status, created_at, updated_at
                   FROM v7_missions ORDER BY updated_at DESC LIMIT ?''',
                (max(1, min(int(limit), 100)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def events(self, mission_id: str, limit: int = 500) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                '''SELECT event_type, payload_json, created_at FROM v7_mission_events
                   WHERE mission_id=? ORDER BY id ASC LIMIT ?''',
                (mission_id, max(1, min(int(limit), 2000))),
            ).fetchall()
        output = []
        for row in rows:
            try:
                payload = json.loads(row['payload_json'])
            except Exception:
                payload = {}
            output.append({
                'event_type': row['event_type'],
                'payload': payload,
                'created_at': row['created_at'],
            })
        return output
