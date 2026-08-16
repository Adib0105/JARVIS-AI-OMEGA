from __future__ import annotations

import subprocess
from pathlib import Path

from .local_files import LocalFiles


class GitWorkspace:
    def __init__(self, files: LocalFiles | None = None):
        self.files = files or LocalFiles()

    def _repo(self, folder: str) -> Path:
        root = Path(folder).expanduser().resolve()
        if not self.files._is_inside_root(root):
            raise PermissionError('Git repository is outside approved roots.')
        if not root.is_dir():
            raise NotADirectoryError(root)
        if not (root / '.git').exists():
            raise ValueError('Selected folder is not a Git working tree with a .git directory.')
        return root

    @staticmethod
    def _run(root: Path, args: list[str], timeout: int = 30) -> str:
        proc = subprocess.run(
            ['git', *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=max(5, min(int(timeout), 60)),
            shell=False,
        )
        output = (proc.stdout + ('\n' + proc.stderr if proc.stderr else '')).strip()
        if proc.returncode != 0:
            raise RuntimeError(output[-5000:] or f'git exited with code {proc.returncode}')
        return output[-30000:]

    def status(self, folder: str) -> dict:
        root = self._repo(folder)
        branch = self._run(root, ['branch', '--show-current'])
        status = self._run(root, ['status', '--short'])
        return {'repository': str(root), 'branch': branch, 'status': status or 'clean'}

    def diff(self, folder: str, staged: bool = False) -> dict:
        root = self._repo(folder)
        args = ['diff', '--no-ext-diff', '--unified=3']
        if staged:
            args.insert(1, '--cached')
        return {'repository': str(root), 'staged': bool(staged), 'diff': self._run(root, args) or 'no diff'}

    def log(self, folder: str, count: int = 10) -> dict:
        root = self._repo(folder)
        count = max(1, min(int(count), 30))
        output = self._run(root, ['log', f'-{count}', '--oneline', '--decorate', '--no-color'])
        return {'repository': str(root), 'log': output}
