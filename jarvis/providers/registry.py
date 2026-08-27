from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Iterable

from ..errors import ErrorCode, Failure, classify_exception
from ..observability.manager import ObservabilityManager
from .base import AIProvider


class ProviderHealthState(str, Enum):
    AVAILABLE = 'AVAILABLE'
    DEGRADED = 'DEGRADED'
    NOT_VERIFIED = 'NOT_VERIFIED'
    BROKEN = 'BROKEN'
    MISSING = 'MISSING'


@dataclass(frozen=True)
class ProviderHealth:
    name: str
    role: str
    state: ProviderHealthState
    circuit_state: str
    last_status: str | None
    last_error_category: str | None
    detail: str

    def as_dict(self) -> dict:
        data = asdict(self)
        data['state'] = self.state.value
        return data


@dataclass(frozen=True)
class ProviderEntry:
    role: str
    provider: AIProvider


class FallbackPolicy:
    """Central policy for whether a primary provider failure may use local fallback.

    Fallback is a resilience mechanism, not an error-hiding mechanism. Authentication,
    authorization, configuration, invalid input, security and user-cancellation
    failures are never silently converted into a different-provider success.
    """

    _ALLOW = frozenset({
        ErrorCode.NETWORK_ERROR,
        ErrorCode.TIMEOUT_ERROR,
        ErrorCode.RATE_LIMIT_ERROR,
        ErrorCode.PROVIDER_ERROR,
    })

    _DENY = frozenset({
        ErrorCode.AUTHENTICATION_ERROR,
        ErrorCode.AUTHORIZATION_ERROR,
        ErrorCode.CONFIGURATION_ERROR,
        ErrorCode.INVALID_INPUT_ERROR,
        ErrorCode.USER_CANCELLED,
        ErrorCode.SECURITY_ERROR,
        ErrorCode.SANDBOX_ERROR,
        ErrorCode.RELEASE_ERROR,
    })

    def decision(self, failure: Failure) -> tuple[bool, str]:
        if failure.code in self._DENY:
            return False, f'fallback denied for {failure.code.value}'
        if failure.code in self._ALLOW:
            return True, f'fallback allowed for transient/provider failure {failure.code.value}'
        return False, f'fallback not authorized for {failure.code.value}'

    def allows_exception(
        self,
        exc: BaseException,
        *,
        provider: str | None = None,
        operation: str | None = None,
    ) -> tuple[bool, Failure, str]:
        failure = classify_exception(exc, provider=provider, operation=operation)
        allowed, reason = self.decision(failure)
        return allowed, failure, reason


class ProviderRegistry:
    """Authoritative runtime inventory of instantiated providers.

    Health is derived from real circuit state plus persisted model telemetry. A
    configured provider with no successful call evidence is NOT_VERIFIED rather than
    AVAILABLE.
    """

    def __init__(self, observability: ObservabilityManager) -> None:
        self.observability = observability
        self._entries: dict[str, ProviderEntry] = {}

    def register(self, role: str, provider: AIProvider | None) -> None:
        role_key = str(role).strip().lower()
        if not role_key:
            raise ValueError('Provider role is required.')
        if provider is None:
            self._entries.pop(role_key, None)
            return
        self._entries[role_key] = ProviderEntry(role_key, provider)

    def get(self, role: str) -> AIProvider | None:
        entry = self._entries.get(str(role).strip().lower())
        return entry.provider if entry else None

    def roles(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    @staticmethod
    def _circuit(provider: AIProvider) -> dict:
        fn = getattr(provider, 'circuit_status', None)
        if not callable(fn):
            return {'state': 'NOT_EXPOSED'}
        try:
            value = fn()
            return dict(value or {})
        except Exception as exc:
            return {'state': 'BROKEN', 'detail': f'{type(exc).__name__}: {exc}'}

    def _recent_model_events(self, provider_name: str, *, limit: int = 200) -> list[dict]:
        try:
            rows = self.observability.events(limit=max(1, min(int(limit), 1000)), category='MODEL')
        except Exception:
            return []
        name = provider_name.strip().lower()
        return [
            row for row in rows
            if str(row.get('provider') or '').strip().lower() == name
        ]

    def health(self, role: str) -> ProviderHealth:
        role_key = str(role).strip().lower()
        entry = self._entries.get(role_key)
        if entry is None:
            return ProviderHealth(
                name='', role=role_key, state=ProviderHealthState.MISSING,
                circuit_state='MISSING', last_status=None, last_error_category=None,
                detail='provider role is not configured/instantiated',
            )

        provider = entry.provider
        name = str(getattr(provider, 'name', '') or type(provider).__name__)
        circuit = self._circuit(provider)
        circuit_state = str(circuit.get('state') or 'UNKNOWN').upper()
        if circuit_state == 'BROKEN':
            return ProviderHealth(
                name=name, role=role_key, state=ProviderHealthState.BROKEN,
                circuit_state=circuit_state, last_status=None, last_error_category=None,
                detail=str(circuit.get('detail') or 'provider circuit status failed'),
            )

        rows = self._recent_model_events(name)
        last = rows[0] if rows else None
        last_status = str(last.get('status') or '') if last else None
        last_error = None
        if last:
            metadata = last.get('metadata') if isinstance(last.get('metadata'), dict) else {}
            last_error = str(metadata.get('error_category') or '') or None

        if circuit_state == 'OPEN':
            state = ProviderHealthState.DEGRADED
            detail = 'circuit is OPEN after retryable provider failures'
        elif circuit_state == 'HALF_OPEN':
            state = ProviderHealthState.DEGRADED
            detail = 'circuit is HALF_OPEN; recovery probe is required'
        elif any(str(row.get('status') or '').upper() == 'SUCCESS' for row in rows):
            state = ProviderHealthState.AVAILABLE
            detail = 'at least one persisted successful provider call exists for this runtime data store'
        elif rows:
            state = ProviderHealthState.DEGRADED
            detail = 'provider has telemetry but no successful call evidence in the inspected window'
        else:
            state = ProviderHealthState.NOT_VERIFIED
            detail = 'provider is instantiated but no persisted live-call evidence was found'

        return ProviderHealth(
            name=name,
            role=role_key,
            state=state,
            circuit_state=circuit_state,
            last_status=last_status,
            last_error_category=last_error,
            detail=detail,
        )

    def snapshot(self) -> list[dict]:
        return [self.health(role).as_dict() for role in self.roles()]


__all__ = [
    'FallbackPolicy', 'ProviderEntry', 'ProviderHealth', 'ProviderHealthState',
    'ProviderRegistry',
]
