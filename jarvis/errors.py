from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ErrorCategory(str, Enum):
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


@dataclass(frozen=True)
class Failure:
    category: ErrorCategory
    message: str
    status_code: int | None = None
    retryable: bool = False
    retry_after: float | None = None
    provider: str | None = None
    operation: str | None = None


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


def classify_exception(
    exc: BaseException,
    *,
    provider: str | None = None,
    operation: str | None = None,
) -> Failure:
    """Normalize failures into stable V7 categories."""
    status = _status_code(exc)
    text = str(exc)
    lower = text.lower()
    retry_after = _retry_after(exc)

    if isinstance(exc, PermissionError) or status == 403 or 'permission denied' in lower:
        category = ErrorCategory.PERMISSION_ERROR
        retryable = False
    elif status == 401 or any(token in lower for token in ('invalid api key', 'authentication', 'unauthorized')):
        category = ErrorCategory.AUTH_ERROR
        retryable = False
    elif status == 429 or 'rate limit' in lower or 'too many requests' in lower:
        category = ErrorCategory.RATE_LIMIT
        retryable = True
    elif status in {408, 504} or 'timeout' in lower or 'timed out' in lower:
        category = ErrorCategory.TIMEOUT
        retryable = True
    elif status in {502, 503} or any(token in lower for token in (
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
    elif isinstance(exc, (ValueError, TypeError, KeyError)) or status in {400, 422}:
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
    )
