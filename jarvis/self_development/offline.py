from __future__ import annotations

from dataclasses import asdict, dataclass

from ..config import settings
from ..providers.local_provider import LocalProvider


UNAVAILABLE_MESSAGE = 'Offline development is unavailable because no local reasoning model is configured.'


@dataclass(frozen=True)
class OfflineDevelopmentStatus:
    enabled: bool
    configured: bool
    provider: str
    base_url: str
    model: str
    message: str

    def as_dict(self) -> dict:
        return asdict(self)


class OfflineDevelopmentRuntime:
    """Reasoning adapter for fully local self-development.

    This class never installs a model or dependency. It only uses an explicitly
    configured OpenAI-compatible local inference endpoint (Ollama, LM Studio or
    another compatible runtime). Repository/tests/Git remain local as well.
    """

    def __init__(self, *, provider=None) -> None:
        self._provider = provider

    def status(self) -> OfflineDevelopmentStatus:
        enabled = bool(settings.offline_development_enabled)
        configured = bool(settings.local_ai_model.strip() and settings.local_ai_base_url.strip())
        if not enabled:
            message = 'Offline development is disabled by configuration.'
        elif not configured:
            message = UNAVAILABLE_MESSAGE
        else:
            message = 'Offline development is configured for a local OpenAI-compatible reasoning model.'
        return OfflineDevelopmentStatus(
            enabled=enabled,
            configured=configured,
            provider=settings.local_model_provider or 'openai-compatible',
            base_url=settings.local_ai_base_url,
            model=settings.local_ai_model,
            message=message,
        )

    def require_ready(self) -> OfflineDevelopmentStatus:
        status = self.status()
        if not status.enabled:
            raise RuntimeError(status.message)
        if not status.configured:
            raise RuntimeError(UNAVAILABLE_MESSAGE)
        return status

    def _client(self):
        status = self.require_ready()
        if self._provider is not None:
            return self._provider
        self._provider = LocalProvider(
            api_key=settings.local_ai_api_key or 'local',
            base_url=status.base_url,
            max_retries=0,
        )
        return self._provider

    def reason(self, system: str, prompt: str) -> str:
        status = self.require_ready()
        provider = self._client()
        text = provider.structured_output(
            system=system,
            prompt=prompt,
            model=status.model,
            timeout=settings.ai_timeout_seconds,
        )
        text = str(text).strip()
        if not text:
            raise RuntimeError('Configured local reasoning model returned no output.')
        return text
