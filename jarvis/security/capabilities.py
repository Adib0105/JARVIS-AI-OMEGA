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
    ACCOUNT_CONFIG_READ = 'ACCOUNT_CONFIG_READ'


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


LOW = RiskLevel.LOW
MEDIUM = RiskLevel.MEDIUM
HIGH = RiskLevel.HIGH


def profile(name: str, risk: RiskLevel, caps: set[Capability], why: str, side_effecting: bool = False) -> ToolSecurityProfile:
    return ToolSecurityProfile(name, risk, frozenset(caps), why, side_effecting)


TOOL_SECURITY: dict[str, ToolSecurityProfile] = {
    # System / local metadata
    'get_current_time': profile('get_current_time', LOW, {Capability.SYSTEM_READ}, 'Reads the local current time.'),
    'get_system_info': profile('get_system_info', LOW, {Capability.SYSTEM_READ}, 'Reads basic local system information.'),
    'get_system_metrics': profile('get_system_metrics', LOW, {Capability.SYSTEM_READ}, 'Reads CPU, memory, disk, network and battery telemetry.'),
    'list_allowed_roots': profile('list_allowed_roots', LOW, {Capability.FILE_READ}, 'Lists the directories already approved for local JARVIS file tools.'),

    # Memory / productivity
    'remember_fact': profile('remember_fact', MEDIUM, {Capability.MEMORY_WRITE}, 'Writes a non-secret fact into local memory.', True),
    'recall_memory': profile('recall_memory', LOW, {Capability.MEMORY_READ}, 'Searches locally stored JARVIS facts.'),
    'search_chat_history': profile('search_chat_history', LOW, {Capability.MEMORY_READ}, 'Searches local conversation history.'),
    'search_knowledge': profile('search_knowledge', LOW, {Capability.MEMORY_READ}, 'Searches indexed local knowledge.'),
    'vector_search_knowledge': profile('vector_search_knowledge', LOW, {Capability.MEMORY_READ}, 'Performs local sparse relevance search over knowledge.'),
    'get_knowledge_stats': profile('get_knowledge_stats', LOW, {Capability.MEMORY_READ}, 'Reads local memory/knowledge statistics.'),
    'add_note': profile('add_note', MEDIUM, {Capability.MEMORY_WRITE}, 'Creates a non-secret local JARVIS note.', True),
    'list_notes': profile('list_notes', LOW, {Capability.MEMORY_READ}, 'Lists local JARVIS notes.'),
    'search_notes': profile('search_notes', LOW, {Capability.MEMORY_READ}, 'Searches local JARVIS notes.'),
    'get_agenda': profile('get_agenda', LOW, {Capability.MEMORY_READ}, 'Reads local todos, reminders and recent notes.'),
    'add_todo': profile('add_todo', MEDIUM, {Capability.MEMORY_WRITE}, 'Creates a local todo.', True),
    'list_todos': profile('list_todos', LOW, {Capability.MEMORY_READ}, 'Reads local todos.'),
    'complete_todo': profile('complete_todo', MEDIUM, {Capability.MEMORY_WRITE}, 'Changes local todo state.', True),
    'add_reminder': profile('add_reminder', MEDIUM, {Capability.MEMORY_WRITE}, 'Creates a local reminder.', True),
    'list_reminders': profile('list_reminders', LOW, {Capability.MEMORY_READ}, 'Reads local reminders.'),

    # Public web / safe browser reads
    'search_web': profile('search_web', LOW, {Capability.WEB_READ}, 'Sends a public search query to the configured search service.'),
    'search_news': profile('search_news', LOW, {Capability.WEB_READ}, 'Sends a public news query to the configured search service.'),
    'read_web_page': profile('read_web_page', LOW, {Capability.WEB_READ, Capability.BROWSER_READ}, 'Downloads and reads a DNS/redirect-validated public HTTP/HTTPS page as untrusted data.'),
    'browser_trust': profile('browser_trust', LOW, {Capability.BROWSER_READ}, 'Checks URL/DNS public-network trust without navigating.'),
    'browser_read_safe': profile('browser_read_safe', LOW, {Capability.WEB_READ, Capability.BROWSER_READ}, 'Reads a DNS/redirect-validated public page and scans returned text as untrusted data.'),
    'browser_extract_safe': profile('browser_extract_safe', LOW, {Capability.WEB_READ, Capability.BROWSER_READ}, 'Extracts text from a DNS/redirect-validated public page as untrusted data.'),
    'browser_snapshot': profile('browser_snapshot', LOW, {Capability.WEB_READ, Capability.BROWSER_READ}, 'Safely fetches a public page and computes a content fingerprint.'),
    'browser_changed': profile('browser_changed', LOW, {Capability.WEB_READ, Capability.BROWSER_READ}, 'Safely re-fetches a public page and compares its content fingerprint.'),
    'browser_research': profile('browser_research', LOW, {Capability.WEB_READ, Capability.BROWSER_READ}, 'Searches and safely reads a bounded set of public sources as untrusted research evidence.'),

    # Google Workspace
    'google_status': profile('google_status', MEDIUM, {Capability.ACCOUNT_CONFIG_READ}, 'Checks whether local Google OAuth configuration files exist.'),
    'gmail_search': profile('gmail_search', MEDIUM, {Capability.EMAIL_READ}, 'Reads email metadata/content from the connected Gmail account.'),
    'gmail_send': profile('gmail_send', HIGH, {Capability.EMAIL_SEND}, 'Sends an external email from the connected Gmail account.', True),
    'calendar_upcoming': profile('calendar_upcoming', MEDIUM, {Capability.CALENDAR_READ}, 'Reads events from the connected Google Calendar.'),
    'calendar_create': profile('calendar_create', HIGH, {Capability.CALENDAR_WRITE}, 'Creates an event in the connected Google Calendar.', True),

    # Local files / documents
    'search_local_files': profile('search_local_files', MEDIUM, {Capability.FILE_READ}, 'Searches filenames inside approved local roots.'),
    'read_local_text_file': profile('read_local_text_file', MEDIUM, {Capability.FILE_READ}, 'Reads a safe text/code file from an approved local root.'),
    'index_local_text_file': profile('index_local_text_file', MEDIUM, {Capability.FILE_READ, Capability.MEMORY_WRITE}, 'Reads an approved text file and indexes its non-secret content locally.', True),
    'read_document': profile('read_document', MEDIUM, {Capability.DOCUMENT_READ, Capability.FILE_READ}, 'Extracts text from an approved local document.'),
    'index_document': profile('index_document', MEDIUM, {Capability.DOCUMENT_READ, Capability.FILE_READ, Capability.MEMORY_WRITE}, 'Reads an approved document and indexes extracted non-secret text locally.', True),
    'open_local_path': profile('open_local_path', MEDIUM, {Capability.FILE_READ, Capability.APP_CONTROL}, 'Opens an approved local file or folder with the operating system.', True),

    # Browser / apps / desktop
    'open_url': profile('open_url', MEDIUM, {Capability.BROWSER_CONTROL}, 'Opens an external public HTTP/HTTPS URL after DNS validation.', True),
    'browser_search': profile('browser_search', MEDIUM, {Capability.BROWSER_CONTROL}, 'Opens a DNS-validated browser search page.', True),
    'open_app': profile('open_app', MEDIUM, {Capability.APP_CONTROL}, 'Launches an allowlisted Windows application.', True),
    'computer_status': profile('computer_status', LOW, {Capability.SCREEN_READ}, 'Reads desktop automation availability plus monitor/DPI metadata.'),
    'list_ui_targets': profile('list_ui_targets', MEDIUM, {Capability.SCREEN_READ}, 'Reads visible UI Automation target metadata without acting on it.'),
    'semantic_click': profile('semantic_click', HIGH, {Capability.SCREEN_READ, Capability.SCREEN_CONTROL, Capability.MOUSE_CONTROL}, 'Resolves and clicks a visible UI target after focus/readiness checks.', True),
    'semantic_type': profile('semantic_type', HIGH, {Capability.SCREEN_READ, Capability.SCREEN_CONTROL, Capability.KEYBOARD_CONTROL}, 'Resolves a visible UI target, recovers focus, types text and verifies readback when possible.', True),
    'type_text': profile('type_text', HIGH, {Capability.KEYBOARD_CONTROL}, 'Types text into the currently focused desktop application.', True),
    'press_key': profile('press_key', HIGH, {Capability.KEYBOARD_CONTROL}, 'Presses an allowlisted key in the focused desktop application.', True),
    'hotkey': profile('hotkey', HIGH, {Capability.KEYBOARD_CONTROL}, 'Presses an allowlisted keyboard shortcut.', True),
    'click_screen': profile('click_screen', HIGH, {Capability.MOUSE_CONTROL, Capability.SCREEN_CONTROL}, 'Clicks a specified screen coordinate.', True),

    # Coding / Git - exact registered V6/V7 tool names
    'list_code_tree': profile('list_code_tree', MEDIUM, {Capability.CODE_READ}, 'Reads an approved project directory tree.'),
    'write_local_text_file': profile('write_local_text_file', HIGH, {Capability.CODE_WRITE, Capability.FILE_WRITE}, 'Creates/replaces an approved source/text file and can alter project behavior.', True),
    'run_project_tests': profile('run_project_tests', MEDIUM, {Capability.CODE_TEST}, 'Runs the allowlisted Python unittest command in an approved project.'),
    'git_status': profile('git_status', MEDIUM, {Capability.GIT_READ, Capability.CODE_READ}, 'Reads Git working-tree status.'),
    'git_diff': profile('git_diff', MEDIUM, {Capability.GIT_READ, Capability.CODE_READ}, 'Reads Git diff output.'),
    'git_log': profile('git_log', MEDIUM, {Capability.GIT_READ, Capability.CODE_READ}, 'Reads recent Git commit metadata.'),
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