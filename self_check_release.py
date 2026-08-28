from __future__ import annotations

import json
import shutil
import sys

from jarvis.capability_registry import CapabilityRegistry
from jarvis.config import ROOT, settings
from jarvis.memory_lifecycle import MemoryLifecycleManager
from jarvis.observability import JarvisHealthSystem, ObservabilityManager
from jarvis.readiness import ReleaseReadinessCertifier
from jarvis.self_development.offline import OfflineDevelopmentRuntime
from jarvis.self_development.policies import SelfDevelopmentPolicy
from jarvis.storage import BackupManager, SchemaMigrator
from jarvis.version import APP_VERSION


MINIMUM_PYTHON = (3, 11)


def line(status: str, name: str, detail: str = '') -> None:
    suffix = f' - {detail}' if detail else ''
    print(f'[{status}] {name}{suffix}')


def prepare_database_for_check(db_path) -> dict:
    """Apply additive migrations before certifying a fresh or upgraded profile DB."""
    migrator = SchemaMigrator(db_path)
    migration = migrator.migrate()
    lifecycle = MemoryLifecycleManager(db_path)
    columns = lifecycle._columns()
    return {
        'schema_version': migrator.current_version(),
        'migration': migration,
        'memory_lifecycle_columns': columns,
    }


def main() -> int:
    failures = 0
    warnings = 0

    def report(ok: bool, name: str, detail: str, *, required: bool = True) -> None:
        nonlocal failures, warnings
        if ok:
            line('PASS', name, detail)
        elif required:
            failures += 1
            line('FAIL', name, detail)
        else:
            warnings += 1
            line('WARN', name, detail)

    print(f'JARVIS AI OMEGA {APP_VERSION} // ENGINEERING SELF CHECK')
    print('=' * 64)
    report(
        sys.version_info >= MINIMUM_PYTHON,
        'Python',
        f"{sys.version.split()[0]} (minimum {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]})",
    )

    try:
        health = JarvisHealthSystem(settings.db_path).run().as_dict()
        report(health['status'] != 'FAIL', 'Health system', health['status'])
        for item in health['checks']:
            if item['status'] == 'FAIL' and item.get('required', True):
                failures += 1
            elif item['status'] == 'WARNING':
                warnings += 1
            print(f"  [{item['status']}] {item['name']} - {item['detail']}")
    except Exception as exc:
        failures += 1
        line('FAIL', 'Health system', f'{type(exc).__name__}: {exc}')

    try:
        registry = CapabilityRegistry().snapshot()
        broken = [item['name'] for item in registry if item['status'] == 'BROKEN']
        report(not broken, 'Capability Registry', f'{len(registry)} capabilities; broken={broken}')
    except Exception as exc:
        failures += 1
        line('FAIL', 'Capability Registry', f'{type(exc).__name__}: {exc}')

    try:
        obs = ObservabilityManager(settings.db_path)
        sample = obs.sample_resources()
        sampling_ready = sample.get('available') is not False and isinstance(sample.get('cpu_percent'), (int, float))
        detail = 'resource sampling + local event store ready'
        if sample.get('warnings'):
            detail += f"; optional probes={sample['warnings']}"
        report(sampling_ready, 'Observability', detail)
    except Exception as exc:
        failures += 1
        line('FAIL', 'Observability', f'{type(exc).__name__}: {exc}')

    try:
        database = prepare_database_for_check(settings.db_path)
        current = database['schema_version']
        report(current >= 1, 'Database schema', f'version={current}')
        integrity = BackupManager(settings.db_path).integrity_check()
        report(integrity['ok'], 'Database integrity', integrity['result'])
        columns = database['memory_lifecycle_columns']
        report('status' in columns, 'Memory lifecycle', f"status-column={'present' if 'status' in columns else 'missing'}")
    except Exception as exc:
        failures += 1
        line('FAIL', 'Database / memory lifecycle', f'{type(exc).__name__}: {exc}')

    git = shutil.which('git')
    report(bool(git), 'Git', git or 'not installed', required=False)
    repo_checkout = (ROOT / '.git').exists()
    report(repo_checkout, 'Repository checkout', str(ROOT), required=False)

    try:
        from jarvis.self_development.release import ControlledReleaseEngine
        from jarvis.skills import SkillRegistry
        from jarvis.skills.activation import SkillActivationEngine
        _ = (ControlledReleaseEngine, SkillRegistry, SkillActivationEngine)
        report(True, 'Controlled release + skill modules', 'release/rollback and deployed-only skill activation modules import successfully')
    except Exception as exc:
        failures += 1
        line('FAIL', 'Controlled release + skill modules', f'{type(exc).__name__}: {exc}')

    try:
        policy = SelfDevelopmentPolicy()
        security_allowed, security_reason = policy.path_allowed('jarvis/security/policy.py')
        env_allowed, env_reason = policy.path_allowed('.env')
        report(not security_allowed and not env_allowed, 'Immutable self-development core', f'security={security_reason}; env={env_reason}')
        report(not settings.production_self_modification, 'Production self-modification default', 'disabled' if not settings.production_self_modification else 'ENABLED — review required')
        report(settings.require_approval_for_production, 'Production release approval', str(settings.require_approval_for_production))
    except Exception as exc:
        failures += 1
        line('FAIL', 'Self-development policy', f'{type(exc).__name__}: {exc}')

    try:
        from jarvis.computer_use.visual_fallback import VisualTargetBackend
        visual = VisualTargetBackend().status()
        report(
            visual.available,
            'Computer Use V2 local OCR fallback',
            visual.detail,
            required=False,
        )
    except Exception as exc:
        warnings += 1
        line('WARN', 'Computer Use V2 local OCR fallback', f'{type(exc).__name__}: {exc}')

    try:
        offline = OfflineDevelopmentRuntime().status().as_dict()
        if offline['configured'] and offline['enabled']:
            line('PASS', 'Offline development configuration', f"{offline['provider']} / {offline['model']}")
        else:
            warnings += 1
            line('WARN', 'Offline development configuration', offline['message'])
    except Exception as exc:
        warnings += 1
        line('WARN', 'Offline development configuration', f'{type(exc).__name__}: {exc}')

    package_script = ROOT / 'build_windows.ps1'
    installer_script = ROOT / 'build_installer.ps1'
    report(package_script.is_file(), 'Windows build script present', str(package_script))
    report(installer_script.is_file(), 'Windows installer script present', str(installer_script))

    readiness_summary = None
    try:
        readiness_summary = ReleaseReadinessCertifier().certify().as_dict()
        report(
            readiness_summary['software_ready'],
            'Automated software readiness',
            f"failures={readiness_summary['failures']}; warnings={readiness_summary['warnings']}",
        )
        pending_live = [
            item['name'] for item in readiness_summary['checks']
            if item['required'] and item['status'] == 'NOT_VERIFIED'
        ]
        if pending_live:
            warnings += 1
            line(
                'WARN', 'Final release live evidence',
                'NOT VERIFIED: ' + ', '.join(pending_live),
            )
        else:
            line('PASS', 'Final release live evidence', 'all required live checks have evidence')
    except Exception as exc:
        failures += 1
        line('FAIL', 'Release readiness certifier', f'{type(exc).__name__}: {exc}')

    print('=' * 64)
    print(json.dumps({
        'app_version': APP_VERSION,
        'minimum_python': f'{MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]}',
        'failures': failures,
        'warnings': warnings,
        'production_self_modification': settings.production_self_modification,
        'self_development_enabled': settings.self_development_enabled,
        'offline_development_enabled': settings.offline_development_enabled,
        'final_release_ready': (
            readiness_summary.get('final_release_ready') if readiness_summary else False
        ),
    }, indent=2))
    if failures:
        print(f'JARVIS OMEGA {APP_VERSION}: NOT READY')
        return 1
    if readiness_summary and readiness_summary.get('final_release_ready'):
        print(f'JARVIS OMEGA {APP_VERSION}: RELEASE READY')
    else:
        print(f'JARVIS OMEGA {APP_VERSION}: SOFTWARE READY / LIVE SMOKE EVIDENCE PENDING')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
