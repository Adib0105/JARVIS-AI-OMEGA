from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProductPaths:
    install_dir: Path
    data_dir: Path
    config_dir: Path
    log_dir: Path
    crash_dir: Path
    export_dir: Path


def product_paths() -> ProductPaths:
    frozen = bool(getattr(sys, 'frozen', False))
    install_dir = Path(sys.executable).resolve().parent if frozen else Path(__file__).resolve().parents[1]
    if frozen and os.name == 'nt':
        local = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
        data_dir = local / 'JARVIS AI OMEGA'
    else:
        data_dir = install_dir / 'data'
    config_dir = data_dir / 'config'
    log_dir = data_dir / 'logs'
    crash_dir = data_dir / 'crash-reports'
    export_dir = data_dir / 'exports'
    for path in (data_dir, config_dir, log_dir, crash_dir, export_dir):
        path.mkdir(parents=True, exist_ok=True)
    return ProductPaths(install_dir, data_dir, config_dir, log_dir, crash_dir, export_dir)


PATHS = product_paths()


def config_env_path() -> Path:
    """Return the canonical environment file for this runtime.

    Packaged applications must never write configuration beside the executable
    under Program Files. Development keeps the historical repository .env path.
    """
    if bool(getattr(sys, 'frozen', False)):
        return PATHS.config_dir / '.env'
    return PATHS.install_dir / '.env'
