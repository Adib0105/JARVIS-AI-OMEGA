from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {'1', 'true', 'yes', 'on'}


@dataclass(frozen=True)
class Settings:
    provider: str = os.getenv('AI_PROVIDER', 'openrouter').strip().lower()

    openrouter_api_key: str = os.getenv('OPENROUTER_API_KEY', '')
    openrouter_model: str = os.getenv('OPENROUTER_MODEL', 'openrouter/free')
    openrouter_base_url: str = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
    openrouter_app_url: str = os.getenv('OPENROUTER_APP_URL', 'https://github.com/Adib0105/JARVIS-AI-OMEGA')
    openrouter_app_title: str = os.getenv('OPENROUTER_APP_TITLE', 'JARVIS AI OMEGA')

    openai_api_key: str = os.getenv('OPENAI_API_KEY', '')
    openai_model: str = os.getenv('OPENAI_MODEL', 'gpt-5.6')
    reasoning_effort: str = os.getenv('REASONING_EFFORT', 'xhigh')

    creator_name: str = os.getenv('CREATOR_NAME', 'Adib Azam')
    user_name: str = os.getenv('USER_NAME', 'Adib')
    assistant_name: str = os.getenv('JARVIS_NAME', 'JARVIS OMEGA')
    language_mode: str = os.getenv('LANGUAGE_MODE', 'auto')

    enable_web_search: bool = _bool('ENABLE_WEB_SEARCH', True)
    enable_code_interpreter: bool = _bool('ENABLE_CODE_INTERPRETER', True)
    enable_local_tools: bool = _bool('ENABLE_LOCAL_TOOLS', True)
    require_local_approval: bool = _bool('REQUIRE_LOCAL_APPROVAL', True)
    enable_voice_output: bool = _bool('ENABLE_VOICE_OUTPUT', True)
    voice_rate: int = int(os.getenv('VOICE_RATE', '185'))
    voice_volume: float = float(os.getenv('VOICE_VOLUME', '1.0'))
    max_tool_rounds: int = int(os.getenv('MAX_TOOL_ROUNDS', '10'))
    history_messages: int = int(os.getenv('HISTORY_MESSAGES', '24'))
    db_path: Path = Path(os.getenv('JARVIS_DB_PATH', str(ROOT / 'data' / 'jarvis.db'))).expanduser()

    @property
    def api_key(self) -> str:
        return self.openrouter_api_key if self.provider == 'openrouter' else self.openai_api_key

    @property
    def model(self) -> str:
        return self.openrouter_model if self.provider == 'openrouter' else self.openai_model

    @property
    def base_url(self) -> str | None:
        return self.openrouter_base_url if self.provider == 'openrouter' else None

    @property
    def hosted_web_search_enabled(self) -> bool:
        return self.provider == 'openai' and self.enable_web_search

    @property
    def code_interpreter_enabled(self) -> bool:
        return self.provider == 'openai' and self.enable_code_interpreter

    @property
    def allowed_file_roots(self) -> tuple[Path, ...]:
        raw = os.getenv('ALLOWED_FILE_ROOTS', '').strip()
        if raw:
            return tuple(Path(p.strip()).expanduser().resolve() for p in raw.split(';') if p.strip())
        home = Path.home()
        roots = [home / 'Desktop', home / 'Documents', home / 'Downloads', ROOT]
        return tuple(p.resolve() for p in roots)


settings = Settings()
