"""
src/whatsapp/sender.py — Meta WhatsApp Cloud API sender for Axension AI.

Twilio has been removed entirely. All WhatsApp messages go through
Meta's Graph API (WABA). The shared axension_core rate limiter is
enforced at every send call.

DRY_RUN=true  → returns fake wamid.DRYRUN_* id, no real API call
DRY_RUN=false → real Meta API call (set this for production Day 6+)
"""

import logging
import os
import time
import uuid

import requests

from config.settings import (
    WABA_TOKEN,
    WABA_PHONE_ID,
    WABA_VERSION,
    FACTORY_ID,
    DRY_RUN,
)
from axension_core.messaging.rate_limiter import (
    check_and_record,
    RateLimitExceeded,
    MAX_MSGS_PER_FACTORY_PER_DAY,
)

logger = logging.getLogger("axension.whatsapp")


def _waba_url() -> str:
    return f"https://graph.facebook.com/{WABA_VERSION}/{WABA_PHONE_ID}/messages"


def _send_via_meta(to_phone: str, message: str) -> dict:
    """
    POST a plain-text message to Meta WhatsApp Cloud API.
    Returns {success, message_id, error}.
    Retries up to 3 times on failure.
    """
    if DRY_RUN:
        fake_id = f"wamid.DRYRUN_{uuid.uuid4().hex[:16]}"
        logger.info("DRY_RUN send to=%s msg_id=%s", to_phone, fake_id)
        return {"success": True, "message_id": fake_id, "error": None}

    if not WABA_TOKEN or not WABA_PHONE_ID:
        return {
            "success": False,
            "message_id": None,
            "error": "WABA_TOKEN or WABA_PHONE_ID not set in .env",
        }

    url = _waba_url()
    headers = {
        "Authorization": f"Bearer {WABA_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message},
    }

    last_err = None
    for attempt in range(1, 4):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            msg_id = data.get("messages", [{}])[0].get("id", "")
            logger.info("Meta WABA sent to=%s wamid=%s", to_phone, msg_id)
            return {"success": True, "message_id": msg_id, "error": None}
        except requests.exceptions.HTTPError as e:
            last_err = f"HTTP {resp.status_code}: {resp.text}"
            logger.warning("WABA attempt %s failed: %s", attempt, last_err)
            time.sleep(2 ** attempt)
        except requests.exceptions.RequestException as e:
            last_err = str(e)
            logger.warning("WABA attempt %s failed: %s", attempt, last_err)
            time.sleep(2 ** attempt)

    return {"success": False, "message_id": None, "error": last_err or "unknown"}


def send_text(to_phone: str, message: str, factory_id: str = None) -> dict:
    """
    Send a WhatsApp message via Meta WABA — rate-limited per factory.

    Args:
        to_phone:   E.164 without '+', e.g. '918121444200'
        message:    Message body text
        factory_id: Rate-limit bucket. Defaults to config.FACTORY_ID.

    Returns:
        {success, message_id, error}
        success=False + error='rate_limit_exceeded' when cap is hit.
    """
    if factory_id is None:
        factory_id = FACTORY_ID

    # ── HARD CAP — enforced in code ───────────────────────────────────────
    if not check_and_record(factory_id):
        logger.warning(
            "RATE_LIMIT_BLOCK factory=%s to=%s cap=%s — WhatsApp NOT sent",
            factory_id, to_phone, MAX_MSGS_PER_FACTORY_PER_DAY,
        )
        return {"success": False, "message_id": None, "error": "rate_limit_exceeded"}

    result = _send_via_meta(to_phone, message)

    if result["success"]:
        return {"success": True, "sid": result["message_id"],
                "message_id": result["message_id"], "error": None}
    return {"success": False, "sid": None,
            "message_id": None, "error": result["error"]}


def format_phone_for_whatsapp(phone: str) -> str:
    """
    Normalise to E.164 without '+' for Meta API.
    Meta expects '918121444200', not 'whatsapp:+918121444200'.
    """
    if not phone:
        return ""
    phone = phone.strip()
    # Strip whatsapp: prefix if present (from old Twilio format)
    if phone.startswith("whatsapp:"):
        phone = phone[9:]
    # Strip leading +
    phone = phone.lstrip("+")
    digits = "".join(c for c in phone if c.isdigit())
    if not digits:
        return ""
    # 10-digit Indian number → prepend 91
    if len(digits) == 10:
        return f"91{digits}"
    return digits


__all__ = [
    "send_text",
    "format_phone_for_whatsapp",
    "RateLimitExceeded",
    "MAX_MSGS_PER_FACTORY_PER_DAY",
]
