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
    api_key: str = os.getenv('OPENAI_API_KEY', '')
    model: str = os.getenv('OPENAI_MODEL', 'gpt-5.6')
    reasoning_effort: str = os.getenv('REASONING_EFFORT', 'xhigh')
    creator_name: str = os.getenv('CREATOR_NAME', 'Adib Azam')
    user_name: str = os.getenv('USER_NAME', 'Adib')
    assistant_name: str = os.getenv('JARVIS_NAME', 'JARVIS OMEGA')
    language_mode: str = os.getenv('LANGUAGE_MODE', 'auto')
    enable_web_search: bool = _bool('ENABLE_WEB_SEARCH', True)
    enable_code_interpreter: bool = _bool('ENABLE_CODE_INTERPRETER', True)
    enable_local_tools: bool = _bool('ENABLE_LOCAL_TOOLS', True)
    require_local_approval: bool = _bool('REQUIRE_LOCAL_APPROVAL', True)
    max_tool_rounds: int = int(os.getenv('MAX_TOOL_ROUNDS', '10'))
    history_messages: int = int(os.getenv('HISTORY_MESSAGES', '24'))
    db_path: Path = Path(os.getenv('JARVIS_DB_PATH', str(ROOT / 'data' / 'jarvis.db'))).expanduser()

    @property
    def allowed_file_roots(self) -> tuple[Path, ...]:
        raw = os.getenv('ALLOWED_FILE_ROOTS', '').strip()
        if raw:
            return tuple(Path(p.strip()).expanduser().resolve() for p in raw.split(';') if p.strip())
        home = Path.home()
        roots = [home / 'Desktop', home / 'Documents', home / 'Downloads', ROOT]
        return tuple(p.resolve() for p in roots)


settings = Settings()
