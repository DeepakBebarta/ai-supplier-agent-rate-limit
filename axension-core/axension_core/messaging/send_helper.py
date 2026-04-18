"""
axension-core/messaging/send_helper.py
═══════════════════════════════════════════════════════════════════════════
SHARED WHATSAPP SEND HELPER — single entry point for all 3 agents.

Imported by:
  - agent-followup     (Agent 1 — Deepak)
  - agent-stock        (Agent 2 — Karthik)
  - agent-invoice      (Agent 3 — Siddhartha)

Nobody calls the WhatsApp Cloud API directly. Everything goes through
send_agent_message(). This is what guarantees:
  • The 3-msg-per-factory-per-day cap is enforced uniformly
  • Every outgoing message is templated + versioned
  • Every send (success / blocked / failed) lands in agent_logs

Day 5 — Week 1 Close
Owner: Deepak (D2)
═══════════════════════════════════════════════════════════════════════════
"""

import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

import requests
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from .rate_limiter import check_and_record, RateLimitExceeded, MAX_MSGS_PER_FACTORY_PER_DAY

logger = logging.getLogger("axension.send_helper")

# ───────────────────────────────────────────────────────────────────────────
# Template loading — one Jinja env shared across all calls
# ───────────────────────────────────────────────────────────────────────────
_TEMPLATES_DIR = Path(__file__).parent / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(disabled_extensions=("j2",), default_for_string=False),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _agent_id_from_template_key(template_key: str) -> str:
    """
    Derive agent_id from the template_key prefix.
    'agent1_followup'        → 'agent1'
    'agent2_stock_alert'     → 'agent2'
    'agent3_mismatch_alert'  → 'agent3'
    """
    parts = template_key.split("_", 1)
    if not parts or not parts[0].startswith("agent"):
        raise ValueError(
            f"Invalid template_key '{template_key}' — must start with "
            f"'agent1_', 'agent2_' or 'agent3_'"
        )
    return parts[0]


def _render_template(template_key: str, template_version: str, params: dict) -> str:
    """Load templates/{key}_{version}.j2 and render with params."""
    filename = f"{template_key}_{template_version}.j2"
    try:
        template = _jinja_env.get_template(filename)
    except TemplateNotFound:
        raise TemplateNotFound(
            f"Template '{filename}' not found in {_TEMPLATES_DIR}"
        )
    return template.render(**params).strip()


# ───────────────────────────────────────────────────────────────────────────
# WhatsApp Cloud API send — Meta WABA
# ───────────────────────────────────────────────────────────────────────────
def _send_via_waba(to_phone: str, message_text: str) -> dict:
    """
    POST a free-form text message to Meta WhatsApp Cloud API.
    Returns {"success": bool, "message_id": str|None, "error": str|None}.

    Honours DRY_RUN=true env var — in DRY_RUN mode no API call is made and a
    fake message_id is returned. W1 runs DRY_RUN=true; Day 6 flips it.
    """
    dry_run = os.environ.get("DRY_RUN", "true").lower() == "true"

    if dry_run:
        fake_id = f"wamid.DRYRUN_{uuid.uuid4().hex[:16]}"
        logger.info("DRY_RUN send to=%s msg_id=%s", to_phone, fake_id)
        return {"success": True, "message_id": fake_id, "error": None}

    token = os.environ.get("WABA_TOKEN", "")
    phone_id = os.environ.get("WABA_PHONE_ID", "")
    version = os.environ.get("WABA_VERSION", "v19.0")

    if not token or not phone_id:
        return {"success": False, "message_id": None,
                "error": "WABA_TOKEN or WABA_PHONE_ID not configured"}

    url = f"https://graph.facebook.com/{version}/{phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": message_text},
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    last_err = None
    for attempt in range(1, 4):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            msg_id = data.get("messages", [{}])[0].get("id", "")
            return {"success": True, "message_id": msg_id, "error": None}
        except requests.exceptions.HTTPError as e:
            last_err = f"HTTP {resp.status_code}: {resp.text}"
            logger.warning("WABA send attempt %s failed: %s", attempt, last_err)
            time.sleep(2 ** attempt)
        except requests.exceptions.RequestException as e:
            last_err = str(e)
            logger.warning("WABA send attempt %s failed: %s", attempt, last_err)
            time.sleep(2 ** attempt)

    return {"success": False, "message_id": None, "error": last_err or "unknown"}


