from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from .mission import Mission, utc_now
from ..config import settings
from ..storage.sqlite_utils import connect_sqlite


class ConcurrentMissionUpdateError(RuntimeError):
    """A stale mission snapshot attempted to overwrite newer persisted state."""


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
        return connect_sqlite(self.db_path, timeout=10)

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS v7_missions (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                goal TEXT NOT NULL,
                status TEXT NOT NULL,
                state_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 0
            )''')
            columns = {
                str(row['name']) for row in conn.execute('PRAGMA table_info(v7_missions)').fetchall()
            }
            if 'revision' not in columns:
                conn.execute(
                    'ALTER TABLE v7_missions ADD COLUMN revision INTEGER NOT NULL DEFAULT 0'
                )
            conn.execute("UPDATE v7_missions SET status='CREATED' WHERE status='IDLE'")
            conn.execute("UPDATE v7_missions SET status='PLANNING' WHERE status='UNDERSTANDING'")
            conn.execute(
                "UPDATE v7_missions SET status='AWAITING_PERMISSION' "
                "WHERE status='WAITING_FOR_PERMISSION'"
            )
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

    @staticmethod
    def _state_payload(mission: Mission) -> str:
        return json.dumps(mission.to_dict(), ensure_ascii=False, default=str)

    def _save_in_transaction(self, conn: sqlite3.Connection, mission: Mission) -> None:
        mission.touch()
        existing = conn.execute(
            'SELECT revision FROM v7_missions WHERE id=?', (mission.id,)
        ).fetchone()
        if existing is None:
            mission.revision = 0
            conn.execute(
                '''INSERT INTO v7_missions(
                       id, session_id, goal, status, state_json, created_at, updated_at, revision
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    mission.id, mission.session_id, mission.goal, mission.status.value,
                    self._state_payload(mission), mission.created_at, mission.updated_at,
                    mission.revision,
                ),
            )
            return

        persisted_revision = int(existing['revision'])
        if mission.revision != persisted_revision:
            raise ConcurrentMissionUpdateError(
                f'Mission {mission.id} revision {mission.revision} is stale; '
                f'current revision is {persisted_revision}.'
            )
        previous_revision = mission.revision
        mission.revision = previous_revision + 1
        cursor = conn.execute(
            '''UPDATE v7_missions SET
                   session_id=?, goal=?, status=?, state_json=?, updated_at=?, revision=?
               WHERE id=? AND revision=?''',
            (
                mission.session_id, mission.goal, mission.status.value,
                self._state_payload(mission), mission.updated_at, mission.revision,
                mission.id, previous_revision,
            ),
        )
        if cursor.rowcount != 1:
            mission.revision = previous_revision
            raise ConcurrentMissionUpdateError(
                f'Mission {mission.id} changed during the update; retry from a fresh snapshot.'
            )

    def save(self, mission: Mission) -> None:
        previous_revision = mission.revision
        try:
            with self._lock, self._connect() as conn:
                conn.execute('BEGIN IMMEDIATE')
                self._save_in_transaction(conn, mission)
                conn.commit()
        except Exception:
            mission.revision = previous_revision
            raise

    def save_with_event(
        self,
        mission: Mission,
        event_type: str,
        payload: dict | None = None,
    ) -> None:
        """Persist mission state and its audit event in one SQLite transaction."""
        previous_revision = mission.revision
        try:
            with self._lock, self._connect() as conn:
                conn.execute('BEGIN IMMEDIATE')
                self._save_in_transaction(conn, mission)
                conn.execute(
                    'INSERT INTO v7_mission_events(mission_id, event_type, payload_json, created_at) '
                    'VALUES (?, ?, ?, ?)',
                    (
                        mission.id,
                        event_type,
                        json.dumps(payload or {}, ensure_ascii=False, default=str),
                        utc_now(),
                    ),
                )
                conn.commit()
        except Exception:
            mission.revision = previous_revision
            raise

    def add_event(self, mission_id: str, event_type: str, payload: dict | None = None) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                'INSERT INTO v7_mission_events(mission_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?)',
                (mission_id, event_type, json.dumps(payload or {}, ensure_ascii=False, default=str), utc_now()),
            )
            conn.commit()

    def get(self, mission_id: str) -> Mission | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                'SELECT state_json, revision FROM v7_missions WHERE id=?', (mission_id,)
            ).fetchone()
        if not row:
            return None
        mission = Mission.from_dict(json.loads(row['state_json']))
        mission.revision = int(row['revision'])
        return mission

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
