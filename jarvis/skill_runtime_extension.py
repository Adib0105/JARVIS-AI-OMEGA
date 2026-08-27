from __future__ import annotations


def install_skill_runtime() -> None:
    """Compatibility shim retained for existing launchers.

    Skill build/activation lifecycle methods are declared directly on
    ``jarvis.core.JarvisOmega``. Keeping this no-op avoids breaking old startup
    scripts while removing runtime mutation of the public core class.
    """
    return None


__all__ = ['install_skill_runtime']
