"""Computer-use public API with lazy imports to keep security helpers acyclic."""

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .action_engine import ComputerActionEngine
    from .browser import BrowserAgent
    from .targets import TargetMatch, UITarget, choose_target, rank_targets
    from .windows_ui import WindowsUIBackend

__all__ = [
    'ComputerActionEngine',
    'BrowserAgent',
    'TargetMatch',
    'UITarget',
    'choose_target',
    'rank_targets',
    'WindowsUIBackend',
]


_EXPORT_MODULES = {
    'ComputerActionEngine': '.action_engine',
    'BrowserAgent': '.browser',
    'TargetMatch': '.targets',
    'UITarget': '.targets',
    'choose_target': '.targets',
    'rank_targets': '.targets',
    'WindowsUIBackend': '.windows_ui',
}


def __getattr__(name: str):
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(name)
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value
