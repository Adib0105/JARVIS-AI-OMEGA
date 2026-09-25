from __future__ import annotations

from pathlib import Path
import os
import stat

from .config import settings

SAFE_EXTENSIONS = {
    '.txt', '.md', '.py', '.js', '.ts', '.tsx', '.jsx', '.json', '.csv', '.log', '.ini', '.cfg',
    '.yaml', '.yml', '.toml', '.html', '.css', '.sql', '.xml', '.java', '.c', '.cpp', '.h', '.hpp',
    '.ps1', '.bat', '.sh', '.go', '.rs'
}
BLOCKED_PARTS = {
    '.ssh', '.gnupg', '.aws', '.azure', '.kube', 'credentials', 'secrets', 'wallet', 'password',
    'passwd', 'private_key', 'id_rsa', 'id_ed25519', '.env', 'token'
}


class LocalFiles:
    def __init__(self):
        self.roots = tuple(p for p in settings.allowed_file_roots if p.exists())

    def roots_info(self) -> list[str]:
        return [str(p) for p in self.roots]

    def _is_inside_root(self, path: Path) -> bool:
        resolved = path.expanduser().resolve()
        for root in self.roots:
            try:
                # Resolve both sides: Windows temp/known folders may have aliases or
                # different casing while still referring to the same approved folder.
                resolved.relative_to(root.expanduser().resolve())
                return True
            except ValueError:
                continue
        return False

    @staticmethod
    def _looks_secret(path: Path) -> bool:
        lowered = [p.lower() for p in path.parts]
        name = path.name.lower()
        return any(part in BLOCKED_PARTS for part in lowered) or any(token in name for token in BLOCKED_PARTS)

    def search(self, query: str, max_results: int = 20) -> list[str]:
        needle = query.strip().lower()
        if not needle:
            return []
        out: list[str] = []
        for root in self.roots:
            try:
                for path in root.rglob('*'):
                    if len(out) >= max(1, min(max_results, 50)):
                        return out
                    if not path.is_file() or self._looks_secret(path):
                        continue
                    if needle in path.name.lower():
                        out.append(str(path))
            except (PermissionError, OSError):
                continue
        return out

    def read_text(self, file_path: str, max_chars: int = 30000) -> str:
        path = Path(file_path).expanduser().resolve()
        if not self._is_inside_root(path):
            raise PermissionError('File is outside approved roots.')
        if self._looks_secret(path):
            raise PermissionError('Secret-like path is blocked.')
        if path.suffix.lower() not in SAFE_EXTENSIONS:
            raise PermissionError(f'Unsupported file type: {path.suffix or "no extension"}')
        if not path.is_file():
            raise FileNotFoundError(path)
        cap = max(1000, min(max_chars, 50000))
        # Open only regular bounded files; nonblocking/no-follow prevents Unix
        # device/FIFO and final-component symlink swaps from hanging the agent.
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > 2_000_000:
                raise ValueError('Only regular text files up to 2 MB may be read.')
            raw = stream.read(min(2_000_001, cap * 4 + 4))
        if b'\0' in raw:
            raise ValueError('Binary content is not a text file.')
        return raw.decode('utf-8', errors='replace')[:cap]
