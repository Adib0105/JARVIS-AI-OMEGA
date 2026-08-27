from __future__ import annotations

import os
import re
import tempfile
import tkinter as tk
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk

from .product_paths import PATHS, config_env_path

_SUPPORTED_PROVIDERS = {'openrouter', 'openai'}
_PLACEHOLDER_MARKERS = ('put_your_', 'your_api_key', 'changeme', 'example')
_KEY_NAMES = {'openrouter': 'OPENROUTER_API_KEY', 'openai': 'OPENAI_API_KEY'}
_MODEL_NAMES = {'openrouter': 'OPENROUTER_MODEL', 'openai': 'OPENAI_MODEL'}
_DEFAULT_MODELS = {'openrouter': 'openrouter/free', 'openai': 'gpt-5.6'}
_MODELS_URL = {'openrouter': 'https://openrouter.ai/api/v1/models', 'openai': 'https://api.openai.com/v1/models'}


@dataclass(frozen=True)
class BootstrapState:
    provider: str
    key_present: bool
    model_present: bool
    config_path: Path
    local_fallback_configured: bool
    ready: bool
    reason: str


def _parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding='utf-8', errors='replace').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        if re.fullmatch(r'[A-Z0-9_]+', key):
            values[key] = value.strip().strip('"').strip("'")
    return values


def _is_real_key(value: str) -> bool:
    value = str(value or '').strip()
    if not value:
        return False
    lower = value.lower()
    return not any(marker in lower for marker in _PLACEHOLDER_MARKERS)


def inspect_bootstrap_state(path: Path | None = None, environ: dict[str, str] | None = None) -> BootstrapState:
    path = path or config_env_path()
    file_values = _parse_env(path)
    env = dict(os.environ if environ is None else environ)
    merged = {**file_values, **{k: v for k, v in env.items() if v is not None}}
    provider = merged.get('AI_PROVIDER', 'openrouter').strip().lower()
    if provider not in _SUPPORTED_PROVIDERS:
        return BootstrapState(provider, False, False, path, False, False, 'AI provider must be openrouter or openai.')
    key = merged.get(_KEY_NAMES[provider], '')
    model = merged.get(_MODEL_NAMES[provider], _DEFAULT_MODELS[provider]).strip()
    local_ready = (
        merged.get('ENABLE_LOCAL_FALLBACK', 'false').strip().lower() in {'1', 'true', 'yes', 'on'}
        and bool(merged.get('LOCAL_AI_BASE_URL', '').strip())
        and bool(merged.get('LOCAL_AI_MODEL', '').strip())
    )
    key_ok = _is_real_key(key)
    model_ok = bool(model)
    if not key_ok:
        reason = f'{provider} API key is required before online AI can be used.'
    elif not model_ok:
        reason = f'{provider} model must be configured.'
    else:
        reason = 'Configuration is ready.'
    return BootstrapState(provider, key_ok, model_ok, path, local_ready, key_ok and model_ok, reason)


