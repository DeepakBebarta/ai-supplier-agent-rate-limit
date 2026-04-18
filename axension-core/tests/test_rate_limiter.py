"""
tests/test_rate_limiter.py — Day 5 / Task 3
─────────────────────────────────────────────
Three pytest tests for the per-factory daily rate limiter using fakeredis.

  1. test_allows_first_three   — 3 calls in a row return True
  2. test_blocks_fourth        — 4th call returns False
  3. test_resets_next_day      — mocked next-day datetime returns True again

Run:
    pytest tests/test_rate_limiter.py -v
"""

import pytest
import fakeredis
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from axension_core.messaging import (
    check_and_record,
    MAX_MSGS_PER_FACTORY_PER_DAY,
    set_redis_client,
    reset_redis_client,
)
from axension_core.messaging.rate_limiter import get_today_count

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture(autouse=True)
def _swap_redis():
    """Each test gets a fresh fakeredis instance — no shared state."""
    fake = fakeredis.FakeRedis(decode_responses=True)
    set_redis_client(fake)
    yield fake
    reset_redis_client()


def test_allows_first_three():
    """First MAX_MSGS_PER_FACTORY_PER_DAY (=3) calls all return True."""
    factory = "factory_001"
    assert MAX_MSGS_PER_FACTORY_PER_DAY == 3, "hard cap must be 3"

    results = [check_and_record(factory) for _ in range(3)]

    assert results == [True, True, True]
    assert get_today_count(factory) == 3


def test_blocks_fourth():
    """Fourth call on the same day returns False."""
    factory = "factory_001"

    for _ in range(3):
        check_and_record(factory)

    assert check_and_record(factory) is False
    # And keeps blocking — 5th, 6th attempts also False
    assert check_and_record(factory) is False
    assert check_and_record(factory) is False


def test_resets_next_day():
    """Next-day call (different YYYYMMDD key) returns True again."""
    factory = "factory_001"

    today = datetime(2026, 4, 17, 14, 30, tzinfo=IST)
    tomorrow = today + timedelta(days=1)

    # Burn through today's quota
    for _ in range(3):
        check_and_record(factory, now=today)
    assert check_and_record(factory, now=today) is False

    # New IST day — fresh counter
    assert check_and_record(factory, now=tomorrow) is True
    assert check_and_record(factory, now=tomorrow) is True
    assert check_and_record(factory, now=tomorrow) is True
    assert check_and_record(factory, now=tomorrow) is False


def test_factories_are_isolated():
    """factory_001 hitting cap does not affect factory_002."""
    check_and_record("factory_001")
    check_and_record("factory_001")
    check_and_record("factory_001")
    assert check_and_record("factory_001") is False

    # factory_002 is untouched
    assert check_and_record("factory_002") is True
    assert check_and_record("factory_002") is True
    assert check_and_record("factory_002") is True
    assert check_and_record("factory_002") is False
