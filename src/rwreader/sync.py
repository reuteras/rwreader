"""Request pacing for the background index sync.

The Reader API rate-limits list requests. A full sync of a large library needs
many paged requests, so :class:`AdaptivePacer` keeps a delay between them that
starts below the documented limit, doubles whenever the API answers 429 and
slowly recovers after a run of successful requests. The sync therefore settles
at a speed the API accepts, also when the rest of the app is using part of the
same budget.
"""

from collections.abc import Callable
from dataclasses import dataclass

# Starting delay between list requests. ~17 requests/minute, below the
# 20/minute the Reader API documents for list requests.
DEFAULT_INTERVAL_SECONDS = 3.5
MAX_INTERVAL_SECONDS = 120.0
# Consecutive successes before the delay is reduced again.
RECOVER_AFTER = 20
RECOVER_FACTOR = 0.8
BACKOFF_FACTOR = 2.0


class AdaptivePacer:
    """Delay between paged requests that backs off on rate limits."""

    def __init__(
        self,
        interval: float = DEFAULT_INTERVAL_SECONDS,
        max_interval: float = MAX_INTERVAL_SECONDS,
    ) -> None:
        """Initialize the pacer.

        Args:
            interval: Starting delay, also the lowest delay it recovers to.
            max_interval: Upper bound for the delay after repeated backoffs.
        """
        self.min_interval = interval
        self.max_interval = max_interval
        self.interval = interval
        self._streak = 0

    def on_success(self) -> None:
        """Record a successful request, speeding up after a long streak."""
        self._streak += 1
        if self._streak >= RECOVER_AFTER and self.interval > self.min_interval:
            self.interval = max(self.min_interval, self.interval * RECOVER_FACTOR)
            self._streak = 0

    def on_rate_limit(self, retry_after: float | None) -> float:
        """Slow down after a 429 and return how long to wait before retrying.

        Args:
            retry_after: Seconds from the ``Retry-After`` header, if any.

        Returns:
            Seconds to wait before the next request.
        """
        self._streak = 0
        self.interval = min(self.max_interval, self.interval * BACKOFF_FACTOR)
        return max(float(retry_after or 0), self.interval)


@dataclass
class SyncProgress:
    """Progress report from a running sync."""

    written: int
    waiting: float = 0.0
    reason: str = ""
    done: bool = False


ProgressCallback = Callable[[SyncProgress], None]
