from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Callable

from openai import OpenAI

from .attachments import image_data_url, normalize_image_paths
from .config import settings
from .memory import MemoryStore
from .prompt import system_prompt
from .tools import ToolRegistry


class JarvisOmega:
    def __init__(self, confirmer: Callable[[str, dict], bool] | None = None):
        if settings.provider not in {'openrouter', 'openai'}:
            raise RuntimeError("AI_PROVIDER must be 'openrouter' or 'openai'.")
        if not settings.api_key:
            key_name = 'OPENROUTER_API_KEY' if settings.provider == 'openrouter' else 'OPENAI_API_KEY'
            raise RuntimeError(f'{key_name} is missing. Add it to your .env file.')

        client_kwargs = {
            'api_key': settings.api_key,
            'timeout': max(settings.ai_timeout_seconds, settings.vision_timeout_seconds),
            'max_retries': max(0, settings.api_max_retries),
        }
        if settings.provider == 'openrouter':
            client_kwargs.update({
                'base_url': settings.openrouter_base_url,
                'default_headers': {
                    'HTTP-Referer': settings.openrouter_app_url,
                    'X-OpenRouter-Title': settings.openrouter_app_title,
                },
            })
        self.client = OpenAI(**client_kwargs)

        self.memory = MemoryStore()
        self.tools = ToolRegistry(self.memory, confirmer)
        self.session_id = self.memory.new_session('JARVIS OMEGA V6 session')
        self.last_latency = 0.0
        self.last_model_used = settings.model
        self.last_tool_mode = 'full'
        self.last_request_kind = 'chat'
        self.last_plan: list[str] = []

    def new_session(self) -> str:
        self.session_id = self.memory.new_session('JARVIS OMEGA V6 session')
        return self.session_id

    def _openai_model_tools(self) -> list[dict]:
        tools = self.tools.schemas(include_local=settings.enable_local_tools)
        if settings.hosted_web_search_enabled:
            tools.append({'type': 'web_search'})
        if settings.code_interpreter_enabled:
            tools.append({'type': 'code_interpreter', 'container': {'type': 'auto'}})
        return tools

    def _openrouter_model_tools(self) -> list[dict]:
        converted = []
        for spec in self.tools.schemas(include_local=settings.enable_local_tools):
            converted.append({
                'type': 'function',
                'function': {
                    'name': spec['name'],
                    'description': spec['description'],
                    'parameters': spec['parameters'],
                },
            })
        return converted

    def _history(self) -> list[dict]:
        return [
            {'role': role, 'content': content}
            for role, content in self.memory.recent_messages(self.session_id)
        ]

    @staticmethod
    def _dump_item(item):
        return item.model_dump(exclude_none=True) if hasattr(item, 'model_dump') else item

    @staticmethod
    def _status_code(exc: Exception) -> int | None:
        status = getattr(exc, 'status_code', None)
        try:
            return int(status) if status is not None else None
        except (TypeError, ValueError):
            return None

    def _friendly_error(self, exc: Exception) -> RuntimeError:
        status = self._status_code(exc)
        raw = str(exc)
        lower = raw.lower()
        provider = 'OpenRouter' if settings.provider == 'openrouter' else 'OpenAI'

        if status == 401 or 'invalid api key' in lower or 'authentication' in lower:
            return RuntimeError(f'{provider} API key reject ho gayi. .env me key check/recreate karo.')
        if status == 429 or 'rate limit' in lower:
            return RuntimeError(f'{provider} rate limit/quota hit hua. Thodi der baad retry karo.')
        if status in {402, 403}:
            return RuntimeError(f'{provider} request permission/credit policy ki wajah se block hui.')
        if 'no endpoints found' in lower or 'model not found' in lower:
            return RuntimeError('Configured AI model abhi available nahi hai. Model setting check karo.')
        if 'image' in lower and any(word in lower for word in ('unsupported', 'modality', 'vision')):
            return RuntimeError('Selected/free model image vision support nahi kar raha. Retry karo ya vision-capable model choose karo.')
        if 'timeout' in lower or 'timed out' in lower:
            return RuntimeError('AI provider response timeout hua. Internet/free-model availability check karke retry karo.')
        return RuntimeError(f'{provider} request failed: {raw[:500]}')

    def chat(self, text: str) -> str:
        text = text.strip()
        if not text:
            return ''

        self.last_request_kind = 'chat'
        started = time.perf_counter()
        self.memory.add_message(self.session_id, 'user', text)
        try:
            if settings.provider == 'openrouter':
                answer = self._chat_openrouter()
            else:
                answer = self._chat_openai()
            self.memory.add_message(self.session_id, 'assistant', answer)
            return answer
        finally:
            self.last_latency = time.perf_counter() - started

    def analyze_image(self, image_path: str | Path, prompt: str) -> str:
        return self.analyze_images([image_path], prompt)

    def analyze_images(self, image_paths: list[str | Path], prompt: str) -> str:
        paths = normalize_image_paths(image_paths)
        user_prompt = prompt.strip() or (
            'Analyze the attached image(s). Explain what is visible, identify important details or errors, '
            'and tell me what I should do next.'
        )
        self.last_request_kind = 'image'
        started = time.perf_counter()
        names = ', '.join(path.name for path in paths)
        self.memory.add_message(self.session_id, 'user', f'[IMAGE ATTACHMENT: {names}] {user_prompt}')

        content: list[dict] = [{'type': 'text', 'text': user_prompt}]
        for path in paths:
            content.append({'type': 'image_url', 'image_url': {'url': image_data_url(path)}})

        try:
            response = self.client.chat.completions.create(
                model=settings.model,
                messages=[
                    {'role': 'system', 'content': system_prompt()},
                    {'role': 'user', 'content': content},
                ],
                timeout=settings.vision_timeout_seconds,
            )
            self.last_model_used = getattr(response, 'model', settings.model) or settings.model
            self.last_tool_mode = f'vision-{len(paths)}-image'
            message = response.choices[0].message
            answer = message.content.strip() if isinstance(message.content, str) else str(message.content or '').strip()
            answer = answer or 'Image analysis completed but no text answer was returned.'
            self.memory.add_message(self.session_id, 'assistant', answer)
            return answer
        except Exception as exc:
            raise self._friendly_error(exc) from exc
        finally:
            self.last_latency = time.perf_counter() - started

    def _one_shot_text(self, instruction: str, prompt: str) -> str:
        try:
            if settings.provider == 'openrouter':
                response = self.client.chat.completions.create(
                    model=settings.model,
                    messages=[
                        {'role': 'system', 'content': instruction},
                        {'role': 'user', 'content': prompt},
                    ],
                    timeout=settings.ai_timeout_seconds,
                )
                self.last_model_used = getattr(response, 'model', settings.model) or settings.model
                content = response.choices[0].message.content
                return content.strip() if isinstance(content, str) else str(content or '').strip()

            response = self.client.responses.create(
                model=settings.model,
                reasoning={'effort': settings.reasoning_effort},
                instructions=instruction,
                input=prompt,
                store=False,
                timeout=settings.ai_timeout_seconds,
            )
            self.last_model_used = getattr(response, 'model', settings.model) or settings.model
            return (response.output_text or '').strip()
        except Exception as exc:
            raise self._friendly_error(exc) from exc

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
            'You are JARVIS OMEGA V6 Planner. Produce only a JSON array of short executable high-level steps. '
            'Do not include private reasoning. Prefer the smallest safe plan. Never plan credential access, security bypass, '
            'arbitrary shell execution, deletion, persistence, or actions outside the available JARVIS tools.',
            f'Goal: {goal}\nMaximum steps: {settings.mission_max_steps}',
        )
        self.last_plan = self._extract_plan(raw, max(1, settings.mission_max_steps))
        return self.last_plan

    def run_mission(self, goal: str, progress: Callable[[str], None] | None = None) -> str:
        """Planner -> tool-capable executor -> reviewer. Approval gates remain active on every local action."""
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
                f'JARVIS OMEGA V6 MISSION\nOverall goal: {goal}\n'
                f'Current step {index}/{len(plan)}: {step}\n'
                'Execute this step using available tools only when needed. Respect every permission gate. '
                'Return a concise result for this step.'
            )
            result = self.chat(prompt)
            results.append(result)
            progress(f'COMPLETED {index}/{len(plan)}')

        joined = '\n\n'.join(f'Step {i + 1}: {r}' for i, r in enumerate(results))
        progress('REVIEWING MISSION...')
        review = self._one_shot_text(
            'You are JARVIS OMEGA V6 Reviewer. Review the supplied mission results. Do not invent tool outcomes. '
            'Give a concise final status, what was completed, any blockers, and exact next action if needed.',
            f'Goal: {goal}\nPlan: {json.dumps(plan, ensure_ascii=False)}\nExecution results:\n{joined}',
        )
        self.memory.add_message(self.session_id, 'assistant', f'[MISSION REVIEW]\n{review}')
        self.last_latency = time.perf_counter() - started
        return review

    def _chat_openrouter(self) -> str:
        messages = [{'role': 'system', 'content': system_prompt()}] + self._history()
        tools = self._openrouter_model_tools()
        self.last_tool_mode = 'full' if tools else 'no-tools'

        for _ in range(settings.max_tool_rounds):
            kwargs = {'model': settings.model, 'messages': messages}
            if tools:
                kwargs['tools'] = tools

            try:
                response = self.client.chat.completions.create(**kwargs, timeout=settings.ai_timeout_seconds)
            except Exception as exc:
                status = self._status_code(exc)
                lower = str(exc).lower()
                tool_problem = (
                    tools and status in {400, 404, 422}
                    and any(word in lower for word in ('tool', 'function', 'unsupported', 'parameter', 'schema'))
                )
                if tool_problem:
                    tools = []
                    self.last_tool_mode = 'fallback-no-tools'
                    continue
                raise self._friendly_error(exc) from exc

            self.last_model_used = getattr(response, 'model', settings.model) or settings.model
            message = response.choices[0].message
            calls = list(message.tool_calls or [])
            if not calls:
                content = message.content
                return (content.strip() if isinstance(content, str) else str(content or '').strip()) or 'I completed the turn but received no text output.'

            assistant_tool_calls = []
            for call in calls:
                assistant_tool_calls.append({
                    'id': call.id,
                    'type': 'function',
                    'function': {'name': call.function.name, 'arguments': call.function.arguments or '{}'},
                })
            messages.append({'role': 'assistant', 'content': message.content or '', 'tool_calls': assistant_tool_calls})

            for call in calls:
                try:
                    args = json.loads(call.function.arguments or '{}')
                except json.JSONDecodeError:
                    args = {}
                result = self.tools.call(call.function.name, args)
                messages.append({'role': 'tool', 'tool_call_id': call.id, 'content': result})

        return 'I hit the configured tool-round limit and stopped safely.'

    def _chat_openai(self) -> str:
        input_items = self._history()
        try:
            response = self.client.responses.create(
                model=settings.model,
                reasoning={'effort': settings.reasoning_effort},
                instructions=system_prompt(),
                input=input_items,
                tools=self._openai_model_tools(),
                store=False,
                timeout=settings.ai_timeout_seconds,
            )
        except Exception as exc:
            raise self._friendly_error(exc) from exc
        self.last_model_used = getattr(response, 'model', settings.model) or settings.model
        self.last_tool_mode = 'full'

        for _ in range(settings.max_tool_rounds):
            calls = [x for x in response.output if getattr(x, 'type', None) == 'function_call']
            if not calls:
                return (response.output_text or '').strip() or 'I completed the turn but received no text output.'

            input_items.extend(self._dump_item(item) for item in response.output)
            for call in calls:
                try:
                    args = json.loads(call.arguments or '{}')
                except json.JSONDecodeError:
                    args = {}
                result = self.tools.call(call.name, args)
                input_items.append({'type': 'function_call_output', 'call_id': call.call_id, 'output': result})

            try:
                response = self.client.responses.create(
                    model=settings.model,
                    reasoning={'effort': settings.reasoning_effort},
                    instructions=system_prompt(),
                    input=input_items,
                    tools=self._openai_model_tools(),
                    store=False,
                    timeout=settings.ai_timeout_seconds,
                )
            except Exception as exc:
                raise self._friendly_error(exc) from exc
            self.last_model_used = getattr(response, 'model', settings.model) or settings.model

        return 'I hit the configured tool-round limit and stopped safely.'