# ───────────────────────────────────────────────────────────────────────────
# Logging to factory_001.agent_logs
# ───────────────────────────────────────────────────────────────────────────
# We import lazily so test files that don't have psycopg installed still work
# for unit-tests of rate-limit / template logic.
def _log_to_agent_logs(
    *,
    factory_id: str,
    agent_id: str,
    to_phone: str,
    template_key: str,
    template_version: str,
    message_text: str,
    message_id: Optional[str],
    status: str,
) -> Optional[str]:
    """
    INSERT a row into {factory_id}.agent_logs.
    Returns the inserted row id (UUID-shaped string), or None on failure.
    Never raises — logging failure must not block the send pipeline.
    """
    logged_id = str(uuid.uuid4())
    try:
        # Late import — keeps unit tests independent of psycopg / DB availability
        from axension_core.messaging.db import insert_agent_log
        insert_agent_log(
            factory_id=factory_id,
            agent_id=agent_id,
            to_phone=to_phone,
            template_key=template_key,
            template_version=template_version,
            message_text=message_text,
            message_id=message_id,
            status=status,
            logged_id=logged_id,
        )
        return logged_id
    except Exception as e:
        logger.error("agent_logs insert failed (non-fatal): %s", e)
        return logged_id  # still return the id we generated; caller can re-log


# ───────────────────────────────────────────────────────────────────────────
# THE ONE FUNCTION THE 3 AGENTS IMPORT
# ───────────────────────────────────────────────────────────────────────────
def send_agent_message(
    factory_id: str,
    to_phone: str,
    template_key: str,
    template_version: str,
    params: dict,
) -> dict:
    """
    Send a templated, rate-limited, logged WhatsApp message.

    This is the ONLY function in the codebase that should call WABA.
    Agents 1, 2, 3 all import this function and never reach for requests
    or twilio themselves.

    Args:
        factory_id:        e.g. 'factory_001' — the rate-limit bucket
        to_phone:          E.164 without '+'  e.g. '918121444200'
        template_key:      e.g. 'agent1_followup', 'agent2_stock_alert'
        template_version:  e.g. 'v1'
        params:            dict of template variables

    Returns:
        {
          "status":      "sent" | "blocked" | "failed",
          "message_id":  str | None,
          "logged_id":   str | None,
          "reason":      str (only when status != "sent"),
        }
    """
    agent_id = _agent_id_from_template_key(template_key)

    # ── Step 1: Rate limit check (HARD CAP, enforced in code) ─────────────
    if not check_and_record(factory_id):
        message_preview = f"[BLOCKED] template={template_key}_{template_version}"
        logged_id = _log_to_agent_logs(
            factory_id=factory_id, agent_id=agent_id, to_phone=to_phone,
            template_key=template_key, template_version=template_version,
            message_text=message_preview, message_id=None,
            status="blocked_rate_limit",
        )
        logger.warning(
            "send_agent_message BLOCKED factory=%s agent=%s template=%s",
            factory_id, agent_id, template_key,
        )
        return {
            "status": "blocked",
            "message_id": None,
            "logged_id": logged_id,
            "reason": f"rate_limit_exceeded (cap={MAX_MSGS_PER_FACTORY_PER_DAY}/day)",
        }

    # ── Step 2: Template lookup + render ──────────────────────────────────
    try:
        message_text = _render_template(template_key, template_version, params)
    except TemplateNotFound as e:
        logged_id = _log_to_agent_logs(
            factory_id=factory_id, agent_id=agent_id, to_phone=to_phone,
            template_key=template_key, template_version=template_version,
            message_text=f"[TEMPLATE_MISSING] {e}", message_id=None,
            status="failed_template",
        )
        return {
            "status": "failed",
            "message_id": None,
            "logged_id": logged_id,
            "reason": f"template_not_found: {e}",
        }
    except Exception as e:
        logged_id = _log_to_agent_logs(
            factory_id=factory_id, agent_id=agent_id, to_phone=to_phone,
            template_key=template_key, template_version=template_version,
            message_text=f"[RENDER_ERROR] {e}", message_id=None,
            status="failed_render",
        )
        return {
            "status": "failed",
            "message_id": None,
            "logged_id": logged_id,
            "reason": f"render_error: {e}",
        }

    # ── Step 3: WABA send ─────────────────────────────────────────────────
    result = _send_via_waba(to_phone, message_text)

    # ── Step 4: Log + return ──────────────────────────────────────────────
    if result["success"]:
        logged_id = _log_to_agent_logs(
            factory_id=factory_id, agent_id=agent_id, to_phone=to_phone,
            template_key=template_key, template_version=template_version,
            message_text=message_text, message_id=result["message_id"],
            status="sent",
        )
        return {
            "status": "sent",
            "message_id": result["message_id"],
            "logged_id": logged_id,
        }

    logged_id = _log_to_agent_logs(
        factory_id=factory_id, agent_id=agent_id, to_phone=to_phone,
        template_key=template_key, template_version=template_version,
        message_text=message_text, message_id=None,
        status="failed_send",
    )
    return {
        "status": "failed",
        "message_id": None,
        "logged_id": logged_id,
        "reason": result["error"] or "waba_send_failed",
    }
