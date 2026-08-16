from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .config import settings


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str = ''


class PermissionGate:
    SAFE = {
        'get_system_info', 'get_system_metrics', 'get_current_time',
        'remember_fact', 'recall_memory', 'search_chat_history',
        'search_knowledge', 'vector_search_knowledge', 'get_knowledge_stats',
        'add_note', 'list_notes', 'search_notes', 'get_agenda',
        'add_todo', 'list_todos', 'complete_todo',
        'add_reminder', 'list_reminders',
        'list_allowed_roots', 'search_web', 'search_news', 'read_web_page',
    }
    APPROVAL = {
        'search_local_files', 'read_local_text_file', 'index_local_text_file',
        'read_document', 'index_document',
        'open_url', 'open_app', 'browser_search', 'open_local_path',
        'type_text', 'press_key', 'hotkey', 'click_screen', 'capture_screen',
        'list_code_tree', 'write_local_text_file', 'run_project_tests',
        'git_status', 'git_diff', 'git_log',
    }

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
