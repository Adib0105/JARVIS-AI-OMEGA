from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .capability_registry import CapabilityRegistry
from .config import ROOT, settings
from .logging_utils import redact_text
from .observability import JarvisHealthSystem
from .security.audit import AuditStore
from .self_development.lease import DevelopmentLeaseStore
from .self_development.proposal import ProposalStatus, ProposalStore
from .storage import BackupManager


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    status: str
    detail: str
    required: bool = True
    category: str = 'software'

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ReadinessReport:
    software_ready: bool
    final_release_ready: bool
    checks: tuple[ReadinessCheck, ...]

    def as_dict(self) -> dict:
        rows = [item.as_dict() for item in self.checks]
        return {
            'software_ready': self.software_ready,
            'final_release_ready': self.final_release_ready,
            'failures': sum(1 for row in rows if row['status'] == 'FAIL'),
            'warnings': sum(1 for row in rows if row['status'] == 'WARNING'),
            'not_verified': sum(1 for row in rows if row['status'] == 'NOT_VERIFIED'),
            'checks': rows,
        }


class ReleaseReadinessCertifier:
    """Truthful local release-readiness report.

    Automated checks can certify software state. Hardware, live provider accounts,
    OAuth and installer execution remain NOT_VERIFIED until explicit external smoke
    evidence is supplied. This prevents a green unit-test suite from pretending that
    a microphone, third-party account or workstation GUI was physically tested.
    """

    def __init__(
        self,
        *,
        root: Path | None = None,
        db_path: Path | None = None,
        settings_obj: Any = settings,
    ) -> None:
        self.root = Path(root or ROOT).resolve()
        self.settings = settings_obj
        self.db_path = Path(db_path or settings_obj.db_path)

    @staticmethod
    def _check(name: str, status: str, detail: str, *, required: bool = True, category: str = 'software') -> ReadinessCheck:
        return ReadinessCheck(
            name=name,
            status=status,
            detail=redact_text(str(detail))[:1200],
            required=required,
            category=category,
        )

    def _git_check(self) -> ReadinessCheck:
        if not (self.root / '.git').exists():
            return self._check(
                'git_worktree', 'NOT_VERIFIED',
                'Packaged/non-checkout runtime: Git cleanliness cannot be certified here.',
                required=False,
            )
        git = shutil.which('git')
        if not git:
            return self._check('git_worktree', 'FAIL', 'Git checkout exists but git executable is unavailable.')
        try:
            proc = subprocess.run(
                [git, 'status', '--porcelain=v1'],
                cwd=str(self.root), text=True, capture_output=True,
                timeout=20, check=False,
            )
        except Exception as exc:
            return self._check('git_worktree', 'FAIL', f'{type(exc).__name__}: {exc}')
        if proc.returncode != 0:
            return self._check('git_worktree', 'FAIL', proc.stderr or 'git status failed')
        dirty = [line for line in proc.stdout.splitlines() if line.strip()]
        return self._check(
            'git_worktree',
            'PASS' if not dirty else 'FAIL',
            'clean' if not dirty else f'{len(dirty)} tracked/untracked worktree change(s) require review',
        )

    def _automated_checks(self) -> list[ReadinessCheck]:
        checks: list[ReadinessCheck] = []
        try:
            integrity = BackupManager(self.db_path).integrity_check()
            checks.append(self._check(
                'database_integrity', 'PASS' if integrity.get('ok') else 'FAIL',
                integrity.get('result', 'unknown'),
            ))
        except Exception as exc:
            checks.append(self._check('database_integrity', 'FAIL', f'{type(exc).__name__}: {exc}'))

        try:
            health = JarvisHealthSystem(self.db_path).run().as_dict()
            checks.append(self._check(
                'health_system', 'PASS' if health.get('status') != 'FAIL' else 'FAIL',
                health.get('status', 'unknown'),
            ))
        except Exception as exc:
            checks.append(self._check('health_system', 'FAIL', f'{type(exc).__name__}: {exc}'))

        try:
            caps = CapabilityRegistry().snapshot()
            broken = [row.get('name') for row in caps if row.get('status') == 'BROKEN']
            checks.append(self._check(
                'capability_registry', 'PASS' if not broken else 'FAIL',
                f'{len(caps)} capabilities; broken={broken}',
            ))
        except Exception as exc:
            checks.append(self._check('capability_registry', 'FAIL', f'{type(exc).__name__}: {exc}'))

        try:
            audit = AuditStore(self.db_path).verify_integrity()
            if not audit.get('ok'):
                status = 'FAIL'
            elif audit.get('legacy_unchained_rows'):
                status = 'WARNING'
            else:
                status = 'PASS'
            checks.append(self._check(
                'audit_integrity', status,
                f"{audit.get('status')}; chained={audit.get('chained_audit_rows', 0)}; "
                f"legacy={audit.get('legacy_unchained_rows', 0)}",
            ))
        except Exception as exc:
            checks.append(self._check('audit_integrity', 'FAIL', f'{type(exc).__name__}: {exc}'))

        try:
            proposals = ProposalStore(self.db_path).list_recent(500)
            leases = DevelopmentLeaseStore(self.db_path)
            active = []
            stale = []
            in_flight = {
                ProposalStatus.TESTING.value,
                ProposalStatus.EVALUATED.value,
                ProposalStatus.SECURITY_REVIEW.value,
            }
            for row in proposals:
                proposal_id = str(row.get('id') or '')
                status = str(row.get('status') or '')
                lease = leases.get(proposal_id) if proposal_id else None
                if lease:
                    active.append(proposal_id)
                elif status in in_flight:
                    stale.append(proposal_id)
            if stale:
                state = 'FAIL'
                detail = f'stale interrupted proposals={stale[:20]}'
            elif active:
                state = 'WARNING'
                detail = f'active self-development operations={active[:20]}'
            else:
                state = 'PASS'
                detail = f'{len(proposals)} proposal(s); no stale in-flight operation'
            checks.append(self._check('self_development_state', state, detail))
        except Exception as exc:
            checks.append(self._check('self_development_state', 'FAIL', f'{type(exc).__name__}: {exc}'))

        checks.append(self._check(
            'production_approval_guard',
            'PASS' if bool(self.settings.require_approval_for_production) else 'FAIL',
            f'require_approval_for_production={bool(self.settings.require_approval_for_production)}',
        ))
        checks.append(self._check(
            'production_self_modification_default',
            'PASS' if not bool(self.settings.production_self_modification) else 'WARNING',
            'disabled by default' if not bool(self.settings.production_self_modification)
            else 'ENABLED: only expected during an intentional controlled release session',
        ))

        checks.append(self._git_check())
        for name in ('build_windows.ps1', 'build_installer.ps1'):
            checks.append(self._check(
                f'file:{name}', 'PASS' if (self.root / name).is_file() else 'FAIL', str(self.root / name)
            ))
        return checks

    @staticmethod
    def _evidence_status(live_evidence: dict[str, Any], key: str) -> tuple[str, str]:
        value = live_evidence.get(key)
        if isinstance(value, dict) and isinstance(value.get('ok'), bool):
            detail = str(value.get('detail') or 'explicit smoke-test evidence supplied')
            return ('PASS' if value['ok'] else 'FAIL'), detail
        if isinstance(value, bool):
            return ('PASS' if value else 'FAIL'), 'explicit smoke-test result supplied'
        return 'NOT_VERIFIED', 'No live workstation evidence supplied.'

    def _live_checks(self, live_evidence: dict[str, Any]) -> list[ReadinessCheck]:
        specs = [
            ('desktop_gui', True, 'workstation'),
            ('computer_use', True, 'workstation'),
            ('provider_live', bool(getattr(self.settings, 'api_key', '')), 'external'),
            ('windows_package_launch', True, 'workstation'),
            ('inno_installer_install_uninstall', True, 'workstation'),
        ]
        if bool(getattr(self.settings, 'enable_mic_input', False)):
            specs.append(('microphone_live', True, 'hardware'))
        if bool(getattr(self.settings, 'enable_google_workspace', False)):
            specs.append(('google_oauth_live', True, 'external'))

        rows = []
        for key, required, category in specs:
            status, detail = self._evidence_status(live_evidence, key)
            rows.append(self._check(key, status, detail, required=required, category=category))
        return rows

    def certify(self, live_evidence: dict[str, Any] | None = None) -> ReadinessReport:
        checks = self._automated_checks() + self._live_checks(dict(live_evidence or {}))
        software_ready = not any(
            item.status == 'FAIL' and item.category == 'software' and item.required
            for item in checks
        )
        final_release_ready = software_ready and not any(
            item.required and item.status in {'FAIL', 'NOT_VERIFIED'}
            for item in checks
        )
        return ReadinessReport(
            software_ready=software_ready,
            final_release_ready=final_release_ready,
            checks=tuple(checks),
        )


__all__ = ['ReadinessCheck', 'ReadinessReport', 'ReleaseReadinessCertifier']
