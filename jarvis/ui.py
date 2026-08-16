from __future__ import annotations

import json
from datetime import datetime

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from .config import settings
from .core import JarvisOmega
from .microphone import record_and_transcribe
from .system_tools import system_metrics
from .vision import capture_screen
from .voice import VoiceOutput
from .web_tools import search_news, search_web

console = Console()


def confirmer(tool: str, args: dict) -> bool:
    console.print(Panel.fit(
        f'[bold yellow]V6 local action request[/bold yellow]\nTool: [cyan]{tool}[/cyan]\nArgs: {args}',
        title='Permission Gate', border_style='yellow'
    ))
    return Confirm.ask('Allow this local action?', default=False)


def banner() -> None:
    title = Text('J A R V I S   O M E G A   V6', style='bold cyan')
    provider = 'OpenRouter Free' if settings.provider == 'openrouter' else 'OpenAI'
    subtitle = (
        f'ARC Agent • Mission Planner • Images • Documents • Web • Memory • Desktop Tools • Neural Voice\n'
        f'OPERATOR: {settings.creator_name} • Provider: {provider} • Model: {settings.model}'
    )
    console.print(Panel.fit(Text.assemble(title, '\n', subtitle), border_style='cyan'))
    console.print('[dim]Type normally, or /help for V6 power commands. Sensitive local actions remain approval-gated.[/dim]\n')


def help_table() -> Table:
    table = Table(title='JARVIS OMEGA V6 Commands', show_header=True, header_style='bold cyan')
    table.add_column('Command')
    table.add_column('Action')
    commands = [
        ('/mission <goal>', 'Planner → Executor → Reviewer mission mode'),
        ('/mic', 'Push-to-talk microphone input, then send to JARVIS'),
        ('/image "path" | prompt', 'Analyze image'),
        ('/screen [prompt]', 'Analyze current screen with approval'),
        ('/document "path"', 'Extract/index PDF/DOCX/XLSX/CSV/TXT with approval'),
        ('/web <query>', 'Free public web search'),
        ('/news <query>', 'Recent news search'),
        ('/browser <engine> | <query>', 'Open google/youtube/github/bing search with approval'),
        ('/app <name>', 'Open allowlisted Windows app with approval'),
        ('/todo <text>', 'Add local todo'),
        ('/todos', 'List open todos'),
        ('/done <id>', 'Complete todo'),
        ('/remind YYYY-MM-DD HH:MM | text', 'Create local reminder'),
        ('/reminders', 'List pending reminders'),
        ('/remember <text>', 'Store long-term fact'),
        ('/recall <query>', 'Recall facts'),
        ('/search-history <query>', 'Search prior local chats'),
        ('/learn <file>', 'Index safe local text/code file'),
        ('/knowledge <query>', 'Search indexed knowledge'),
        ('/metrics', 'Live CPU/RAM/disk/battery metrics'),
        ('/history [n]', 'Show recent messages'),
        ('/export', 'Export current chat to Markdown'),
        ('/stats', 'Memory/task/knowledge stats'),
        ('/status', 'Full V6 status'),
        ('/voice-test [mode]', 'Test neural voice'),
        ('/mute / /unmute', 'Control speech'),
        ('/new', 'New session'),
        ('/sessions', 'List sessions'),
        ('/version', 'Show V6 version'),
        ('/exit', 'Close JARVIS'),
    ]
    for cmd, desc in commands:
        table.add_row(cmd, desc)
    return table


def _print_search_results(title: str, results: list[dict]) -> None:
    if not results:
        console.print('[yellow]No results found.[/yellow]')
        return
    table = Table(title=title, show_lines=True)
    table.add_column('#', width=3)
    table.add_column('Title', ratio=2)
    table.add_column('Snippet', ratio=3)
    table.add_column('URL', ratio=2)
    for i, row in enumerate(results, 1):
        table.add_row(str(i), row.get('title', ''), row.get('snippet', '')[:300], row.get('url', ''))
    console.print(table)


def _show_json(title: str, value) -> None:
    console.print(Panel(json.dumps(value, ensure_ascii=False, indent=2, default=str), title=title, border_style='magenta'))


