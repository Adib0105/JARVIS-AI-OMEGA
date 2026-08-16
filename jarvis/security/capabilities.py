from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Capability(str, Enum):
    SYSTEM_READ = 'SYSTEM_READ'
    MEMORY_READ = 'MEMORY_READ'
    MEMORY_WRITE = 'MEMORY_WRITE'
    FILE_READ = 'FILE_READ'
    FILE_WRITE = 'FILE_WRITE'
    SCREEN_READ = 'SCREEN_READ'
    SCREEN_CONTROL = 'SCREEN_CONTROL'
    BROWSER_READ = 'BROWSER_READ'
    BROWSER_CONTROL = 'BROWSER_CONTROL'
    KEYBOARD_CONTROL = 'KEYBOARD_CONTROL'
    MOUSE_CONTROL = 'MOUSE_CONTROL'
    CODE_READ = 'CODE_READ'
    CODE_WRITE = 'CODE_WRITE'
    CODE_TEST = 'CODE_TEST'
    EMAIL_READ = 'EMAIL_READ'
    EMAIL_SEND = 'EMAIL_SEND'
    CALENDAR_READ = 'CALENDAR_READ'
    CALENDAR_WRITE = 'CALENDAR_WRITE'
    WEB_READ = 'WEB_READ'
    APP_CONTROL = 'APP_CONTROL'
    DOCUMENT_READ = 'DOCUMENT_READ'
    GIT_READ = 'GIT_READ'


class RiskLevel(str, Enum):
    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'
    CRITICAL = 'CRITICAL'


@dataclass(frozen=True)
class ToolSecurityProfile:
    name: str
    risk: RiskLevel
    capabilities: frozenset[Capability]
    why: str
    side_effecting: bool = False


LOW_READ = RiskLevel.LOW
MEDIUM = RiskLevel.MEDIUM
HIGH = RiskLevel.HIGH


