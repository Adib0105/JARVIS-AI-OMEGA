from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ProductModule:
    name: str
    components: tuple[str, ...]
    maturity: str
    physical_e2e_required: bool = False


MODULES: tuple[ProductModule, ...] = (
    ProductModule('CORE', ('Reasoning', 'Planning', 'Memory', 'Context', 'Mission Recovery', 'Verification'), 'IMPLEMENTED_AUTOMATED'),
    ProductModule('VOICE', ('STT', 'TTS', 'Wake Word', 'Interruption', 'Continuous Conversation'), 'IMPLEMENTED_NEEDS_DEVICE_E2E', True),
    ProductModule('VISION', ('Screenshot', 'OCR', 'Image Attachments', 'Visual Reasoning', 'Camera Adapter'), 'PARTIAL_NEEDS_MODEL_DEVICE_E2E', True),
    ProductModule('COMPUTER', ('Mouse', 'Keyboard', 'Apps', 'Windows', 'Semantic UIA', 'OCR Fallback', 'Media Controls'), 'IMPLEMENTED_NEEDS_WINDOWS_E2E', True),
    ProductModule('BROWSER', ('Search', 'Research', 'Safe Read', 'Navigation', 'Web Automation'), 'PARTIAL_NEEDS_BROWSER_E2E', True),
    ProductModule('PRODUCTIVITY', ('Tasks', 'Calendar', 'Reminders', 'Notes', 'Agenda', 'Focus'), 'PARTIAL'),
    ProductModule('HOME', ('Smart Home Connectors', 'Scenes', 'Shopping', 'Household', 'Sensors'), 'FOUNDATION_REQUIRED', True),
    ProductModule('OFFICE', ('Email', 'Meetings', 'Documents', 'Projects'), 'PARTIAL'),
    ProductModule('DEVELOPER', ('Coding', 'Testing', 'Git', 'Debugging', 'Self Development'), 'IMPLEMENTED_GUARDED'),
    ProductModule('SECURITY', ('Permissions', 'Audit', 'Sandbox', 'Secrets', 'Recovery'), 'IMPLEMENTED_AUTOMATED'),
    ProductModule('ANALYTICS', ('Performance', 'Usage', 'Tests', 'Reliability', 'Diagnostics'), 'IMPLEMENTED_NO_FAKE_METRICS'),
    ProductModule('COMMERCIAL', ('Onboarding', 'Activation', 'Licensing', 'Updates', 'Rollback', 'Backup', 'Diagnostics Bundle'), 'PARTIAL'),
)


def product_architecture() -> dict:
    return {
        'product': 'JARVIS OMEGA Home AI',
        'contract': 'implementation + regression + packaged build + real scenario + failure/recovery',
        'release_gate': {'P0': 0, 'P1': 0},
        'modules': [asdict(item) for item in MODULES],
    }
