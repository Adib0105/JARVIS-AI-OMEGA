"""One cooperative request budget shared by planning, retries, tools and review."""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
import threading
import time


class BudgetExceeded(TimeoutError):
    pass


@dataclass
class ExecutionBudget:
    seconds: float = 120.0
    max_model_calls: int = 16
    max_tool_calls: int = 30
    max_tokens: int = 32_000
    cancel_event: threading.Event = field(default_factory=threading.Event)
    owner_check: object = None
    started: float = field(default_factory=time.monotonic)
    model_calls: int = 0
    tool_calls: int = 0
    tokens: int = 0

    def check(self):
        if self.owner_check is not None:
            self.owner_check()
        if self.cancel_event.is_set():
            raise BudgetExceeded('Cancellation requested; no further action was started.')
        if time.monotonic() - self.started >= self.seconds:
            raise BudgetExceeded('Mission/request time budget exhausted; check any action already in progress before retrying.')
        if self.tokens >= self.max_tokens:
            raise BudgetExceeded('Provider token budget exhausted.')

    def timeout(self, requested):
        self.check()
        if self.model_calls >= self.max_model_calls:
            raise BudgetExceeded('Model request budget exhausted.')
        self.model_calls += 1
        return max(0.01, min(float(requested), self.seconds - (time.monotonic() - self.started)))

    def tool(self):
        self.check()
        if self.tool_calls >= self.max_tool_calls:
            raise BudgetExceeded('Tool action budget exhausted.')
        self.tool_calls += 1

    def usage(self, usage):
        reported = (usage or {}).get('total_tokens')
        if isinstance(reported, (int, float)) and reported > 0:
            self.tokens += int(reported)
        self.check()


CURRENT = ContextVar('jarvis_execution_budget', default=None)


def checked_timeout(requested):
    budget = CURRENT.get()
    return budget.timeout(requested) if budget else requested


def bounded_request(method):
    @wraps(method)
    def wrapper(*args, **kwargs):
        token = None
        if CURRENT.get() is None:
            token = CURRENT.set(ExecutionBudget())
        try:
            CURRENT.get().check()
            return method(*args, **kwargs)
        finally:
            if token is not None:
                CURRENT.reset(token)
    return wrapper
