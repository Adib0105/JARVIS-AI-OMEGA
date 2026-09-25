"""Atomic connection persistence and live provider replacement without losing chat state."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import threading
from functools import wraps

_CONNECTION_LOCK = threading.RLock()

def serialized_connection(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with _CONNECTION_LOCK:
            return function(*args, **kwargs)
    return wrapped

from dotenv import dotenv_values, set_key
from .config import ROOT, settings
from .providers.factory import create_primary_provider
from .providers.observed import ObservedProvider

KEY_FIELDS = {'openrouter': 'openrouter_api_key', 'openai': 'openai_api_key'}
ROUTES = ('fast_model', 'smart_model', 'vision_model', 'coding_model', 'planning_model', 'review_model', 'summary_model')


class ConnectionInputError(ValueError):
    pass


def read_connection_file(path=None):
    path = Path(path) if path is not None else ROOT / '.env'
    return dict(dotenv_values(path, encoding='utf-8-sig', interpolate=False)) if path.exists() else {}


def atomic_save(path, values):
    path = Path(path)
    content = path.read_text(encoding='utf-8-sig') if path.exists() else ''
    descriptor, name = tempfile.mkstemp(prefix='.jarvis-connection-', dir=path.parent)
    staged = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            handle.write(content)
        for key, value in values.items():
            set_key(str(staged), key, value, encoding='utf-8')
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)


def close_client(provider):
    client = getattr(provider, 'client', None)
    if client is not None:
        try:
            client.close()
        except Exception:
            pass


@serialized_connection
def save_and_apply(core, provider, key='', model=None, path=None):
    """Call only while no request is running. Applying is not online authentication."""
    if provider not in KEY_FIELDS:
        raise ConnectionInputError('Choose OpenRouter or OpenAI.')
    path = Path(path) if path is not None else ROOT / '.env'
    field = KEY_FIELDS[provider]
    saved = read_connection_file(path)
    value = key.strip() or saved.get(field.upper()) or getattr(settings, field)
    if not value or any(c.isspace() for c in value) or '\0' in value or '=' in value:
        raise ConnectionInputError('Paste only the API key, without spaces or an API_KEY= prefix.')
    if provider == 'openai' and value.startswith('sk-or-'):
        raise ConnectionInputError('This is an OpenRouter key. Choose OpenRouter, not OpenAI.')
    model_field = provider + '_model'
    selected_model = str(model if model is not None else getattr(settings, model_field)).strip()
    if not selected_model or any(c in selected_model for c in '\r\n\0'):
        raise ConnectionInputError('Enter a single-line model identifier.')
    fields = {'provider': provider, field: value, model_field: selected_model}
    if provider != settings.provider:
        fields.update({route: '' for route in ROUTES})
    candidate = replace(settings, **fields)
    new_provider = create_primary_provider(candidate)
    try:
        observed = ObservedProvider(new_provider, core.observability, context_provider=core._model_observability_context)
        values = {('AI_PROVIDER' if name == 'provider' else name.upper()): val for name, val in fields.items()}
        atomic_save(path, values)
    except Exception:
        close_client(new_provider)
        raise
    old_provider = core.provider
    # Imported modules retain this shared object; rebinding settings leaves stale keys.
    for name, val in fields.items():
        object.__setattr__(settings, name, val)
    os.environ.update(values)
    core.provider = observed
    core.client = observed.client
    core.last_provider_used = provider
    core.last_model_used = candidate.model
    core._active_model = candidate.model
    close_client(old_provider)
    return 'Connection saved and applied now. Online validity has not been tested yet.'


def test_connection(core):
    model = core._select_model('Hello', 'chat')
    result = core.provider.chat(system='Reply only OK.', messages=[{'role': 'user', 'content': 'Reply OK.'}], model=model, timeout=12)
    if not result.text.strip():
        raise RuntimeError('Provider returned no text. Check model availability.')
    return 'AI reply received successfully. Your active connection works.'
