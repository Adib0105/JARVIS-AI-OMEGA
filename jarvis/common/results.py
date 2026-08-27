from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable


class OperationStatus(str, Enum):
    VERIFIED = 'VERIFIED'
    PARTIAL = 'PARTIAL'
    FAILED = 'FAILED'
    UNVERIFIED = 'UNVERIFIED'


@dataclass(frozen=True)
class OperationResult:
    """Canonical evidence-aware result for tool/agent operations.

    `success` describes whether execution achieved a usable outcome. `status`
    describes how strongly that outcome is evidenced. A successful but unobserved
    external action is therefore valid as `success=True, status=UNVERIFIED`; callers
    must not upgrade it to VERIFIED merely because no exception was raised.
    """

    success: bool
    status: OperationStatus
    message: str
    evidence: tuple[Any, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    capability: str = ''

    def __post_init__(self) -> None:
        if self.status == OperationStatus.FAILED and self.success:
            raise ValueError('FAILED OperationResult cannot have success=True.')
        if self.duration_ms < 0:
            raise ValueError('duration_ms cannot be negative.')

    @property
    def verified(self) -> bool:
        return self.success and self.status == OperationStatus.VERIFIED

    @classmethod
    def verified_result(
        cls,
        message: str,
        *,
        capability: str = '',
        evidence: Iterable[Any] = (),
        warnings: Iterable[str] = (),
        metadata: dict[str, Any] | None = None,
        duration_ms: float = 0.0,
    ) -> 'OperationResult':
        return cls(
            True, OperationStatus.VERIFIED, str(message), tuple(evidence),
            tuple(str(item) for item in warnings), (), dict(metadata or {}),
            float(duration_ms), str(capability),
        )

    @classmethod
    def partial(
        cls,
        message: str,
        *,
        capability: str = '',
        evidence: Iterable[Any] = (),
        warnings: Iterable[str] = (),
        errors: Iterable[str] = (),
        metadata: dict[str, Any] | None = None,
        duration_ms: float = 0.0,
    ) -> 'OperationResult':
        return cls(
            True, OperationStatus.PARTIAL, str(message), tuple(evidence),
            tuple(str(item) for item in warnings), tuple(str(item) for item in errors),
            dict(metadata or {}), float(duration_ms), str(capability),
        )

    @classmethod
    def unverified(
        cls,
        message: str,
        *,
        capability: str = '',
        evidence: Iterable[Any] = (),
        warnings: Iterable[str] = (),
        metadata: dict[str, Any] | None = None,
        duration_ms: float = 0.0,
    ) -> 'OperationResult':
        return cls(
            True, OperationStatus.UNVERIFIED, str(message), tuple(evidence),
            tuple(str(item) for item in warnings), (), dict(metadata or {}),
            float(duration_ms), str(capability),
        )

    @classmethod
    def failed(
        cls,
        message: str,
        *,
        capability: str = '',
        evidence: Iterable[Any] = (),
        warnings: Iterable[str] = (),
        errors: Iterable[str] = (),
        metadata: dict[str, Any] | None = None,
        duration_ms: float = 0.0,
    ) -> 'OperationResult':
        normalized_errors = tuple(str(item) for item in errors) or (str(message),)
        return cls(
            False, OperationStatus.FAILED, str(message), tuple(evidence),
            tuple(str(item) for item in warnings), normalized_errors,
            dict(metadata or {}), float(duration_ms), str(capability),
        )

    def as_dict(self, *, flatten_metadata: bool = False) -> dict[str, Any]:
        data = asdict(self)
        data['status'] = self.status.value
        data['ok'] = self.success
        data['verified'] = self.verified
        data['evidence'] = list(self.evidence)
        data['warnings'] = list(self.warnings)
        data['errors'] = list(self.errors)
        if flatten_metadata:
            metadata = dict(data.pop('metadata'))
            # Canonical fields always win over compatibility metadata.
            for key, value in metadata.items():
                data.setdefault(key, value)
        return data

    @classmethod
    def from_legacy(
        cls,
        value: Any,
        *,
        capability: str = '',
        duration_ms: float = 0.0,
    ) -> 'OperationResult':
        """Normalize an existing string/dict tool result without inventing proof."""
        if isinstance(value, OperationResult):
            return value
        if isinstance(value, dict):
            ok = bool(value.get('ok', value.get('success', False)))
            verification = value.get('verification')
            verification_status = ''
            evidence: list[Any] = []
            if isinstance(verification, dict):
                verification_status = str(verification.get('status') or '').upper()
                if verification.get('evidence') not in (None, ''):
                    evidence.append(verification.get('evidence'))
            elif verification is not None:
                verification_status = str(verification).upper()

            if not ok:
                return cls.failed(
                    str(value.get('error') or value.get('message') or 'Operation failed.'),
                    capability=capability,
                    evidence=evidence,
                    metadata=dict(value),
                    duration_ms=duration_ms,
                )
            if verification_status == OperationStatus.VERIFIED.value:
                status = OperationStatus.VERIFIED
            elif verification_status == OperationStatus.PARTIAL.value:
                status = OperationStatus.PARTIAL
            elif verification_status == OperationStatus.FAILED.value:
                status = OperationStatus.FAILED
            else:
                status = OperationStatus.UNVERIFIED
            if status == OperationStatus.FAILED:
                return cls.failed(
                    str(value.get('message') or 'Verification failed.'),
                    capability=capability,
                    evidence=evidence,
                    metadata=dict(value),
                    duration_ms=duration_ms,
                )
            return cls(
                True,
                status,
                str(value.get('message') or value.get('result') or 'Operation completed.'),
                tuple(evidence),
                (),
                (),
                dict(value),
                float(duration_ms),
                str(capability),
            )

        text = str(value)
        return cls.unverified(
            text or 'Operation returned no structured evidence.',
            capability=capability,
            metadata={'legacy_output': text},
            duration_ms=duration_ms,
        )
