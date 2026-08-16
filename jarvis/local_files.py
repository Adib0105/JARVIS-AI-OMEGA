from __future__ import annotations

from pathlib import Path

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
                resolved.relative_to(root)
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
        return path.read_text(encoding='utf-8', errors='replace')[:cap]
