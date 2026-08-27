from __future__ import annotations


def install_skill_ui() -> None:
    """Backward-compatible no-op.

    The SKILLS tab now lives in ``ui_command_center_composed.AgentCommandCenter``
    and is composed by inheritance rather than by mutating the base UI class.
    """
    return None


__all__ = ['install_skill_ui']
