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
    """Runtime-derived inventory of what this JARVIS installation can actually do.

    Status is derived from code/config/dependency state rather than marketing claims.
    A feature that still needs a live provider/device/operator release step remains
    EXPERIMENTAL or DEGRADED even when its deterministic engineering tests are green.
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
            dependencies=('openai-compatible SDK',), permissions=('WEB_READ',), risk='LOW',
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
            detail='image pipeline present; provider/model vision support is required at runtime',
        )

        records['Memory'] = self._record(
            'Memory', 'Working, episodic, semantic and procedural memory with hybrid retrieval.',
            CapabilityStatus.AVAILABLE,
            dependencies=('sqlite3',), permissions=('MEMORY_READ', 'MEMORY_WRITE'), risk='MEDIUM',
            tests=('tests/test_memory.py', 'tests/test_v7_memory.py'),
            implementation_path='jarvis/memory.py; jarvis/memory_v7.py; jarvis/retrieval.py',
        )
        records['Memory Lifecycle'] = self._record(
            'Memory Lifecycle', 'Reinforcement, contradiction detection, superseding and stale-confidence decay.',
            CapabilityStatus.AVAILABLE if _module('jarvis.memory_lifecycle') else CapabilityStatus.MISSING,
            dependencies=('sqlite3', 'V7 layered memory'), permissions=('MEMORY_READ', 'MEMORY_WRITE'), risk='MEDIUM',
            tests=('tests/test_v75_memory_lifecycle.py',),
            implementation_path='jarvis/memory_lifecycle.py',
            detail='additive status lifecycle preserves existing V7 memory data',
        )

        records['Missions'] = self._record(
            'Missions', 'Persisted mission orchestration with verification, retry, recovery and replanning.',
            CapabilityStatus.AVAILABLE,
            dependencies=('sqlite3',), permissions=('capability-dependent',), risk='MEDIUM',
            tests=('tests/test_v7_missions.py',), implementation_path='jarvis/agent/',
        )

        visual_available = False
        visual_detail = 'local OCR not checked'
        try:
            from .computer_use.visual_fallback import VisualTargetBackend
            visual = VisualTargetBackend().status()
            visual_available = bool(visual.available)
            visual_detail = visual.detail
        except Exception as exc:
            visual_detail = f'{type(exc).__name__}: {exc}'

        if not settings.enable_desktop_automation:
            computer_status = CapabilityStatus.DISABLED
            computer_detail = 'desktop automation disabled by configuration'
        elif os.name != 'nt':
            computer_status = CapabilityStatus.DEGRADED
            computer_detail = 'Windows UIA/action execution needs Windows; semantic/OCR logic remains testable'
        else:
            try:
                from .computer_use.windows_ui import WindowsUIBackend
                backend = WindowsUIBackend().status()
                if backend.available:
                    computer_status = CapabilityStatus.AVAILABLE
                    computer_detail = f'UIA ready; OCR fallback={visual_available}'
                elif _module('pyautogui') and visual_available:
                    computer_status = CapabilityStatus.DEGRADED
                    computer_detail = f'UIA unavailable ({backend.detail}); confidence-gated local OCR fallback ready'
                elif _module('pyautogui'):
                    computer_status = CapabilityStatus.DEGRADED
                    computer_detail = f'UIA unavailable ({backend.detail}); low-level fallback exists but OCR unavailable ({visual_detail})'
                else:
                    computer_status = CapabilityStatus.MISSING
                    computer_detail = f'UIA unavailable ({backend.detail}) and action fallback dependency missing'
            except Exception as exc:
                computer_status = CapabilityStatus.BROKEN
                computer_detail = f'{type(exc).__name__}: {exc}'
        records['Computer Use'] = self._record(
            'Computer Use', 'UIA-first semantic targeting with stricter OCR fallback, no-guess policy and post-action evidence.',
            computer_status,
            dependencies=('pywinauto (semantic UIA)', 'pyautogui (actions)', 'optional pytesseract/Tesseract OCR'),
            permissions=('APP_CONTROL', 'SCREEN_CONTROL', 'KEYBOARD_CONTROL', 'MOUSE_CONTROL'), risk='HIGH',
            tests=('tests/test_v7_computer_use.py', 'tests/test_v75_computer_use_integration.py', 'tests/test_v75_visual_fallback.py'),
            implementation_path='jarvis/computer_use/', detail=computer_detail,
        )

        records['Browser'] = self._record(
            'Browser', 'Browser navigation/read/search with public-address checks, prompt-injection scanning and untrusted-content handling.',
            CapabilityStatus.AVAILABLE if settings.enable_desktop_automation else CapabilityStatus.DISABLED,
            dependencies=('webbrowser', 'DDGS for public reads/search'), permissions=('BROWSER_READ', 'BROWSER_CONTROL'), risk='MEDIUM',
            tests=('tests/test_v7_computer_use.py', 'tests/test_v75_browser_security.py', 'tests/evaluation/test_adversarial_security.py'),
            implementation_path='jarvis/computer_use/browser.py; jarvis/computer_use/browser_security.py; jarvis/automation.py',
        )

        records['Coding'] = self._record(
            'Coding', 'Approved project inspection, safe editing, tests, Git diagnostics and bounded coding-agent workflows.',
            CapabilityStatus.AVAILABLE if settings.enable_coding_tools else CapabilityStatus.DISABLED,
            dependencies=('git executable for Git operations',),
            permissions=('CODE_READ', 'CODE_WRITE', 'CODE_TEST', 'GIT_READ'), risk='HIGH',
            tests=('tests/test_v6_coding.py', 'tests/test_v6_git_tools.py', 'tests/test_v75_coding_agent.py'),
            implementation_path='jarvis/coding_tools.py; jarvis/git_tools.py; jarvis/coding_agent.py',
        )

        document_deps = _all_modules('pypdf', 'docx', 'openpyxl')
        if not settings.enable_document_intelligence:
            document_status = CapabilityStatus.DISABLED
        elif document_deps:
            document_status = CapabilityStatus.AVAILABLE
        else:
            document_status = CapabilityStatus.DEGRADED
        records['Documents'] = self._record(
            'Documents', 'PDF, DOCX, XLSX/XLSM, CSV, TXT/Markdown extraction plus hash-based dedupe/provenance indexing.',
            document_status,
            dependencies=('pypdf', 'python-docx', 'openpyxl'), permissions=('DOCUMENT_READ', 'FILE_READ'), risk='MEDIUM',
            tests=('tests/test_v6_documents.py', 'tests/test_v7_memory.py'),
            implementation_path='jarvis/documents.py; jarvis/memory_v7.py',
            detail='full advertised document set requires all document dependencies',
        )

        voice_deps = _module('edge_tts') or _module('pyttsx3')
        voice_status = CapabilityStatus.DISABLED if not settings.enable_voice_output else (
            CapabilityStatus.AVAILABLE if voice_deps else CapabilityStatus.MISSING
        )
        records['Voice'] = self._record(
            'Voice', 'Hindi/Hinglish/English spoken output with play/pause/stop/speed and shutdown-safe playback.', voice_status,
            dependencies=('edge-tts or pyttsx3',), permissions=(), risk='LOW',
            tests=('tests/test_voice.py', 'tests/test_voice_controls.py'), implementation_path='jarvis/voice.py; jarvis/voice_ui.py',
        )

        mic_deps = _all_modules('sounddevice', 'speech_recognition')
        mic_status = CapabilityStatus.DISABLED if not settings.enable_mic_input else (
            CapabilityStatus.AVAILABLE if mic_deps else CapabilityStatus.DEGRADED
        )
        records['Microphone'] = self._record(
            'Microphone', 'Push-to-talk and optional wake-word speech input.', mic_status,
            dependencies=('sounddevice', 'SpeechRecognition', 'working microphone device'), permissions=(), risk='MEDIUM',
            tests=(), implementation_path='jarvis/microphone.py',
            detail='physical microphone availability is verified only when recording is attempted',
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
                google_detail = 'enabled but OAuth dependencies or OAuth client file are missing'
        records['Google Workspace'] = self._record(
            'Google Workspace', 'Optional Gmail and Google Calendar integration through OAuth.', google_status,
            dependencies=('Google OAuth client', 'google-api-python-client'),
            permissions=('EMAIL_READ', 'EMAIL_SEND', 'CALENDAR_READ', 'CALENDAR_WRITE'), risk='HIGH',
            tests=('tests/test_v6_google.py',), implementation_path='jarvis/google_workspace.py', detail=google_detail,
        )

        local_configured = settings.enable_local_fallback and bool(settings.local_ai_model.strip())
        records['Local AI'] = self._record(
            'Local AI', 'Provider-neutral local OpenAI-compatible fallback and optional offline-development reasoning.',
            CapabilityStatus.EXPERIMENTAL if local_configured else CapabilityStatus.MISSING,
            dependencies=('local OpenAI-compatible server', 'configured local model'), permissions=(), risk='MEDIUM',
            tests=('tests/test_v7_foundation.py', 'tests/test_v75_offline_development.py'),
            implementation_path='jarvis/providers/local_provider.py; jarvis/self_development/offline.py',
            detail='configured' if local_configured else 'adapter exists but no local model is configured',
        )

        records['Capability Registry'] = self._record(
            'Capability Registry', 'Runtime-derived inventory of actual JARVIS capabilities and status.',
            CapabilityStatus.AVAILABLE,
            dependencies=(), permissions=(), risk='LOW', tests=('tests/test_v75_capability_registry.py',),
            implementation_path='jarvis/capability_registry.py',
        )

        evaluation_exists = _module('jarvis.evaluation.engine')
        records['Self Evaluation'] = self._record(
            'Self Evaluation', 'Evidence-based mission/tool/verification/recovery performance measurement with history.',
            CapabilityStatus.AVAILABLE if evaluation_exists else CapabilityStatus.MISSING,
            dependencies=('sqlite3', 'mission history', 'audit evidence'), permissions=(), risk='LOW',
            tests=('tests/test_v75_evaluation.py',), implementation_path='jarvis/evaluation/engine.py',
            detail='unsupported metrics remain N/A rather than fabricated percentages',
        )

        gaps_exist = _module('jarvis.evaluation.gaps')
        records['Gap Detection'] = self._record(
            'Gap Detection', 'Detects missing/degraded capabilities and repeated evidence-backed failures.',
            CapabilityStatus.AVAILABLE if gaps_exist else CapabilityStatus.MISSING,
            dependencies=('Self Evaluation', 'Capability Registry'), permissions=(), risk='LOW',
            tests=('tests/test_v75_gap_detector.py',), implementation_path='jarvis/evaluation/gaps.py',
        )

        records['Evaluation Benchmarks'] = self._record(
            'Evaluation Benchmarks', 'Stores deterministic before/after task, tool, verification, recovery, safety, memory, computer-use and browser metrics.',
            CapabilityStatus.AVAILABLE if _module('jarvis.evaluation.benchmark') else CapabilityStatus.MISSING,
            dependencies=('sqlite3',), permissions=(), risk='LOW',
            tests=('tests/evaluation/test_self_improvement_benchmark.py',), implementation_path='jarvis/evaluation/benchmark.py',
        )

        records['Observability'] = self._record(
            'Observability', 'Structured model/mission/system telemetry, latency/fallback counters and provider-reported-only cost tracking.',
            CapabilityStatus.AVAILABLE if _module('jarvis.observability.manager') else CapabilityStatus.MISSING,
            dependencies=('sqlite3', 'psutil'), permissions=(), risk='LOW',
            tests=('tests/test_v75_observability.py',), implementation_path='jarvis/observability/manager.py',
            detail='cost is N/A when the provider does not explicitly report it',
        )
        records['Health System'] = self._record(
            'Health System', 'Runtime health checks for database, capabilities and local system dependencies.',
            CapabilityStatus.AVAILABLE if _module('jarvis.observability.health') else CapabilityStatus.MISSING,
            dependencies=('psutil', 'Capability Registry'), permissions=(), risk='LOW',
            tests=('tests/test_v75_observability.py',), implementation_path='jarvis/observability/health.py',
        )

        records['Backup / Restore'] = self._record(
            'Backup / Restore', 'Consistent SQLite backups, hash manifests, export/import, pre-restore checkpoints and integrity verification.',
            CapabilityStatus.AVAILABLE if _module('jarvis.storage.backup') else CapabilityStatus.MISSING,
            dependencies=('sqlite3',), permissions=('MEMORY_WRITE',), risk='HIGH',
            tests=('tests/test_v75_backup.py',), implementation_path='jarvis/storage/backup.py',
            detail='restore/import remain explicitly confirmed destructive transitions',
        )

        records['Workflow Learning'] = self._record(
            'Workflow Learning', 'Detects repeated audited workflows and persists reusable automation proposals without silent activation.',
            CapabilityStatus.AVAILABLE if _module('jarvis.skills.workflow') else CapabilityStatus.MISSING,
            dependencies=('audit evidence', 'sqlite3'), permissions=(), risk='MEDIUM',
            tests=('tests/test_v75_skills.py',), implementation_path='jarvis/skills/workflow.py',
        )

        records['Skill Generation'] = self._record(
            'Skill Generation', 'Gap-to-skill manifest, isolated build/test pipeline and activation only after verified deployment/evaluation.',
            CapabilityStatus.EXPERIMENTAL if _module('jarvis.skills.activation') and _module('jarvis.skills.builder') else CapabilityStatus.MISSING,
            dependencies=('Self Development', 'controlled release', 'Git'), permissions=('CODE_WRITE',), risk='CRITICAL',
            tests=('tests/test_v75_skills.py', 'tests/test_v75_skill_activation.py', 'tests/test_v75_skill_runtime_extension.py'),
            implementation_path='jarvis/skills/; jarvis/skill_runtime_extension.py; jarvis/ui_skill_extension.py',
            detail='build/activation gates are implemented; generated skills remain inactive until operator-approved deployment and evaluation pass',
        )

        self_dev_exists = _module('jarvis.self_development.engine')
        self_dev_enabled = getattr(settings, 'self_development_enabled', True)
        if not self_dev_enabled:
            self_dev_status = CapabilityStatus.DISABLED
            self_dev_detail = 'controlled self-development disabled by configuration'
        elif self_dev_exists:
            self_dev_status = CapabilityStatus.EXPERIMENTAL
            self_dev_detail = 'sandbox proposal/build/test/evaluate/diff/approval pipeline is integrated; production release remains locked by default'
        else:
            self_dev_status = CapabilityStatus.MISSING
            self_dev_detail = 'self-development package is absent'
        records['Self Development'] = self._record(
            'Self Development', 'Controlled sandboxed improvement discovery/build/test/evaluate/diff/approval pipeline.',
            self_dev_status,
            dependencies=('Git', 'sandbox', 'Self Evaluation', 'rollback checkpointing'), permissions=('CODE_WRITE',), risk='CRITICAL',
            tests=('tests/test_v75_self_development.py',), implementation_path='jarvis/self_development/', detail=self_dev_detail,
        )

        self_coding_exists = _module('jarvis.self_development.coding')
        records['Self Coding'] = self._record(
            'Self Coding', 'Bounded JSON-only code generation and repair inside an isolated Git worktree.',
            CapabilityStatus.EXPERIMENTAL if self_coding_exists and self_dev_enabled else (
                CapabilityStatus.DISABLED if not self_dev_enabled else CapabilityStatus.MISSING
            ),
            dependencies=('Self Development', 'reasoning provider', 'Git'), permissions=('CODE_WRITE',), risk='CRITICAL',
            tests=('tests/test_v75_self_coding.py',), implementation_path='jarvis/self_development/coding.py',
            detail='sandbox generation/repair is tested; production modification is not automatic',
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

        release_exists = _module('jarvis.self_development.release')
        release_status = CapabilityStatus.EXPERIMENTAL if release_exists and self_dev_enabled else (
            CapabilityStatus.DISABLED if not self_dev_enabled else CapabilityStatus.MISSING
        )
        records['Controlled Release'] = self._record(
            'Controlled Release', 'APPROVED-only, clean-HEAD, fast-forward production deployment with pre/post regression gates.',
            release_status,
            dependencies=('Git', 'Self Development', 'regression suite'), permissions=('CODE_WRITE',), risk='CRITICAL',
            tests=('tests/test_v75_release.py',),
            implementation_path='jarvis/self_development/release.py; jarvis/ui_release_extension.py',
            detail=(
                'release engine is implemented/tested; PRODUCTION_SELF_MODIFICATION is OFF by default'
                if release_exists else 'release engine missing'
            ),
        )

        rollback_exists = _module('jarvis.self_development.rollback') and release_exists
        records['Rollback'] = self._record(
            'Rollback', 'Known-good checkpoints plus history-preserving Git revert and regression verification.',
            CapabilityStatus.EXPERIMENTAL if rollback_exists else CapabilityStatus.MISSING,
            dependencies=('Git', 'Controlled Release'), permissions=('CODE_WRITE',), risk='CRITICAL',
            tests=('tests/test_v75_self_development.py', 'tests/test_v75_release.py'),
            implementation_path='jarvis/self_development/rollback.py; jarvis/self_development/release.py',
            detail='controlled rollback is implemented/tested; automatic rollback is configuration-gated',
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
