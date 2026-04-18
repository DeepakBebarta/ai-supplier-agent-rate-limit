"""
src/tasks/agent1_tasks.py — Agent 1 daily supplier follow-up task.

W2: Now uses send_agent_message() from axension_core instead of the
legacy Twilio sender. This means:
  - Messages go via Meta WABA (no Twilio)
  - Versioned Jinja2 templates are used
  - template_key and template_version are written to agent_logs
  - DRY_RUN=true → fake wamid, nothing sent (safe for testing)
  - DRY_RUN=false → real WhatsApp via Meta API
"""

import logging
from datetime import datetime, date

from src.tasks.celery_app import app
from src.agents.agent1.po_scanner import get_overdue_pos, get_pos_due_today
from src.db.connection import get_db_cursor
from config.settings import FACTORY_ID, OWNER_PHONE, MAX_MESSAGES_PER_RUN

# ── Shared send helper (Meta WABA, rate-limited, templated) ──────────────
from axension_core.messaging import send_agent_message
from axension_core.messaging.rate_limiter import MAX_MSGS_PER_FACTORY_PER_DAY

logger = logging.getLogger("axension.agent1.task")

HARD_CAP = MAX_MSGS_PER_FACTORY_PER_DAY  # = 3, enforced in code


def log_to_agent_logs(agent_id: str, factory_id: str, po_number: str,
                      supplier_phone: str, message_type: str,
                      message_preview: str, status: str):
    """Insert a row into {factory_id}.agent_logs."""
    query = """
        INSERT INTO {schema}.agent_logs
            (agent_id, factory_id, po_number, supplier_phone,
             message_type, message_preview, sent_at, status)
        VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
    """.format(schema=factory_id)
    try:
        with get_db_cursor() as cur:
            cur.execute(query, (
                agent_id, factory_id, po_number, supplier_phone,
                message_type, message_preview[:200], status
            ))
        logger.info(f"Logged to agent_logs: {message_type} for {po_number}")
    except Exception as e:
        logger.error(f"Failed to log to agent_logs: {e}")


@app.task(name="agent1.daily_supplier_followup", bind=True, max_retries=2)
def daily_supplier_followup(self):
    """
    Main Agent 1 task — runs daily at 8 AM IST.

    1. Fetch overdue POs + POs due today
    2. Apply HARD_CAP (top 3 by days_overdue)
    3. Send each via send_agent_message() → Meta WABA
    4. Log results to agent_logs with template_key + template_version
    5. Send owner summary
    """
    run_start = datetime.now()
    run_time  = run_start.strftime("%I:%M %p")
    factory_id = FACTORY_ID
    agent_id   = "agent1"

    logger.info(f"═══ Agent 1 starting at {run_time} for {factory_id} ═══")

    # ── Fetch POs ──────────────────────────────────────────────────────────
    overdue_pos = get_overdue_pos(factory_id)
    due_today   = get_pos_due_today(factory_id)

    seen = set()
    combined = []
    for po in overdue_pos:
        if po["po_number"] not in seen:
            seen.add(po["po_number"])
            combined.append(po)
    for po in due_today:
        if po["po_number"] not in seen:
            seen.add(po["po_number"])
            po["days_overdue"] = 0
            combined.append(po)

    logger.info(f"Total POs to follow up: {len(combined)} (before cap)")
    capped = combined[:HARD_CAP]
    logger.info(f"After per-run cap ({HARD_CAP}): {len(capped)} POs selected")

    # ── Send supplier messages ─────────────────────────────────────────────
    messages_sent  = 0
    rate_blocked   = 0
    skipped        = 0
    errors         = []
    supplier_names = []

    for po in capped:
        supplier_phone = po.get("supplier_phone", "")

        if not supplier_phone or not str(supplier_phone).strip():
            logger.warning(f"Skipping PO {po['po_number']} — no phone")
            log_to_agent_logs(
                agent_id, factory_id, po["po_number"],
                "N/A", "supplier_followup",
                f"SKIPPED: No phone for {po['supplier_name']}", "skipped",
            )
            skipped += 1
            continue

        # Normalise phone to E.164 without '+' for Meta API
        from src.whatsapp.sender import format_phone_for_whatsapp
        clean_phone = format_phone_for_whatsapp(str(supplier_phone))

        promised_str = (
            po["promised_date"].strftime("%d-%b-%Y")
            if hasattr(po["promised_date"], "strftime")
            else str(po["promised_date"])
        )

        result = send_agent_message(
            factory_id=factory_id,
            to_phone=clean_phone,
            template_key="agent1_followup",
            template_version="v1",
            params={
                "supplier_name": po["supplier_name"],
                "po_number":     po["po_number"],
                "item_name":     po["item_name"],
                "promised_date": promised_str,
                "days_overdue":  po["days_overdue"],
            },
        )

        if result["status"] == "sent":
            messages_sent += 1
            supplier_names.append(po["supplier_name"])
            logger.info(
                f"✓ Sent to {po['supplier_name']} ({po['po_number']}) "
                f"— {po['days_overdue']} days overdue | wamid={result['message_id']}"
            )

        elif result["status"] == "blocked":
            rate_blocked += 1
            log_to_agent_logs(
                agent_id, factory_id, po["po_number"],
                clean_phone, "supplier_followup",
                f"BLOCKED: daily cap of {HARD_CAP}/factory reached",
                "rate_limit_exceeded",
            )
            logger.warning(f"⛔ Rate-limited for {po['supplier_name']}")

        else:
            errors.append({
                "po_number": po["po_number"],
                "supplier":  po["supplier_name"],
                "error":     result.get("reason", "unknown"),
            })
            logger.error(
                f"✗ Failed to send to {po['supplier_name']}: {result.get('reason')}"
            )

    # ── Owner summary ──────────────────────────────────────────────────────
    owner_notified = False
    if OWNER_PHONE:
        from src.whatsapp.sender import format_phone_for_whatsapp
        owner_clean = format_phone_for_whatsapp(OWNER_PHONE)

        names_str = ", ".join(supplier_names) if supplier_names else "none"
        owner_result = send_agent_message(
            factory_id=factory_id,
            to_phone=owner_clean,
            template_key="agent1_owner_summary",
            template_version="v1",
            params={
                "date_str":     run_start.strftime("%d-%b-%Y"),
                "followed_up":  messages_sent,
                "replied":      0,       # will be populated in W2 from webhook replies
                "no_reply":     messages_sent,
                "escalations":  [
                    po for po in combined
                    if int(po.get("days_overdue", 0)) >= 5
                ][:3],
                "stock_summary": None,   # Agent 2 (Karthik) fills this in W2
            },
        )

        if owner_result["status"] == "sent":
            owner_notified = True
            logger.info("✓ Owner summary sent")
        elif owner_result["status"] == "blocked":
            logger.warning("⛔ Rate-limited — owner summary not sent")
        else:
            logger.error(f"✗ Owner summary failed: {owner_result.get('reason')}")
    else:
        logger.warning("OWNER_PHONE not set — skipping owner summary")

    summary = {
        "factory_id":    factory_id,
        "run_time":      run_time,
        "total_overdue": len(combined),
        "messages_sent": messages_sent,
        "rate_blocked":  rate_blocked,
        "skipped":       skipped,
        "errors":        errors,
        "owner_notified": owner_notified,
        "hard_cap":      HARD_CAP,
    }

    logger.info(
        f"═══ Agent 1 complete: {messages_sent} sent, {rate_blocked} blocked, "
        f"{skipped} skipped, {len(errors)} errors ═══"
    )
    return summary
