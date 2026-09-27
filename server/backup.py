"""Consistent SQLite snapshot: python -m server.backup --database PATH --output PATH."""
import argparse
import os
from pathlib import Path
import sqlite3
import tempfile


def backup(database, output):
    database, output = Path(database).resolve(), Path(output).resolve()
    if not database.is_file() or database == output or output.exists():
        raise ValueError('Use an existing database and a new, different backup path.')
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=output.parent, prefix='.backup-')
    os.close(fd)
    staging = Path(name)
    source = destination = None
    try:
        source = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=5)
        destination = sqlite3.connect(staging)
        import time
        deadline = time.monotonic() + 30
        def progress(*_):
            if time.monotonic() >= deadline:
                raise TimeoutError('Account backup exceeded its time budget.')
        source.backup(destination, pages=128, progress=progress, sleep=.05)
        if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Backup integrity check failed.')
        destination.close(); destination = None
        source.close(); source = None
        staging.chmod(0o600)
        # Hard-link publication is exclusive: never overwrite an existing backup.
        os.link(staging, output)
    finally:
        if destination is not None:
            destination.close()
        if source is not None:
            source.close()
        staging.unlink(missing_ok=True)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(backup(args.database, args.output))


if __name__ == '__main__':
    main()
