from __future__ import annotations

from typing import Any

from openai import OpenAI

from .base import AIProvider, ProviderTurn, ToolCall, ToolResult
from .deadline import call_with_deadline, transport_timeout_seconds


class OpenRouterProvider(AIProvider):
    name = 'openrouter'

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        app_url: str,
        app_title: str,
        max_retries: int = 0,
    ) -> None:
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers={
                'HTTP-Referer': app_url,
                'X-Title': app_title,
            },
            max_retries=max(0, int(max_retries)),
        )

    @staticmethod
    def _tools(tools: list[dict]) -> list[dict]:
        converted = []
        for spec in tools:
            if spec.get('type') != 'function' or 'name' not in spec:
                continue
            converted.append({
                'type': 'function',
                'function': {
                    'name': spec['name'],
                    'description': spec.get('description', ''),
                    'parameters': spec.get('parameters', {'type': 'object', 'properties': {}}),
                },
            })
        return converted

    @staticmethod
    def _usage(response: Any) -> dict[str, Any]:
        usage = getattr(response, 'usage', None)
        if usage is None:
            return {}
        if hasattr(usage, 'model_dump'):
            return usage.model_dump(exclude_none=True)
        return {'raw': str(usage)}

    @staticmethod
    def _assistant_payload(message) -> dict:
        calls = []
        for call in list(getattr(message, 'tool_calls', None) or []):
            function = getattr(call, 'function', None)
            if function is None or not getattr(function, 'name', None):
                continue
            calls.append({
                'id': getattr(call, 'id', '') or '',
                'type': 'function',
                'function': {
                    'name': function.name,
                    'arguments': getattr(function, 'arguments', None) or '{}',
                },
            })
        payload = {'role': 'assistant', 'content': getattr(message, 'content', None) or ''}
        if calls:
            payload['tool_calls'] = calls
        return payload

    def _turn(self, response, messages: list[dict]) -> ProviderTurn:
        choices = getattr(response, 'choices', None)
        if not choices:
            raise ValueError('OpenRouter returned a malformed response: missing choices.')
        message = getattr(choices[0], 'message', None)
        if message is None:
            raise ValueError('OpenRouter returned a malformed response: missing assistant message.')
        calls = []
        for call in list(getattr(message, 'tool_calls', None) or []):
            function = getattr(call, 'function', None)
            if function is None or not getattr(function, 'name', None):
                raise ValueError('OpenRouter returned a malformed tool call.')
            calls.append(ToolCall(
                id=getattr(call, 'id', '') or '',
                name=function.name,
                arguments=getattr(function, 'arguments', None) or '{}',
            ))
        content = getattr(message, 'content', None)
        text = content.strip() if isinstance(content, str) else str(content or '').strip()
        return ProviderTurn(
            text=text,
            tool_calls=calls,
            state={'messages': list(messages), 'assistant': self._assistant_payload(message)},
            model=getattr(response, 'model', '') or '',
            provider=self.name,
            usage=self._usage(response),
        )

    def _create(self, *, messages: list[dict], model: str, tools: list[dict] | None, timeout: float) -> ProviderTurn:
        kwargs: dict[str, Any] = {
            'model': model,
            'messages': messages,
            # The desktop path is intentionally non-streaming. Make that explicit
            # so there is no SSE iterator that can be left partially consumed.
            'stream': False,
            # Finite SDK connect/read/write inactivity timeout. The outer deadline
            # below is the strict end-to-end wall-clock limit.
            'timeout': transport_timeout_seconds(timeout),
        }
        converted = self._tools(tools or [])
        if converted:
            kwargs['tools'] = converted
        response = call_with_deadline(
            lambda: self.client.chat.completions.create(**kwargs),
            timeout,
            operation='OpenRouter chat completion',
        )
        return self._turn(response, messages)

    def chat(self, *, system: str, messages: list[dict], model: str, timeout: float) -> ProviderTurn:
        working = [{'role': 'system', 'content': system}] + list(messages)
        return self._create(messages=working, model=model, tools=None, timeout=timeout)

    def chat_with_tools(
        self,
        *,
        system: str,
        messages: list[dict],
        model: str,
        tools: list[dict],
        timeout: float,
    ) -> ProviderTurn:
        working = [{'role': 'system', 'content': system}] + list(messages)
        return self._create(messages=working, model=model, tools=tools, timeout=timeout)

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
        working = list(state.get('messages') or [{'role': 'system', 'content': system}])
        assistant = state.get('assistant')
        if assistant:
            working.append(assistant)
        for result in tool_results:
            working.append({'role': 'tool', 'tool_call_id': result.call_id, 'content': result.output})
        return self._create(messages=working, model=model, tools=tools, timeout=timeout)

    def vision(
        self,
        *,
        system: str,
        prompt: str,
        image_urls: list[str],
        model: str,
        timeout: float,
    ) -> ProviderTurn:
        content: list[dict] = [{'type': 'text', 'text': prompt}]
        for url in image_urls:
            content.append({'type': 'image_url', 'image_url': {'url': url}})
        working = [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': content},
        ]
        response = call_with_deadline(
            lambda: self.client.chat.completions.create(
                model=model,
                messages=working,
                stream=False,
                timeout=transport_timeout_seconds(timeout),
            ),
            timeout,
            operation='OpenRouter vision completion',
        )
        return self._turn(response, working)
