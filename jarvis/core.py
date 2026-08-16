from __future__ import annotations

import json
import time
from typing import Callable

from openai import OpenAI

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

        client_kwargs = {'api_key': settings.api_key}
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
        self.session_id = self.memory.new_session('JARVIS OMEGA session')
        self.last_latency = 0.0
        self.last_model_used = settings.model

    def new_session(self) -> str:
        self.session_id = self.memory.new_session('JARVIS OMEGA session')
        return self.session_id

    def _openai_model_tools(self) -> list[dict]:
        tools = self.tools.schemas() if settings.enable_local_tools else []
        if settings.hosted_web_search_enabled:
            tools.append({'type': 'web_search'})
        if settings.code_interpreter_enabled:
            tools.append({'type': 'code_interpreter', 'container': {'type': 'auto'}})
        return tools

    def _openrouter_model_tools(self) -> list[dict]:
        if not settings.enable_local_tools:
            return []
        converted = []
        for spec in self.tools.schemas():
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

    def chat(self, text: str) -> str:
        text = text.strip()
        if not text:
            return ''

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

    def _chat_openrouter(self) -> str:
        messages = [{'role': 'system', 'content': system_prompt()}] + self._history()
        tools = self._openrouter_model_tools()

        for _ in range(settings.max_tool_rounds):
            kwargs = {
                'model': settings.model,
                'messages': messages,
            }
            if tools:
                kwargs['tools'] = tools

            response = self.client.chat.completions.create(**kwargs)
            self.last_model_used = getattr(response, 'model', settings.model) or settings.model
            message = response.choices[0].message
            calls = list(message.tool_calls or [])

            if not calls:
                content = message.content
                if isinstance(content, str):
                    answer = content.strip()
                else:
                    answer = str(content or '').strip()
                return answer or 'I completed the turn but received no text output.'

            assistant_tool_calls = []
            for call in calls:
                assistant_tool_calls.append({
                    'id': call.id,
                    'type': 'function',
                    'function': {
                        'name': call.function.name,
                        'arguments': call.function.arguments or '{}',
                    },
                })

            messages.append({
                'role': 'assistant',
                'content': message.content or '',
                'tool_calls': assistant_tool_calls,
            })

            for call in calls:
                try:
                    args = json.loads(call.function.arguments or '{}')
                except json.JSONDecodeError:
                    args = {}
                result = self.tools.call(call.function.name, args)
                messages.append({
                    'role': 'tool',
                    'tool_call_id': call.id,
                    'content': result,
                })

        return 'I hit the configured tool-round limit and stopped safely.'

    def _chat_openai(self) -> str:
        input_items = self._history()
        response = self.client.responses.create(
            model=settings.model,
            reasoning={'effort': settings.reasoning_effort},
            instructions=system_prompt(),
            input=input_items,
            tools=self._openai_model_tools(),
            store=False,
        )
        self.last_model_used = getattr(response, 'model', settings.model) or settings.model

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
                input_items.append({
                    'type': 'function_call_output',
                    'call_id': call.call_id,
                    'output': result,
                })

            response = self.client.responses.create(
                model=settings.model,
                reasoning={'effort': settings.reasoning_effort},
                instructions=system_prompt(),
                input=input_items,
                tools=self._openai_model_tools(),
                store=False,
            )
            self.last_model_used = getattr(response, 'model', settings.model) or settings.model

        return 'I hit the configured tool-round limit and stopped safely.'
