from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .config import settings


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str = ''


class PermissionGate:
    SAFE = {'get_system_info', 'get_current_time', 'remember_fact', 'recall_memory', 'list_allowed_roots'}
    APPROVAL = {'search_local_files', 'read_local_text_file', 'open_url', 'open_app'}

    def __init__(self, confirmer: Callable[[str, dict], bool] | None = None):
        self.confirmer = confirmer

    def check(self, name: str, args: dict) -> Decision:
        if name in self.SAFE:
            return Decision(True)
        if name in self.APPROVAL:
            if not settings.require_local_approval:
                return Decision(True)
            if self.confirmer and self.confirmer(name, args):
                return Decision(True)
            return Decision(False, 'Local action was not approved by the user.')
        return Decision(False, f"Tool '{name}' is not permitted.")
