from __future__ import annotations

import sqlite3
from pathlib import Path


class ClosingConnection(sqlite3.Connection):
    """SQLite connection that closes after a `with` block.

    Python's built-in sqlite3.Connection context manager commits/rolls back but
    does not close the connection. That is easy to miss and can leave temporary
    databases locked on Windows. V7 uses this subclass so existing
    `with self._connect() as conn:` call sites keep their transaction semantics
    while also releasing the file handle deterministically.
    """

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect_sqlite(db_path: str | Path, *, timeout: float = 10.0) -> sqlite3.Connection:
    conn = sqlite3.connect(
        str(db_path),
        timeout=float(timeout),
        factory=ClosingConnection,
    )
    conn.row_factory = sqlite3.Row
    return conn
