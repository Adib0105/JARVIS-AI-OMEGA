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
        if not settings.api_key:
            raise RuntimeError('OPENAI_API_KEY is missing. Copy .env.example to .env and add your key.')
        self.client = OpenAI(api_key=settings.api_key)
        self.memory = MemoryStore()
        self.tools = ToolRegistry(self.memory, confirmer)
        self.session_id = self.memory.new_session('JARVIS OMEGA session')
        self.last_latency = 0.0

    def new_session(self) -> str:
        self.session_id = self.memory.new_session('JARVIS OMEGA session')
        return self.session_id

    def _model_tools(self) -> list[dict]:
        tools = self.tools.schemas() if settings.enable_local_tools else []
        if settings.enable_web_search:
            tools.append({'type': 'web_search'})
        if settings.enable_code_interpreter:
            tools.append({'type': 'code_interpreter', 'container': {'type': 'auto'}})
        return tools

    def _history(self) -> list[dict]:
        return [{'role': role, 'content': content}
                for role, content in self.memory.recent_messages(self.session_id)]

    @staticmethod
    def _dump_item(item):
        return item.model_dump(exclude_none=True) if hasattr(item, 'model_dump') else item

    def chat(self, text: str) -> str:
        text = text.strip()
        if not text:
            return ''
        started = time.perf_counter()
        self.memory.add_message(self.session_id, 'user', text)
        input_items = self._history()
        response = self.client.responses.create(
            model=settings.model,
            reasoning={'effort': settings.reasoning_effort},
            instructions=system_prompt(),
            input=input_items,
            tools=self._model_tools(),
            store=False,
        )

        for _ in range(settings.max_tool_rounds):
            calls = [x for x in response.output if getattr(x, 'type', None) == 'function_call']
            if not calls:
                answer = (response.output_text or '').strip() or 'I completed the turn but received no text output.'
                self.memory.add_message(self.session_id, 'assistant', answer)
                self.last_latency = time.perf_counter() - started
                return answer

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
                tools=self._model_tools(),
                store=False,
            )

        answer = 'I hit the configured tool-round limit and stopped safely.'
        self.memory.add_message(self.session_id, 'assistant', answer)
        self.last_latency = time.perf_counter() - started
        return answer
