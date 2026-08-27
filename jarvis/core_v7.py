from __future__ import annotations

import json
import re
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from .attachments import image_data_url, normalize_image_paths
from .config import settings
from .config_validation import require_valid_settings
from .errors import ErrorCategory, classify_exception
from .memory import MemoryStore
from .prompt import system_prompt
from .providers import ToolResult, create_local_provider, create_primary_provider
from .providers.deadline import (
    RequestBudget,
    RequestCancelledError,
    call_with_deadline,
    current_request_budget,
    request_lifecycle,
)
from .tools import ToolRegistry


class JarvisOmega:
    """JARVIS OMEGA V7 compatibility core.

    Phase 1 keeps the public V6 JarvisOmega interface while moving model/provider
    SDK details behind `jarvis.providers`. Later V7 phases place orchestration,
    mission state, verification and recovery above this class.
    """

    SMART_HINTS = {
        'analyze', 'analyse', 'debug', 'error', 'architecture', 'plan', 'mission', 'compare',
        'reason', 'why', 'code', 'project', 'security', 'document', 'review', 'research',
        'समझाओ', 'क्यों', 'विश्लेषण', 'problem', 'issue', 'fix', 'advance', 'advanced',
    }

    def __init__(self, confirmer: Callable[[str, dict], bool] | None = None):
        require_valid_settings(settings)
        self.provider = create_primary_provider(settings)
        self.local_provider = create_local_provider(settings)
        # Temporary compatibility for the V6 runtime quality guard. This will be
        # removed when the quality/model router becomes a normal V7 service.
        self.client = getattr(self.provider, 'client', None)

        self.memory = MemoryStore()
        self.tools = ToolRegistry(self.memory, confirmer)
        self.session_id = self.memory.new_session('JARVIS OMEGA V7 session')
        self.last_latency = 0.0
        self.last_model_used = settings.model
        self.last_provider_used = settings.provider
        self.last_route = 'default'
        self.last_tool_mode = 'full'
        self.last_request_kind = 'chat'
        self.last_plan: list[str] = []
        self._active_model = settings.model
        self._request_lock = threading.RLock()
        self._active_request: RequestBudget | None = None
        self.last_request_id: str | None = None

    @contextmanager
    def _request_scope(
        self,
        timeout: float,
        operation: str,
        request_id: str | None = None,
    ) -> Iterator[RequestBudget]:
        parent = current_request_budget()
        if parent is not None:
            yield parent
            return
        with request_lifecycle(timeout, operation=operation, request_id=request_id) as budget:
            with self._request_lock:
                self._active_request = budget
                self.last_request_id = budget.request_id
            try:
                yield budget
            finally:
                with self._request_lock:
                    if self._active_request is budget:
                        self._active_request = None

    def cancel_current_request(self) -> bool:
        """Return control to the UI promptly; blocking provider work is daemonized."""
        with self._request_lock:
            request = self._active_request
        if request is None:
            return False
        request.cancel()
        return True

    def new_session(self) -> str:
        self.session_id = self.memory.new_session('JARVIS OMEGA V7 session')
        return self.session_id

    def _select_model(self, text: str, kind: str = 'chat') -> str:
        if kind == 'image':
            self.last_route = 'vision'
            return settings.routed_vision_model
        if kind in {'mission', 'summary', 'review'}:
            self.last_route = 'smart'
            return settings.routed_smart_model
        if settings.model_routing not in {'auto', 'on', 'true'}:
            self.last_route = 'default'
            return settings.model
        lower = text.lower()
        smart = len(text) > 700 or any(hint in lower for hint in self.SMART_HINTS)
        self.last_route = 'smart' if smart else 'fast'
        return settings.routed_smart_model if smart else settings.routed_fast_model

    def _system_instructions(self) -> str:
        prompt = system_prompt()
        summary = self.memory.get_session_summary(self.session_id)
        if summary:
            prompt += (
                '\n\nSESSION CONTINUITY SUMMARY (locally stored, may be incomplete):\n'
                + summary[:12000]
                + '\nUse it only as conversation context; current user messages override stale summary details.'
            )
        return prompt

    def _history(self) -> list[dict]:
        return [
            {'role': role, 'content': content}
            for role, content in self.memory.recent_messages(self.session_id)
        ]

    @staticmethod
    def _status_code(exc: BaseException) -> int | None:
        value = getattr(exc, 'status_code', None)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _friendly_error(self, exc: BaseException) -> RuntimeError:
        failure = classify_exception(exc, provider=settings.provider, operation=self.last_request_kind)
        provider = 'OpenRouter' if settings.provider == 'openrouter' else 'OpenAI'
        messages = {
            ErrorCategory.AUTH_ERROR: f'{provider} API key reject ho gayi. .env me key check/recreate karo.',
            ErrorCategory.PERMISSION_ERROR: f'{provider} request permission/policy ki wajah se block hui.',
            ErrorCategory.RATE_LIMIT: f'{provider} rate limit/quota hit hua. Thodi der baad retry karo.',
            ErrorCategory.TIMEOUT: 'AI provider response timeout hua. Internet/model availability check karke retry karo.',
            ErrorCategory.NETWORK_ERROR: 'AI provider/network temporarily unavailable hai. Connection check karke retry karo.',
            ErrorCategory.RESOURCE_NOT_FOUND: 'Requested model/resource available nahi mila.',
            ErrorCategory.VISION_ERROR: 'Selected model image vision support nahi kar raha. Vision-capable model se retry karo.',
            ErrorCategory.MODEL_ERROR: 'Configured AI model abhi available nahi hai. Model setting check karo.',
            ErrorCategory.INVALID_INPUT: f'{provider} request input invalid tha: {failure.message[:350]}',
        }
        return RuntimeError(messages.get(failure.category, f'{provider} request failed: {failure.message[:500]}'))

    def _can_local_fallback(self) -> bool:
        return self.local_provider is not None and bool(settings.local_ai_model)

    def _chat_local_fallback(self, primary_error: BaseException) -> str:
        if not self._can_local_fallback():
            raise self._friendly_error(primary_error) from primary_error
        assert self.local_provider is not None
        try:
            turn = self.local_provider.chat(
                system=self._system_instructions(),
                messages=self._history(),
                model=settings.local_ai_model,
                timeout=settings.ai_timeout_seconds,
            )
            self.last_provider_used = 'local-fallback'
            self.last_model_used = turn.model or settings.local_ai_model
            self.last_tool_mode = 'local-fallback-no-tools'
            return turn.text.strip() or 'Local fallback model returned no text output.'
        except Exception as local_exc:
            friendly = self._friendly_error(primary_error)
            raise RuntimeError(f'{friendly}\nLocal fallback also failed: {local_exc}') from local_exc

    def chat(self, text: str, *, request_id: str | None = None) -> str:
        text = text.strip()
        if not text:
            return ''

        self.last_request_kind = 'chat'
        self._active_model = self._select_model(text, 'chat')
        self.last_provider_used = settings.provider
        started = time.perf_counter()
        with self._request_scope(settings.ai_timeout_seconds, 'AI request', request_id):
            self.memory.add_message(self.session_id, 'user', text)
            try:
                try:
                    answer = self._chat_provider()
                except RequestCancelledError:
                    raise
                except Exception as exc:
                    answer = self._chat_local_fallback(exc)
                self.memory.add_message(self.session_id, 'assistant', answer)
                self._maybe_auto_summary()
                return answer
            finally:
                self.last_latency = time.perf_counter() - started

    def analyze_image(self, image_path: str | Path, prompt: str) -> str:
        return self.analyze_images([image_path], prompt)

    def analyze_images(
        self,
        image_paths: list[str | Path],
        prompt: str,
        *,
        request_id: str | None = None,
    ) -> str:
        paths = normalize_image_paths(image_paths)
        user_prompt = prompt.strip() or (
            'Analyze the attached image(s). Explain what is visible, identify important details or errors, '
            'and tell me what I should do next.'
        )
        self.last_request_kind = 'image'
        self._active_model = self._select_model(user_prompt, 'image')
        self.last_provider_used = settings.provider
        started = time.perf_counter()
        names = ', '.join(path.name for path in paths)
        with self._request_scope(settings.vision_timeout_seconds, 'AI vision request', request_id):
            self.memory.add_message(self.session_id, 'user', f'[IMAGE ATTACHMENT: {names}] {user_prompt}')
            try:
                turn = self.provider.vision(
                    system=self._system_instructions(),
                    prompt=user_prompt,
                    image_urls=[image_data_url(path) for path in paths],
                    model=self._active_model,
                    timeout=settings.vision_timeout_seconds,
                )
                self.last_model_used = turn.model or self._active_model
                self.last_provider_used = turn.provider or settings.provider
                self.last_tool_mode = f'vision-{len(paths)}-image'
                answer = turn.text.strip() or 'Image analysis completed but no text answer was returned.'
                self.memory.add_message(self.session_id, 'assistant', answer)
                return answer
            except RequestCancelledError:
                raise
            except Exception as exc:
                raise self._friendly_error(exc) from exc
            finally:
                self.last_latency = time.perf_counter() - started

    def _one_shot_text(self, instruction: str, prompt: str, kind: str = 'smart') -> str:
        model = self._select_model(prompt, kind if kind in {'mission', 'summary', 'review'} else 'mission')
        try:
            text = self.provider.structured_output(
                system=instruction,
                prompt=prompt,
                model=model,
                timeout=settings.ai_timeout_seconds,
            )
            self.last_provider_used = self.provider.name
            self.last_model_used = model
            return text.strip()
        except Exception as exc:
            if self._can_local_fallback():
                assert self.local_provider is not None
                try:
                    text = self.local_provider.structured_output(
                        system=instruction,
                        prompt=prompt,
                        model=settings.local_ai_model,
                        timeout=settings.ai_timeout_seconds,
                    )
                    self.last_provider_used = 'local-fallback'
                    self.last_model_used = settings.local_ai_model
                    return text.strip()
                except Exception:
                    pass
            raise self._friendly_error(exc) from exc

    def summarize_session(self) -> str:
        rows = self.memory.session_messages(self.session_id, 250)
        if not rows:
            return 'No conversation to summarize.'
        transcript_parts = []
        for row in rows:
            label = 'USER' if row['role'] == 'user' else 'JARVIS'
            transcript_parts.append(f'{label}: {row["content"]}')
        transcript = '\n'.join(transcript_parts)
        if len(transcript) > 60000:
            transcript = transcript[-60000:]
        summary = self._one_shot_text(
            'Create a compact factual continuity summary for a future AI turn. Preserve user preferences, decisions, '
            'project state, unresolved tasks, important tool outcomes, and constraints. Do not include private chain-of-thought. '
            'Do not store passwords/API keys/secrets. Output plain concise text.',
            transcript,
            'summary',
        )
        self.memory.set_session_summary(self.session_id, summary)
        return summary

    def _maybe_auto_summary(self) -> None:
        if not settings.auto_summarize:
            return
        threshold = max(20, settings.summarize_after_messages)
        count = self.memory.message_count(self.session_id)
        if count >= threshold and count % threshold in {0, 1}:
            try:
                self.summarize_session()
            except Exception:
                pass

    @staticmethod
    def _extract_plan(raw: str, max_steps: int) -> list[str]:
        cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.IGNORECASE)
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                parsed = parsed.get('steps', [])
            if isinstance(parsed, list):
                steps = [str(x).strip() for x in parsed if str(x).strip()]
                if steps:
                    return steps[:max_steps]
        except Exception:
            pass
        steps = []
        for line in raw.splitlines():
            line = re.sub(r'^\s*(?:[-*]|\d+[.)])\s*', '', line).strip()
            if line:
                steps.append(line)
        return steps[:max_steps] or [raw.strip()[:600]]

    def plan_mission(self, goal: str) -> list[str]:
        goal = goal.strip()
        if not goal:
            return []
        self.last_request_kind = 'mission-plan'
        raw = self._one_shot_text(
            'You are JARVIS OMEGA V7 Planner. Produce only a JSON array of short executable high-level steps. '
            'Do not include private reasoning. Prefer the smallest safe plan. Never plan credential access, security bypass, '
            'arbitrary shell execution, deletion, persistence, or actions outside the available JARVIS tools.',
            f'Goal: {goal}\nMaximum steps: {settings.mission_max_steps}',
            'mission',
        )
        self.last_plan = self._extract_plan(raw, max(1, settings.mission_max_steps))
        return self.last_plan

    def run_mission(self, goal: str, progress: Callable[[str], None] | None = None) -> str:
        """V6-compatible mission loop. Replaced by persisted V7 orchestrator in Phase 2."""
        progress = progress or (lambda _msg: None)
        started = time.perf_counter()
        self.last_request_kind = 'mission'
        plan = self.plan_mission(goal)
        if not plan:
            return 'Mission plan could not be created.'
        progress('PLAN: ' + ' | '.join(plan))

        results: list[str] = []
        for index, step in enumerate(plan, 1):
            progress(f'EXECUTING {index}/{len(plan)}: {step}')
            prompt = (
                f'JARVIS OMEGA V7 MISSION\nOverall goal: {goal}\n'
                f'Current step {index}/{len(plan)}: {step}\n'
                'Execute this step using available tools only when needed. Respect every permission gate. '
                'Return a concise result for this step. Never claim a tool succeeded if its result says it failed.'
            )
            result = self.chat(prompt)
            results.append(result)
            progress(f'COMPLETED {index}/{len(plan)}')

        joined = '\n\n'.join(f'Step {i + 1}: {r}' for i, r in enumerate(results))
        progress('REVIEWING MISSION...')
        review = self._one_shot_text(
            'You are JARVIS OMEGA V7 Reviewer. Review the supplied mission results. Do not invent tool outcomes. '
            'Give a concise final status, what was completed, what is unverified, blockers, and exact next action if needed.',
            f'Goal: {goal}\nPlan: {json.dumps(plan, ensure_ascii=False)}\nExecution results:\n{joined}',
            'review',
        )
        self.memory.add_message(self.session_id, 'assistant', f'[MISSION REVIEW]\n{review}')
        self.last_latency = time.perf_counter() - started
        return review

    @staticmethod
    def _tool_compat_problem(exc: BaseException) -> bool:
        status = JarvisOmega._status_code(exc)
        lower = str(exc).lower()
        return (
            status in {400, 404, 422}
            and any(word in lower for word in ('tool', 'function', 'unsupported', 'parameter', 'schema'))
        )

    def _chat_provider(self) -> str:
        messages = self._history()
        tools = self.tools.schemas(include_local=settings.enable_local_tools)
        self.last_tool_mode = 'full' if tools else 'no-tools'

        try:
            turn = self.provider.chat_with_tools(
                system=self._system_instructions(),
                messages=messages,
                model=self._active_model,
                tools=tools,
                timeout=settings.ai_timeout_seconds,
            ) if tools else self.provider.chat(
                system=self._system_instructions(),
                messages=messages,
                model=self._active_model,
                timeout=settings.ai_timeout_seconds,
            )
        except Exception as exc:
            if tools and self._tool_compat_problem(exc):
                self.last_tool_mode = 'fallback-no-tools'
                tools = []
                turn = self.provider.chat(
                    system=self._system_instructions(),
                    messages=messages,
                    model=self._active_model,
                    timeout=settings.ai_timeout_seconds,
                )
            else:
                raise

        for _ in range(settings.max_tool_rounds):
            self.last_model_used = turn.model or self._active_model
            self.last_provider_used = turn.provider or self.provider.name
            if not turn.tool_calls:
                return turn.text.strip() or 'I completed the turn but received no text output.'

            results: list[ToolResult] = []
            for call in turn.tool_calls:
                try:
                    args = json.loads(call.arguments or '{}')
                    if not isinstance(args, dict):
                        args = {}
                except json.JSONDecodeError:
                    args = {}
                output = call_with_deadline(
                    lambda name=call.name, arguments=args: self.tools.call(name, arguments),
                    settings.ai_timeout_seconds,
                    operation=f'Tool {call.name}',
                )
                results.append(ToolResult(call_id=call.id, output=output))

            turn = self.provider.continue_with_tools(
                previous=turn,
                tool_results=results,
                system=self._system_instructions(),
                model=self._active_model,
                tools=tools,
                timeout=settings.ai_timeout_seconds,
            )

        return 'I hit the configured tool-round limit and stopped safely.'

    # Compatibility methods retained for the V6 runtime guard during Phase 1.
    def _chat_openrouter(self) -> str:
        return self._chat_provider()

    def _chat_openai(self) -> str:
        return self._chat_provider()
