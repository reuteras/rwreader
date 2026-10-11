"""Tests for the adaptive request pacer used by the index sync."""

import pytest

from rwreader.sync import RECOVER_AFTER, AdaptivePacer

START = 4.0
MAX = 30.0
RETRY_AFTER = 50.0


class TestAdaptivePacer:
    """Tests for AdaptivePacer."""

    def test_starts_at_interval(self) -> None:
        """The first delay is the configured interval."""
        assert AdaptivePacer(interval=START).interval == START

    def test_rate_limit_doubles_interval(self) -> None:
        """Each 429 doubles the delay."""
        pacer = AdaptivePacer(interval=START, max_interval=MAX)
        pacer.on_rate_limit(None)
        assert pacer.interval == START * 2

    def test_rate_limit_waits_at_least_retry_after(self) -> None:
        """The wait honours Retry-After when it is longer than the delay."""
        pacer = AdaptivePacer(interval=START, max_interval=MAX)
        assert pacer.on_rate_limit(RETRY_AFTER) == RETRY_AFTER
        assert pacer.on_rate_limit(None) == pacer.interval

    def test_interval_is_capped(self) -> None:
        """Repeated 429s never push the delay past the maximum."""
        pacer = AdaptivePacer(interval=START, max_interval=MAX)
        for _ in range(10):
            pacer.on_rate_limit(None)
        assert pacer.interval == MAX

    def test_recovers_after_success_streak(self) -> None:
        """A long run of successes speeds up again, but not past the start."""
        pacer = AdaptivePacer(interval=START, max_interval=MAX)
        pacer.on_rate_limit(None)
        slowed = pacer.interval
        for _ in range(RECOVER_AFTER):
            pacer.on_success()
        assert START < pacer.interval < slowed
        for _ in range(RECOVER_AFTER * 20):
            pacer.on_success()
        assert pacer.interval == pytest.approx(START)

    def test_rate_limit_resets_streak(self) -> None:
        """Successes before a 429 do not count toward recovery."""
        pacer = AdaptivePacer(interval=START, max_interval=MAX)
        for _ in range(RECOVER_AFTER - 1):
            pacer.on_success()
        pacer.on_rate_limit(None)
        slowed = pacer.interval
        pacer.on_success()
        assert pacer.interval == slowed
