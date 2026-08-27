from __future__ import annotations

from typing import Any

from openai import OpenAI

from .base import AIProvider, ProviderTurn, ToolCall, ToolResult
from .deadline import call_with_deadline, transport_timeout_seconds


class OpenAIProvider(AIProvider):
    name = 'openai'

    def __init__(
        self,
        *,
        api_key: str,
        reasoning_effort: str = 'high',
        enable_web_search: bool = False,
        enable_code_interpreter: bool = False,
        max_retries: int = 0,
    ) -> None:
        self.client = OpenAI(api_key=api_key, max_retries=max(0, int(max_retries)))
        self.reasoning_effort = reasoning_effort
        self.enable_web_search = enable_web_search
        self.enable_code_interpreter = enable_code_interpreter

    @staticmethod
    def _dump(item):
        return item.model_dump(exclude_none=True) if hasattr(item, 'model_dump') else item

    @staticmethod
    def _usage(response: Any) -> dict[str, Any]:
        usage = getattr(response, 'usage', None)
        if usage is None:
            return {}
        if hasattr(usage, 'model_dump'):
            return usage.model_dump(exclude_none=True)
        return {'raw': str(usage)}

    def _tools(self, tools: list[dict]) -> list[dict]:
        out = [dict(spec) for spec in tools if spec.get('type') == 'function']
        if self.enable_web_search:
            out.append({'type': 'web_search'})
        if self.enable_code_interpreter:
            out.append({'type': 'code_interpreter', 'container': {'type': 'auto'}})
        return out

    def _turn(self, response, input_items: list[dict]) -> ProviderTurn:
        output = getattr(response, 'output', None)
        if output is None:
            raise ValueError('OpenAI returned a malformed response: missing output.')
        calls = []
        for item in output:
            if getattr(item, 'type', None) == 'function_call':
                calls.append(ToolCall(
                    id=item.call_id,
                    name=item.name,
                    arguments=item.arguments or '{}',
                ))
        return ProviderTurn(
            text=(getattr(response, 'output_text', '') or '').strip(),
            tool_calls=calls,
            state={
                'input_items': list(input_items),
                'output_items': [self._dump(item) for item in output],
            },
            model=getattr(response, 'model', '') or '',
            provider=self.name,
            usage=self._usage(response),
        )

    def _create(
        self,
        *,
        system: str,
        input_items: list[dict],
        model: str,
        tools: list[dict] | None,
        timeout: float,
    ) -> ProviderTurn:
        kwargs: dict[str, Any] = {
            'model': model,
            'instructions': system,
            'input': input_items,
            'store': False,
            'timeout': transport_timeout_seconds(timeout),
        }
        if self.reasoning_effort:
            kwargs['reasoning'] = {'effort': self.reasoning_effort}
        normalized_tools = self._tools(tools or [])
        if normalized_tools:
            kwargs['tools'] = normalized_tools
        response = call_with_deadline(
            lambda: self.client.responses.create(**kwargs),
            timeout,
            operation='OpenAI response',
        )
        return self._turn(response, input_items)

    def chat(self, *, system: str, messages: list[dict], model: str, timeout: float) -> ProviderTurn:
        return self._create(system=system, input_items=list(messages), model=model, tools=None, timeout=timeout)

    def chat_with_tools(
        self,
        *,
        system: str,
        messages: list[dict],
        model: str,
        tools: list[dict],
        timeout: float,
    ) -> ProviderTurn:
        return self._create(system=system, input_items=list(messages), model=model, tools=tools, timeout=timeout)

    def continue_with_tools(
        self,
        *,
        previous: ProviderTurn,
        tool_results: list[ToolResult],
        system: str,
        model: str,
        tools: list[dict],
        timeout: float,
    ) -> ProviderTurn:
        state = previous.state if isinstance(previous.state, dict) else {}
        input_items = list(state.get('input_items') or [])
        input_items.extend(state.get('output_items') or [])
        for result in tool_results:
            input_items.append({
                'type': 'function_call_output',
                'call_id': result.call_id,
                'output': result.output,
            })
        return self._create(system=system, input_items=input_items, model=model, tools=tools, timeout=timeout)

    def vision(
        self,
        *,
        system: str,
        prompt: str,
        image_urls: list[str],
        model: str,
        timeout: float,
    ) -> ProviderTurn:
        content: list[dict] = [{'type': 'input_text', 'text': prompt}]
        for url in image_urls:
            content.append({'type': 'input_image', 'image_url': url, 'detail': 'auto'})
        input_items = [{'role': 'user', 'content': content}]
        response = call_with_deadline(
            lambda: self.client.responses.create(
                model=model,
                instructions=system,
                input=input_items,
                store=False,
                timeout=transport_timeout_seconds(timeout),
            ),
            timeout,
            operation='OpenAI vision response',
        )
        return self._turn(response, input_items)
