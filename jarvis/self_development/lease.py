from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from ..config import settings
from ..storage.sqlite_utils import connect_sqlite


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class DevelopmentLease:
    proposal_id: str
    owner_token: str
    operation: str
    acquired_at: str
    expires_at: str

    def as_dict(self) -> dict:
        return asdict(self)


class DevelopmentLeaseStore:
    """SQLite-backed cross-process mutex for one improvement proposal.

    Leases are intentionally short-lived and renewable. A process crash cannot
    permanently lock self-development because expired rows are reclaimable. The
    table is additive and contains no generated code or private prompt content.
    """

    def __init__(self, db_path: Path | None = None, *, default_ttl_seconds: int = 900) -> None:
        self.db_path = Path(db_path or settings.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.default_ttl_seconds = max(30, min(int(default_ttl_seconds), 7200))
        self._init_db()

    def _connect(self):
        return connect_sqlite(self.db_path, timeout=15)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS v75_self_development_leases (
                proposal_id TEXT PRIMARY KEY,
                owner_token TEXT NOT NULL,
                operation TEXT NOT NULL,
                acquired_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )''')
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_v75_dev_lease_expiry '
                'ON v75_self_development_leases(expires_at)'
            )
            conn.commit()

    @staticmethod
    def _row_to_lease(row) -> DevelopmentLease | None:
        if not row:
            return None
        return DevelopmentLease(
            proposal_id=str(row['proposal_id']),
            owner_token=str(row['owner_token']),
            operation=str(row['operation']),
            acquired_at=str(row['acquired_at']),
            expires_at=str(row['expires_at']),
        )

    def cleanup_expired(self) -> int:
        now = _iso(_now())
        with self._connect() as conn:
            cur = conn.execute(
                'DELETE FROM v75_self_development_leases WHERE expires_at<=?',
                (now,),
            )
            conn.commit()
            return int(cur.rowcount)

    def get(self, proposal_id: str) -> DevelopmentLease | None:
        proposal_id = str(proposal_id).strip().upper()
        with self._connect() as conn:
            row = conn.execute(
                'SELECT proposal_id, owner_token, operation, acquired_at, expires_at '
                'FROM v75_self_development_leases WHERE proposal_id=?',
                (proposal_id,),
            ).fetchone()
        lease = self._row_to_lease(row)
        if lease is None:
            return None
        try:
            expiry = datetime.fromisoformat(lease.expires_at)
        except ValueError:
            expiry = _now() - timedelta(seconds=1)
        if expiry <= _now():
            self.cleanup_expired()
            return None
        return lease

    def acquire(
        self,
        proposal_id: str,
        operation: str,
        *,
        owner_token: str | None = None,
        ttl_seconds: int | None = None,
    ) -> DevelopmentLease:
        proposal_id = str(proposal_id).strip().upper()
        operation = str(operation).strip()[:120] or 'self-development'
        if not proposal_id.startswith('IMP-'):
            raise ValueError('Development leases require an IMP-* proposal ID.')
        token = str(owner_token or uuid4().hex)
        ttl = max(30, min(int(ttl_seconds or self.default_ttl_seconds), 7200))
        now_dt = _now()
        now = _iso(now_dt)
        expires = _iso(now_dt + timedelta(seconds=ttl))

        with self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute(
                'DELETE FROM v75_self_development_leases WHERE expires_at<=?',
                (now,),
            )
            row = conn.execute(
                'SELECT owner_token, operation, expires_at FROM v75_self_development_leases '
                'WHERE proposal_id=?',
                (proposal_id,),
            ).fetchone()
            if row and str(row['owner_token']) != token:
                conn.rollback()
                raise RuntimeError(
                    f'Proposal {proposal_id} is busy with operation '
                    f'{row["operation"]} until {row["expires_at"]}.'
                )
            if row:
                conn.execute(
                    'UPDATE v75_self_development_leases '
                    'SET operation=?, expires_at=? WHERE proposal_id=? AND owner_token=?',
                    (operation, expires, proposal_id, token),
                )
                acquired = now
            else:
                conn.execute(
                    'INSERT INTO v75_self_development_leases('
                    'proposal_id, owner_token, operation, acquired_at, expires_at'
                    ') VALUES (?, ?, ?, ?, ?)',
                    (proposal_id, token, operation, now, expires),
                )
                acquired = now
            conn.commit()
        return DevelopmentLease(proposal_id, token, operation, acquired, expires)

    def refresh(
        self,
        proposal_id: str,
        owner_token: str,
        *,
        operation: str | None = None,
        ttl_seconds: int | None = None,
    ) -> DevelopmentLease:
        current = self.get(proposal_id)
        if current is None or current.owner_token != owner_token:
            raise RuntimeError(f'Lease ownership lost for proposal {proposal_id}.')
        return self.acquire(
            proposal_id,
            operation or current.operation,
            owner_token=owner_token,
            ttl_seconds=ttl_seconds,
        )

    def release(self, proposal_id: str, owner_token: str) -> bool:
        proposal_id = str(proposal_id).strip().upper()
        with self._connect() as conn:
            cur = conn.execute(
                'DELETE FROM v75_self_development_leases '
                'WHERE proposal_id=? AND owner_token=?',
                (proposal_id, str(owner_token)),
            )
            conn.commit()
            return bool(cur.rowcount)

    @contextmanager
    def hold(
        self,
        proposal_id: str,
        operation: str,
        *,
        owner_token: str | None = None,
        ttl_seconds: int | None = None,
    ):
        lease = self.acquire(
            proposal_id,
            operation,
            owner_token=owner_token,
            ttl_seconds=ttl_seconds,
        )
        owns_lifetime = owner_token is None
        try:
            yield lease
        finally:
            if owns_lifetime:
                self.release(lease.proposal_id, lease.owner_token)


__all__ = ['DevelopmentLease', 'DevelopmentLeaseStore']
