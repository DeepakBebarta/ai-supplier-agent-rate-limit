"""
axension-core/messaging/rate_limiter.py
═══════════════════════════════════════════════════════════════════════════
PER-FACTORY DAILY RATE LIMITER — Hard cap enforced at the send layer.

The 3-messages-per-factory-per-day cap is NOT configurable.
It lives as a module-level constant. Changing it requires a code change + PR.

Imported by:
  - axension-core.messaging.send_helper (the shared helper)
  - axension-agent1.src.whatsapp.sender (legacy direct send_text wrapper)
  - any future agent that sends WhatsApp must go through send_helper

Day 5 — Week 1 Close
Owner: Deepak (D2)
═══════════════════════════════════════════════════════════════════════════
"""

import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

import redis

logger = logging.getLogger("axension.rate_limiter")

# ───────────────────────────────────────────────────────────────────────────
# HARD CAP — DO NOT MOVE TO .env, DO NOT MOVE TO config/settings.py
# Changing this number requires a code change and PR review.
# ───────────────────────────────────────────────────────────────────────────
MAX_MSGS_PER_FACTORY_PER_DAY: int = 3

# TTL > 24h so rolling-day boundaries are safe (covers DST + clock skew).
_KEY_TTL_SECONDS: int = 26 * 3600

# IST is the only timezone we care about — all factories are in India for MVP.
_IST = ZoneInfo("Asia/Kolkata")


class RateLimitExceeded(Exception):
    """Raised when a factory has hit MAX_MSGS_PER_FACTORY_PER_DAY for today."""

    def __init__(self, factory_id: str, count: int):
        self.factory_id = factory_id
        self.count = count
        super().__init__(
            f"Factory {factory_id} has hit {MAX_MSGS_PER_FACTORY_PER_DAY}-msg "
            f"daily cap (current count: {count})"
        )


# ───────────────────────────────────────────────────────────────────────────
# Redis client (lazy-init so tests can swap with fakeredis)
# ───────────────────────────────────────────────────────────────────────────
_redis_client: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    """Lazy-init the Redis client. Tests override via set_redis_client()."""
    global _redis_client
    if _redis_client is None:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.from_url(url, decode_responses=True)
    return _redis_client


def set_redis_client(client) -> None:
    """Test hook — inject fakeredis or any other redis-compatible client."""
    global _redis_client
    _redis_client = client


def reset_redis_client() -> None:
    """Test hook — clear the cached client so next call re-initialises."""
    global _redis_client
    _redis_client = None


# ───────────────────────────────────────────────────────────────────────────
# Core API
# ───────────────────────────────────────────────────────────────────────────
def _today_key(factory_id: str, now: Optional[datetime] = None) -> str:
    """Build the Redis key for today's counter for this factory."""
    if now is None:
        now = datetime.now(tz=_IST)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=_IST)
    today = now.strftime("%Y%m%d")
    return f"ratelimit:msgs:{factory_id}:{today}"


def check_and_record(factory_id: str, now: Optional[datetime] = None) -> bool:
    """
    Atomically increment today's send-count for `factory_id` and check the cap.

    Returns:
        True  → safe to send (count is at or under the cap after increment)
        False → over cap; caller MUST NOT send

    Side effects:
        Increments a Redis counter. The counter is incremented even on a
        rejection so that repeated attempts after the cap is hit do not
        masquerade as the first send of the next day.
    """
    key = _today_key(factory_id, now)
    r = _get_redis()

    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, _KEY_TTL_SECONDS)
    count, _ = pipe.execute()

    count = int(count)

    if count > MAX_MSGS_PER_FACTORY_PER_DAY:
        logger.warning(
            "RATE_LIMIT_BLOCK factory=%s count=%s cap=%s",
            factory_id, count, MAX_MSGS_PER_FACTORY_PER_DAY,
        )
        return False

    logger.info(
        "RATE_LIMIT_OK factory=%s count=%s/%s",
        factory_id, count, MAX_MSGS_PER_FACTORY_PER_DAY,
    )
    return True


def get_today_count(factory_id: str, now: Optional[datetime] = None) -> int:
    """Read-only — current count for today. Used by dashboards/diagnostics."""
    key = _today_key(factory_id, now)
    val = _get_redis().get(key)
    return int(val) if val else 0


def reset_factory_today(factory_id: str, now: Optional[datetime] = None) -> None:
    """
    Manual override — wipes today's counter for a factory.
    Only used by ops in genuine emergencies. Logged loudly.
    """
    key = _today_key(factory_id, now)
    _get_redis().delete(key)
    logger.warning("RATE_LIMIT_MANUAL_RESET factory=%s key=%s", factory_id, key)
