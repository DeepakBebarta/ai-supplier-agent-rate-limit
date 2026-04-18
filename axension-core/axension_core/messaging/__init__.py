"""
axension_core.messaging — the shared WhatsApp send pipeline.

Public API (this is what Agents 1, 2, 3 import):
    from axension_core.messaging import send_agent_message
    from axension_core.messaging import RateLimitExceeded
    from axension_core.messaging import MAX_MSGS_PER_FACTORY_PER_DAY
"""

from .send_helper import send_agent_message
from .rate_limiter import (
    check_and_record,
    RateLimitExceeded,
    MAX_MSGS_PER_FACTORY_PER_DAY,
    get_today_count,
    reset_factory_today,
    set_redis_client,
    reset_redis_client,
)

__all__ = [
    "send_agent_message",
    "check_and_record",
    "RateLimitExceeded",
    "MAX_MSGS_PER_FACTORY_PER_DAY",
    "get_today_count",
    "reset_factory_today",
    "set_redis_client",
    "reset_redis_client",
]
