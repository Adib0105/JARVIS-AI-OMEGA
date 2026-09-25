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

from .security.redaction import redact_text, redact_value


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
            payload['event'] = redact_text(str(event))
        if category:
            payload['category'] = redact_text(str(category))
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
            sys.stderr.write(redact_text(''.join(traceback.format_exception(exc_type, exc, tb))))

    sys.excepthook = hook
