from __future__ import annotations

import logging
import sys
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler

from .config import ROOT


LOG_DIR = ROOT / 'data' / 'logs'
CRASH_DIR = ROOT / 'data' / 'crash-reports'


def configure_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger('jarvis')
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        LOG_DIR / 'jarvis-v6.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8'
    )
    handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s'))
    logger.addHandler(handler)
    logger.propagate = False
    logger.info('JARVIS OMEGA V6 logging initialized')
    return logger


def write_crash_report(exc_type, exc, tb) -> str:
    CRASH_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    target = CRASH_DIR / f'crash-{stamp}.txt'
    target.write_text(''.join(traceback.format_exception(exc_type, exc, tb)), encoding='utf-8')
    return str(target)


def install_exception_hook() -> None:
    logger = configure_logging()
    original = sys.excepthook

    def hook(exc_type, exc, tb):
        try:
            target = write_crash_report(exc_type, exc, tb)
            logger.exception('Unhandled exception. Crash report: %s', target, exc_info=(exc_type, exc, tb))
        finally:
            original(exc_type, exc, tb)

    sys.excepthook = hook
