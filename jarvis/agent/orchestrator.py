from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Callable

from ..errors import ErrorCategory, Failure, classify_exception
from ..logging_utils import log_event
from .mission import Mission, MissionStatus, MissionStep, StepStatus, VerificationResult, utc_now
from .mission_store import MissionStore
from .recovery import RetryManager
from .verification import VerificationEngine


@dataclass
class MissionControl:
    cancel_event: threading.Event
    pause_event: threading.Event

    @classmethod
    def create(cls) -> 'MissionControl':
        return cls(threading.Event(), threading.Event())

    def cancel(self) -> None:
        self.cancel_event.set()
        self.pause_event.clear()

    def pause(self) -> None:
        self.pause_event.set()

    def resume(self) -> None:
        self.pause_event.clear()

    @property
    def cancelled(self) -> bool:
        return self.cancel_event.is_set()

    @property
    def paused(self) -> bool:
        return self.pause_event.is_set()

    def wait_if_paused(self, progress: Callable[[str], None]) -> bool:
        announced = False
        while self.paused and not self.cancelled:
            if not announced:
                progress('MISSION PAUSED')
                announced = True
            time.sleep(0.1)
        return not self.cancelled


class MissionOrchestrator:
    """Persisted V7 mission state machine with bounded recovery and evidence."""

    MAX_REPLANS = 2
    TERMINAL_STATES = frozenset({
        MissionStatus.COMPLETED,
        MissionStatus.PARTIAL,
        MissionStatus.FAILED,
        MissionStatus.CANCELLED,
    })
    LEGAL_TRANSITIONS = {
        MissionStatus.CREATED: frozenset({
            MissionStatus.PLANNING, MissionStatus.FAILED, MissionStatus.CANCELLED,
        }),
        MissionStatus.PLANNING: frozenset({
            MissionStatus.EXECUTING, MissionStatus.PAUSED,
            MissionStatus.FAILED, MissionStatus.CANCELLED,
        }),
        MissionStatus.AWAITING_PERMISSION: frozenset({
            MissionStatus.EXECUTING, MissionStatus.PAUSED,
            MissionStatus.FAILED, MissionStatus.CANCELLED,
        }),
        MissionStatus.EXECUTING: frozenset({
            MissionStatus.VERIFYING, MissionStatus.RECOVERING,
            MissionStatus.REPLANNING, MissionStatus.PAUSED,
            MissionStatus.FAILED, MissionStatus.CANCELLED,
        }),
        MissionStatus.VERIFYING: frozenset({
            MissionStatus.EXECUTING, MissionStatus.RECOVERING,
            MissionStatus.REPLANNING, MissionStatus.PAUSED,
            MissionStatus.COMPLETED, MissionStatus.PARTIAL,
            MissionStatus.FAILED, MissionStatus.CANCELLED,
        }),
        MissionStatus.RECOVERING: frozenset({
            MissionStatus.EXECUTING, MissionStatus.REPLANNING,
            MissionStatus.PAUSED, MissionStatus.FAILED, MissionStatus.CANCELLED,
        }),
        MissionStatus.REPLANNING: frozenset({
            MissionStatus.EXECUTING, MissionStatus.PAUSED,
            MissionStatus.FAILED, MissionStatus.CANCELLED,
        }),
        MissionStatus.PAUSED: frozenset({
            MissionStatus.EXECUTING, MissionStatus.VERIFYING,
            MissionStatus.RECOVERING, MissionStatus.REPLANNING,
            MissionStatus.FAILED, MissionStatus.CANCELLED,
        }),
    }

    def __init__(self, core, store: MissionStore | None = None) -> None:
        self.core = core
        self.store = store or MissionStore()
        self.verifier = VerificationEngine()
        self.retry = RetryManager()
        self._controls: dict[str, MissionControl] = {}
        self._lock = threading.RLock()
        self.current_mission_id: str | None = None

    def _control(self, mission_id: str) -> MissionControl | None:
        with self._lock:
            return self._controls.get(mission_id)

    def cancel(self, mission_id: str | None = None) -> bool:
        target = mission_id or self.current_mission_id
        if not target:
            return False
        control = self._control(target)
        if not control:
            return False
        control.cancel()
        self.store.add_event(target, 'control.cancel_requested')
        return True

    def pause(self, mission_id: str | None = None) -> bool:
        target = mission_id or self.current_mission_id
        if not target:
            return False
        control = self._control(target)
        if not control:
            return False
        control.pause()
        # The worker that owns the current mission snapshot acknowledges PAUSED.
        # Persisting a second snapshot here would race its optimistic revision.
        self.store.add_event(target, 'control.pause_requested')
        return True

    def resume(self, mission_id: str | None = None) -> bool:
        target = mission_id or self.current_mission_id
        if not target:
            return False
        control = self._control(target)
        if not control:
            return False
        control.resume()
        self.store.add_event(target, 'control.resume_requested')
        return True

    def get(self, mission_id: str) -> Mission | None:
        return self.store.get(mission_id)

    def recent(self, limit: int = 20) -> list[dict]:
        return self.store.list_recent(limit)

    def _transition(
        self,
        mission: Mission,
        status: MissionStatus,
        progress: Callable[[str], None],
        detail: str = '',
    ) -> None:
        current = mission.status
        if status != current and status not in self.LEGAL_TRANSITIONS.get(current, frozenset()):
            raise RuntimeError(
                f'Illegal mission transition: {current.value} -> {status.value}'
            )
        mission.touch(status)
        payload = {'status': status.value}
        if detail:
            payload['detail'] = detail[:1000]
        self.store.save_with_event(mission, 'mission.state', payload)
        log_event('MISSION', 'mission.state', mission_id=mission.id, status=status.value, detail=detail[:500])
        progress(status.value.replace('_', ' ') + (f': {detail}' if detail else ''))

    def _collect_tool_events(self) -> list[dict]:
        drain = getattr(getattr(self.core, 'tools', None), 'drain_events', None)
        return drain() if callable(drain) else []

    def _clear_tool_events(self) -> None:
        clear = getattr(getattr(self.core, 'tools', None), 'clear_events', None)
        if callable(clear):
            clear()

    def _await_control(
        self,
        mission: Mission,
        control: MissionControl,
        resume_status: MissionStatus,
        progress: Callable[[str], None],
    ) -> bool:
        """Acknowledge pause/resume on the worker-owned mission revision."""
        if control.cancelled:
            return False
        if control.paused:
            if mission.status != MissionStatus.PAUSED:
                self._transition(mission, MissionStatus.PAUSED, progress)
            if not control.wait_if_paused(progress):
                return False
            self._transition(mission, resume_status, progress, 'Resumed by operator')
        return not control.cancelled

    @staticmethod
    def _failure_from_verification(verification: VerificationResult) -> Failure:
        evidence_text = json.dumps(verification.evidence, ensure_ascii=False, default=str).lower()
        if 'not approved' in evidence_text or 'permission' in evidence_text or 'denied' in evidence_text:
            return Failure(ErrorCategory.PERMISSION_ERROR, verification.summary, retryable=False)
        if 'timeout' in evidence_text or 'timed out' in evidence_text:
            return Failure(ErrorCategory.TIMEOUT, verification.summary, retryable=True)
        if 'rate limit' in evidence_text:
            return Failure(ErrorCategory.RATE_LIMIT, verification.summary, retryable=True)
        return Failure(ErrorCategory.TOOL_ERROR, verification.summary, retryable=False)

    def _execute_step(
        self,
        mission: Mission,
        step: MissionStep,
        control: MissionControl,
        progress: Callable[[str], None],
    ) -> tuple[bool, Failure | None]:
        step.started_at = step.started_at or utc_now()
        step.status = StepStatus.EXECUTING
        mission.current_step = step.index
        self._transition(mission, MissionStatus.EXECUTING, progress, f'Step {step.index}: {step.description}')

        attempt = 0
        while True:
            if not self._await_control(
                mission, control, MissionStatus.EXECUTING, progress
            ):
                step.status = StepStatus.CANCELLED
                step.completed_at = utc_now()
                self.store.save(mission)
                return False, Failure(ErrorCategory.UNKNOWN_ERROR, 'Mission cancelled.', retryable=False)

            attempt += 1
            step.attempts = attempt
            if mission.status == MissionStatus.RECOVERING:
                self._transition(
                    mission,
                    MissionStatus.EXECUTING,
                    progress,
                    f'Step {step.index} retry {attempt}',
                )
            self._clear_tool_events()
            prompt = (
                'JARVIS OMEGA V7 MISSION STEP\n'
                f'Mission ID: {mission.id}\n'
                f'Overall goal: {mission.goal}\n'
                f'Current step {step.index}: {step.description}\n'
                'Use available tools only when needed. Respect every permission gate. '
                'Do not repeat a side-effecting action merely because a prior outcome is uncertain. '
                'Return a concise factual step result. Never invent a tool outcome.'
            )
            try:
                result = self.core.chat(prompt)
                events = self._collect_tool_events()
                step.result = result
                step.tool_events = events
                if not self._await_control(
                    mission, control, MissionStatus.EXECUTING, progress
                ):
                    step.status = StepStatus.CANCELLED
                    step.completed_at = utc_now()
                    self.store.save(mission)
                    return False, Failure(
                        ErrorCategory.UNKNOWN_ERROR,
                        'Mission cancelled.',
                        retryable=False,
                    )
                step.status = StepStatus.VERIFYING
                self._transition(mission, MissionStatus.VERIFYING, progress, f'Step {step.index}')
                verification = self.verifier.verify_step(result, events)
                step.verification = verification
                step.completed_at = utc_now()
                self.store.add_event(mission.id, 'step.verification', {
                    'step_id': step.id,
                    'step': step.index,
                    'status': verification.status,
                    'verified': verification.verified,
                    'summary': verification.summary,
                    'unverified_actions': verification.unverified_actions,
                })

                if verification.status != 'FAILED':
                    step.status = StepStatus.COMPLETED
                    if step.id not in mission.completed_steps:
                        mission.completed_steps.append(step.id)
                    mission.results.append({
                        'step': step.index,
                        'description': step.description,
                        'result': result,
                        'verification': verification.status,
                    })
                    self.store.save(mission)
                    progress(f'STEP {step.index} {verification.status}: {verification.summary}')
                    return True, None

                failure = self._failure_from_verification(verification)
            except Exception as exc:
                step.tool_events = self._collect_tool_events()
                step.error = f'{type(exc).__name__}: {exc}'[:2000]
                failure = classify_exception(
                    exc,
                    provider=getattr(self.core, 'last_provider_used', None),
                    operation='mission-step',
                )

            side_effecting = self.verifier.has_unsafe_retry_risk(step.tool_events)
            policy = self.retry.policy_for(failure, side_effecting=side_effecting)
            if attempt <= policy.max_attempts and failure.retryable:
                mission.retry_count += 1
                self._transition(
                    mission,
                    MissionStatus.RECOVERING,
                    progress,
                    f'Step {step.index} retry {attempt}/{policy.max_attempts} after {failure.category.value}',
                )
                if not self.retry.wait(failure, attempt, policy, lambda: control.cancelled):
                    return False, failure
                continue

            step.status = StepStatus.FAILED
            step.completed_at = utc_now()
            step.error = failure.message[:2000]
            if step.id not in mission.failed_steps:
                mission.failed_steps.append(step.id)
            mission.last_error = failure.message[:2000]
            self.store.save(mission)
            self.store.add_event(mission.id, 'step.failed', {
                'step_id': step.id,
                'step': step.index,
                'category': failure.category.value,
                'message': failure.message[:1000],
                'side_effecting_retry_blocked': side_effecting,
            })
            return False, failure

    def _replan(
        self,
        mission: Mission,
        failed_step: MissionStep,
        failure: Failure,
        progress: Callable[[str], None],
    ) -> list[MissionStep]:
        completed = [
            {'step': step.index, 'description': step.description, 'result': step.result[:1200]}
            for step in mission.plan
            if step.status == StepStatus.COMPLETED
        ]
        raw = self.core._one_shot_text(
            'You are JARVIS OMEGA V7 Replanner. Return only a JSON array of the smallest safe remaining steps. '
            'Preserve completed work. Do not repeat uncertain side effects. Do not bypass permissions. '
            'If recovery is impossible, return an empty JSON array.',
            (
                f'Goal: {mission.goal}\n'
                f'Completed work: {json.dumps(completed, ensure_ascii=False)}\n'
                f'Failed step: {failed_step.description}\n'
                f'Failure category: {failure.category.value}\n'
                f'Failure: {failure.message[:1500]}\n'
                'Maximum new steps: 5'
            ),
            'mission',
        )
        descriptions = self.core._extract_plan(raw, 5)
        start = max((step.index for step in mission.plan), default=0) + 1
        replacements = [
            MissionStep(index=start + i, description=text)
            for i, text in enumerate(descriptions)
            if text.strip() and text.strip() != '[]'
        ]
        failed_step.recovered_by = [step.id for step in replacements]
        self.store.add_event(mission.id, 'mission.replanned', {
            'failed_step': failed_step.index,
            'new_steps': [step.description for step in replacements],
        })
        progress('REPLAN: ' + (' | '.join(step.description for step in replacements) if replacements else 'No safe recovery plan.'))
        return replacements

    @staticmethod
    def _resolve_recovered_failures(mission: Mission) -> None:
        by_id = {step.id: step for step in mission.plan}
        for step in mission.plan:
            if step.status != StepStatus.FAILED or not step.recovered_by:
                continue
            recovery_steps = [by_id.get(step_id) for step_id in step.recovered_by]
            if recovery_steps and all(item is not None and item.status == StepStatus.COMPLETED for item in recovery_steps):
                step.recovered = True

    def _final_verification(self, mission: Mission) -> VerificationResult:
        self._resolve_recovered_failures(mission)
        completed = [step for step in mission.plan if step.status == StepStatus.COMPLETED]
        verifications = [step.verification for step in completed if step.verification]
        active_failures = [step for step in mission.plan if step.status == StepStatus.FAILED and not step.recovered]
        unverified: list[str] = []
        evidence: list[dict] = []
        for verification in verifications:
            evidence.extend(verification.evidence)
            unverified.extend(verification.unverified_actions)

        fully_verified = (
            bool(completed)
            and not active_failures
            and len(verifications) == len(completed)
            and all(item.verified for item in verifications)
        )
        if active_failures:
            status = 'FAILED'
            summary = f'{len(active_failures)} unrecovered mission step(s) failed.'
        elif unverified:
            status = 'PARTIAL'
            summary = f'Mission completed with {len(unverified)} externally unverified action(s).'
        elif fully_verified:
            status = 'VERIFIED'
            summary = 'All effective mission steps have verification evidence.'
        else:
            status = 'PARTIAL'
            summary = 'Mission produced results but final verification is incomplete.'
        return VerificationResult(
            verified=fully_verified,
            status=status,
            summary=summary,
            evidence=evidence[-100:],
            unverified_actions=unverified,
        )

    def _build_report(self, mission: Mission) -> str:
        verification = mission.final_verification
        lines = [
            f'Mission {mission.id}',
            f'Goal: {mission.goal}',
            f'Status: {mission.status.value}',
        ]
        if verification:
            lines.append(f'Verification: {verification.status} — {verification.summary}')
        lines.append('Steps:')
        for step in mission.plan:
            check = step.verification.status if step.verification else 'NOT VERIFIED'
            recovery = ' RECOVERED' if step.recovered else ''
            lines.append(f'- {step.index}. {step.description} [{step.status.value}{recovery}; {check}]')
        if mission.last_error and mission.status == MissionStatus.FAILED:
            lines.append(f'Blocker: {mission.last_error}')
        if verification and verification.unverified_actions:
            lines.append('Unverified external actions: ' + ', '.join(sorted(set(verification.unverified_actions))))
        if mission.status == MissionStatus.PARTIAL and verification and not verification.verified:
            lines.append('Important: JARVIS is not claiming full verified success for the unverified actions above.')
        return '\n'.join(lines)

    def run(self, goal: str, progress: Callable[[str], None] | None = None) -> Mission:
        progress = progress or (lambda _message: None)
        goal = goal.strip()
        if not goal:
            raise ValueError('Mission goal is empty.')

        mission = Mission(goal=goal, session_id=self.core.session_id)
        control = MissionControl.create()
        with self._lock:
            self._controls[mission.id] = control
            self.current_mission_id = mission.id
        self.store.save_with_event(mission, 'mission.created', {'goal': goal[:2000]})
        log_event('MISSION', 'mission.created', mission_id=mission.id, goal=goal[:500])

        try:
            self._transition(
                mission,
                MissionStatus.PLANNING,
                progress,
                'Understanding the goal and producing a bounded plan',
            )
            descriptions = self.core.plan_mission(goal)
            if not descriptions:
                mission.last_error = 'Planner returned no executable steps.'
                self._transition(mission, MissionStatus.FAILED, progress, mission.last_error)
                mission.final_verification = VerificationResult(False, 'FAILED', mission.last_error)
                mission.final_report = self._build_report(mission)
                self.store.save(mission)
                return mission

            mission.plan = [MissionStep(index=i + 1, description=text) for i, text in enumerate(descriptions)]
            self.store.save(mission)
            self.store.add_event(mission.id, 'mission.plan', {'steps': descriptions})
            progress('PLAN: ' + ' | '.join(descriptions))

            cursor = 0
            replans = 0
            while cursor < len(mission.plan):
                if control.cancelled:
                    self._transition(mission, MissionStatus.CANCELLED, progress)
                    break
                if not control.wait_if_paused(progress):
                    self._transition(mission, MissionStatus.CANCELLED, progress)
                    break

                step = mission.plan[cursor]
                if step.status in {StepStatus.COMPLETED, StepStatus.SUPERSEDED}:
                    cursor += 1
                    continue

                ok, failure = self._execute_step(mission, step, control, progress)
                if ok:
                    cursor += 1
                    continue
                if control.cancelled:
                    self._transition(mission, MissionStatus.CANCELLED, progress)
                    break

                if failure and failure.category == ErrorCategory.PERMISSION_ERROR:
                    mission.last_error = 'User permission was denied; mission stopped without bypassing the decision.'
                    self._transition(mission, MissionStatus.FAILED, progress, mission.last_error)
                    break

                if failure and replans < self.MAX_REPLANS:
                    replans += 1
                    mission.recovery_count += 1
                    self._transition(mission, MissionStatus.REPLANNING, progress, f'After step {step.index} failure')
                    try:
                        replacements = self._replan(mission, step, failure, progress)
                    except Exception as exc:
                        mission.last_error = f'Replanning failed: {type(exc).__name__}: {exc}'[:2000]
                        self._transition(mission, MissionStatus.FAILED, progress, mission.last_error)
                        break
                    if replacements:
                        for pending in mission.plan[cursor + 1:]:
                            if pending.status == StepStatus.PENDING:
                                pending.status = StepStatus.SUPERSEDED
                        mission.plan.extend(replacements)
                        self.store.save(mission)
                        cursor += 1
                        continue

                mission.last_error = failure.message if failure else 'Mission step failed.'
                self._transition(mission, MissionStatus.FAILED, progress, mission.last_error)
                break

            mission.final_verification = self._final_verification(mission)
            if mission.status not in {MissionStatus.FAILED, MissionStatus.CANCELLED}:
                if mission.final_verification.status == 'FAILED':
                    mission.last_error = mission.final_verification.summary
                    self._transition(mission, MissionStatus.FAILED, progress, mission.last_error)
                else:
                    mission.last_error = ''
                    final_status = (
                        MissionStatus.COMPLETED
                        if mission.final_verification.verified
                        else MissionStatus.PARTIAL
                    )
                    self._transition(mission, final_status, progress, mission.final_verification.summary)

            mission.final_report = self._build_report(mission)
            self.store.save(mission)
            self.store.add_event(mission.id, 'mission.finished', {
                'status': mission.status.value,
                'verification': mission.final_verification.status if mission.final_verification else 'UNKNOWN',
                'retry_count': mission.retry_count,
                'recovery_count': mission.recovery_count,
            })
            return mission
        finally:
            with self._lock:
                self._controls.pop(mission.id, None)
                if self.current_mission_id == mission.id:
                    self.current_mission_id = None
