from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable


class ValidationLevel(str, Enum):
    PASS = 'PASS'
    WARNING = 'WARNING'
    FAIL = 'FAIL'


@dataclass(frozen=True)
class ValidationFinding:
    key: str
    level: ValidationLevel
    message: str


class ConfigurationError(RuntimeError):
    def __init__(self, findings: Iterable[ValidationFinding]):
        self.findings = tuple(findings)
        message = '; '.join(f'{item.key}: {item.message}' for item in self.findings if item.level == ValidationLevel.FAIL)
        super().__init__(message or 'Invalid JARVIS configuration.')


def validate_settings(settings) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []

    def add(key: str, ok: bool, message: str, warning: bool = False) -> None:
        if ok:
            findings.append(ValidationFinding(key, ValidationLevel.PASS, message))
        else:
            findings.append(ValidationFinding(key, ValidationLevel.WARNING if warning else ValidationLevel.FAIL, message))

    add('AI_PROVIDER', settings.provider in {'openrouter', 'openai'}, 'Provider must be openrouter or openai.')
    add('MODEL', bool(settings.model.strip()), 'A primary model must be configured.')
    add('API_KEY', bool(settings.api_key.strip()), f'{settings.provider} API key must be configured.')
    add('AI_TIMEOUT_SECONDS', settings.ai_timeout_seconds > 0, 'AI timeout must be greater than zero.')
    add('VISION_TIMEOUT_SECONDS', settings.vision_timeout_seconds > 0, 'Vision timeout must be greater than zero.')
    add('MISSION_TIMEOUT_SECONDS', settings.mission_timeout_seconds > 0, 'Mission timeout must be greater than zero.')
    add('API_MAX_RETRIES', 0 <= settings.api_max_retries <= 10, 'API retries must be between 0 and 10.')
    add('MAX_TOOL_ROUNDS', 1 <= settings.max_tool_rounds <= 50, 'Tool rounds must be between 1 and 50.')
    add('MISSION_MAX_STEPS', 1 <= settings.mission_max_steps <= 20, 'Mission steps must be between 1 and 20.')
    add('MAX_IMAGE_ATTACHMENTS', 1 <= settings.max_image_attachments <= 12, 'Image attachment limit must be between 1 and 12.')
    add('MAX_IMAGE_MB', 1 <= settings.max_image_mb <= 100, 'Image size limit must be between 1 and 100 MB.')
    add('IMAGE_MAX_DIMENSION', 256 <= settings.image_max_dimension <= 8192, 'Image maximum dimension must be 256..8192.')
    add('IMAGE_JPEG_QUALITY', 30 <= settings.image_jpeg_quality <= 100, 'JPEG quality must be 30..100.')
    add('VOICE_VOLUME', 0.0 <= settings.voice_volume <= 1.0, 'Offline voice volume must be 0.0..1.0.')
    if hasattr(settings, 'voice_profile'):
        add('VOICE_PROFILE', bool(str(settings.voice_profile).strip()), 'Voice profile must not be empty.')
    add('VOICE_ENGLISH', bool(settings.voice_english), 'English voice must be configured.')
    add('VOICE_HINGLISH', bool(settings.voice_hinglish), 'Hinglish voice must be configured.')
    add('VOICE_HINDI', bool(settings.voice_hindi), 'Hindi voice must be configured.')
    if hasattr(settings, 'voice_chunk_chars'):
        add('VOICE_CHUNK_CHARS', 80 <= settings.voice_chunk_chars <= 6000, 'Voice chunk size must be 80..6000 characters.')
    add('TTS_TIMEOUT_SECONDS', settings.tts_timeout_seconds > 0, 'Edge TTS timeout must be greater than zero.')
    add('OFFLINE_TTS_TIMEOUT_SECONDS', settings.offline_tts_timeout_seconds > 0, 'Offline TTS timeout must be greater than zero.')
    add('MIC_RECORD_SECONDS', 1.0 <= settings.mic_record_seconds <= 20.0, 'Microphone recording length must be 1..20 seconds.')
    if hasattr(settings, 'wake_chunk_seconds'):
        add('WAKE_CHUNK_SECONDS', 2.0 <= settings.wake_chunk_seconds <= 8.0, 'Wake-word sample length must be 2..8 seconds.')
    if hasattr(settings, 'voice_continuous_seconds'):
        add('VOICE_CONTINUOUS_SECONDS', 0.0 <= settings.voice_continuous_seconds <= 60.0, 'Continuous voice window must be 0..60 seconds.')
    if hasattr(settings, 'speech_language'):
        add('SPEECH_LANGUAGE', bool(str(settings.speech_language).strip()), 'Speech language must be auto or a configured locale.')

    roots = tuple(settings.allowed_file_roots)
    add('ALLOWED_FILE_ROOTS', bool(roots), 'At least one local root must be configured.')
    for index, root in enumerate(roots, 1):
        add(f'ALLOWED_FILE_ROOTS[{index}]', isinstance(root, Path), f'Root resolved to {root}.')

    if settings.enable_google_workspace:
        add(
            'GOOGLE_OAUTH_CLIENT_FILE',
            settings.google_credentials_file.is_file(),
            f'Google integration enabled but OAuth client file is missing: {settings.google_credentials_file}',
            warning=True,
        )

    if settings.enable_local_fallback:
        add('LOCAL_AI_BASE_URL', bool(settings.local_ai_base_url), 'Local fallback requires a base URL.')
        add('LOCAL_AI_MODEL', bool(settings.local_ai_model), 'Local fallback requires LOCAL_AI_MODEL.')

    return findings


def fatal_findings(findings: Iterable[ValidationFinding]) -> list[ValidationFinding]:
    return [item for item in findings if item.level == ValidationLevel.FAIL]


def require_valid_settings(settings) -> list[ValidationFinding]:
    findings = validate_settings(settings)
    failures = fatal_findings(findings)
    if failures:
        raise ConfigurationError(failures)
    return findings