def _replace_env_values(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding='utf-8', errors='replace').splitlines() if path.exists() else []
    clean = {str(k).strip(): str(v).strip() for k, v in values.items()}
    out: list[str] = []
    seen: set[str] = set()
    pattern = re.compile(r'^\s*([A-Z0-9_]+)\s*=')
    for line in existing:
        match = pattern.match(line)
        key = match.group(1) if match else None
        if key in clean:
            out.append(f'{key}={clean[key]}')
            seen.add(key)
        else:
            out.append(line)
    if out and out[-1].strip():
        out.append('')
    for key, value in clean.items():
        if key not in seen:
            out.append(f'{key}={value}')
    text = '\n'.join(out).rstrip() + '\n'
    fd, temp_name = tempfile.mkstemp(prefix='.env.', dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(text)
        try:
            os.chmod(temp_name, 0o600)
        except OSError:
            pass
        os.replace(temp_name, path)
    finally:
        try:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        except OSError:
            pass


def save_ai_configuration(provider: str, api_key: str, model: str = '', path: Path | None = None) -> Path:
    provider = provider.strip().lower()
    if provider not in _SUPPORTED_PROVIDERS:
        raise ValueError('Provider must be openrouter or openai.')
    if not _is_real_key(api_key):
        raise ValueError(f'{provider} API key is missing or still a placeholder.')
    model = model.strip() or _DEFAULT_MODELS[provider]
    target = path or config_env_path()
    values = {
        'AI_PROVIDER': provider,
        _KEY_NAMES[provider]: api_key.strip(),
        _MODEL_NAMES[provider]: model,
    }
    _replace_env_values(target, values)
    return target


def test_provider_connection(provider: str, api_key: str, opener=urllib.request.urlopen) -> tuple[bool, str]:
    provider = provider.strip().lower()
    if provider not in _SUPPORTED_PROVIDERS:
        return False, 'Unsupported provider configuration.'
    if not _is_real_key(api_key):
        return False, 'API key is missing or still a placeholder.'
    request = urllib.request.Request(
        _MODELS_URL[provider],
        headers={'Authorization': f'Bearer {api_key.strip()}', 'User-Agent': 'JARVIS-AI-OMEGA/first-run'},
        method='GET',
    )
    try:
        with opener(request, timeout=12) as response:
            status = int(getattr(response, 'status', 200))
        if 200 <= status < 300:
            return True, f'{provider} connection succeeded.'
        return False, f'{provider} returned HTTP {status}.'
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            return False, f'{provider} rejected the credential. Check or recreate the key.'
        return False, f'{provider} connection returned HTTP {exc.code}.'
    except (urllib.error.URLError, TimeoutError, OSError):
        return False, 'Could not reach the provider. Check internet/network access and retry.'


def run_first_run_setup() -> bool:
    state = inspect_bootstrap_state()
    if state.ready:
        return True

    root = tk.Tk()
    root.title('JARVIS AI OMEGA // FIRST-RUN SETUP')
    root.geometry('650x560')
    root.minsize(620, 520)
    root.configure(bg='#06111a')

    provider_var = tk.StringVar(value=state.provider if state.provider in _SUPPORTED_PROVIDERS else 'openrouter')
    key_var = tk.StringVar(value='')
    model_var = tk.StringVar(value=_DEFAULT_MODELS[provider_var.get()])
    result = {'launch': False}

    tk.Label(root, text='JARVIS AI OMEGA // FIRST-RUN SETUP', bg='#06111a', fg='#53e7ff', font=('Segoe UI', 16, 'bold')).pack(anchor='w', padx=22, pady=(20, 8))
    info = (
        'Online AI needs a provider credential so JARVIS can send your AI requests to the selected service. '
        'The key is stored only in your writable per-user configuration folder, never in Program Files or the application bundle.\n\n'
        f'Configuration file:\n{state.config_path}\n\n'
        'Without a valid online key, online chat/vision/planning remain unavailable. '
        + ('A local fallback is configured, but this build still uses the online provider as its primary AI path.' if state.local_fallback_configured else 'No local/offline AI fallback is currently configured.')
    )
    tk.Label(root, text=info, bg='#06111a', fg='#dff9ff', justify='left', wraplength=595, font=('Segoe UI', 10)).pack(anchor='w', padx=22, pady=(0, 16))

    form = tk.Frame(root, bg='#091a26', padx=16, pady=14)
    form.pack(fill='x', padx=22)
    tk.Label(form, text='Provider', bg='#091a26', fg='#86a8b8').grid(row=0, column=0, sticky='w', pady=5)
    provider_box = ttk.Combobox(form, textvariable=provider_var, values=('openrouter', 'openai'), state='readonly', width=38)
    provider_box.grid(row=0, column=1, sticky='ew', pady=5)
    tk.Label(form, text='API key', bg='#091a26', fg='#86a8b8').grid(row=1, column=0, sticky='w', pady=5)
    tk.Entry(form, textvariable=key_var, show='•', bg='#07131d', fg='white', insertbackground='#53e7ff', relief='flat', width=42).grid(row=1, column=1, sticky='ew', pady=5, ipady=5)
    tk.Label(form, text='Model', bg='#091a26', fg='#86a8b8').grid(row=2, column=0, sticky='w', pady=5)
    tk.Entry(form, textvariable=model_var, bg='#07131d', fg='white', insertbackground='#53e7ff', relief='flat', width=42).grid(row=2, column=1, sticky='ew', pady=5, ipady=5)
    form.columnconfigure(1, weight=1)

    status_var = tk.StringVar(value=state.reason)
    tk.Label(root, textvariable=status_var, bg='#06111a', fg='#ffd166', justify='left', wraplength=595).pack(anchor='w', padx=22, pady=(14, 8))

    def provider_changed(_event=None):
        model_var.set(_DEFAULT_MODELS[provider_var.get()])
    provider_box.bind('<<ComboboxSelected>>', provider_changed)

    def test_connection():
        ok, message = test_provider_connection(provider_var.get(), key_var.get())
        status_var.set(message)
        if ok:
            messagebox.showinfo('Test Connection', message, parent=root)
        else:
            messagebox.showwarning('Test Connection', message, parent=root)

    def save_and_launch():
        try:
            save_ai_configuration(provider_var.get(), key_var.get(), model_var.get())
        except Exception as exc:
            status_var.set(str(exc))
            messagebox.showerror('Configuration', str(exc), parent=root)
            return
        result['launch'] = True
        root.destroy()

    buttons = tk.Frame(root, bg='#06111a')
    buttons.pack(fill='x', padx=22, pady=12)
    tk.Button(buttons, text='TEST CONNECTION', command=test_connection, bg='#0b2a3a', fg='#53e7ff', relief='flat', padx=12, pady=8).pack(side='left')
    tk.Button(buttons, text='SAVE & LAUNCH', command=save_and_launch, bg='#0b2a3a', fg='#6affb8', relief='flat', padx=12, pady=8).pack(side='left', padx=8)
    tk.Button(buttons, text='EXIT', command=root.destroy, bg='#0b2a3a', fg='#ff5c73', relief='flat', padx=12, pady=8).pack(side='right')

    root.protocol('WM_DELETE_WINDOW', root.destroy)
    root.mainloop()
    return bool(result['launch'])