def run_cli() -> None:
    banner()
    jarvis = JarvisOmega(confirmer=confirmer)
    voice = VoiceOutput()

    while True:
        try:
            text = Prompt.ask('[bold green]YOU[/bold green]').strip()
        except (EOFError, KeyboardInterrupt):
            console.print('\n[cyan]JARVIS[/cyan]: Goodbye.')
            voice.stop()
            break
        if not text:
            continue
        low = text.lower()

        if low in {'/exit', '/quit', 'exit', 'quit'}:
            goodbye = f'Goodbye, {settings.user_name}.'
            console.print(f'[cyan]JARVIS[/cyan]: {goodbye}')
            voice.speak(goodbye)
            voice.stop()
            break
        if low == '/help':
            console.print(help_table()); continue
        if low == '/version':
            console.print(f'[cyan]JARVIS AI OMEGA[/cyan] {settings.app_version}'); continue
        if low == '/clear':
            console.clear(); banner(); continue
        if low == '/new':
            console.print(f'[green]New V6 session:[/green] {jarvis.new_session()}'); continue

        if low == '/status':
            stats = jarvis.memory.stats()
            provider = 'OpenRouter Free' if settings.provider == 'openrouter' else 'OpenAI'
            console.print(Panel(
                f'Version: {settings.app_version}\nOperator: {settings.creator_name}\nProvider: {provider}\n'
                f'Model: {settings.model}\nLast model: {jarvis.last_model_used}\nLast request: {jarvis.last_request_kind}\n'
                f'Tool mode: {jarvis.last_tool_mode}\nDesktop automation: {settings.enable_desktop_automation}\n'
                f'Document intelligence: {settings.enable_document_intelligence}\nCoding tools: {settings.enable_coding_tools}\n'
                f'Microphone: {settings.enable_mic_input}\nWake default: {settings.enable_wake_word}\n'
                f'Voice: {settings.voice_engine} • pitch {settings.edge_voice_pitch}\n'
                f'Images: {settings.max_image_attachments} max\nAI/Vision timeout: {settings.ai_timeout_seconds}/{settings.vision_timeout_seconds}s\n'
                f'Open todos: {stats["open_todos"]}\nPending reminders: {stats["pending_reminders"]}\n'
                f'Session: {jarvis.session_id}\nLast latency: {jarvis.last_latency:.2f}s',
                title='OMEGA V6 Status', border_style='green'))
            continue

        if low.startswith('/mission '):
            goal = text[len('/mission '):].strip()
            try:
                with console.status('[magenta]V6 mission planner/executor running...[/magenta]'):
                    result = jarvis.run_mission(goal, lambda m: console.print(f'[magenta]MISSION[/magenta] {m}'))
                console.print(Panel(Markdown(result), title='MISSION REVIEW', border_style='magenta'))
                voice.speak(result)
            except Exception as exc:
                console.print(Panel(str(exc), title='Mission Error', border_style='red'))
            continue

        if low == '/mic':
            if not settings.enable_mic_input:
                console.print('[yellow]ENABLE_MIC_INPUT=false in .env[/yellow]'); continue
            try:
                with console.status('[magenta]Listening...[/magenta]'):
                    heard = record_and_transcribe(settings.mic_record_seconds, settings.speech_language)
                console.print(f'[green]HEARD:[/green] {heard}')
                with console.status('[cyan]JARVIS is thinking...[/cyan]'):
                    answer = jarvis.chat(heard)
                console.print(Panel(Markdown(answer), title='JARVIS', border_style='cyan'))
                voice.speak(answer)
            except Exception as exc:
                console.print(Panel(str(exc), title='Microphone Error', border_style='red'))
            continue

        if low.startswith('/image '):
            raw = text[len('/image '):].strip()
            path_text, prompt = (raw.split('|', 1) + [''])[:2] if '|' in raw else (raw, '')
            path = path_text.strip().strip('"')
            prompt = prompt.strip() or 'Analyze this image carefully and tell me the important details.'
            try:
                with console.status('[magenta]Analyzing image...[/magenta]'):
                    answer = jarvis.analyze_image(path, prompt)
                console.print(Panel(Markdown(answer), title='JARVIS VISION', border_style='magenta'))
                voice.speak(answer)
            except Exception as exc:
                console.print(Panel(str(exc), title='Image Error', border_style='red'))
            continue

        if low.startswith('/screen'):
            prompt = text[len('/screen'):].strip() or 'Analyze my screen and tell me what matters and what to do next.'
            decision = jarvis.tools.permissions.check('capture_screen', {'purpose': prompt})
            if not decision.allowed:
                console.print(f'[yellow]{decision.reason}[/yellow]'); continue
            try:
                with console.status('[magenta]Capturing/analyzing screen...[/magenta]'):
                    screenshot = capture_screen()
                    answer = jarvis.analyze_image(screenshot, prompt)
                console.print(Panel(Markdown(answer), title=f'VISION • {screenshot.name}', border_style='magenta'))
                voice.speak(answer)
            except Exception as exc:
                console.print(Panel(str(exc), title='Screen Vision Error', border_style='red'))
            continue

        if low.startswith('/document '):
            path = text[len('/document '):].strip().strip('"')
            result = jarvis.tools.call('index_document', {'file_path': path})
            console.print(Panel(result, title='Document Intelligence', border_style='magenta')); continue

        if low.startswith('/web '):
            try:
                _print_search_results('Free Web Search', search_web(text[5:].strip(), 7))
            except Exception as exc:
                console.print(f'[red]Web search failed:[/red] {exc}')
            continue
        if low.startswith('/news '):
            try:
                _print_search_results('Recent News', search_news(text[6:].strip(), 7, 'w'))
            except Exception as exc:
                console.print(f'[red]News search failed:[/red] {exc}')
            continue
        if low.startswith('/browser '):
            raw = text[len('/browser '):].strip()
            if '|' not in raw:
                console.print('[yellow]Use: /browser google | your query[/yellow]'); continue
            engine, query = [x.strip() for x in raw.split('|', 1)]
            console.print(jarvis.tools.call('browser_search', {'query': query, 'engine': engine})); continue
        if low.startswith('/app '):
            console.print(jarvis.tools.call('open_app', {'app': text[len('/app '):].strip()})); continue

        if low.startswith('/todo '):
            _show_json('Todo', jarvis.memory.add_todo(text[len('/todo '):])); continue
        if low == '/todos':
            _show_json('Open Todos', jarvis.memory.list_todos(False, 30)); continue
        if low.startswith('/done '):
            try:
                _show_json('Todo', jarvis.memory.complete_todo(int(text[len('/done '):].strip())))
            except Exception as exc:
                console.print(f'[red]{exc}[/red]')
            continue
        if low.startswith('/remind '):
            raw = text[len('/remind '):].strip()
            if '|' not in raw:
                console.print('[yellow]Use: /remind YYYY-MM-DD HH:MM | message[/yellow]'); continue
            due_text, reminder_text = [x.strip() for x in raw.split('|', 1)]
            try:
                due = datetime.strptime(due_text, '%Y-%m-%d %H:%M').astimezone()
                _show_json('Reminder', jarvis.memory.add_reminder(reminder_text, due.isoformat()))
            except Exception as exc:
                console.print(f'[red]{exc}[/red]')
            continue
        if low == '/reminders':
            _show_json('Pending Reminders', jarvis.memory.list_reminders(False, 30)); continue

        if low.startswith('/remember '):
            console.print(jarvis.memory.remember(text[len('/remember '):])); continue
        if low.startswith('/recall '):
            _show_json('Memory', jarvis.memory.recall(text[len('/recall '):], 10)); continue
        if low.startswith('/search-history '):
            _show_json('Chat History', jarvis.memory.search_messages(text[len('/search-history '):], 20)); continue
        if low.startswith('/learn '):
            path = text[len('/learn '):].strip().strip('"')
            console.print(Panel(jarvis.tools.call('index_local_text_file', {'file_path': path}), title='Knowledge Import')); continue
        if low.startswith('/knowledge '):
            _show_json('Local Knowledge', jarvis.memory.search_knowledge(text[len('/knowledge '):], 8)); continue
        if low == '/metrics':
            _show_json('System Telemetry', system_metrics()); continue

        if low.startswith('/history'):
            parts = text.split(maxsplit=1)
            try:
                count = max(1, min(int(parts[1]), 50)) if len(parts) > 1 else 12
            except ValueError:
                count = 12
            rows = jarvis.memory.session_messages(jarvis.session_id, count)
            for row in rows[-count:]:
                label = 'YOU' if row['role'] == 'user' else 'JARVIS'
                console.print(Panel(Markdown(row['content']), title=label, border_style='green' if label == 'YOU' else 'cyan'))
            continue
        if low == '/export':
            console.print(f'[green]Exported:[/green] {jarvis.memory.export_session(jarvis.session_id, settings.export_dir)}'); continue
        if low == '/stats':
            _show_json('Memory & Knowledge Stats', jarvis.memory.stats()); continue
        if low.startswith('/voice-test'):
            parts = text.split(maxsplit=1)
            voice.test(parts[1].strip().lower() if len(parts) > 1 else 'hinglish'); continue
        if low == '/mute':
            voice.mute(); console.print('[yellow]Spoken replies muted.[/yellow]'); continue
        if low == '/unmute':
            voice.unmute(); voice.test('hinglish'); console.print('[green]Spoken replies enabled.[/green]'); continue
        if low == '/sessions':
            _show_json('Sessions', jarvis.memory.list_sessions()); continue

        with console.status('[cyan]JARVIS V6 is thinking...[/cyan]', spinner='dots12'):
            try:
                answer = jarvis.chat(text)
            except Exception as exc:
                console.print(Panel(str(exc), title='JARVIS Error', border_style='red'))
                continue
        console.print(Panel(Markdown(answer), title='JARVIS V6', border_style='cyan'))
        voice.speak(answer)
