from __future__ import annotations

import time

from .fast_commands import execute_fast_command


def install_fast_command_runtime() -> None:
    """Put deterministic low-risk commands ahead of the remote LLM path."""
    from .core import JarvisOmega

    if getattr(JarvisOmega, '_fast_command_runtime_installed', False):
        return
    original_chat = JarvisOmega.chat

    def fast_chat(self, text: str) -> str:
        clean = str(text or '').strip()
        if clean:
            started = time.perf_counter()
            answer = execute_fast_command(self, clean)
            if answer is not None:
                self.last_request_kind = 'local-command'
                self.last_provider_used = 'local-fast-command'
                self.last_model_used = 'deterministic-local'
                self.last_tool_mode = 'fast-command'
                self.last_latency = time.perf_counter() - started
                try:
                    self.memory.add_message(self.session_id, 'user', clean)
                    self.memory.add_message(self.session_id, 'assistant', answer)
                except Exception:
                    pass
                return answer
        return original_chat(self, text)

    JarvisOmega.chat = fast_chat
    JarvisOmega._fast_command_runtime_installed = True
