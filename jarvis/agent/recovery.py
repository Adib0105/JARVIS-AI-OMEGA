from __future__ import annotations

import random
import time
from dataclasses import dataclass

from ..errors import ErrorCategory, Failure


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    base_delay: float
    max_delay: float
    jitter: float = 0.25


POLICIES = {
    ErrorCategory.TIMEOUT: RetryPolicy(2, 1.0, 4.0),
    ErrorCategory.NETWORK_ERROR: RetryPolicy(2, 1.0, 4.0),
    ErrorCategory.RATE_LIMIT: RetryPolicy(3, 1.0, 12.0),
    ErrorCategory.MODEL_ERROR: RetryPolicy(1, 0.5, 1.0),
    ErrorCategory.VISION_ERROR: RetryPolicy(1, 0.5, 1.0),
}


class RetryManager:
    """Bounded transient retry policy. Side effects are never blindly retried."""

    def policy_for(self, failure: Failure, *, side_effecting: bool = False) -> RetryPolicy:
        if side_effecting:
            return RetryPolicy(0, 0.0, 0.0, 0.0)
        return POLICIES.get(failure.category, RetryPolicy(0, 0.0, 0.0, 0.0))

    def delay(self, failure: Failure, attempt: int, policy: RetryPolicy) -> float:
        if failure.retry_after is not None:
            return min(max(0.0, failure.retry_after), policy.max_delay or failure.retry_after)
        base = min(policy.max_delay, policy.base_delay * (2 ** max(0, attempt - 1)))
        return max(0.0, base + random.uniform(0.0, policy.jitter))

    def wait(self, failure: Failure, attempt: int, policy: RetryPolicy, cancel_check=None) -> bool:
        seconds = self.delay(failure, attempt, policy)
        if seconds <= 0:
            return True
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if cancel_check and cancel_check():
                return False
            time.sleep(min(0.1, max(0.0, end - time.monotonic())))
        return True
