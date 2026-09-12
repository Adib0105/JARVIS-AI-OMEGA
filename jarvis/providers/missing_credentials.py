"""A startup-safe provider used until an AI key is configured."""
from __future__ import annotations

from .base import AIProvider, ProviderTurn, ToolResult


class MissingCredentialsProvider(AIProvider):
    name = 'setup-required'

    def __init__(self, provider: str):
        self.provider = provider

    def _error(self):
        variable = 'OPENROUTER_API_KEY' if self.provider == 'openrouter' else 'OPENAI_API_KEY'
        raise RuntimeError(
            f'AI setup is incomplete. Open the .env file beside JARVIS-OMEGA-V7.exe and set {variable}=your_key, then restart JARVIS.'
        )

    def chat(self, **_kwargs) -> ProviderTurn:
        self._error()

    def chat_with_tools(self, **_kwargs) -> ProviderTurn:
        self._error()

    def continue_with_tools(self, **_kwargs) -> ProviderTurn:
        self._error()

    def vision(self, **_kwargs) -> ProviderTurn:
        self._error()
