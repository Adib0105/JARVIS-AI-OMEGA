from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from .config import settings
from .core import JarvisOmega
from .voice import VoiceOutput

console = Console()


def confirmer(tool: str, args: dict) -> bool:
    console.print(Panel.fit(
        f'[bold yellow]Local tool request[/bold yellow]\nTool: [cyan]{tool}[/cyan]\nArgs: {args}',
        title='Permission Gate', border_style='yellow'
    ))
    return Confirm.ask('Allow this local action?', default=False)


def banner() -> None:
    title = Text('J A R V I S   O M E G A', style='bold cyan')
    subtitle = f'Type commands • Spoken AI replies • Creator: {settings.creator_name} • Model: {settings.model}'
    console.print(Panel.fit(Text.assemble(title, '\n', subtitle), border_style='cyan'))
    console.print('[dim]Type /help for commands. Microphone/voice input is not installed; you type, JARVIS speaks its reply.[/dim]\n')


def help_table() -> Table:
    table = Table(title='JARVIS OMEGA Commands', show_header=True, header_style='bold cyan')
    table.add_column('Command')
    table.add_column('Action')
    for cmd, desc in [
        ('/help', 'Show this command list'),
        ('/new', 'Start a fresh conversation session'),
        ('/status', 'Show model/features/session status'),
        ('/remember <text>', 'Save a fact to local long-term memory'),
        ('/recall <query>', 'Search local long-term memory'),
        ('/sessions', 'Show recent chat sessions'),
        ('/exit', 'Close JARVIS'),
    ]:
        table.add_row(cmd, desc)
    return table


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
        if low == '/new':
            sid = jarvis.new_session()
            console.print(f'[green]New session:[/green] {sid}')
            continue
        if low == '/status':
            console.print(Panel(
                f'Model: {settings.model}\nReasoning: {settings.reasoning_effort}\n'
                f'Web search: {settings.enable_web_search}\nCode Interpreter: {settings.enable_code_interpreter}\n'
                f'Local tools: {settings.enable_local_tools}\nVoice output: {settings.enable_voice_output}\n'
                f'Microphone input: False\nSession: {jarvis.session_id}\n'
                f'Last latency: {jarvis.last_latency:.2f}s',
                title='Status', border_style='green'))
            continue
        if low.startswith('/remember '):
            console.print(jarvis.memory.remember(text[len('/remember '):]))
            continue
        if low.startswith('/recall '):
            facts = jarvis.memory.recall(text[len('/recall '):], 10)
            console.print('\n'.join(f'• {f}' for f in facts) if facts else '[dim]No matching memories.[/dim]')
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
                console.print(Panel(f'{type(exc).__name__}: {exc}', title='JARVIS Error', border_style='red'))
                continue

        console.print(Panel(Markdown(answer), title='JARVIS', border_style='cyan'))
        voice.speak(answer)
