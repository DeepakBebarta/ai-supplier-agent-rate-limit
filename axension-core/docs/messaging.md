# `axension_core.messaging` — Shared WhatsApp Send Helper

> **Day 5, W1 close.** Owner: Deepak (D2).
> Karthik (Agent 2) and Siddhartha (Agent 3) — **import this. Do not reimplement `send_text()`.**

This module is the single entry point for every WhatsApp message that leaves
any Axension AI agent. It guarantees three things:

1. **Rate-limit hard cap** — no factory will ever receive more than
   `MAX_MSGS_PER_FACTORY_PER_DAY = 3` messages in a calendar day (IST).
2. **Template discipline** — every send uses a versioned Jinja2 template from
   `axension_core/messaging/templates/`. No ad-hoc string formatting.
3. **Audit trail** — every send (success / blocked / failed) lands in
   `factory_001.agent_logs` with `template_key`, `template_version`,
   `message_id`, and `status`.

---

## Install

In your agent repo's `requirements-dev.txt`:

```
-e ../axension-core
```

Then:

```bash
pip install -r requirements-dev.txt
```

---

## The one function

```python
from axension_core.messaging import send_agent_message

result = send_agent_message(
    factory_id="factory_001",
    to_phone="918121444200",            # E.164 without '+'
    template_key="agent1_followup",     # must start with agent1_, agent2_ or agent3_
    template_version="v1",
    params={                            # vars used by the template
        "supplier_name": "Ravi Steel Traders",
        "po_number":     "PUR-ORD-2026-00011",
        "item_name":     "HR Sheet 2mm",
        "promised_date": "15-Mar-2026",
        "days_overdue":  31,
    },
)

# result == {
#   "status":     "sent",
#   "message_id": "wamid.HBgM...",
#   "logged_id":  "8e3b2f..."
# }
```

### Return values

| status      | meaning                                              | when           |
| ----------- | ---------------------------------------------------- | -------------- |
| `"sent"`    | WABA accepted the send                               | normal path    |
| `"blocked"` | factory hit the 3-msg/day cap                        | rate limiter   |
| `"failed"`  | template missing, render error, or WABA send failure | error path     |

When `status != "sent"`, the response also has a `"reason"` field.

---

## Examples — one per agent

### Agent 1 (Deepak) — supplier follow-up

```python
from axension_core.messaging import send_agent_message

send_agent_message(
    factory_id="factory_001",
    to_phone=po["supplier_phone"],
    template_key="agent1_followup",
    template_version="v1",
    params={
        "supplier_name": po["supplier_name"],
        "po_number":     po["po_number"],
        "item_name":     po["item_name"],
        "promised_date": po["promised_date"].strftime("%d-%b-%Y"),
        "days_overdue":  po["days_overdue"],
    },
)
```

### Agent 2 (Karthik) — stock alert

```python
from axension_core.messaging import send_agent_message

send_agent_message(
    factory_id="factory_001",
    to_phone=OWNER_PHONE,
    template_key="agent2_stock_alert",
    template_version="v1",
    params={
        "severity":           "critical",
        "item_name":          "HR Sheet 2mm",
        "current_qty":        45,
        "unit":               "Kg",
        "critical_threshold": 100,
        "warning_threshold":  250,
        "last_consumed_date": "16-Apr-2026",
        "avg_daily":          22,
    },
)
```

### Agent 3 (Siddhartha) — invoice mismatch

```python
from axension_core.messaging import send_agent_message

send_agent_message(
    factory_id="factory_001",
    to_phone=OWNER_PHONE,
    template_key="agent3_mismatch_alert",
    template_version="v1",
    params={
        "po_number":       "PUR-ORD-2026-00011",
        "invoice_number":  "INV-A-2204",
        "supplier_name":   "Ravi Steel Traders",
        "po_amount":       "1,25,000",
        "invoice_amount":  "1,38,500",
        "variance":        "13,500",
        "variance_pct":    "10.8",
        "line_items_diff": [
            {"item": "HR Sheet 2mm", "po_qty": 500, "inv_qty": 540},
        ],
    },
)
```

---

## Rate limiter — the hard cap

```python
from axension_core.messaging import (
    MAX_MSGS_PER_FACTORY_PER_DAY,   # = 3
    RateLimitExceeded,
)
```

The cap **lives in code** (`rate_limiter.py`, module-level constant). It is
**not** in `.env`. It is **not** in `config/settings.py`. Changing it
requires a code change + PR review — that is the whole point.

You don't need to call `check_and_record()` yourself if you go through
`send_agent_message()`. The helper does it. You also don't need to handle
`RateLimitExceeded` — `send_agent_message()` returns
`{"status": "blocked", ...}` and never raises.

---

## Adding a new template

1. Drop a `.j2` file into `axension_core/messaging/templates/`.
2. Name it `{agent_prefix}_{purpose}_{version}.j2`
   (e.g. `agent2_reorder_suggest_v1.j2`).
3. Get Sakeena to approve in `#tl-template-review`.
4. Add it to `approved-templates.md`.
5. Bump version (`v2`, `v3`, ...) — never edit a shipped template in place.

---

## DRY_RUN mode

While `DRY_RUN=true` in the environment (the W1 default), the helper does
**not** call WABA. It returns a fake `message_id` like
`wamid.DRYRUN_<hex>` and still writes the `agent_logs` row with
`status="sent"`. Day 6 flips `DRY_RUN=false` for the first real factory.

---

## What NOT to do

❌ `import requests; requests.post("https://graph.facebook.com/...", ...)`
❌ `from twilio.rest import Client; Client(...).messages.create(...)`
❌ Inline f-string message bodies
❌ Reading the cap from `os.environ`

✅ `from axension_core.messaging import send_agent_message`

---

## Questions

Slack `#dev-agents` — Deepak.
