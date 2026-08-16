from __future__ import annotations

import json

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from .config import settings
from .core import JarvisOmega
from .vision import capture_screen
from .voice import VoiceOutput
from .web_tools import search_news, search_web

console = Console()


def confirmer(tool: str, args: dict) -> bool:
    console.print(Panel.fit(
        f'[bold yellow]Local tool request[/bold yellow]\nTool: [cyan]{tool}[/cyan]\nArgs: {args}',
        title='Permission Gate', border_style='yellow'
    ))
    return Confirm.ask('Allow this local action?', default=False)


def banner() -> None:
    title = Text('J A R V I S   O M E G A   V3', style='bold cyan')
    provider = 'OpenRouter Free' if settings.provider == 'openrouter' else 'OpenAI'
    subtitle = (
        f'Agent • Free Web • Screen Vision • Memory • Knowledge • Deep Neural Voice • '
        f'Creator: {settings.creator_name} • Provider: {provider}'
    )
    console.print(Panel.fit(Text.assemble(title, '\n', subtitle), border_style='cyan'))
    console.print('[dim]No microphone input. You type; JARVIS reasons, uses tools, answers and speaks.[/dim]\n')


def help_table() -> Table:
    table = Table(title='JARVIS OMEGA V3 Commands', show_header=True, header_style='bold cyan')
    table.add_column('Command')
    table.add_column('Action')
    commands = [
        ('/help', 'Show this command list'),
        ('/new', 'Start a fresh conversation session'),
        ('/status', 'Show provider/model/tools/voice status'),
        ('/screen [prompt]', 'Capture the current screen with approval and analyze it using AI vision'),
        ('/web <query>', 'Free public web search without using paid OpenAI web search'),
        ('/news <query>', 'Search recent public news'),
        ('/remember <text>', 'Save a fact to local long-term memory'),
        ('/recall <query>', 'Search local long-term memory'),
        ('/learn <file>', 'Index an approved local text/code file into JARVIS knowledge'),
        ('/knowledge <query>', 'Search indexed local knowledge'),
        ('/history [n]', 'Show recent messages from this session'),
        ('/export', 'Export this chat to Markdown in the exports folder'),
        ('/stats', 'Show memory/knowledge statistics'),
        ('/voice-test [hinglish|hindi|english]', 'Test the deep neural voice'),
        ('/mute', 'Mute spoken replies'),
        ('/unmute', 'Enable spoken replies'),
        ('/clear', 'Clear the terminal display'),
        ('/sessions', 'Show recent chat sessions'),
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
            console.print(help_table())
            continue
        if low == '/clear':
            console.clear()
            banner()
            continue
        if low == '/new':
            sid = jarvis.new_session()
            console.print(f'[green]New session:[/green] {sid}')
            continue
        if low == '/status':
            provider = 'OpenRouter Free' if settings.provider == 'openrouter' else 'OpenAI'
            console.print(Panel(
                f'Provider: {provider}\nConfigured model: {settings.model}\nLast model used: {jarvis.last_model_used}\n'
                f'Tool mode: {jarvis.last_tool_mode}\n'
                f'Reasoning setting: {settings.reasoning_effort if settings.provider == "openai" else "provider-managed"}\n'
                f'Free custom web search: {settings.enable_public_web_tools}\n'
                f'Screen vision: {settings.provider == "openrouter"}\n'
                f'Hosted web search: {settings.hosted_web_search_enabled}\n'
                f'Code Interpreter: {settings.code_interpreter_enabled}\n'
                f'Local tools: {settings.enable_local_tools}\n'
                f'Voice output: {settings.enable_voice_output and not voice.muted}\nVoice engine: {settings.voice_engine}\n'
                f'Hindi voice: {settings.voice_hindi}\nHinglish voice: {settings.voice_hinglish}\n'
                f'Voice rate/pitch: {settings.edge_voice_rate} / {settings.edge_voice_pitch}\n'
                f'Microphone input: False\nSession: {jarvis.session_id}\n'
                f'Last latency: {jarvis.last_latency:.2f}s',
                title='OMEGA V3 Status', border_style='green'))
            continue

        if low.startswith('/screen'):
            prompt = text[len('/screen'):].strip() or 'Analyze this screenshot. Tell me what is visible, identify any errors or important UI state, and explain what I should do next.'
            decision = jarvis.tools.permissions.check('capture_screen', {'purpose': prompt})
            if not decision.allowed:
                console.print(f'[yellow]{decision.reason}[/yellow]')
                continue
            try:
                with console.status('[cyan]Capturing and analyzing screen...[/cyan]'):
                    screenshot = capture_screen()
                    answer = jarvis.analyze_image(screenshot, prompt)
                console.print(Panel(Markdown(answer), title=f'JARVIS VISION • {screenshot.name}', border_style='magenta'))
                voice.speak(answer)
            except Exception as exc:
                console.print(Panel(str(exc), title='Screen Vision Error', border_style='red'))
            continue

        if low.startswith('/web '):
            query = text[5:].strip()
            try:
                with console.status('[cyan]Searching the web...[/cyan]'):
                    results = search_web(query, 7)
                _print_search_results('Free Web Search', results)
            except Exception as exc:
                console.print(f'[red]Web search failed:[/red] {exc}')
            continue
        if low.startswith('/news '):
            query = text[6:].strip()
            try:
                with console.status('[cyan]Searching recent news...[/cyan]'):
                    results = search_news(query, 7, 'w')
                _print_search_results('Recent News', results)
            except Exception as exc:
                console.print(f'[red]News search failed:[/red] {exc}')
            continue

        if low.startswith('/remember '):
            console.print(jarvis.memory.remember(text[len('/remember '):]))
            continue
        if low.startswith('/recall '):
            facts = jarvis.memory.recall(text[len('/recall '):], 10)
            console.print('\n'.join(f'• {f}' for f in facts) if facts else '[dim]No matching memories.[/dim]')
            continue
        if low.startswith('/learn '):
            path = text[len('/learn '):].strip().strip('"')
            result = jarvis.tools.call('index_local_text_file', {'file_path': path})
            console.print(Panel(result, title='Knowledge Import', border_style='magenta'))
            continue
        if low.startswith('/knowledge '):
            query = text[len('/knowledge '):].strip()
            rows = jarvis.memory.search_knowledge(query, 8)
            if not rows:
                console.print('[dim]No matching indexed knowledge.[/dim]')
            else:
                table = Table('Score', 'Source', 'Chunk', 'Preview', title='Local Knowledge')
                for row in rows:
                    table.add_row(str(row['score']), row['source'], str(row['chunk_index']), row['content'][:300])
                console.print(table)
            continue
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
            target = jarvis.memory.export_session(jarvis.session_id, settings.export_dir)
            console.print(f'[green]Exported:[/green] {target}')
            continue
        if low == '/stats':
            console.print(Panel(json.dumps(jarvis.memory.stats(), indent=2), title='Memory & Knowledge Stats', border_style='magenta'))
            continue

        if low.startswith('/voice-test'):
            parts = text.split(maxsplit=1)
            mode = parts[1].strip().lower() if len(parts) > 1 else 'hinglish'
            voice.test(mode)
            console.print(f'[cyan]Voice test queued:[/cyan] {mode}')
            continue
        if low == '/mute':
            voice.mute()
            console.print('[yellow]Spoken replies muted.[/yellow]')
            continue
        if low == '/unmute':
            voice.unmute()
            console.print('[green]Spoken replies enabled.[/green]')
            voice.test('hinglish')
            continue

        if low == '/sessions':
            rows = jarvis.memory.list_sessions()
            table = Table('ID', 'Title', 'Created')
            for row in rows:
                table.add_row(row['id'], row['title'], row['created_at'])
            console.print(table)
            continue

        with console.status('[cyan]JARVIS is thinking...[/cyan]', spinner='dots12'):
            try:
                answer = jarvis.chat(text)
            except Exception as exc:
                console.print(Panel(str(exc), title='JARVIS Error', border_style='red'))
                continue

        console.print(Panel(Markdown(answer), title='JARVIS', border_style='cyan'))
        voice.speak(answer)
