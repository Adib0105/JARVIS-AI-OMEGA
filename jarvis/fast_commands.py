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

_WINDOWS_COMMANDS = {
    'volume_up': (r'volume up', r'volume badhao', r'awaz badhao', r'awaaz badhao'),
    'volume_down': (r'volume down', r'volume kam karo', r'awaz kam karo', r'awaaz kam karo'),
    'volume_mute': (r'mute', r'unmute', r'volume mute', r'awaz band karo', r'awaaz band karo'),
    'media_play_pause': (r'play pause', r'pause music', r'resume music', r'music pause karo'),
    'media_next': (r'next track', r'next song', r'agla gana', r'agla gaana'),
    'media_previous': (r'previous track', r'previous song', r'pichla gana', r'pichla gaana'),
    'show_desktop': (r'show desktop', r'desktop dikhao'),
    'switch_window': (r'switch window', r'agla window', r'window badlo'),
    'minimize_window': (r'minimize window', r'window minimize karo'),
    'maximize_window': (r'maximize window', r'window maximize karo'),
    'close_window': (r'close current window', r'current window close karo'),
    'new_virtual_desktop': (r'new virtual desktop', r'naya desktop banao'),
    'next_virtual_desktop': (r'next virtual desktop', r'agla desktop'),
    'previous_virtual_desktop': (r'previous virtual desktop', r'pichla desktop'),
    'lock_pc': (r'lock pc', r'lock computer', r'computer lock karo'),
    'open_wifi_settings': (r'open wifi settings', r'wifi settings kholo'),
    'open_bluetooth_settings': (r'open bluetooth settings', r'bluetooth settings kholo'),
    'open_display_settings': (r'open display settings', r'display settings kholo'),
    'open_sound_settings': (r'open sound settings', r'sound settings kholo'),
    'open_apps_settings': (r'open apps settings', r'apps settings kholo'),
}


def parse_windows_command(text: str) -> tuple[str, dict] | None:
    normalized = ' '.join(str(text or '').lower().strip(' .!?').split())
    normalized = re.sub(r'^(?:(?:hey|please|jarvis|jarves|jervis|friday|zara|jara)[,\s]+)+', '', normalized)
    if not normalized or len(normalized) > 100:
        return None
    for action, patterns in _WINDOWS_COMMANDS.items():
        if any(re.fullmatch(pattern, normalized, re.I) for pattern in patterns):
            return ('windows_control', {'action': action})
    return None


def parse_fast_command(text: str) -> tuple[str, dict] | None:
    """Recognize deterministic, low-risk commands without an LLM round trip."""
    normalized = ' '.join(str(text or '').lower().strip().split())
    windows = parse_windows_command(normalized)
    if windows:
        return windows
    search = parse_youtube_search(normalized)
    if search:
        return ('browser_search', {'engine': 'youtube', 'query': search})
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
    if tool == 'browser_search':
        if isinstance(payload, dict) and payload.get('ok') is True:
            return 'YouTube search aapke default browser mein khol di. Video apne aap play nahi kiya.'
        return 'YouTube search complete nahi hui. Browser permission/result check kijiye.'
    if tool == 'windows_control':
        if not isinstance(payload, dict) or payload.get('ok') is not True:
            error = payload.get('error', 'Permission ya Windows action failed') if isinstance(payload, dict) else payload
            return f'Windows control complete nahi hua: {error}'
        labels = {
            'volume_up': 'Volume-up command Windows ko bhej diya',
            'volume_down': 'Volume-down command Windows ko bhej diya',
            'volume_mute': 'Mute-toggle command Windows ko bhej diya',
            'media_play_pause': 'Media play/pause command bhej diya',
            'media_next': 'Next track command bhej diya', 'media_previous': 'Previous track command bhej diya',
            'show_desktop': 'Desktop shortcut bhej diya', 'switch_window': 'Window switch command bhej diya',
            'minimize_window': 'Current window minimize command bhej diya',
            'maximize_window': 'Current window maximize command bhej diya',
            'close_window': 'Current window close command bhej diya',
            'new_virtual_desktop': 'Naya virtual desktop command bhej diya',
            'next_virtual_desktop': 'Next virtual desktop command bhej diya',
            'previous_virtual_desktop': 'Previous virtual desktop command bhej diya',
            'lock_pc': 'Computer lock request complete hua',
            'open_wifi_settings': 'Wi-Fi settings open request bhej diya',
            'open_bluetooth_settings': 'Bluetooth settings open request bhej diya',
            'open_display_settings': 'Display settings open request bhej diya',
            'open_sound_settings': 'Sound settings open request bhej diya',
            'open_apps_settings': 'Apps settings open request bhej diya',
        }
        return labels.get(args['action'], 'Windows control request bhej diya.')
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


def parse_youtube_search(text):
    text = re.sub(r'^(?:(?:hey|please|jarvis|jarves|friday)[,\s]+)+', '', text.strip(), flags=re.I)
    patterns = (
        r'(?:chrome\s+(?:me|mein)\s+jao\s+)?youtube\s+search\s+(?:kro|karo)\s+aur\s+(.+?)\s+search[.!]?$',
        r'youtube\s+(?:par|pe)\s+(.+?)\s+search\s+(?:karo|kro)[.!]?$',
        r'search\s+(.+?)\s+on\s+youtube[.!]?$',
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, text, re.I)
        if match and 1 <= len(match.group(1)) <= 300:
            return match.group(1).strip()
    return None


def local_quick_reply(text):
    """Exact small-talk and factual local requests avoid remote inference entirely."""
    from datetime import datetime
    clean = ' '.join(str(text).lower().strip(' .!?').split())
    clean = re.sub(r'^(?:(?:hey|jarvis|jarves|friday|please)\s+)+', '', clean)
    if clean in {'hi', 'hello', 'hey', 'namaste', 'kaisi ho', 'kaise ho', 'hello friday'}:
        from .config import settings
        return f'Hello {settings.user_name}! Main Friday hoon. Bataiye, kya karna hai?'
    if clean in {'time', 'what time is it', 'kitne baje hain', 'kitna time hua', 'time batao'}:
        return 'Abhi ' + datetime.now().strftime('%I:%M %p') + ' hua hai, boss.'
    if clean in {'system status', 'system report', 'cpu usage', 'ram usage', 'system kitna use ho raha hai'}:
        from .daily_briefing import system_report
        return system_report()
    if clean in {'weather', 'weather report', 'weather batao', 'mausam batao', 'aaj ka mausam', 'aaj barish hogi', 'aaj barish hogi ya nahi', 'aaj barish hogi ya nhi', 'weather now', 'kal ka mausam', 'tomorrow weather', 'air quality', 'aqi', 'pollution', 'pollution kitna hai'}:
        from .daily_briefing import weather_report, rich_weather_report, air_report
        from .config import settings
        try:
            preferences = json.loads((settings.db_path.parent / 'background-settings.json').read_text(encoding='utf-8'))
            location = preferences.get('location') if isinstance(preferences, dict) else None
        except (OSError, ValueError):
            location = None
        try:
            if clean in {'air quality', 'aqi', 'pollution', 'pollution kitna hai'}:
                return air_report(location)
            if clean in {'kal ka mausam', 'tomorrow weather'}:
                return weather_report(location, mode='tomorrow')
            return rich_weather_report(location)
        except Exception:
            return 'Weather service abhi available nahi hai. Internet check karke dobara boliye.'
    return None