TOOL_SECURITY: dict[str, ToolSecurityProfile] = {
    'get_current_time': ToolSecurityProfile('get_current_time', LOW_READ, frozenset({Capability.SYSTEM_READ}), 'Reads the local current time.'),
    'get_system_info': ToolSecurityProfile('get_system_info', LOW_READ, frozenset({Capability.SYSTEM_READ}), 'Reads basic local system information.'),
    'get_system_metrics': ToolSecurityProfile('get_system_metrics', LOW_READ, frozenset({Capability.SYSTEM_READ}), 'Reads CPU, memory, disk and battery telemetry.'),
    'recall_fact': ToolSecurityProfile('recall_fact', LOW_READ, frozenset({Capability.MEMORY_READ}), 'Reads a locally stored JARVIS fact.'),
    'search_chat_history': ToolSecurityProfile('search_chat_history', LOW_READ, frozenset({Capability.MEMORY_READ}), 'Searches local conversation history.'),
    'search_notes': ToolSecurityProfile('search_notes', LOW_READ, frozenset({Capability.MEMORY_READ}), 'Searches local notes.'),
    'search_knowledge': ToolSecurityProfile('search_knowledge', LOW_READ, frozenset({Capability.MEMORY_READ}), 'Searches the local knowledge store.'),
    'vector_search_knowledge': ToolSecurityProfile('vector_search_knowledge', LOW_READ, frozenset({Capability.MEMORY_READ}), 'Performs local relevance search over knowledge.'),
    'list_todos': ToolSecurityProfile('list_todos', LOW_READ, frozenset({Capability.MEMORY_READ}), 'Reads local todos.'),
    'list_reminders': ToolSecurityProfile('list_reminders', LOW_READ, frozenset({Capability.MEMORY_READ}), 'Reads local reminders.'),
    'remember_fact': ToolSecurityProfile('remember_fact', MEDIUM, frozenset({Capability.MEMORY_WRITE}), 'Writes a non-secret fact into local memory.', True),
    'add_note': ToolSecurityProfile('add_note', MEDIUM, frozenset({Capability.MEMORY_WRITE}), 'Creates a local JARVIS note.', True),
    'add_todo': ToolSecurityProfile('add_todo', MEDIUM, frozenset({Capability.MEMORY_WRITE}), 'Creates a local todo.', True),
    'complete_todo': ToolSecurityProfile('complete_todo', MEDIUM, frozenset({Capability.MEMORY_WRITE}), 'Changes local todo state.', True),
    'add_reminder': ToolSecurityProfile('add_reminder', MEDIUM, frozenset({Capability.MEMORY_WRITE}), 'Creates a local reminder.', True),
    'search_web': ToolSecurityProfile('search_web', LOW_READ, frozenset({Capability.WEB_READ}), 'Sends a public search query to the configured web search service.'),
    'search_news': ToolSecurityProfile('search_news', LOW_READ, frozenset({Capability.WEB_READ}), 'Sends a public news query to the configured search service.'),
    'read_web_page': ToolSecurityProfile('read_web_page', LOW_READ, frozenset({Capability.WEB_READ}), 'Downloads and reads a public HTTP/HTTPS page.'),
    'gmail_search': ToolSecurityProfile('gmail_search', MEDIUM, frozenset({Capability.EMAIL_READ}), 'Reads email metadata/content from the connected Gmail account.'),
    'gmail_send': ToolSecurityProfile('gmail_send', HIGH, frozenset({Capability.EMAIL_SEND}), 'Sends an external email from the connected account.', True),
    'calendar_upcoming': ToolSecurityProfile('calendar_upcoming', MEDIUM, frozenset({Capability.CALENDAR_READ}), 'Reads events from the connected Google Calendar.'),
    'calendar_create': ToolSecurityProfile('calendar_create', HIGH, frozenset({Capability.CALENDAR_WRITE}), 'Creates an event in the connected Google Calendar.', True),
    'search_local_files': ToolSecurityProfile('search_local_files', MEDIUM, frozenset({Capability.FILE_READ}), 'Searches filenames inside approved local roots.'),
    'read_local_text_file': ToolSecurityProfile('read_local_text_file', MEDIUM, frozenset({Capability.FILE_READ}), 'Reads a safe text/code file from an approved local root.'),
    'index_local_text_file': ToolSecurityProfile('index_local_text_file', MEDIUM, frozenset({Capability.FILE_READ, Capability.MEMORY_WRITE}), 'Reads an approved text file and indexes it locally.', True),
    'index_document': ToolSecurityProfile('index_document', MEDIUM, frozenset({Capability.DOCUMENT_READ, Capability.MEMORY_WRITE}), 'Reads an approved document and indexes extracted text locally.', True),
    'open_url': ToolSecurityProfile('open_url', MEDIUM, frozenset({Capability.BROWSER_CONTROL}), 'Opens an external URL in the default browser.', True),
    'browser_search': ToolSecurityProfile('browser_search', MEDIUM, frozenset({Capability.BROWSER_CONTROL}), 'Opens a browser search page.', True),
    'open_app': ToolSecurityProfile('open_app', MEDIUM, frozenset({Capability.APP_CONTROL}), 'Launches an allowlisted Windows application.', True),
    'open_local_path': ToolSecurityProfile('open_local_path', MEDIUM, frozenset({Capability.FILE_READ, Capability.APP_CONTROL}), 'Opens an approved local file/folder with the operating system.', True),
    'type_text': ToolSecurityProfile('type_text', HIGH, frozenset({Capability.KEYBOARD_CONTROL}), 'Types text into the currently focused desktop application.', True),
    'press_key': ToolSecurityProfile('press_key', HIGH, frozenset({Capability.KEYBOARD_CONTROL}), 'Presses an allowlisted key in the focused desktop application.', True),
    'hotkey': ToolSecurityProfile('hotkey', HIGH, frozenset({Capability.KEYBOARD_CONTROL}), 'Presses an allowlisted keyboard shortcut.', True),
    'click_screen': ToolSecurityProfile('click_screen', HIGH, frozenset({Capability.MOUSE_CONTROL, Capability.SCREEN_CONTROL}), 'Clicks a specified screen coordinate.', True),
    'inspect_project_tree': ToolSecurityProfile('inspect_project_tree', MEDIUM, frozenset({Capability.CODE_READ}), 'Reads an approved project tree.'),
    'read_project_file': ToolSecurityProfile('read_project_file', MEDIUM, frozenset({Capability.CODE_READ, Capability.FILE_READ}), 'Reads an approved source/text file.'),
    'write_project_file': ToolSecurityProfile('write_project_file', HIGH, frozenset({Capability.CODE_WRITE, Capability.FILE_WRITE}), 'Writes an approved source/text file and may alter project behavior.', True),
    'run_project_tests': ToolSecurityProfile('run_project_tests', MEDIUM, frozenset({Capability.CODE_TEST}), 'Runs the allowlisted Python unittest command in an approved project.'),
    'git_status': ToolSecurityProfile('git_status', MEDIUM, frozenset({Capability.GIT_READ, Capability.CODE_READ}), 'Reads Git working-tree status.'),
    'git_diff': ToolSecurityProfile('git_diff', MEDIUM, frozenset({Capability.GIT_READ, Capability.CODE_READ}), 'Reads Git diff output.'),
    'git_log': ToolSecurityProfile('git_log', MEDIUM, frozenset({Capability.GIT_READ, Capability.CODE_READ}), 'Reads recent Git commit metadata.'),
}


def profile_for(tool_name: str) -> ToolSecurityProfile:
    return TOOL_SECURITY.get(
        tool_name,
        ToolSecurityProfile(
            name=tool_name,
            risk=RiskLevel.HIGH,
            capabilities=frozenset(),
            why='Unknown/unprofiled tool. V7 treats it as high risk until explicitly classified.',
            side_effecting=True,
        ),
    )
