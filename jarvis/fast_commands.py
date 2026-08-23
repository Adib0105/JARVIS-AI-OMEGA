from __future__ import annotations

import json
import re


_APP_ALIASES = {
    'chrome': 'chrome',
    'google chrome': 'chrome',
    'edge': 'edge',
    'microsoft edge': 'edge',
    'notepad': 'notepad',
    'calculator': 'calculator',
    'calc': 'calculator',
    'paint': 'paint',
    'explorer': 'explorer',
    'file explorer': 'explorer',
    'task manager': 'task manager',
    'vscode': 'vscode',
    'vs code': 'vscode',
    'visual studio code': 'vscode',
}

_OPEN_WORDS = r'(?:open|launch|start|khol|kholo|kholna|chalao|chalu\s+karo)'
_FILLER = r'(?:please\s+|jarvis\s+|zara\s+|jara\s+|mere\s+liye\s+)*'


def parse_fast_command(text: str) -> tuple[str, dict] | None:
    """Recognize deterministic, low-risk commands without an LLM round trip."""
    normalized = ' '.join(str(text or '').lower().strip().split())
    if not normalized or len(normalized) > 100:
        return None
    match = re.fullmatch(rf'{_FILLER}{_OPEN_WORDS}\s+(?:the\s+)?(.+?)(?:\s+please)?', normalized)
    if not match:
        # Natural Hinglish commonly puts the verb last: "chrome kholo".
        match = re.fullmatch(rf'{_FILLER}(.+?)\s+{_OPEN_WORDS}(?:\s+please)?', normalized)
    if not match:
        return None
    target = match.group(1).strip()
    app = _APP_ALIASES.get(target)
    return ('open_app', {'app': app}) if app else None


def execute_fast_command(jarvis, text: str) -> str | None:
    parsed = parse_fast_command(text)
    if parsed is None:
        return None
    tool, args = parsed
    raw = jarvis.tools.call(tool, args)
    try:
        payload = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        payload = raw
    if isinstance(payload, dict) and payload.get('ok') is False:
        # Permission policy still wins. Never bypass a denied/approval-gated action.
        return None
    app = args['app']
    names = {'vscode': 'VS Code', 'chrome': 'Chrome', 'edge': 'Edge', 'explorer': 'File Explorer'}
    return f"Done. {names.get(app, app.title())} open kar diya."
