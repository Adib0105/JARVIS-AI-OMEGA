from __future__ import annotations

import importlib.util
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from .config import settings


class CapabilityStatus(str, Enum):
    AVAILABLE = 'AVAILABLE'
    EXPERIMENTAL = 'EXPERIMENTAL'
    DEGRADED = 'DEGRADED'
    DISABLED = 'DISABLED'
    MISSING = 'MISSING'
    BROKEN = 'BROKEN'


@dataclass(frozen=True)
class CapabilityRecord:
    name: str
    version: str
    description: str
    status: CapabilityStatus
    dependencies: tuple[str, ...]
    permissions: tuple[str, ...]
    risk: str
    tests: tuple[str, ...]
    success_rate: float | None
    last_verified: str
    implementation_path: str
    detail: str = ''

    def as_dict(self) -> dict:
        data = asdict(self)
        data['status'] = self.status.value
        return data


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _all_modules(*names: str) -> bool:
    return all(_module(name) for name in names)


def _provider_ready() -> tuple[bool, str]:
    primary_key = bool(settings.api_key.strip())
    if primary_key:
        return True, f'primary provider configured: {settings.provider}'
    if settings.enable_local_fallback and settings.local_ai_model.strip():
        return True, 'local OpenAI-compatible fallback configured'
    return False, 'no configured hosted API key or local fallback model'


