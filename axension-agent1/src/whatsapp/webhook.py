"""
src/whatsapp/webhook.py — Meta WhatsApp Cloud API webhook for Axension AI.

Twilio has been removed entirely. This webhook handles:
  - Meta webhook verification (GET /webhook)
  - Incoming owner commands: 9, status, run, logs, help, overdue, today, week
  - Incoming supplier replies: dispatched, delay, eta, issue, status

Meta sends POST to /webhook with JSON body.
Use Cloudflare Tunnel or ngrok to expose localhost:5000 to Meta.

Run with:
    python -m src.whatsapp.webhook
"""

import hashlib
import hmac
import json
import logging
import os
import sys
from datetime import datetime, date

from flask import Flask, request, jsonify

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import FACTORY_ID, OWNER_PHONE, WABA_VERIFY_TOKEN, WABA_TOKEN
from src.whatsapp.sender import send_text, format_phone_for_whatsapp
from src.db.connection import get_db_cursor
from src.agents.agent1.po_scanner import (
    get_overdue_pos,
    get_pos_due_today,
    get_pos_due_this_week,
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("axension.webhook")


# ═══════════════════════════════════════════════════════════
#  META WEBHOOK VERIFICATION
# ═══════════════════════════════════════════════════════════

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """
    Meta calls this endpoint with a challenge when you register the webhook.
    It verifies using WABA_VERIFY_TOKEN from your .env.
    """
    mode      = request.args.get("hub.mode")
    token     = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == WABA_VERIFY_TOKEN:
        logger.info("✅ Meta webhook verified successfully")
        return challenge, 200

    logger.warning("❌ Meta webhook verification failed — token mismatch")
    return "Forbidden", 403


# ═══════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════

def _parse_meta_message(body: dict):
    """
    Extract sender phone and message text from Meta webhook POST body.
    Returns (sender_phone, message_text) or (None, None) if not a text message.
    """
    try:
        entry   = body["entry"][0]
        changes = entry["changes"][0]
        value   = changes["value"]

        # Status update (delivered/read) — skip silently
        if "statuses" in value and "messages" not in value:
            return None, None

        message = value["messages"][0]
        if message.get("type") != "text":
            return message.get("from"), f"[{message.get('type','?').upper()} MESSAGE]"

        return message["from"], message["text"]["body"]
    except (KeyError, IndexError, TypeError):
        return None, None


def get_recent_agent_logs(factory_id: str, limit: int = 10) -> list:
    query = """
        SELECT po_number, supplier_phone, message_type,
               message_preview, sent_at, status
        FROM {schema}.agent_logs
        ORDER BY sent_at DESC
        LIMIT %s
    """.format(schema=factory_id)
    try:
        with get_db_cursor() as cur:
            cur.execute(query, (limit,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error fetching agent_logs: {e}")
        return []


def get_supplier_by_phone(factory_id: str, phone: str) -> list:
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    query = """
        SELECT po_number, supplier_name, item_name, quantity, unit,
               promised_date, status,
               (CURRENT_DATE - promised_date::date) AS days_overdue
        FROM {schema}.purchase_orders
        WHERE supplier_phone LIKE %s
          AND status = 'To Receive and Bill'
        ORDER BY promised_date ASC
    """.format(schema=factory_id)
    try:
        with get_db_cursor() as cur:
            cur.execute(query, (f"%{digits[-10:]}%",))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error finding supplier: {e}")
        return []


def log_incoming(factory_id: str, phone: str, message: str, msg_type: str):
    query = """
        INSERT INTO {schema}.agent_logs
            (agent_id, factory_id, po_number, supplier_phone,
             message_type, message_preview, sent_at, status)
        VALUES ('agent1', %s, 'N/A', %s, %s, %s, NOW(), 'received')
    """.format(schema=factory_id)
    try:
        with get_db_cursor() as cur:
            cur.execute(query, (factory_id, phone, msg_type, message[:200]))
    except Exception as e:
        logger.error(f"Error logging: {e}")


def format_date(d) -> str:
    if isinstance(d, date):
        return d.strftime("%d-%b-%Y")
    return str(d)


def _send_reply(to_phone: str, message: str):
    """Send a reply back to the user via Meta WABA."""
    result = send_text(to_phone, message, factory_id=FACTORY_ID)
    if not result["success"]:
        logger.error(f"Failed to send reply to {to_phone}: {result['error']}")


# ═══════════════════════════════════════════════════════════
#  OWNER RESPONSE BUILDERS
# ═══════════════════════════════════════════════════════════

def build_full_report() -> str:
    overdue   = get_overdue_pos(FACTORY_ID)
    due_today = get_pos_due_today(FACTORY_ID)
    due_week  = get_pos_due_this_week(FACTORY_ID)

    lines = [
        "📋 *AXENSION AI — FULL PO REPORT*",
        f"📅 {datetime.now().strftime('%d-%b-%Y %I:%M %p')} IST",
        "",
        f"🔴 *OVERDUE ({len(overdue)} POs):*",
    ]
    if overdue:
        for i, po in enumerate(overdue, 1):
            days = int(po["days_overdue"])
            lines.append(
                f"{i}. *{po['supplier_name']}*\n"
                f"   PO #{po['po_number']}\n"
                f"   {po['item_name']} — {po['quantity']} {po['unit']}\n"
                f"   Due: {format_date(po['promised_date'])} (*{days} days late*)"
            )
    else:
        lines.append("   ✅ None! All clear.")
    lines.append("")

    lines.append(f"🟡 *DUE TODAY ({len(due_today)} POs):*")
    if due_today:
        for po in due_today:
            lines.append(f"• {po['supplier_name']} — {po['item_name']}\n  PO #{po['po_number']}")
    else:
        lines.append("   None due today.")
    lines.append("")

    lines.append(f"🟢 *DUE THIS WEEK ({len(due_week)} POs):*")
    if due_week:
        for po in due_week:
            lines.append(
                f"• {po['supplier_name']} — {po['item_name']}\n"
                f"  PO #{po['po_number']} — Due {format_date(po['promised_date'])}"
            )
    else:
        lines.append("   None due this week.")

    total = len(overdue) + len(due_today) + len(due_week)
    lines += [
        "",
        "─────────────────────",
        f"📊 Total active: {total} POs",
        f"🔴 Overdue: {len(overdue)} | 🟡 Today: {len(due_today)} | 🟢 This week: {len(due_week)}",
        "",
        "💬 *Reply:*",
        "• *9* — Refresh this report",
        "• *logs* — Recent agent activity",
        "• *help* — All commands",
    ]
    return "\n".join(lines)


def build_quick_status() -> str:
    overdue   = get_overdue_pos(FACTORY_ID)
    due_today = get_pos_due_today(FACTORY_ID)
    due_week  = get_pos_due_this_week(FACTORY_ID)
    top = "\n".join(
        f"• {po['supplier_name']} — *{po['days_overdue']}d* late"
        for po in overdue[:5]
    ) if overdue else "• ✅ None!"
    return (
        f"⚡ *Quick Status — {datetime.now().strftime('%I:%M %p')} IST*\n\n"
        f"🔴 Overdue: *{len(overdue)}* POs\n"
        f"🟡 Due today: *{len(due_today)}* POs\n"
        f"🟢 Due this week: *{len(due_week)}* POs\n\n"
        f"Top overdue:\n{top}\n\n"
        f"💬 Reply *9* for full report"
    )


def build_logs_report() -> str:
    logs = get_recent_agent_logs(FACTORY_ID, 10)
    if not logs:
        return "📝 No recent agent activity found."
    lines = ["📝 *RECENT AGENT ACTIVITY:*", ""]
    for log in logs:
        sent = log["sent_at"]
        time_str = sent.strftime("%d-%b %I:%M %p") if isinstance(sent, datetime) else str(sent)
        icon = {"sent": "✅", "skipped": "⏭️", "failed": "❌",
                "received": "📨", "rate_limit_exceeded": "⛔"}.get(log["status"], "▪️")
        lines.append(
            f"{icon} {time_str}\n"
            f"   {log['message_type']} | {log.get('po_number','N/A')} | {log['status']}"
        )
    lines.append("\n💬 Reply *9* for full PO report")
    return "\n".join(lines)


def build_owner_help() -> str:
    return (
        "🤖 *AXENSION AI — COMMAND MENU*\n\n"
        "📋 *Reports:*\n"
        "• *9* — Full PO report (overdue + today + this week)\n"
        "• *status* — Quick overview with counts\n"
        "• *overdue* — List only overdue POs\n"
        "• *today* — POs due today\n"
        "• *week* — POs due this week\n"
        "• *logs* — Recent agent activity\n\n"
        "⚙️ *Actions:*\n"
        "• *run* — Trigger supplier follow-up now\n"
        "• *help* — Show this menu\n\n"
        "📊 All data is live from your Supabase database."
    )


def build_overdue_only() -> str:
    overdue = get_overdue_pos(FACTORY_ID)
    if not overdue:
        return "✅ No overdue POs right now!"
    lines = [f"🔴 *OVERDUE POs ({len(overdue)}):*", ""]
    for i, po in enumerate(overdue, 1):
        lines.append(
            f"{i}. *{po['supplier_name']}*\n"
            f"   {po['item_name']} — {po['quantity']} {po['unit']}\n"
            f"   PO #{po['po_number']} — {po['days_overdue']}d late\n"
            f"   📞 {po['supplier_phone']}"
        )
    lines.append("\n💬 Reply *9* for complete report")
    return "\n".join(lines)


def build_today_only() -> str:
    due_today = get_pos_due_today(FACTORY_ID)
    if not due_today:
        return "🟡 No POs due today."
    lines = [f"🟡 *DUE TODAY ({len(due_today)} POs):*", ""]
    for po in due_today:
        lines.append(f"• *{po['supplier_name']}*\n  {po['item_name']} — PO #{po['po_number']}")
    return "\n".join(lines)


def build_week_only() -> str:
    due_week = get_pos_due_this_week(FACTORY_ID)
    if not due_week:
        return "🟢 No POs due this week."
    lines = [f"🟢 *DUE THIS WEEK ({len(due_week)} POs):*", ""]
    for po in due_week:
        lines.append(
            f"• *{po['supplier_name']}* — {po['item_name']}\n"
            f"  PO #{po['po_number']} — Due {format_date(po['promised_date'])}"
        )
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
#  SUPPLIER REPLY HANDLER
# ═══════════════════════════════════════════════════════════

def handle_supplier_reply(phone: str, message: str, supplier_pos: list) -> str:
    supplier_name = supplier_pos[0]["supplier_name"] if supplier_pos else "Supplier"
    msg_lower = message.lower().strip()

    if msg_lower in ("dispatched", "shipped", "sent", "dispatch"):
        for po in supplier_pos:
            log_incoming(FACTORY_ID, phone,
                         f"DISPATCHED: {supplier_name} confirmed for PO #{po['po_number']}",
                         "supplier_dispatch_confirm")
        po_list = ", ".join(f"#{po['po_number']}" for po in supplier_pos)
        return (
            f"✅ *Dispatch confirmed!*\n\n"
            f"Thank you, *{supplier_name}*.\n"
            f"Recorded dispatch for: {po_list}\n\n"
            f"📦 Factory team has been notified.\n"
            f"Please share tracking details if available."
        )

    if msg_lower.startswith("delay"):
        parts = message.split()
        delay_days = parts[1] if len(parts) > 1 else "unspecified"
        for po in supplier_pos:
            log_incoming(FACTORY_ID, phone,
                         f"DELAY: {supplier_name} reported {delay_days} day delay for PO #{po['po_number']}",
                         "supplier_delay_report")
        return (
            f"⏳ *Delay noted.*\n\n"
            f"Thank you, *{supplier_name}*.\n"
            f"Delay of *{delay_days} days* has been recorded.\n\n"
            f"Please update us when goods are dispatched."
        )

    if msg_lower.startswith("eta"):
        parts = message.split(maxsplit=1)
        new_date = parts[1] if len(parts) > 1 else "not specified"
        for po in supplier_pos:
            log_incoming(FACTORY_ID, phone,
                         f"NEW ETA: {supplier_name} updated ETA to {new_date} for PO #{po['po_number']}",
                         "supplier_eta_update")
        return (
            f"📅 *New ETA recorded: {new_date}*\n\n"
            f"Thank you, *{supplier_name}*.\n"
            f"Reply *dispatched* when goods are shipped."
        )

    if msg_lower in ("issue", "problem", "hold"):
        log_incoming(FACTORY_ID, phone,
                     f"ISSUE REPORTED: {supplier_name} flagged a problem",
                     "supplier_issue")
        return (
            f"⚠️ *Issue flagged.*\n\n"
            f"Thank you, *{supplier_name}*.\n"
            f"Please describe the issue in your next message."
        )

    log_incoming(FACTORY_ID, phone,
                 f"MESSAGE FROM {supplier_name}: {message}",
                 "supplier_freetext")
    return (
        f"📩 *Message received!*\n\n"
        f"Thank you, *{supplier_name}*. Your message has been logged.\n\n"
        f"💬 *Quick commands:*\n"
        f"• *dispatched* — Confirm shipment\n"
        f"• *delay [days]* — Report delay\n"
        f"• *eta [date]* — Update delivery date\n"
        f"• *issue* — Report a problem"
    )


# ═══════════════════════════════════════════════════════════
#  META WEBHOOK — MAIN HANDLER
# ═══════════════════════════════════════════════════════════

@app.route("/webhook", methods=["POST"])
def whatsapp_webhook():
    """
    Meta sends incoming messages as JSON POST to /webhook.
    No TwiML — we just return HTTP 200 and send replies via the API.
    """
    body = request.get_json(silent=True) or {}
    sender_phone, incoming_msg = _parse_meta_message(body)

    if not sender_phone or not incoming_msg:
        return jsonify({"status": "ok"}), 200

    logger.info("📨 Incoming from %s: %s", sender_phone, incoming_msg)
    msg_lower = incoming_msg.lower().strip()

    # Normalise owner phone for comparison
    owner_digits = format_phone_for_whatsapp(OWNER_PHONE)
    sender_digits = format_phone_for_whatsapp(sender_phone)
    is_owner = (sender_digits == owner_digits) or (sender_phone == OWNER_PHONE)

    if is_owner:
        logger.info("👤 Owner message detected")
        log_incoming(FACTORY_ID, sender_phone, incoming_msg, "owner_command")

        if msg_lower == "9":
            reply = build_full_report()
        elif msg_lower in ("status", "quick", "overview"):
            reply = build_quick_status()
        elif msg_lower in ("overdue", "late"):
            reply = build_overdue_only()
        elif msg_lower == "today":
            reply = build_today_only()
        elif msg_lower in ("week", "upcoming"):
            reply = build_week_only()
        elif msg_lower == "logs":
            reply = build_logs_report()
        elif msg_lower == "run":
            try:
                from src.tasks.agent1_tasks import daily_supplier_followup
                daily_supplier_followup.delay()
                reply = (
                    "🚀 *Follow-up run triggered!*\n\n"
                    "Agent 1 is now scanning for overdue POs "
                    "and sending supplier messages.\n\n"
                    "You'll receive a summary shortly."
                )
            except Exception as e:
                reply = f"❌ Failed to trigger run: {str(e)}"
        elif msg_lower in ("help", "menu", "hi", "hello"):
            reply = build_owner_help()
        else:
            reply = (
                f"🤖 Got it: \"{incoming_msg}\"\n\n"
                f"I didn't recognize that command.\n"
                f"Reply *help* to see available commands."
            )
    else:
        logger.info("🏭 Supplier message from %s", sender_phone)
        supplier_pos = get_supplier_by_phone(FACTORY_ID, sender_phone)

        if msg_lower in ("hi", "hello", "hey", "status"):
            if supplier_pos:
                po = supplier_pos[0]
                reply = (
                    f"👋 Hello *{po['supplier_name']}*!\n\n"
                    f"You have {len(supplier_pos)} active PO(s).\n"
                    f"Reply *dispatched*, *delay [days]*, or *eta [date]*."
                )
            else:
                reply = "👋 Hello! Please reply with your PO status update."
        else:
            reply = handle_supplier_reply(sender_phone, incoming_msg, supplier_pos)

    # Send reply back via Meta API
    _send_reply(sender_phone, reply)

    # Meta requires HTTP 200 to acknowledge receipt
    return jsonify({"status": "ok"}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "agent": "axension-agent1",
        "transport": "meta-waba",
        "time": datetime.now().isoformat(),
    }), 200


# ═══════════════════════════════════════════════════════════
#  MAIN — start Flask + Cloudflare tunnel
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.environ.get("WEBHOOK_PORT", 5000))

    print(f"\n{'═' * 60}")
    print(f"  🤖 Axension AI — WhatsApp Webhook (Meta WABA)")
    print(f"  📡 Running on http://localhost:{port}")
    print(f"{'═' * 60}")
    print(f"\n  📋 NEXT STEPS:")
    print(f"  1. Expose this port to the internet:")
    print(f"     Option A (Cloudflare): cloudflared tunnel --url http://localhost:{port}")
    print(f"     Option B (ngrok):      ngrok http {port}")
    print(f"  2. Copy the public URL")
    print(f"  3. Set it in Meta Developer Console:")
    print(f"     App → WhatsApp → Configuration → Webhook URL")
    print(f"     Webhook URL: https://YOUR-URL/webhook")
    print(f"     Verify Token: {os.environ.get('WABA_VERIFY_TOKEN', 'axension_verify')}")
    print(f"  4. Subscribe to 'messages' webhook field")
    print(f"{'═' * 60}\n")

    app.run(host="0.0.0.0", port=port, debug=False)
