"""Unattended candidate import/Tk health check before an updater relaunch.

Uses temporary profile state; never migrates or restores a user's database.
"""
import json
import os
from pathlib import Path
import tempfile


def main(report_path):
    result = {'ok': False}
    try:
        with tempfile.TemporaryDirectory(prefix='jarvis-candidate-health-') as folder:
            os.environ['JARVIS_ACTIVE_DATA_DIR'] = folder
            os.environ['ENABLE_MIC_INPUT'] = 'false'
            os.environ['ENABLE_VOICE_OUTPUT'] = 'false'
            from . import __version__
            from . import core, background_ui, account_ui, documents, voice
            from .storage import TARGET_SCHEMA_VERSION
            import tkinter
            root = tkinter.Tk()
            try:
                root.withdraw()
                root.update_idletasks()
                result = {'ok': True, 'version': __version__, 'schema': TARGET_SCHEMA_VERSION,
                          'test': 'candidate-imports-and-tk', 'user_database_opened': False}
            finally:
                root.destroy()
    except Exception as exc:
        result['error_type'] = type(exc).__name__
    Path(report_path).write_text(json.dumps(result), encoding='utf-8')
    return 0 if result['ok'] else 1
