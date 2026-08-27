from __future__ import annotations

import json
import logging
import re
import sys
import traceback
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any

from .config import settings
from .product_paths import PATHS

LOG_DIR = PATHS.log_dir
CRASH_DIR = PATHS.crash_dir
_SECRET_KEY_RE = re.compile(r'(?i)(api[_-]?key|authorization|password|passwd|secret|token|refresh[_-]?token|access[_-]?token)')
_SECRET_VALUE_PATTERNS = [re.compile(r'\bsk-[A-Za-z0-9_-]{12,}\b'), re.compile(r'\bsk-or-v1-[A-Za-z0-9_-]{12,}\b'), re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{12,}')]

def redact_text(value: str) -> str:
    text = str(value)
    for pattern in _SECRET_VALUE_PATTERNS:
        text = pattern.sub(r'\1[REDACTED]' if 'bearer' in pattern.pattern.lower() else '[REDACTED]', text)
    return re.sub(r'(?i)\b(api[_-]?key|password|passwd|secret|token|refresh[_-]?token|access[_-]?token)\s*[:=]\s*[^\s,;]+', lambda m: f'{m.group(1)}=[REDACTED]', text)

def redact_value(value: Any) -> Any:
    if isinstance(value, dict): return {str(k): '[REDACTED]' if _SECRET_KEY_RE.search(str(k)) else redact_value(v) for k,v in value.items()}
    if isinstance(value, (list, tuple, set)): return [redact_value(v) for v in value]
    if isinstance(value, str): return redact_text(value)
    return value

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {'timestamp': datetime.now(timezone.utc).isoformat(), 'level': record.levelname, 'logger': record.name, 'message': redact_text(record.getMessage())}
        for key in ('event','category'):
            value = getattr(record, key, None)
            if value: payload[key] = str(value)
        fields = getattr(record, 'fields', None)
        if fields: payload['fields'] = redact_value(fields)
        if record.exc_info: payload['exception'] = redact_text(''.join(traceback.format_exception(*record.exc_info)))[-12000:]
        return json.dumps(payload, ensure_ascii=False, default=str)

def configure_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger('jarvis')
    if logger.handlers: return logger
    logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
    handler = RotatingFileHandler(LOG_DIR / 'jarvis.jsonl', maxBytes=4_000_000, backupCount=5, encoding='utf-8')
    handler.setFormatter(JsonFormatter()); logger.addHandler(handler); logger.propagate = False
    logger.info('JARVIS OMEGA logging initialized', extra={'category':'INFO','event':'runtime.logging_initialized','fields':{'version':settings.app_version}})
    return logger

def log_event(category: str, event: str, message: str = '', **fields: Any) -> None:
    logger = configure_logging(); level = logging.ERROR if category.upper() in {'ERROR','SECURITY'} and fields.get('failed') else logging.INFO
    logger.log(level, message or event, extra={'category':category.upper(),'event':event,'fields':redact_value(fields)})

def write_crash_report(exc_type, exc, tb) -> str:
    CRASH_DIR.mkdir(parents=True, exist_ok=True); stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f'); target = CRASH_DIR / f'crash-{stamp}.txt'; target.write_text(redact_text(''.join(traceback.format_exception(exc_type, exc, tb))), encoding='utf-8'); return str(target)

def install_exception_hook() -> None:
    logger = configure_logging(); original = sys.excepthook
    def hook(exc_type, exc, tb):
        try:
            target = write_crash_report(exc_type, exc, tb); logger.error('Unhandled exception', exc_info=(exc_type,exc,tb), extra={'category':'ERROR','event':'runtime.unhandled_exception','fields':{'crash_report':target}})
        finally: original(exc_type, exc, tb)
    sys.excepthook = hook