class CapabilityRegistry:
    """Runtime-derived registry of what this JARVIS installation can actually do.

    The registry intentionally derives status from code/config/dependency state instead
    of hard-coding every capability as available. Evaluation success rates are left
    unset until measured historical results can be attached by observability/evaluation.
    """

    def __init__(self) -> None:
        self._records: dict[str, CapabilityRecord] = {}
        self.refresh()

    @staticmethod
    def _record(
        name: str,
        description: str,
        status: CapabilityStatus,
        *,
        dependencies: tuple[str, ...] = (),
        permissions: tuple[str, ...] = (),
        risk: str = 'LOW',
        tests: tuple[str, ...] = (),
        implementation_path: str,
        detail: str = '',
        version: str = '1.0',
    ) -> CapabilityRecord:
        return CapabilityRecord(
            name=name,
            version=version,
            description=description,
            status=status,
            dependencies=dependencies,
            permissions=permissions,
            risk=risk,
            tests=tests,
            success_rate=None,
            last_verified=_now(),
            implementation_path=implementation_path,
            detail=detail,
        )

    def refresh(self) -> dict[str, CapabilityRecord]:
        provider_ready, provider_detail = _provider_ready()
        records: dict[str, CapabilityRecord] = {}

        records['Chat'] = self._record(
            'Chat', 'Provider-neutral conversational reasoning and tool calling.',
            CapabilityStatus.AVAILABLE if provider_ready else CapabilityStatus.DEGRADED,
            dependencies=('openai',), permissions=('WEB_READ',), risk='LOW',
            tests=('tests/test_v7_foundation.py', 'tests/test_runtime_guard.py'),
            implementation_path='jarvis/core_v7.py; jarvis/providers/', detail=provider_detail,
        )

        vision_deps = _all_modules('PIL')
        vision_status = CapabilityStatus.AVAILABLE if vision_deps and provider_ready else (
            CapabilityStatus.DEGRADED if vision_deps else CapabilityStatus.MISSING
        )
        records['Vision'] = self._record(
            'Vision', 'Image attachments and permission-gated screen analysis.', vision_status,
            dependencies=('Pillow', 'vision-capable AI model'), permissions=('SCREEN_READ',), risk='MEDIUM',
            tests=('tests/test_attachments.py', 'tests/test_vision.py'),
            implementation_path='jarvis/attachments.py; jarvis/vision.py',
            detail='image pipeline present; provider/model capability is required at runtime',
        )

        records['Memory'] = self._record(
            'Memory', 'Working, episodic, semantic and procedural memory with hybrid retrieval.',
            CapabilityStatus.AVAILABLE,
            dependencies=('sqlite3',), permissions=('MEMORY_READ', 'MEMORY_WRITE'), risk='MEDIUM',
            tests=('tests/test_memory.py', 'tests/test_v7_memory.py'),
            implementation_path='jarvis/memory.py; jarvis/memory_v7.py; jarvis/retrieval.py',
        )

        records['Missions'] = self._record(
            'Missions', 'Persisted mission orchestration with verification, retry, recovery and replanning.',
            CapabilityStatus.AVAILABLE,
            dependencies=('sqlite3',), permissions=('capability-dependent',), risk='MEDIUM',
            tests=('tests/test_v7_missions.py',),
            implementation_path='jarvis/agent/',
        )

        if not settings.enable_desktop_automation:
            computer_status = CapabilityStatus.DISABLED
            computer_detail = 'desktop automation disabled by configuration'
        elif os.name != 'nt':
            computer_status = CapabilityStatus.DEGRADED
            computer_detail = 'semantic Windows UI Automation requires Windows; non-Windows runtime can only test logic'
        else:
            try:
                from .computer_use.windows_ui import WindowsUIBackend
                backend = WindowsUIBackend().status()
                if backend.available:
                    computer_status = CapabilityStatus.AVAILABLE
                    computer_detail = backend.detail
                elif _module('pyautogui'):
                    computer_status = CapabilityStatus.DEGRADED
                    computer_detail = f'UIA unavailable ({backend.detail}); coordinate fallback available'
                else:
                    computer_status = CapabilityStatus.MISSING
                    computer_detail = f'UIA unavailable ({backend.detail}) and coordinate fallback dependency missing'
            except Exception as exc:
                computer_status = CapabilityStatus.BROKEN
                computer_detail = f'{type(exc).__name__}: {exc}'
        records['Computer Use'] = self._record(
            'Computer Use', 'Semantic Windows UI targeting with confidence thresholds and verified actions.',
            computer_status,
            dependencies=('pywinauto (semantic UIA)', 'pyautogui (fallback)'),
            permissions=('APP_CONTROL', 'SCREEN_CONTROL', 'KEYBOARD_CONTROL', 'MOUSE_CONTROL'), risk='HIGH',
            tests=('tests/test_v7_computer_use.py',),
            implementation_path='jarvis/computer_use/', detail=computer_detail,
        )

        records['Browser'] = self._record(
            'Browser', 'Browser navigation/search abstraction with untrusted-content handling and verification.',
            CapabilityStatus.AVAILABLE if settings.enable_desktop_automation else CapabilityStatus.DISABLED,
            dependencies=('webbrowser',), permissions=('BROWSER_READ', 'BROWSER_CONTROL'), risk='MEDIUM',
            tests=('tests/test_v7_computer_use.py',),
            implementation_path='jarvis/computer_use/browser.py; jarvis/automation.py',
        )

        records['Coding'] = self._record(
            'Coding', 'Approved project inspection, safe text/code editing, tests and Git diagnostics.',
            CapabilityStatus.AVAILABLE if settings.enable_coding_tools else CapabilityStatus.DISABLED,
            dependencies=('git executable for Git operations',),
            permissions=('CODE_READ', 'CODE_WRITE', 'CODE_TEST', 'GIT_READ'), risk='HIGH',
            tests=('tests/test_v6_coding.py', 'tests/test_v6_git_tools.py'),
            implementation_path='jarvis/coding_tools.py; jarvis/git_tools.py',
        )

        document_deps = _all_modules('pypdf', 'docx', 'openpyxl')
        if not settings.enable_document_intelligence:
            document_status = CapabilityStatus.DISABLED
        elif document_deps:
            document_status = CapabilityStatus.AVAILABLE
        else:
            document_status = CapabilityStatus.DEGRADED
        records['Documents'] = self._record(
            'Documents', 'PDF, DOCX, XLSX/XLSM, CSV, TXT and Markdown extraction/indexing.',
            document_status,
            dependencies=('pypdf', 'python-docx', 'openpyxl'), permissions=('DOCUMENT_READ', 'FILE_READ'), risk='MEDIUM',
            tests=('tests/test_v6_documents.py', 'tests/test_v7_memory.py'),
            implementation_path='jarvis/documents.py',
            detail='full advertised document set requires all optional document dependencies',
        )

        voice_deps = _module('edge_tts') or _module('pyttsx3')
        if not settings.enable_voice_output:
            voice_status = CapabilityStatus.DISABLED
        else:
            voice_status = CapabilityStatus.AVAILABLE if voice_deps else CapabilityStatus.MISSING
        records['Voice'] = self._record(
            'Voice', 'Hindi/Hinglish/English spoken output with runtime playback controls.', voice_status,
            dependencies=('edge-tts or pyttsx3',), permissions=(), risk='LOW',
            tests=('tests/test_voice.py',), implementation_path='jarvis/voice.py; jarvis/voice_ui.py',
        )

        mic_deps = _all_modules('sounddevice', 'speech_recognition')
        if not settings.enable_mic_input:
            mic_status = CapabilityStatus.DISABLED
        else:
            mic_status = CapabilityStatus.AVAILABLE if mic_deps else CapabilityStatus.DEGRADED
        records['Microphone'] = self._record(
            'Microphone', 'Push-to-talk and optional wake-word speech input.', mic_status,
            dependencies=('sounddevice', 'SpeechRecognition', 'working microphone device'), permissions=(), risk='MEDIUM',
            tests=(), implementation_path='jarvis/microphone.py',
            detail='device availability is verified only when recording is attempted',
        )

        if not settings.enable_google_workspace:
            google_status = CapabilityStatus.DISABLED
            google_detail = 'Google Workspace integration disabled by configuration'
        else:
            google_libs = _all_modules('google.oauth2.credentials', 'googleapiclient.discovery')
            creds_exist = Path(settings.google_credentials_file).exists()
            if google_libs and creds_exist:
                google_status = CapabilityStatus.EXPERIMENTAL
                google_detail = 'OAuth dependencies/client file present; user authorization still required'
            else:
                google_status = CapabilityStatus.DEGRADED
                google_detail = 'enabled but OAuth dependencies or client credential file are missing'
        records['Google Workspace'] = self._record(
            'Google Workspace', 'Optional Gmail and Google Calendar integration through OAuth.', google_status,
            dependencies=('Google OAuth client', 'google-api-python-client'),
            permissions=('EMAIL_READ', 'EMAIL_SEND', 'CALENDAR_READ', 'CALENDAR_WRITE'), risk='HIGH',
            tests=('tests/test_v6_google.py',), implementation_path='jarvis/google_workspace.py', detail=google_detail,
        )

        local_configured = settings.enable_local_fallback and bool(settings.local_ai_model.strip())
        records['Local AI'] = self._record(
            'Local AI', 'Provider-neutral local OpenAI-compatible fallback runtime.',
            CapabilityStatus.EXPERIMENTAL if local_configured else CapabilityStatus.MISSING,
            dependencies=('local OpenAI-compatible server', 'configured local model'), permissions=(), risk='MEDIUM',
            tests=('tests/test_v7_foundation.py',), implementation_path='jarvis/providers/local_provider.py',
            detail='configured' if local_configured else 'provider adapter exists but no local model is configured',
        )

        records['Capability Registry'] = self._record(
            'Capability Registry', 'Runtime-derived inventory of actual JARVIS capabilities and status.',
            CapabilityStatus.AVAILABLE,
            dependencies=(), permissions=(), risk='LOW',
            tests=('tests/test_v75_capability_registry.py',),
            implementation_path='jarvis/capability_registry.py',
        )

        evaluation_exists = _module('jarvis.evaluation.engine')
        records['Self Evaluation'] = self._record(
            'Self Evaluation', 'Evidence-based mission/tool/verification/recovery performance measurement with history.',
            CapabilityStatus.AVAILABLE if evaluation_exists else CapabilityStatus.MISSING,
            dependencies=('sqlite3', 'mission history', 'audit evidence'), permissions=(), risk='LOW',
            tests=('tests/test_v75_evaluation.py',), implementation_path='jarvis/evaluation/engine.py',
            detail='measures only supported evidence; unsupported accuracy metrics remain N/A',
        )

        gaps_exist = _module('jarvis.evaluation.gaps')
        records['Gap Detection'] = self._record(
            'Gap Detection', 'Detects missing/degraded capabilities and repeated evidence-backed failures.',
            CapabilityStatus.AVAILABLE if gaps_exist else CapabilityStatus.MISSING,
            dependencies=('Self Evaluation', 'Capability Registry'), permissions=(), risk='LOW',
            tests=('tests/test_v75_gap_detector.py',), implementation_path='jarvis/evaluation/gaps.py',
        )

        self_dev_exists = _module('jarvis.self_development.engine')
        self_dev_enabled = getattr(settings, 'self_development_enabled', True)
        if not self_dev_enabled:
            self_dev_status = CapabilityStatus.DISABLED
            self_dev_detail = 'controlled self-development disabled by configuration'
        elif self_dev_exists:
            self_dev_status = CapabilityStatus.EXPERIMENTAL
            self_dev_detail = 'sandbox proposal/build/test/diff/approval pipeline exists; production release activation is intentionally separate'
        else:
            self_dev_status = CapabilityStatus.MISSING
            self_dev_detail = 'self-development package is absent'
        records['Self Development'] = self._record(
            'Self Development', 'Controlled sandboxed improvement proposal/build/test/evaluate/diff/approval pipeline.',
            self_dev_status,
            dependencies=('Git', 'sandbox', 'Self Evaluation', 'rollback checkpointing'), permissions=('CODE_WRITE',), risk='CRITICAL',
            tests=('tests/test_v75_self_development.py',), implementation_path='jarvis/self_development/',
            detail=self_dev_detail,
        )

        self_coding_exists = _module('jarvis.self_development.coding')
        records['Self Coding'] = self._record(
            'Self Coding', 'Bounded JSON-only code generation and repair inside an isolated Git worktree.',
            CapabilityStatus.EXPERIMENTAL if self_coding_exists and self_dev_enabled else (
                CapabilityStatus.DISABLED if not self_dev_enabled else CapabilityStatus.MISSING
            ),
            dependencies=('Self Development', 'reasoning provider', 'Git'), permissions=('CODE_WRITE',), risk='CRITICAL',
            tests=('tests/test_v75_self_coding.py',), implementation_path='jarvis/self_development/coding.py',
            detail='production merge is not exposed; live provider integration remains guarded/experimental',
        )

        self_debug_exists = _module('jarvis.self_development.debugger')
        records['Self Debugging'] = self._record(
            'Self Debugging', 'Bounded failure classification and limited repair loop for sandbox-generated changes.',
            CapabilityStatus.EXPERIMENTAL if self_debug_exists and self_dev_enabled else (
                CapabilityStatus.DISABLED if not self_dev_enabled else CapabilityStatus.MISSING
            ),
            dependencies=('Self Coding', 'regression tester'), permissions=('CODE_WRITE',), risk='HIGH',
            tests=('tests/test_v75_self_coding.py',), implementation_path='jarvis/self_development/debugger.py',
            detail=f'max repair attempts={getattr(settings, "max_self_repair_attempts", 3)}',
        )

        rollback_exists = _module('jarvis.self_development.rollback')
        records['Rollback'] = self._record(
            'Rollback', 'Stores known-good before/deployed commit checkpoints for controlled release recovery.',
            CapabilityStatus.EXPERIMENTAL if rollback_exists else CapabilityStatus.MISSING,
            dependencies=('Git', 'controlled release engine'), permissions=('CODE_WRITE',), risk='CRITICAL',
            tests=('tests/test_v75_self_development.py',), implementation_path='jarvis/self_development/rollback.py',
            detail='checkpointing exists; automatic production revert remains planned until release-engine verification',
        )

        self._records = records
        return dict(records)

    def get(self, name: str) -> CapabilityRecord | None:
        return self._records.get(name)

    def snapshot(self, *, refresh: bool = True) -> list[dict]:
        if refresh:
            self.refresh()
        return [self._records[name].as_dict() for name in sorted(self._records)]

    def summary_for_prompt(self) -> str:
        self.refresh()
        lines = [
            'Runtime capability truth. Do not claim MISSING or DISABLED capabilities as working.',
        ]
        for name in sorted(self._records):
            item = self._records[name]
            suffix = f' — {item.detail}' if item.detail and item.status != CapabilityStatus.AVAILABLE else ''
            lines.append(f'- {item.name}: {item.status.value}{suffix}')
        return '\n'.join(lines)
