from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .capabilities import Capability, RiskLevel, ToolSecurityProfile, profile_for


class PermissionPolicy(str, Enum):
    ALLOW = 'allow'
    ASK = 'ask'
    ALWAYS_ASK = 'always_ask'
    DENY = 'deny'


class ApprovalDecision(str, Enum):
    ALLOW_ONCE = 'allow_once'
    ALLOW_SESSION = 'allow_session'
    DENY = 'deny'
    CANCEL_MISSION = 'cancel_mission'


DEFAULT_POLICIES: dict[Capability, PermissionPolicy] = {
    Capability.SYSTEM_READ: PermissionPolicy.ALLOW,
    Capability.MEMORY_READ: PermissionPolicy.ALLOW,
    Capability.MEMORY_WRITE: PermissionPolicy.ALLOW,
    Capability.FILE_READ: PermissionPolicy.ALLOW,
    Capability.FILE_WRITE: PermissionPolicy.ASK,
    Capability.SCREEN_READ: PermissionPolicy.ASK,
    Capability.SCREEN_CONTROL: PermissionPolicy.ASK,
    Capability.BROWSER_READ: PermissionPolicy.ALLOW,
    Capability.BROWSER_CONTROL: PermissionPolicy.ASK,
    Capability.KEYBOARD_CONTROL: PermissionPolicy.ASK,
    Capability.MOUSE_CONTROL: PermissionPolicy.ASK,
    Capability.CODE_READ: PermissionPolicy.ALLOW,
    Capability.CODE_WRITE: PermissionPolicy.ASK,
    Capability.CODE_TEST: PermissionPolicy.ASK,
    Capability.EMAIL_READ: PermissionPolicy.ALLOW,
    Capability.EMAIL_SEND: PermissionPolicy.ALWAYS_ASK,
    Capability.CALENDAR_READ: PermissionPolicy.ALLOW,
    Capability.CALENDAR_WRITE: PermissionPolicy.ALWAYS_ASK,
    Capability.WEB_READ: PermissionPolicy.ALLOW,
    Capability.APP_CONTROL: PermissionPolicy.ASK,
    Capability.DOCUMENT_READ: PermissionPolicy.ASK,
    Capability.GIT_READ: PermissionPolicy.ALLOW,
    Capability.ACCOUNT_CONFIG_READ: PermissionPolicy.ASK,
}


@dataclass(frozen=True)
class ApprovalRequest:
    tool_name: str
    risk: RiskLevel
    capabilities: tuple[Capability, ...]
    args: dict
    why: str
    policies: dict[str, str]

    def display_payload(self) -> dict:
        return {
            '__approval__': {
                'action': self.tool_name,
                'target': _target_summary(self.tool_name, self.args),
                'risk': self.risk.value,
                'why': self.why,
                'capabilities': [item.value for item in self.capabilities],
                'policies': self.policies,
            },
            'arguments': _safe_argument_summary(self.args),
        }


@dataclass(frozen=True)
class PermissionOutcome:
    allowed: bool
    decision: ApprovalDecision
    profile: ToolSecurityProfile
    reason: str


def _safe_argument_summary(args: dict) -> dict:
    secret_tokens = ('key', 'token', 'password', 'secret', 'authorization', 'credential')
    output = {}
    for key, value in args.items():
        lower = str(key).lower()
        if any(token in lower for token in secret_tokens):
            output[str(key)] = '[REDACTED]'
            continue
        if str(key) in {'content', 'body', 'text'} and len(str(value)) > 160:
            output[str(key)] = f'<{key} {len(str(value))} chars>'
            continue
        text = str(value)
        output[str(key)] = text if len(text) <= 500 else text[:500] + '…'
    return output


def _target_summary(tool_name: str, args: dict) -> str:
    for key in ('to', 'file_path', 'path', 'url', 'app', 'query', 'folder', 'project_dir', 'summary', 'subject'):
        if key in args and str(args[key]).strip():
            return f'{key}: {str(args[key])[:240]}'
    if tool_name == 'click_screen':
        return f'coordinate: ({args.get("x")}, {args.get("y")})'
    if tool_name in {'type_text', 'press_key', 'hotkey'}:
        return 'currently focused desktop application'
    return 'local JARVIS runtime'


def _normalize_policy(raw: str | None, default: PermissionPolicy) -> PermissionPolicy:
    value = (raw or '').strip().lower()
    aliases = {
        'allow': PermissionPolicy.ALLOW,
        'allowed': PermissionPolicy.ALLOW,
        'ask': PermissionPolicy.ASK,
        'always_ask': PermissionPolicy.ALWAYS_ASK,
        'always-ask': PermissionPolicy.ALWAYS_ASK,
        'deny': PermissionPolicy.DENY,
        'denied': PermissionPolicy.DENY,
    }
    return aliases.get(value, default)


