from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {'1', 'true', 'yes', 'on'}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name, '').strip()
    if not raw:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    raw = os.getenv(name, '').strip()
    if not raw:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _path(name: str, default: Path) -> Path:
    raw = os.getenv(name, '').strip()
    return Path(raw).expanduser() if raw else default


@dataclass(frozen=True)
class Settings:
    app_version: str = '7.0.0'
    provider: str = os.getenv('AI_PROVIDER', 'openrouter').strip().lower()

    openrouter_api_key: str = os.getenv('OPENROUTER_API_KEY', '')
    openrouter_model: str = os.getenv('OPENROUTER_MODEL', 'openrouter/free').strip()
    openrouter_base_url: str = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1').strip()
    openrouter_app_url: str = os.getenv('OPENROUTER_APP_URL', 'https://github.com/Adib0105/JARVIS-AI-OMEGA').strip()
    openrouter_app_title: str = os.getenv('OPENROUTER_APP_TITLE', 'JARVIS AI OMEGA V7').strip()

    openai_api_key: str = os.getenv('OPENAI_API_KEY', '')
    openai_model: str = os.getenv('OPENAI_MODEL', 'gpt-5.6').strip()
    reasoning_effort: str = os.getenv('REASONING_EFFORT', 'xhigh').strip()

    # Optional model routing. Blank values fall back to the configured primary model.
    model_routing: str = os.getenv('MODEL_ROUTING', 'auto').strip().lower()
    fast_model: str = os.getenv('FAST_MODEL', '').strip()
    smart_model: str = os.getenv('SMART_MODEL', '').strip()
    vision_model: str = os.getenv('VISION_MODEL', '').strip()

    # Optional local OpenAI-compatible fallback.
    enable_local_fallback: bool = _bool('ENABLE_LOCAL_FALLBACK', False)
    local_ai_base_url: str = os.getenv('LOCAL_AI_BASE_URL', 'http://127.0.0.1:11434/v1').strip()
    local_ai_model: str = os.getenv('LOCAL_AI_MODEL', '').strip()
    local_ai_api_key: str = os.getenv('LOCAL_AI_API_KEY', 'local').strip() or 'local'

    creator_name: str = os.getenv('CREATOR_NAME', 'Adib Azam').strip() or 'Adib Azam'
    user_name: str = os.getenv('USER_NAME', 'Adib').strip() or 'Adib'
    assistant_name: str = os.getenv('JARVIS_NAME', 'JARVIS OMEGA').strip() or 'JARVIS OMEGA'
    language_mode: str = os.getenv('LANGUAGE_MODE', 'auto').strip().lower()

    enable_web_search: bool = _bool('ENABLE_WEB_SEARCH', True)
    enable_public_web_tools: bool = _bool('ENABLE_PUBLIC_WEB_TOOLS', True)
    enable_code_interpreter: bool = _bool('ENABLE_CODE_INTERPRETER', True)
    enable_local_tools: bool = _bool('ENABLE_LOCAL_TOOLS', True)
    require_local_approval: bool = _bool('REQUIRE_LOCAL_APPROVAL', True)
    enable_desktop_automation: bool = _bool('ENABLE_DESKTOP_AUTOMATION', True)
    enable_document_intelligence: bool = _bool('ENABLE_DOCUMENT_INTELLIGENCE', True)
    enable_coding_tools: bool = _bool('ENABLE_CODING_TOOLS', True)
    enable_google_workspace: bool = _bool('ENABLE_GOOGLE_WORKSPACE', False)
    google_credentials_file: Path = _path('GOOGLE_OAUTH_CLIENT_FILE', ROOT / 'google_credentials.json')
    google_token_file: Path = _path('GOOGLE_TOKEN_FILE', ROOT / 'data' / 'google_token.json')

    enable_voice_output: bool = _bool('ENABLE_VOICE_OUTPUT', True)
    voice_engine: str = os.getenv('VOICE_ENGINE', 'edge').strip().lower()
    voice_hindi: str = os.getenv('VOICE_HINDI', 'hi-IN-MadhurNeural').strip()
    voice_hinglish: str = os.getenv('VOICE_HINGLISH', 'en-IN-PrabhatNeural').strip()
    voice_english: str = os.getenv('VOICE_ENGLISH', 'en-IN-PrabhatNeural').strip()
    edge_voice_rate: str = os.getenv('EDGE_VOICE_RATE', '-2%').strip()
    edge_voice_volume: str = os.getenv('EDGE_VOICE_VOLUME', '+5%').strip()
    edge_voice_pitch: str = os.getenv('EDGE_VOICE_PITCH', '-20Hz').strip()
    voice_rate: int = _int('VOICE_RATE', 170)
    voice_volume: float = _float('VOICE_VOLUME', 1.0)

    enable_mic_input: bool = _bool('ENABLE_MIC_INPUT', True)
    enable_wake_word: bool = _bool('ENABLE_WAKE_WORD', False)
    wake_word: str = os.getenv('WAKE_WORD', 'hey jarvis').strip() or 'hey jarvis'
    speech_language: str = os.getenv('SPEECH_LANGUAGE', 'en-IN').strip() or 'en-IN'
    mic_record_seconds: float = _float('MIC_RECORD_SECONDS', 6.0)

    ai_timeout_seconds: float = _float('AI_TIMEOUT_SECONDS', 60.0)
    vision_timeout_seconds: float = _float('VISION_TIMEOUT_SECONDS', 75.0)
    api_max_retries: int = _int('API_MAX_RETRIES', 2)
    max_tool_rounds: int = _int('MAX_TOOL_ROUNDS', 12)
    history_messages: int = _int('HISTORY_MESSAGES', 36)
    mission_max_steps: int = _int('MISSION_MAX_STEPS', 5)
    auto_summarize: bool = _bool('AUTO_SUMMARIZE', False)
    summarize_after_messages: int = _int('SUMMARIZE_AFTER_MESSAGES', 60)

    max_image_attachments: int = _int('MAX_IMAGE_ATTACHMENTS', 4)
    max_image_mb: int = _int('MAX_IMAGE_MB', 12)
    image_max_dimension: int = _int('IMAGE_MAX_DIMENSION', 1600)
    image_jpeg_quality: int = _int('IMAGE_JPEG_QUALITY', 82)

    system_refresh_ms: int = _int('SYSTEM_REFRESH_MS', 1200)
    reminder_poll_seconds: float = _float('REMINDER_POLL_SECONDS', 5.0)

    log_level: str = os.getenv('JARVIS_LOG_LEVEL', 'INFO').strip().upper() or 'INFO'
    db_path: Path = _path('JARVIS_DB_PATH', ROOT / 'data' / 'jarvis.db')
    export_dir: Path = _path('JARVIS_EXPORT_DIR', ROOT / 'exports')

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
    def routed_fast_model(self) -> str:
        return self.fast_model or self.model

    @property
    def routed_smart_model(self) -> str:
        return self.smart_model or self.model

    @property
    def routed_vision_model(self) -> str:
        return self.vision_model or self.routed_smart_model

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
            roots = []
            for value in raw.split(';'):
                value = value.strip()
                if value:
                    try:
                        roots.append(Path(value).expanduser().resolve())
                    except OSError:
                        roots.append(Path(value).expanduser().absolute())
            return tuple(roots)
        home = Path.home()
        roots = [home / 'Desktop', home / 'Documents', home / 'Downloads', ROOT]
        return tuple(p.resolve() for p in roots)


settings = Settings()
