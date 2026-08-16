from __future__ import annotations

import importlib.util
import os
import shutil
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from ..capability_registry import CapabilityRegistry
from ..config import ROOT, settings
from ..storage.sqlite_utils import connect_sqlite


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


class HealthStatus(str, Enum):
    PASS = 'PASS'
    WARNING = 'WARNING'
    FAIL = 'FAIL'


@dataclass(frozen=True)
class HealthCheck:
    name: str
    status: HealthStatus
    detail: str
    required: bool = True

    def as_dict(self) -> dict:
        data = asdict(self)
        data['status'] = self.status.value
        return data


@dataclass(frozen=True)
class HealthReport:
    status: HealthStatus
    created_at: str
    checks: tuple[HealthCheck, ...]

    def as_dict(self) -> dict:
        return {
            'status': self.status.value,
            'created_at': self.created_at,
            'checks': [item.as_dict() for item in self.checks],
            'counts': {
                'PASS': sum(1 for item in self.checks if item.status == HealthStatus.PASS),
                'WARNING': sum(1 for item in self.checks if item.status == HealthStatus.WARNING),
                'FAIL': sum(1 for item in self.checks if item.status == HealthStatus.FAIL),
            },
        }


class JarvisHealthSystem:
    """Truthful local health check. No network reachability is invented.

    Provider configuration can PASS as configured, but remote reachability remains
    explicitly unverified unless a separate live request has produced observability
    evidence. Optional systems produce WARNING rather than taking core chat down.
    """

    def __init__(self, db_path: Path | None = None, *, registry: CapabilityRegistry | None = None) -> None:
        self.db_path = db_path or settings.db_path
        self.registry = registry or CapabilityRegistry()

    @staticmethod
    def _check(name: str, ok: bool, detail: str, *, required: bool = True, warning_if_false: bool = False) -> HealthCheck:
        if ok:
            status = HealthStatus.PASS
        elif warning_if_false or not required:
            status = HealthStatus.WARNING
        else:
            status = HealthStatus.FAIL
        return HealthCheck(name, status, detail, required)

    def _database(self) -> HealthCheck:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with connect_sqlite(self.db_path, timeout=10) as conn:
                result = conn.execute('PRAGMA quick_check').fetchone()[0]
            return self._check('Database', result == 'ok', f'PRAGMA quick_check={result}; {self.db_path}')
        except Exception as exc:
            return self._check('Database', False, f'{type(exc).__name__}: {exc}')

    def _provider(self) -> HealthCheck:
        placeholders = {'put_your_openrouter_key_here', 'put_your_api_key_here', 'YAHAN_APNI_OPENROUTER_KEY'}
        key_ok = bool(settings.api_key and settings.api_key not in placeholders)
        local_ok = bool(settings.enable_local_fallback and settings.local_ai_model.strip())
        if key_ok:
            return HealthCheck(
                'AI Provider', HealthStatus.PASS,
                f'{settings.provider}/{settings.model} configured; remote reachability is not probed by local health check.', True,
            )
        if local_ok:
            return HealthCheck(
                'AI Provider', HealthStatus.WARNING,
                f'hosted key unavailable; local fallback configured as {settings.local_ai_model}; endpoint reachability unverified.', True,
            )
        return HealthCheck('AI Provider', HealthStatus.FAIL, 'No usable hosted API key or configured local fallback model.', True)

    def _local_ai(self) -> HealthCheck:
        configured = bool(settings.local_ai_model.strip() and settings.local_ai_base_url.strip())
        if configured:
            return HealthCheck(
                'Local AI', HealthStatus.PASS,
                f'{settings.local_model_provider}: {settings.local_ai_model} @ {settings.local_ai_base_url}; endpoint not actively probed.', False,
            )
        return HealthCheck('Local AI', HealthStatus.WARNING, 'No local reasoning model configured.', False)

    def _computer_use(self) -> HealthCheck:
        if not settings.enable_desktop_automation:
            return HealthCheck('Computer Use', HealthStatus.WARNING, 'Desktop automation disabled by configuration.', False)
        if os.name != 'nt':
            return HealthCheck('Computer Use', HealthStatus.WARNING, 'Semantic Windows UI Automation is only available on Windows.', False)
        try:
            from ..computer_use.windows_ui import WindowsUIBackend
            backend = WindowsUIBackend().status()
            if backend.available:
                return HealthCheck('Computer Use', HealthStatus.PASS, f'{backend.backend}: {backend.detail}', False)
            fallback = _module('pyautogui')
            return HealthCheck(
                'Computer Use', HealthStatus.WARNING if fallback else HealthStatus.FAIL,
                f'UIA unavailable: {backend.detail}; coordinate fallback={fallback}', False,
            )
        except Exception as exc:
            return HealthCheck('Computer Use', HealthStatus.WARNING, f'{type(exc).__name__}: {exc}', False)

    def _vision(self) -> HealthCheck:
        ok = _module('PIL') and settings.max_image_attachments >= 1
        detail = 'Pillow/image pipeline loaded; live model vision support depends on selected model.' if ok else 'Image pipeline dependency/config unavailable.'
        return self._check('Vision', ok, detail, required=False, warning_if_false=True)

    def _voice(self) -> HealthCheck:
        if not settings.enable_voice_output:
            return HealthCheck('Voice', HealthStatus.WARNING, 'Voice output disabled by configuration.', False)
        ok = _module('edge_tts') or _module('pyttsx3')
        return self._check('Voice', ok, f'engine={settings.voice_engine}; edge_tts={_module("edge_tts")}; pyttsx3={_module("pyttsx3")}', required=False, warning_if_false=True)

    def _microphone(self) -> HealthCheck:
        if not settings.enable_mic_input:
            return HealthCheck('Microphone', HealthStatus.WARNING, 'Microphone input disabled by configuration.', False)
        libs = _module('sounddevice') and _module('speech_recognition')
        return self._check(
            'Microphone', libs,
            'speech libraries installed; physical microphone device is verified only during recording.' if libs else 'sounddevice/SpeechRecognition dependency missing.',
            required=False, warning_if_false=True,
        )

    def _google(self) -> HealthCheck:
        if not settings.enable_google_workspace:
            return HealthCheck('Google Workspace', HealthStatus.WARNING, 'Optional Google Workspace integration is disabled.', False)
        libs = _module('google.oauth2.credentials') and _module('googleapiclient.discovery')
        creds = Path(settings.google_credentials_file).exists()
        if libs and creds:
            return HealthCheck('Google Workspace', HealthStatus.PASS, 'OAuth libraries/client file present; live user authorization may still be required.', False)
        return HealthCheck('Google Workspace', HealthStatus.WARNING, f'libs={libs}; client_credentials={creds}', False)

    def _coding(self) -> HealthCheck:
        git_ok = bool(shutil.which('git'))
        enabled = settings.enable_coding_tools
        if enabled and git_ok:
            return HealthCheck('Coding Environment', HealthStatus.PASS, 'Coding tools enabled; Git executable found.', False)
        return HealthCheck('Coding Environment', HealthStatus.WARNING, f'coding_enabled={enabled}; git={git_ok}', False)

    def _filesystem(self) -> HealthCheck:
        roots = [path for path in settings.allowed_file_roots if path.exists()]
        writable_db = self.db_path.parent.exists() and os.access(self.db_path.parent, os.W_OK)
        ok = bool(roots) and writable_db
        return self._check(
            'Filesystem', ok,
            f'allowed_roots={len(roots)}; db_parent_writable={writable_db}',
            required=True,
        )

    def _self_development(self) -> HealthCheck:
        if not settings.self_development_enabled:
            return HealthCheck('Self Development', HealthStatus.WARNING, 'Controlled self-development disabled.', False)
        package = _module('jarvis.self_development.engine')
        git_ok = bool(shutil.which('git'))
        repo = (ROOT / '.git').exists()
        if package and git_ok and repo:
            return HealthCheck('Self Development', HealthStatus.PASS, 'sandbox package + Git + repository checkout available; production activation remains approval-gated.', False)
        return HealthCheck('Self Development', HealthStatus.WARNING, f'package={package}; git={git_ok}; repo_checkout={repo}', False)

    def _sandbox(self) -> HealthCheck:
        workspace = ROOT / 'workspace'
        try:
            workspace.mkdir(parents=True, exist_ok=True)
            test = workspace / '.health-write-test'
            test.write_text('ok', encoding='utf-8')
            test.unlink(missing_ok=True)
            return HealthCheck('Sandbox', HealthStatus.PASS, f'workspace writable: {workspace}', False)
        except Exception as exc:
            return HealthCheck('Sandbox', HealthStatus.WARNING, f'{type(exc).__name__}: {exc}', False)

    def _git(self) -> HealthCheck:
        git = shutil.which('git')
        repo = (ROOT / '.git').exists()
        return self._check('Git', bool(git and repo), f'executable={git or "missing"}; repo_checkout={repo}', required=False, warning_if_false=True)

    def run(self) -> HealthReport:
        checks: list[HealthCheck] = [
            self._check('Python', sys.version_info >= (3, 10), f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'),
            self._provider(),
            self._local_ai(),
            self._database(),
            self._filesystem(),
            self._vision(),
            self._voice(),
            self._microphone(),
            self._google(),
            self._coding(),
            self._computer_use(),
            self._self_development(),
            self._sandbox(),
            self._git(),
        ]

        for item in self.registry.snapshot():
            status = item['status']
            if status == 'BROKEN':
                checks.append(HealthCheck(f"Capability:{item['name']}", HealthStatus.FAIL, item.get('detail') or 'capability broken', False))
            elif status in {'MISSING', 'DEGRADED'}:
                checks.append(HealthCheck(f"Capability:{item['name']}", HealthStatus.WARNING, item.get('detail') or status, False))

        if any(item.status == HealthStatus.FAIL and item.required for item in checks):
            overall = HealthStatus.FAIL
        elif any(item.status in {HealthStatus.FAIL, HealthStatus.WARNING} for item in checks):
            overall = HealthStatus.WARNING
        else:
            overall = HealthStatus.PASS
        return HealthReport(overall, _now(), tuple(checks))
