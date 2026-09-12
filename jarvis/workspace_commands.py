"""Searchable UI commands and editable prompt starters. Never executes model tools."""
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceCommand:
    id: str
    label: str
    keywords: str
    method: str = ''
    draft: str = ''


COMMANDS = (
    WorkspaceCommand('chats', 'Search / resume saved chats', 'history purani conversation', '_chat_library'),
    WorkspaceCommand('new', 'Start a new chat', 'new naya session', '_new_chat'),
    WorkspaceCommand('voice', 'Voice settings and previews', 'female awaaz microphone', '_voice_preferences'),
    WorkspaceCommand('export', 'Export current chat', 'save markdown download', '_export_chat'),
    WorkspaceCommand('image', 'Attach an image', 'photo screenshot upload', '_upload_images'),
    WorkspaceCommand('document', 'Read / index a document', 'pdf excel word file', '_learn_document'),
    WorkspaceCommand('mission', 'Plan a mission', 'goal task steps', '_mission'),
    WorkspaceCommand('status', 'Show system status', 'health model system', '_show_status'),
    WorkspaceCommand('python', 'Draft: debug Python', 'code error programming', draft='Help me debug this Python code. Explain the root cause, give the corrected code, and show a small test.\n\nCode:\n[paste code]\n\nError:\n[paste error]'),
    WorkspaceCommand('sql', 'Draft: SQL practice', 'database query analytics', draft='Teach me SQL step by step in Hinglish. Give one practice question at a time using a small sales table, wait for my answer, and explain mistakes. Start with SELECT and WHERE.'),
    WorkspaceCommand('excel', 'Draft: Excel analysis', 'spreadsheet data kpi', draft='Help me analyze this Excel dataset. First ask for the column names or file. Then guide me through cleaning, formulas, pivots, and useful KPIs. Do not invent numbers.'),
    WorkspaceCommand('study', 'Draft: study a topic', 'learn class explain hindi', draft='Teach me [topic] in simple Hinglish. Explain with one everyday example, then give a small exercise and wait for my answer.'),
    WorkspaceCommand('review', 'Draft: review code', 'quality bugs security', draft='Review the code I provide for bugs, edge cases, and security issues. Explain confirmed problems with examples and separate them from suggestions.\n\n[paste code]'),
)


def search_commands(query: str):
    words = query.casefold().split()
    return [item for item in COMMANDS if all(word in f'{item.label} {item.keywords}'.casefold() for word in words)]


def apply_command(desktop, command_id: str) -> bool:
    command = next((item for item in COMMANDS if item.id == command_id), None)
    if command is None:
        raise ValueError('Unknown workspace command.')
    if desktop.busy:
        raise RuntimeError('Wait for the current task to finish.')
    if command.draft:
        if desktop.entry.get().strip():
            raise ValueError('Your input already contains a draft. Send or clear it first.')
        desktop.entry.insert(0, command.draft)
        desktop.entry.focus_set()
        return False  # Draft only. User chooses when to send.
    getattr(desktop, command.method)()
    return True
