from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


_SECRET_PATTERNS = (
    re.compile(rb'\bsk-(?:proj-|or-v1-)?[A-Za-z0-9_-]{16,}\b'),
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
)
_PRIVATE_NAMES = {
    '.env',
    'google_token.json',
    'google_credentials.json',
}
_PRIVATE_SUFFIXES = {'.db', '.sqlite', '.sqlite3'}


def validate_bundle(root: Path) -> list[str]:
    findings: list[str] = []
    if not root.is_dir():
        return [f'Bundle directory does not exist: {root}']
    for path in root.rglob('*'):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if path.name.lower() in _PRIVATE_NAMES or path.suffix.lower() in _PRIVATE_SUFFIXES:
            findings.append(f'private runtime file: {relative}')
            continue
        try:
            previous = b''
            with path.open('rb') as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    sample = previous + chunk
                    if any(pattern.search(sample) for pattern in _SECRET_PATTERNS):
                        findings.append(f'secret-like byte sequence: {relative}')
                        break
                    previous = sample[-256:]
        except OSError as exc:
            findings.append(f'unreadable bundle file: {relative} ({type(exc).__name__})')
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('bundle', type=Path)
    args = parser.parse_args(argv)
    findings = validate_bundle(args.bundle.resolve())
    if findings:
        for finding in findings:
            print(f'FAIL: {finding}')
        return 1
    print('PASS: release bundle contains no credential/private-runtime artifacts.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
