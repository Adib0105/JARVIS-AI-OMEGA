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
_FILLER = r'(?:please\s+|jarvis\s+|friday\s+|zara\s+|jara\s+|mere\s+liye\s+)*'


def parse_fast_command(text: str) -> tuple[str, dict] | None:
    """Recognize deterministic, low-risk commands without an LLM round trip."""
    normalized = ' '.join(str(text or '').lower().strip().split())
    youtube = parse_youtube_command(normalized)
    if youtube:
        return ('youtube_play_first', {'query': youtube})
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
    local = local_quick_reply(text)
    if local is not None:
        return local
    parsed = parse_fast_command(text)
    if parsed is None:
        return None
    tool, args = parsed
    raw = jarvis.tools.call(tool, args)
    try:
        payload = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        payload = raw
    if tool == 'youtube_play_first':
        if not isinstance(payload, dict) or not payload.get('ok'):
            return 'YouTube action complete nahi hua: ' + str(payload.get('error', 'Unknown error') if isinstance(payload, dict) else payload)
        result = payload.get('result')
        return result.get('message', 'YouTube playback verify nahi hua.') if isinstance(result, dict) else 'YouTube playback verify nahi hua.'
    if not isinstance(payload, dict) or payload.get('ok') is not True:
        # A recognized command is terminal even when denied or malformed.
        # Falling through to the model can retry an action the user just denied.
        error = payload.get('error', 'Invalid tool response') if isinstance(payload, dict) else 'Invalid tool response'
        return f'App open nahi hua: {error}'
    app = args['app']
    names = {'vscode': 'VS Code', 'chrome': 'Chrome', 'edge': 'Edge', 'explorer': 'File Explorer'}
    return f"Done. {names.get(app, app.title())} open kar diya."


def parse_youtube_command(text: str) -> str | None:
    text = ' '.join(text.strip().split())
    if len(text) > 400:
        return None
    text = re.sub(r'^(?:(?:hey|please|jarvis|jarves)\s+)+', '', text, flags=re.I)
    patterns = [
        r'(?:play|search and play)\s+(.+?)\s+on\s+youtube[.!]?$',
        r'youtube\s+(?:par|pe|पर|पे)\s+(.+?)\s+(?:chalao|chala do|play karo|बजाओ|चलाओ|चला दो)[.!]?$',
        r'youtube\s+(?:jaao|jao|kholo)\s+(?:aur\s+)?(.+?)\s+(?:search karo|search kro)\s+aur\s+(?:jo\s+)?(?:pahla|pehla|first)\s+video(?:\s+aaye)?\s+(?:wo\s+)?(?:chala do|chalao|play karo)[.!]?$',
    ]
    for pattern in patterns:
        match = re.fullmatch(pattern, text, re.I)
        if match:
            query = match.group(1).strip()
            return query if 1 <= len(query) <= 300 else None
    return None


def local_quick_reply(text):
    """Exact small-talk and factual local requests avoid remote inference entirely."""
    from datetime import datetime
    clean = ' '.join(str(text).lower().strip(' .!?').split())
    clean = re.sub(r'^(?:(?:hey|jarvis|jarves|friday|please)\s+)+', '', clean)
    if clean in {'hi', 'hello', 'hey', 'namaste', 'kaisi ho', 'kaise ho', 'hello friday'}:
        return 'Hello boss! Main Friday hoon. Bataiye, kya karna hai?'
    if clean in {'time', 'what time is it', 'kitne baje hain', 'kitna time hua', 'time batao'}:
        return 'Abhi ' + datetime.now().strftime('%I:%M %p') + ' hua hai, boss.'
    if clean in {'system status', 'system report', 'cpu usage', 'ram usage', 'system kitna use ho raha hai'}:
        from .daily_briefing import system_report
        return system_report()
    if clean in {'weather', 'weather report', 'weather batao', 'mausam batao', 'aaj ka mausam', 'aaj barish hogi', 'aaj barish hogi ya nahi', 'aaj barish hogi ya nhi'}:
        from .daily_briefing import weather_report
        from .config import settings
        try:
            preferences = json.loads((settings.db_path.parent / 'background-settings.json').read_text(encoding='utf-8'))
            location = preferences.get('location') if isinstance(preferences, dict) else None
        except (OSError, ValueError):
            location = None
        try:
            return weather_report(location)
        except Exception:
            return 'Weather service abhi available nahi hai. Internet check karke dobara boliye.'
    return None
