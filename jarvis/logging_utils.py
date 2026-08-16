from __future__ import annotations

import json
import logging
import re
import sys
import traceback
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any

from .config import ROOT, settings

LOG_DIR = ROOT / 'data' / 'logs'
CRASH_DIR = ROOT / 'data' / 'crash-reports'

_SECRET_KEY_RE = re.compile(
    r'(?i)(api[_-]?key|authorization|password|passwd|secret|token|refresh[_-]?token|access[_-]?token)'
)
_SECRET_VALUE_PATTERNS = [
    re.compile(r'\bsk-[A-Za-z0-9_-]{12,}\b'),
    re.compile(r'\bsk-or-v1-[A-Za-z0-9_-]{12,}\b'),
    re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{12,}'),
]


def redact_text(value: str) -> str:
    text = str(value)
    for pattern in _SECRET_VALUE_PATTERNS:
        if 'bearer' in pattern.pattern.lower():
            text = pattern.sub(r'\1[REDACTED]', text)
        else:
            text = pattern.sub('[REDACTED]', text)
    text = re.sub(
        r'(?i)\b(api[_-]?key|password|passwd|secret|token|refresh[_-]?token|access[_-]?token)\s*[:=]\s*[^\s,;]+',
        lambda match: f'{match.group(1)}=[REDACTED]',
        text,
    )
    return text


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            if _SECRET_KEY_RE.search(str(key)):
                clean[str(key)] = '[REDACTED]'
            else:
                clean[str(key)] = redact_value(item)
        return clean
    if isinstance(value, (list, tuple, set)):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': redact_text(record.getMessage()),
        }
        event = getattr(record, 'event', None)
        category = getattr(record, 'category', None)
        fields = getattr(record, 'fields', None)
        if event:
            payload['event'] = str(event)
        if category:
            payload['category'] = str(category)
        if fields:
            payload['fields'] = redact_value(fields)
        if record.exc_info:
            payload['exception'] = redact_text(''.join(traceback.format_exception(*record.exc_info)))[-12000:]
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger('jarvis')
    if logger.handlers:
        return logger
    level = getattr(logging, settings.log_level, logging.INFO)
    logger.setLevel(level)
    handler = RotatingFileHandler(
        LOG_DIR / 'jarvis-v7.jsonl', maxBytes=4_000_000, backupCount=5, encoding='utf-8'
    )
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    logger.info(
        'JARVIS OMEGA V7 logging initialized',
        extra={'category': 'INFO', 'event': 'runtime.logging_initialized', 'fields': {'version': settings.app_version}},
    )
    return logger


def log_event(category: str, event: str, message: str = '', **fields: Any) -> None:
    logger = configure_logging()
    level = logging.ERROR if category.upper() in {'ERROR', 'SECURITY'} and fields.get('failed') else logging.INFO
    logger.log(
        level,
        message or event,
        extra={
            'category': category.upper(),
            'event': event,
            'fields': redact_value(fields),
        },
    )


def write_crash_report(exc_type, exc, tb) -> str:
    CRASH_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    target = CRASH_DIR / f'crash-{stamp}.txt'
    trace = ''.join(traceback.format_exception(exc_type, exc, tb))
    target.write_text(redact_text(trace), encoding='utf-8')
    return str(target)


def install_exception_hook() -> None:
    logger = configure_logging()
    original = sys.excepthook

    def hook(exc_type, exc, tb):
        try:
            target = write_crash_report(exc_type, exc, tb)
            logger.error(
                'Unhandled exception',
                exc_info=(exc_type, exc, tb),
                extra={
                    'category': 'ERROR',
                    'event': 'runtime.unhandled_exception',
                    'fields': {'crash_report': target},
                },
            )
        finally:
            original(exc_type, exc, tb)

    sys.excepthook = hook
