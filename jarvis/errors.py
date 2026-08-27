from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ErrorCategory(str, Enum):
    """Legacy/broad V7 categories retained for compatibility and persisted evidence."""

    AUTH_ERROR = 'AUTH_ERROR'
    PERMISSION_ERROR = 'PERMISSION_ERROR'
    RATE_LIMIT = 'RATE_LIMIT'
    TIMEOUT = 'TIMEOUT'
    NETWORK_ERROR = 'NETWORK_ERROR'
    INVALID_INPUT = 'INVALID_INPUT'
    TOOL_ERROR = 'TOOL_ERROR'
    RESOURCE_NOT_FOUND = 'RESOURCE_NOT_FOUND'
    VISION_ERROR = 'VISION_ERROR'
    MODEL_ERROR = 'MODEL_ERROR'
    CONFIG_ERROR = 'CONFIG_ERROR'
    UNKNOWN_ERROR = 'UNKNOWN_ERROR'


class ErrorCode(str, Enum):
    """Canonical production error taxonomy used by new recovery/telemetry code."""

    CONFIGURATION_ERROR = 'CONFIGURATION_ERROR'
    AUTHENTICATION_ERROR = 'AUTHENTICATION_ERROR'
    AUTHORIZATION_ERROR = 'AUTHORIZATION_ERROR'
    NETWORK_ERROR = 'NETWORK_ERROR'
    TIMEOUT_ERROR = 'TIMEOUT_ERROR'
    RATE_LIMIT_ERROR = 'RATE_LIMIT_ERROR'
    PROVIDER_ERROR = 'PROVIDER_ERROR'
    TOOL_ERROR = 'TOOL_ERROR'
    VERIFICATION_ERROR = 'VERIFICATION_ERROR'
    BROWSER_ERROR = 'BROWSER_ERROR'
    COMPUTER_USE_ERROR = 'COMPUTER_USE_ERROR'
    STORAGE_ERROR = 'STORAGE_ERROR'
    SECURITY_ERROR = 'SECURITY_ERROR'
    SANDBOX_ERROR = 'SANDBOX_ERROR'
    RELEASE_ERROR = 'RELEASE_ERROR'
    USER_CANCELLED = 'USER_CANCELLED'
    DEPENDENCY_ERROR = 'DEPENDENCY_ERROR'
    INVALID_INPUT_ERROR = 'INVALID_INPUT_ERROR'
    RESOURCE_NOT_FOUND_ERROR = 'RESOURCE_NOT_FOUND_ERROR'
    UNKNOWN_ERROR = 'UNKNOWN_ERROR'


@dataclass(frozen=True)
class Failure:
    category: ErrorCategory
    message: str
    status_code: int | None = None
    retryable: bool = False
    retry_after: float | None = None
    provider: str | None = None
    operation: str | None = None
    code: ErrorCode = ErrorCode.UNKNOWN_ERROR

    @property
    def canonical_code(self) -> ErrorCode:
        return self.code


class JarvisError(RuntimeError):
    def __init__(self, failure: Failure):
        super().__init__(failure.message)
        self.failure = failure