def policy_for(capability: Capability) -> PermissionPolicy:
    env_name = f'PERMISSION_{capability.value}'
    return _normalize_policy(os.getenv(env_name), DEFAULT_POLICIES.get(capability, PermissionPolicy.DENY))


def normalize_decision(value) -> ApprovalDecision:
    if isinstance(value, ApprovalDecision):
        return value
    if value is True:
        return ApprovalDecision.ALLOW_ONCE
    if value is False or value is None:
        return ApprovalDecision.DENY
    raw = str(value).strip().lower()
    for decision in ApprovalDecision:
        if raw == decision.value:
            return decision
    return ApprovalDecision.DENY


class CapabilityPermissionGate:
    """Granular V7 capability gate with backward-compatible approval callbacks."""

    def __init__(
        self,
        confirmer: Callable[[str, dict], object] | None = None,
        *,
        require_approval: bool = True,
    ) -> None:
        self.confirmer = confirmer
        self.require_approval = require_approval
        self._session_grants: set[Capability] = set()
        self._lock = threading.RLock()
        self._last_outcome: PermissionOutcome | None = None

    def clear_session_grants(self) -> None:
        with self._lock:
            self._session_grants.clear()

    def _set_outcome(self, outcome: PermissionOutcome) -> None:
        with self._lock:
            self._last_outcome = outcome

    def consume_last_outcome(self) -> PermissionOutcome | None:
        with self._lock:
            outcome = self._last_outcome
            self._last_outcome = None
            return outcome

    def check(self, tool_name: str, args: dict) -> bool:
        profile = profile_for(tool_name)
        capabilities = tuple(sorted(profile.capabilities, key=lambda item: item.value))

        if not capabilities:
            outcome = PermissionOutcome(False, ApprovalDecision.DENY, profile, 'Unprofiled tool has no granted capabilities.')
            self._set_outcome(outcome)
            raise PermissionError(f"Tool '{tool_name}' has no V7 capability profile and is denied by default.")

        policies = {cap.value: policy_for(cap) for cap in capabilities}
        if any(policy == PermissionPolicy.DENY for policy in policies.values()):
            outcome = PermissionOutcome(False, ApprovalDecision.DENY, profile, 'One or more required capabilities are denied.')
            self._set_outcome(outcome)
            denied = ', '.join(cap for cap, policy in policies.items() if policy == PermissionPolicy.DENY)
            raise PermissionError(f'Denied by V7 capability policy: {denied}')

        with self._lock:
            granted = set(self._session_grants)

        requires_always = [cap for cap in capabilities if policies[cap.value] == PermissionPolicy.ALWAYS_ASK]
        requires_ask = [
            cap for cap in capabilities
            if policies[cap.value] == PermissionPolicy.ASK and cap not in granted
        ]
        needs_prompt = bool(requires_always or requires_ask)

        if not self.require_approval and not requires_always:
            needs_prompt = False

        if not needs_prompt:
            outcome = PermissionOutcome(True, ApprovalDecision.ALLOW_ONCE, profile, 'Allowed by configured capability policy.')
            self._set_outcome(outcome)
            return True

        if self.confirmer is None:
            outcome = PermissionOutcome(False, ApprovalDecision.DENY, profile, 'Approval is required but no approval UI/callback is available.')
            self._set_outcome(outcome)
            raise PermissionError(f"Tool '{tool_name}' requires user approval.")

        request = ApprovalRequest(
            tool_name=tool_name,
            risk=profile.risk,
            capabilities=capabilities,
            args=dict(args),
            why=profile.why,
            policies={key: value.value for key, value in policies.items()},
        )
        decision = normalize_decision(self.confirmer(tool_name, request.display_payload()))

        if decision == ApprovalDecision.ALLOW_SESSION:
            grantable = [cap for cap in requires_ask if policies[cap.value] == PermissionPolicy.ASK]
            with self._lock:
                self._session_grants.update(grantable)
            if requires_always:
                decision = ApprovalDecision.ALLOW_ONCE

        allowed = decision in {ApprovalDecision.ALLOW_ONCE, ApprovalDecision.ALLOW_SESSION}
        reason = 'User approved the action.' if allowed else 'User denied/cancelled the action.'
        outcome = PermissionOutcome(allowed, decision, profile, reason)
        self._set_outcome(outcome)
        if not allowed:
            raise PermissionError(
                'Mission cancellation requested by user.'
                if decision == ApprovalDecision.CANCEL_MISSION
                else 'Action was not approved by user.'
            )
        return True
