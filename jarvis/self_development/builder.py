from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .policies import SelfDevelopmentPolicy


@dataclass(frozen=True)
class BuildChange:
    path: str
    bytes_written: int
    lines_written: int

    def as_dict(self) -> dict:
        return {
            'path': self.path,
            'bytes_written': self.bytes_written,
            'lines_written': self.lines_written,
        }


class SelfDevelopmentBuilder:
    """Writes generated text only inside a prepared sandbox worktree."""

    ALLOWED_SUFFIXES = {
        '.py', '.md', '.txt', '.json', '.toml', '.yaml', '.yml', '.ini', '.cfg',
        '.html', '.css', '.js', '.ts', '.tsx', '.jsx', '.sql', '.ps1', '.bat', '.sh',
    }

    def __init__(self, sandbox_root: Path, policy: SelfDevelopmentPolicy | None = None) -> None:
        self.sandbox_root = sandbox_root.resolve()
        self.policy = policy or SelfDevelopmentPolicy()

    def _safe(self, relative_path: str) -> tuple[Path, str]:
        normalized = self.policy.normalize(relative_path)
        allowed, reason = self.policy.path_allowed(normalized)
        if not allowed:
            raise PermissionError(f'{normalized}: {reason}')
        target = (self.sandbox_root / normalized).resolve()
        if self.sandbox_root != target and self.sandbox_root not in target.parents:
            raise PermissionError('Generated path escaped sandbox.')
        if target.suffix.lower() not in self.ALLOWED_SUFFIXES:
            raise PermissionError(f'Generated file type is not allowlisted: {target.suffix or "<none>"}')
        return target, normalized

    def write_text(self, relative_path: str, content: str) -> BuildChange:
        target, normalized = self._safe(relative_path)
        text = str(content)
        if '\x00' in text:
            raise ValueError('Binary/NUL content is not allowed in self-development text writes.')
        encoded = text.encode('utf-8')
        if len(encoded) > 2_000_000:
            raise ValueError('Single generated file exceeds the 2 MB safety limit.')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')
        return BuildChange(normalized, len(encoded), len(text.splitlines()))

    def apply(self, changes: dict[str, str]) -> list[BuildChange]:
        if len(changes) > self.policy.max_files_changed:
            raise PermissionError('Generated change set exceeds MAX_FILES_CHANGED before writing.')
        planned_lines = sum(len(str(content).splitlines()) for content in changes.values())
        check = self.policy.validate_change_set(list(changes), planned_lines)
        if not check.allowed:
            raise PermissionError('; '.join(check.reasons))
        return [self.write_text(path, content) for path, content in changes.items()]
