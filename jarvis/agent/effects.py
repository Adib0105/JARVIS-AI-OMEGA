"""Durable action intents and process ownership. Uncertain actions are never replayed."""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path

import psutil
from ..storage.sqlite_utils import connect_sqlite


class EffectLedger:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.owner = uuid.uuid4().hex
        self.pid = os.getpid()
        try:
            self.process_start = psutil.Process(self.pid).create_time()
        except psutil.NoSuchProcess:
            # PID namespaces may expose host /proc with container os.getpid().
            # Resolve the OS-provided self link, never guess another process.
            if os.name != 'posix':
                raise
            self.pid = int(Path('/proc/self').resolve().name)
            self.process_start = psutil.Process(self.pid).create_time()
        with connect_sqlite(self.path) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS action_intents (
                    id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, tool TEXT NOT NULL,
                    owner TEXT NOT NULL, pid INTEGER NOT NULL, process_start REAL NOT NULL,
                    mission TEXT, state TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
                    resolution TEXT
                );
                CREATE INDEX IF NOT EXISTS action_intent_fingerprint ON action_intents(fingerprint,state);
                CREATE TABLE IF NOT EXISTS mission_owners (
                    slot TEXT PRIMARY KEY, owner TEXT NOT NULL, pid INTEGER NOT NULL,
                    process_start REAL NOT NULL, mission TEXT NOT NULL, expires REAL NOT NULL
                );
            ''')

    @staticmethod
    def _alive(row):
        try:
            return abs(psutil.Process(row['pid']).create_time() - row['process_start']) < .01
        except psutil.NoSuchProcess:
            return False
        except psutil.Error:
            return True  # uncertainty must not steal a live worker's ownership

    def claim_mission(self, mission, seconds=240):
        with connect_sqlite(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM mission_owners WHERE slot='assistant'").fetchone()
            if row and self._alive(row):
                raise RuntimeError('MISSION_BUSY: another process owns this profile mission.')
            if row:
                db.execute("UPDATE action_intents SET state='UNCERTAIN',updated=? WHERE mission=? AND state='INTENT'", (time.time(), row['mission']))
            db.execute("INSERT OR REPLACE INTO mission_owners VALUES('assistant',?,?,?,?,?)",
                       (self.owner, self.pid, self.process_start, mission, time.time() + seconds))

    def release_mission(self):
        with connect_sqlite(self.path) as db:
            db.execute('DELETE FROM mission_owners WHERE owner=?', (self.owner,))

    def check_owner(self):
        with connect_sqlite(self.path) as db:
            row = db.execute('SELECT expires FROM mission_owners WHERE owner=?', (self.owner,)).fetchone()
        if row is None or row['expires'] <= time.time():
            raise RuntimeError('Mission ownership expired; no further action may start.')

    def begin(self, tool, args, mission=None):
        # No raw private arguments, email bodies or credentials are persisted.
        encoded = json.dumps([tool, args], sort_keys=True, ensure_ascii=False, default=str).encode()
        fingerprint = hashlib.sha256(encoded).hexdigest()
        identity = uuid.uuid4().hex
        with connect_sqlite(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute("SELECT * FROM action_intents WHERE fingerprint=? AND state IN ('INTENT','UNCERTAIN')", (fingerprint,)).fetchall()
            for row in rows:
                if row['state'] == 'INTENT' and not self._alive(row):
                    db.execute("UPDATE action_intents SET state='UNCERTAIN',updated=? WHERE id=?", (time.time(), row['id']))
                # Raising after the transaction below retains the reconciliation.
            if not rows:
                db.execute("INSERT INTO action_intents VALUES(?,?,?,?,?,?,?,'INTENT',?,?,NULL)",
                           (identity, fingerprint, tool, self.owner, self.pid, self.process_start, mission, time.time(), time.time()))
        if rows:
            raise RuntimeError('UNCERTAIN_PRIOR_ACTION: inspect action ' + rows[0]['id'] + ' before repeating it. It may already have happened.')
        return identity

    def finish(self, identity, status):
        if status not in {'ACKNOWLEDGED', 'FAILED', 'DENIED', 'UNCERTAIN'}:
            raise ValueError('Invalid effect state.')
        with connect_sqlite(self.path) as db:
            db.execute("UPDATE action_intents SET state=?,updated=? WHERE id=? AND owner=? AND state='INTENT'",
                       (status, time.time(), identity, self.owner))

    def unresolved(self):
        with connect_sqlite(self.path) as db:
            return [dict(row) for row in db.execute("SELECT id,tool,state,created,mission FROM action_intents WHERE state IN ('INTENT','UNCERTAIN') ORDER BY created LIMIT 100")]

    def resolve(self, identity, resolution):
        if resolution not in {'observed_applied', 'observed_not_applied'}:
            raise ValueError('Inspect the real postcondition before selecting a resolution.')
        with connect_sqlite(self.path) as db:
            row = db.execute('SELECT * FROM action_intents WHERE id=?', (identity,)).fetchone()
            if not row or (row['state'] == 'INTENT' and self._alive(row)):
                raise RuntimeError('Action is missing or still owned by a live process.')
            db.execute("UPDATE action_intents SET state='RESOLVED',resolution=?,updated=? WHERE id=?", (resolution, time.time(), identity))
