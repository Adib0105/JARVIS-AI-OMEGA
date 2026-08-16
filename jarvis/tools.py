from __future__ import annotations

import json
from typing import Callable

from .local_files import LocalFiles
from .memory import MemoryStore
from .permissions import PermissionGate
from .system_tools import current_time, open_app, open_url, system_info


class ToolRegistry:
    def __init__(self, memory: MemoryStore, confirmer: Callable[[str, dict], bool] | None = None):
        self.memory = memory
        self.files = LocalFiles()
        self.permissions = PermissionGate(confirmer)

    def schemas(self) -> list[dict]:
        return [
            {
                'type': 'function', 'name': 'get_system_info',
                'description': "Get basic information about the user's computer and Python runtime.",
                'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False},
                'strict': True,
            },
            {
                'type': 'function', 'name': 'get_current_time',
                'description': "Get the user's current local date/time from the computer.",
                'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False},
                'strict': True,
            },
            {
                'type': 'function', 'name': 'remember_fact',
                'description': 'Store a useful non-secret fact or user preference in local long-term memory.',
                'parameters': {
                    'type': 'object', 'properties': {'fact': {'type': 'string'}},
                    'required': ['fact'], 'additionalProperties': False,
                }, 'strict': True,
            },
            {
                'type': 'function', 'name': 'recall_memory',
                'description': 'Search local long-term memory for relevant facts.',
                'parameters': {
                    'type': 'object', 'properties': {
                        'query': {'type': 'string'},
                        'limit': {'type': 'integer', 'minimum': 1, 'maximum': 20},
                    }, 'required': ['query', 'limit'], 'additionalProperties': False,
                }, 'strict': True,
            },
            {
                'type': 'function', 'name': 'list_allowed_roots',
                'description': 'List folders JARVIS is allowed to search/read.',
                'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False},
                'strict': True,
            },
            {
                'type': 'function', 'name': 'search_local_files',
                'description': 'Read-only filename search inside approved local folders. Requires approval.',
                'parameters': {
                    'type': 'object', 'properties': {
                        'query': {'type': 'string'},
                        'max_results': {'type': 'integer', 'minimum': 1, 'maximum': 50},
                    }, 'required': ['query', 'max_results'], 'additionalProperties': False,
                }, 'strict': True,
            },
            {
                'type': 'function', 'name': 'read_local_text_file',
                'description': 'Read a safe text/code file inside approved folders. Secret-like paths are blocked. Requires approval.',
                'parameters': {
                    'type': 'object', 'properties': {
                        'file_path': {'type': 'string'},
                        'max_chars': {'type': 'integer', 'minimum': 1000, 'maximum': 50000},
                    }, 'required': ['file_path', 'max_chars'], 'additionalProperties': False,
                }, 'strict': True,
            },
            {
                'type': 'function', 'name': 'open_url',
                'description': 'Open an http/https URL in the default browser. Requires approval.',
                'parameters': {
                    'type': 'object', 'properties': {'url': {'type': 'string'}},
                    'required': ['url'], 'additionalProperties': False,
                }, 'strict': True,
            },
            {
                'type': 'function', 'name': 'open_app',
                'description': 'Open an allowlisted Windows app such as notepad, calculator, explorer, or paint. Requires approval.',
                'parameters': {
                    'type': 'object', 'properties': {'app': {'type': 'string'}},
                    'required': ['app'], 'additionalProperties': False,
                }, 'strict': True,
            },
        ]

    def call(self, name: str, args: dict) -> str:
        decision = self.permissions.check(name, args)
        if not decision.allowed:
            return json.dumps({'ok': False, 'error': decision.reason}, ensure_ascii=False)
        try:
            handlers = {
                'get_system_info': lambda: system_info(),
                'get_current_time': lambda: current_time(),
                'remember_fact': lambda: self.memory.remember(args['fact']),
                'recall_memory': lambda: self.memory.recall(args['query'], args['limit']),
                'list_allowed_roots': lambda: self.files.roots_info(),
                'search_local_files': lambda: self.files.search(args['query'], args['max_results']),
                'read_local_text_file': lambda: self.files.read_text(args['file_path'], args['max_chars']),
                'open_url': lambda: open_url(args['url']),
                'open_app': lambda: open_app(args['app']),
            }
            if name not in handlers:
                raise KeyError(name)
            return json.dumps({'ok': True, 'result': handlers[name]()}, ensure_ascii=False, default=str)
        except Exception as exc:
            return json.dumps({'ok': False, 'error': f'{type(exc).__name__}: {exc}'}, ensure_ascii=False)