def _status_code(exc: BaseException) -> int | None:
    value = getattr(exc, 'status_code', None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _retry_after(exc: BaseException) -> float | None:
    direct = getattr(exc, 'retry_after', None)
    if isinstance(direct, (int, float)) and not isinstance(direct, bool):
        return max(0.0, float(direct))
    response = getattr(exc, 'response', None)
    headers: Any = getattr(response, 'headers', None)
    if not headers:
        return None
    try:
        raw = headers.get('retry-after') or headers.get('Retry-After')
        if raw is None:
            return None
        value = float(raw)
        return value if value >= 0 else None
    except (TypeError, ValueError, AttributeError):
        return None


def _operation_code(operation: str | None, *, provider: str | None = None) -> ErrorCode:
    value = (operation or '').strip().lower().replace('-', '_').replace(' ', '_')
    if any(token in value for token in ('release', 'rollback', 'deploy', 'promotion')):
        return ErrorCode.RELEASE_ERROR
    if any(token in value for token in ('sandbox', 'self_development', 'self_coding', 'self_debug')):
        return ErrorCode.SANDBOX_ERROR
    if any(token in value for token in ('browser', 'web_page', 'navigation')):
        return ErrorCode.BROWSER_ERROR
    if any(token in value for token in ('computer_use', 'desktop', 'uia', 'mouse', 'keyboard')):
        return ErrorCode.COMPUTER_USE_ERROR
    if any(token in value for token in ('storage', 'database', 'sqlite', 'memory', 'backup', 'restore')):
        return ErrorCode.STORAGE_ERROR
    if any(token in value for token in ('security', 'audit', 'permission_policy', 'secret')):
        return ErrorCode.SECURITY_ERROR
    if 'verification' in value or value.startswith('verify'):
        return ErrorCode.VERIFICATION_ERROR
    if 'tool' in value:
        return ErrorCode.TOOL_ERROR
    if any(token in value for token in ('config', 'startup_validation')):
        return ErrorCode.CONFIGURATION_ERROR
    if any(token in value for token in ('dependency', 'import')):
        return ErrorCode.DEPENDENCY_ERROR
    if provider or any(token in value for token in ('provider', 'chat', 'vision', 'model', 'ai_request')):
        return ErrorCode.PROVIDER_ERROR
    return ErrorCode.UNKNOWN_ERROR


def _canonical_code(
    category: ErrorCategory,
    *,
    operation: str | None,
    provider: str | None,
    cancelled: bool = False,
) -> ErrorCode:
    if cancelled:
        return ErrorCode.USER_CANCELLED
    mapping = {
        ErrorCategory.AUTH_ERROR: ErrorCode.AUTHENTICATION_ERROR,
        ErrorCategory.PERMISSION_ERROR: ErrorCode.AUTHORIZATION_ERROR,
        ErrorCategory.RATE_LIMIT: ErrorCode.RATE_LIMIT_ERROR,
        ErrorCategory.TIMEOUT: ErrorCode.TIMEOUT_ERROR,
        ErrorCategory.NETWORK_ERROR: ErrorCode.NETWORK_ERROR,
        ErrorCategory.INVALID_INPUT: ErrorCode.INVALID_INPUT_ERROR,
        ErrorCategory.RESOURCE_NOT_FOUND: ErrorCode.RESOURCE_NOT_FOUND_ERROR,
        ErrorCategory.CONFIG_ERROR: ErrorCode.CONFIGURATION_ERROR,
        ErrorCategory.TOOL_ERROR: ErrorCode.TOOL_ERROR,
        ErrorCategory.VISION_ERROR: ErrorCode.PROVIDER_ERROR,
        ErrorCategory.MODEL_ERROR: ErrorCode.PROVIDER_ERROR,
    }
    if category in mapping:
        return mapping[category]
    return _operation_code(operation, provider=provider)


def classify_exception(
    exc: BaseException,
    *,
    provider: str | None = None,
    operation: str | None = None,
) -> Failure:
    """Normalize exceptions into legacy and canonical production categories.

    Legacy ``ErrorCategory`` values remain stable for stored V7 telemetry. New code
    should use ``Failure.code`` / ``canonical_code`` for recovery decisions.
    """
    status = _status_code(exc)
    text = str(exc)
    lower = text.lower()
    retry_after = _retry_after(exc)
    class_name = type(exc).__name__.lower()

    cancelled = (
        class_name in {'requestcancellederror', 'missioncancellederror', 'operationcancellederror'}
        or 'was cancelled' in lower
        or 'user cancelled' in lower
        or 'cancellation requested' in lower
    )

    if cancelled:
        category = ErrorCategory.PERMISSION_ERROR  # legacy compatibility bucket
        retryable = False
    elif isinstance(exc, PermissionError) or status == 403 or 'permission denied' in lower:
        category = ErrorCategory.PERMISSION_ERROR
        retryable = False
    elif status == 401 or any(token in lower for token in ('invalid api key', 'authentication', 'unauthorized')):
        category = ErrorCategory.AUTH_ERROR
        retryable = False
    elif status == 429 or 'rate limit' in lower or 'too many requests' in lower:
        category = ErrorCategory.RATE_LIMIT
        retryable = True
    elif status in {408, 504} or 'timeout' in lower or 'timed out' in lower or 'request deadline' in lower:
        category = ErrorCategory.TIMEOUT
        retryable = True
    elif status is not None and 500 <= status <= 599:
        category = ErrorCategory.NETWORK_ERROR
        retryable = True
    elif any(token in lower for token in (
        'connection error', 'network error', 'connection reset', 'circuit open',
    )):
        category = ErrorCategory.NETWORK_ERROR
        retryable = True
    elif 'image' in lower and any(token in lower for token in ('vision', 'modality', 'unsupported')):
        category = ErrorCategory.VISION_ERROR
        retryable = True
    elif any(token in lower for token in ('model not found', 'no endpoints found', 'model unavailable')):
        category = ErrorCategory.MODEL_ERROR
        retryable = True
    elif isinstance(exc, FileNotFoundError) or (status == 404 and 'model' not in lower) or 'resource not found' in lower:
        category = ErrorCategory.RESOURCE_NOT_FOUND
        retryable = False
    elif isinstance(exc, (ValueError, TypeError, KeyError, IndexError)) or status in {400, 422}:
        category = ErrorCategory.INVALID_INPUT
        retryable = False
    else:
        category = ErrorCategory.UNKNOWN_ERROR
        retryable = False

    message = text.strip()[:800] or type(exc).__name__
    return Failure(
        category=category,
        message=message,
        status_code=status,
        retryable=retryable,
        retry_after=retry_after,
        provider=provider,
        operation=operation,
        code=_canonical_code(
            category,
            operation=operation,
            provider=provider,
            cancelled=cancelled,
        ),
    )


__all__ = [
    'ErrorCategory', 'ErrorCode', 'Failure', 'JarvisError', 'classify_exception',
]
