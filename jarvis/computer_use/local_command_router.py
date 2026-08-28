from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class LocalCommandResult:
    handled: bool
    reply: str = ''
    tool: str = ''
    success: bool = False


_APP_ALIASES = {
    'chrome': 'chrome', 'google chrome': 'chrome', 'edge': 'edge', 'microsoft edge': 'edge',
    'notepad': 'notepad', 'calculator': 'calculator', 'calc': 'calculator',
    'file explorer': 'explorer', 'explorer': 'explorer', 'paint': 'paint',
    'task manager': 'taskmgr', 'vs code': 'vscode', 'vscode': 'vscode', 'visual studio code': 'vscode',
}


def _payload(output: str) -> dict:
    try:
        value = json.loads(output)
        return value if isinstance(value, dict) else {'ok': False, 'error': 'Invalid tool result.'}
    except Exception:
        return {'ok': False, 'error': 'Invalid tool result.'}


def _reply_from_tool(output: str, success_text: str) -> tuple[bool, str]:
    data = _payload(output)
    if data.get('ok') is True:
        return True, success_text
    return False, str(data.get('error') or 'Action complete nahi ho saka.')


def route_local_command(text: str, tool_call: Callable[[str, dict], str]) -> LocalCommandResult:
    """Handle obvious Windows commands locally before spending an AI request.

    This deliberately covers only deterministic, low-ambiguity intents. Every side
    effect still goes through the normal audited ToolRegistry permission gate.
    Complex/multi-step requests return handled=False so the agent can plan them.
    """
    raw = ' '.join(str(text or '').strip().lower().split())
    if not raw:
        return LocalCommandResult(False)

    # Do not steal compound requests from the mission/tool planner.
    compound_markers = (' aur ', ' then ', ' phir ', ' uske baad ', ' and then ', ' -> ', '→')
    if any(marker in raw for marker in compound_markers):
        return LocalCommandResult(False)

    # App launch: "chrome", "chrome kholo/open/start/chalao".
    for phrase, app in sorted(_APP_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if raw == phrase or re.fullmatch(rf'(?:please\s+)?{re.escape(phrase)}\s*(?:kholo|khol do|open|open karo|start|start karo|chalao|launch)?', raw):
            ok, reply = _reply_from_tool(tool_call('open_app', {'app': app}), f'{phrase.title()} open kar diya.')
            return LocalCommandResult(True, reply, 'open_app', ok)

    key: str | None = None
    success = ''
    if re.search(r'\b(volume|awaz|awaaz|sound)\b', raw):
        if re.search(r'\b(mute|chup|band)\b', raw):
            key, success = 'volumemute', 'Volume mute toggle kar diya.'
        elif re.search(r'\b(increase|badhao|badh[a-z]*|up|tez)\b', raw):
            key, success = 'volumeup', 'Volume badha diya.'
        elif re.search(r'\b(decrease|kam|down|ghatao)\b', raw):
            key, success = 'volumedown', 'Volume kam kar diya.'
    elif re.search(r'\b(play|pause|resume)\b', raw) and re.search(r'\b(song|music|video|media|gaana|gana)?\b', raw):
        key, success = 'playpause', 'Media play/pause toggle kar diya.'
    elif re.search(r'\b(next)\b', raw) and re.search(r'\b(song|track|media|gaana|gana)\b', raw):
        key, success = 'nexttrack', 'Next media track kar diya.'
    elif re.search(r'\b(previous|prev|pichla|pichli)\b', raw) and re.search(r'\b(song|track|media|gaana|gana)\b', raw):
        key, success = 'prevtrack', 'Previous media track kar diya.'

    if key:
        ok, reply = _reply_from_tool(tool_call('press_key', {'key': key}), success)
        return LocalCommandResult(True, reply, 'press_key', ok)

    window_hotkeys: list[str] | None = None
    success = ''
    if re.fullmatch(r'(?:current |active )?(?:window|app)\s*(?:minimize|minimise|chhota|chota)(?: karo)?', raw):
        window_hotkeys, success = ['win', 'down'], 'Active window minimize command bhej diya.'
    elif re.fullmatch(r'(?:current |active )?(?:window|app)\s*(?:maximize|maximise|bada)(?: karo)?', raw):
        window_hotkeys, success = ['win', 'up'], 'Active window maximize command bhej diya.'
    elif re.fullmatch(r'(?:current |active )?(?:window|app)\s*(?:close|band)(?: karo)?', raw):
        window_hotkeys, success = ['alt', 'f4'], 'Active window close command bhej diya.'
    elif raw in {'task view', 'task view kholo', 'open task view'}:
        window_hotkeys, success = ['win', 'tab'], 'Task View khol diya.'

    if window_hotkeys:
        ok, reply = _reply_from_tool(tool_call('hotkey', {'keys': window_hotkeys}), success)
        return LocalCommandResult(True, reply, 'hotkey', ok)

    return LocalCommandResult(False)
