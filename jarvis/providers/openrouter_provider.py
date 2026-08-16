from __future__ import annotations

from typing import Any

from openai import OpenAI

from .base import AIProvider, ProviderTurn, ToolCall, ToolResult


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
                'X-OpenRouter-Title': app_title,
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
        for call in list(message.tool_calls or []):
            calls.append({
                'id': call.id,
                'type': 'function',
                'function': {
                    'name': call.function.name,
                    'arguments': call.function.arguments or '{}',
                },
            })
        payload = {'role': 'assistant', 'content': message.content or ''}
        if calls:
            payload['tool_calls'] = calls
        return payload

    def _turn(self, response, messages: list[dict]) -> ProviderTurn:
        message = response.choices[0].message
        calls = [
            ToolCall(
                id=call.id,
                name=call.function.name,
                arguments=call.function.arguments or '{}',
            )
            for call in list(message.tool_calls or [])
        ]
        text = message.content.strip() if isinstance(message.content, str) else str(message.content or '').strip()
        return ProviderTurn(
            text=text,
            tool_calls=calls,
            state={'messages': list(messages), 'assistant': self._assistant_payload(message)},
            model=getattr(response, 'model', '') or '',
            provider=self.name,
            usage=self._usage(response),
        )

    def _create(self, *, messages: list[dict], model: str, tools: list[dict] | None, timeout: float) -> ProviderTurn:
        kwargs: dict[str, Any] = {'model': model, 'messages': messages, 'timeout': timeout}
        converted = self._tools(tools or [])
        if converted:
            kwargs['tools'] = converted
        response = self.client.chat.completions.create(**kwargs)
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
        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': content},
            ],
            timeout=timeout,
        )
        return self._turn(response, [{'role': 'system', 'content': system}, {'role': 'user', 'content': content}])
