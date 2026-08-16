from __future__ import annotations

from .base import AIProvider
from .local_provider import LocalProvider
from .openai_provider import OpenAIProvider
from .openrouter_provider import OpenRouterProvider


def create_primary_provider(settings) -> AIProvider:
    if settings.provider == 'openrouter':
        return OpenRouterProvider(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            app_url=settings.openrouter_app_url,
            app_title=settings.openrouter_app_title,
            max_retries=settings.api_max_retries,
        )
    if settings.provider == 'openai':
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            reasoning_effort=settings.reasoning_effort,
            enable_web_search=settings.enable_web_search,
            enable_code_interpreter=settings.enable_code_interpreter,
            max_retries=settings.api_max_retries,
        )
    raise ValueError(f'Unsupported AI provider: {settings.provider}')


def create_local_provider(settings) -> LocalProvider | None:
    if not settings.enable_local_fallback or not settings.local_ai_model or not settings.local_ai_base_url:
        return None
    return LocalProvider(
        api_key=settings.local_ai_api_key,
        base_url=settings.local_ai_base_url,
        max_retries=0,
    )
