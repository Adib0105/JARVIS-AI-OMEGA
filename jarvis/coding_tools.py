from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .local_files import LocalFiles, SAFE_EXTENSIONS


class CodingWorkspace:
    def __init__(self, files: LocalFiles | None = None):
        self.files = files or LocalFiles()

    def _safe(self, raw: str, must_exist: bool = True) -> Path:
        path = Path(raw).expanduser().resolve()
        if not self.files._is_inside_root(path):
            raise PermissionError('Path is outside approved roots.')
        if self.files._looks_secret(path):
            raise PermissionError('Secret-like path is blocked.')
        if must_exist and not path.exists():
            raise FileNotFoundError(path)
        return path

    def tree(self, folder: str, max_items: int = 200) -> list[str]:
        root = self._safe(folder)
        if not root.is_dir():
            raise NotADirectoryError(root)
        out: list[str] = []
        limit = max(10, min(int(max_items), 500))
        for path in root.rglob('*'):
            if len(out) >= limit:
                break
            if self.files._looks_secret(path):
                continue
            try:
                rel = path.relative_to(root)
            except ValueError:
                continue
            if any(part in {'.git', '.venv', 'venv', '__pycache__', 'node_modules'} for part in rel.parts):
                continue
            out.append(str(rel) + ('/' if path.is_dir() else ''))
        return out

    def write_text(self, file_path: str, content: str) -> dict:
        path = self._safe(file_path, must_exist=False)
        if path.suffix.lower() not in SAFE_EXTENSIONS:
            raise PermissionError(f'Unsupported writable file type: {path.suffix or "no extension"}')
        if len(content) > 200000:
            raise ValueError('Refusing to write more than 200,000 characters in one action.')
        path.parent.mkdir(parents=True, exist_ok=True)
        backup = None
        if path.exists():
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            backup = path.with_name(f'{path.name}.jarvis-backup-{stamp}')
            shutil.copy2(path, backup)
        path.write_text(content, encoding='utf-8')
        return {'path': str(path), 'characters': len(content), 'backup': str(backup) if backup else None}

    def run_unit_tests(self, project_dir: str, timeout: int = 120) -> dict:
        root = self._safe(project_dir)
        if not root.is_dir():
            raise NotADirectoryError(root)
        tests = root / 'tests'
        if not tests.is_dir():
            raise FileNotFoundError('A tests/ folder is required for this allowlisted test action.')
        proc = subprocess.run(
            [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=max(10, min(int(timeout), 300)),
            shell=False,
        )
        output = (proc.stdout + '\n' + proc.stderr).strip()
        return {'returncode': proc.returncode, 'output': output[-30000:]}
