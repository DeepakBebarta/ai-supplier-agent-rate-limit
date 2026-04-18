# Axension AI — Week 1 Close (Day 5)
### Agent 1: WhatsApp Supplier Follow-Up — D2 Deepak

**Transport: Meta WhatsApp Cloud API (WABA) — Twilio removed in W2.**

---

## What Was Built (W1 → W2 Summary)

| Before (W1) | After (W2) |
|---|---|
| Twilio REST API | Meta Graph API |
| `twilio` Python package | `requests` + Meta WABA |
| 50 message/day sandbox limit | 1000 conversations/month free |
| `whatsapp:+14155238886` from number | Your own WABA phone number |
| `TwiML` response format | JSON POST to Meta API |
| `twilio.twiml.messaging_response` | Plain Flask JSON responses |
| No rate limiter | Hard cap: 3 messages/factory/day in code |
| No shared helper | `send_agent_message()` shared across all 3 agents |

---

## Day 5 Deliverables — All 5 Complete ✅

### ✅ 1. All Tests Green — 20 Tests Passing

| Test File | Tests | What It Covers |
|---|---|---|
| `axension-core/tests/test_rate_limiter.py` | 4 | allows first 3, blocks 4th, resets next day, factory isolation |
| `axension-core/tests/test_send_helper.py` | 9 | template rendering, happy path, rate block, dry run, edge cases |
| `axension-agent1/tests/test_scheduler.py` | 3 | Celery beat wiring, task registration, 5→3 sent/2 blocked integration |
| `axension-agent1/tests/test_agent1.py` | 4 | overdue sort, days_overdue int, hard cap, template fields |

**Total: 20 tests. Minimum required: 10.**

### ✅ 2. W1 Close Demo — Full Agent 1 Flow

Demonstrated live:
1. Celery beat log → `daily_supplier_followup` registered and scheduled at 8 AM IST
2. Task manually triggered → fetched overdue POs from Supabase, sent messages
3. WhatsApp delivered on owner's phone within 30 seconds
4. `factory_001.agent_logs` rows confirmed with `template_version`, `supplier_phone`, `status="sent"`
5. Rate limiter blocked 4th message → logged `rate_limit_exceeded`
6. All 20 pytest tests green

### ✅ 3. Rate Limiter — Hard Cap in Code

- `MAX_MSGS_PER_FACTORY_PER_DAY = 3` — module-level constant, not in `.env`, not configurable without a PR
- `check_and_record(factory_id)` — Redis `INCR` + 26h `EXPIRE` pipeline
- Day key: `ratelimit:msgs:{factory_id}:{YYYYMMDD}` in IST
- 4th message → blocked, logged as `rate_limit_exceeded`, nothing sent to WhatsApp

### ✅ 4. `send_agent_message()` Shared Helper Published

- Lives in `axension-core/axension_core/messaging/send_helper.py`
- All 3 agents import from here — nobody calls WABA directly
- Handles: rate limit check → template render → WABA send → agent_logs INSERT → return `{status, message_id, logged_id}`
- Install: `pip install -e ../axension-core`

### ✅ 5. Owner Summary Template Drafted

- `axension-core/axension_core/messaging/templates/agent1_owner_summary_v1.j2`
- 3 scenarios rendered (quiet / busy / bad morning) — posted in `#tl-template-review`
- Not wired into scheduler yet — Day 6 task

---

## Repository Structure

```
axension-week2/
├── axension-core/                          ← Shared package (new in W2)
│   ├── axension_core/
│   │   ├── __init__.py
│   │   └── messaging/
│   │       ├── __init__.py                 ← Public API: send_agent_message, check_and_record
│   │       ├── rate_limiter.py             ← HARD CAP = 3, in code not config
│   │       ├── send_helper.py              ← Single function all 3 agents import
│   │       ├── db.py                       ← agent_logs INSERT
│   │       └── templates/
│   │           ├── agent1_followup_v1.j2
│   │           ├── agent1_owner_summary_v1.j2
│   │           ├── agent1_escalation_v1.j2
│   │           ├── agent1_ack_v1.j2
│   │           ├── agent2_stock_alert_v1.j2    ← Karthik's stub
│   │           └── agent3_mismatch_alert_v1.j2 ← Siddhartha's stub
│   ├── tests/
│   │   ├── test_rate_limiter.py            ← 4 tests (fakeredis)
│   │   └── test_send_helper.py             ← 9 tests
│   ├── setup.py
│   └── README.md
│
└── axension-agent1/                        ← Agent 1 repo (updated in W2)
    ├── src/
    │   ├── whatsapp/
    │   │   ├── sender.py                   ← Rate-limited at every call
    │   │   └── webhook.py                  ← Flask — receives WhatsApp messages
    │   ├── tasks/
    │   │   ├── celery_app.py               ← Beat schedule: 8 AM IST daily
    │   │   └── agent1_tasks.py             ← daily_supplier_followup task
    │   ├── agents/agent1/
    │   │   └── po_scanner.py               ← Fetches overdue POs from Supabase
    │   └── db/connection.py
    ├── tests/
    │   ├── test_agent1.py                  ← 4 tests
    │   └── test_scheduler.py               ← 3 tests
    ├── config/settings.py
    ├── requirements.txt
    └── .env.example
```

---

## Setup — Step by Step

### Prerequisites
- Python 3.11+
- Docker (for Redis)
- A Meta WhatsApp Business Account with API access
- Supabase project with `purchase_orders` and `agent_logs` tables

---

### Step 1 — Install dependencies

```bash
cd axension-week2

# Install shared core package (editable)
pip install -e axension-core

# Install agent1 dependencies
cd axension-agent1
pip install -r requirements.txt
```

---

### Step 2 — Set up `.env`

```bash
cd axension-agent1
cp .env.example .env
```

Open `.env` and fill in:

```env
DB_URL=postgresql://...            # Supabase connection string
REDIS_URL=redis://localhost:6379/0
WABA_TOKEN=your_meta_access_token
WABA_PHONE_ID=your_phone_number_id
WABA_VERIFY_TOKEN=axension_verify
OWNER_PHONE=919876543210           # E.164 without +
FACTORY_ID=factory_001
DRY_RUN=true                       # Set to false for real sends
```

Verify it loaded correctly:
```bash
python -c "from config.settings import FACTORY_ID, OWNER_PHONE; print(FACTORY_ID, OWNER_PHONE)"
```

---

### Step 3 — Start Redis

```bash
docker run -d --name redis -p 6379:6379 redis:alpine
redis-cli ping   # → PONG
```

---

### Step 4 — Run all tests

```bash
# From axension-week2/ root
cd axension-core
python -m pytest tests -v               # 13 tests

cd ../axension-agent1
python -m pytest tests -v --import-mode=importlib   # 7 tests
```

Expected: **20 passed, 0 failed, 0 skipped.**

---

### Step 5 — Start the stack (3 terminals)

**Terminal 1 — Celery worker:**
```bash
cd axension-agent1
celery -A src.tasks.celery_app worker --loglevel=info --pool=solo
```

**Terminal 2 — Flask webhook:**
```bash
cd axension-agent1
python -m src.whatsapp.webhook
```

**Terminal 3 — Expose to internet (use cloudflared — ngrok has interstitial issues with Meta):**
```bash
cloudflared tunnel --url http://localhost:5000
```

> ⚠️ **Why cloudflared over ngrok?** Free ngrok accounts show an interstitial browser warning page (`ERR_NGROK_6024`) that blocks Meta's webhook verification. Cloudflared (`trycloudflare.com`) has no interstitial and works with Meta out of the box.

---

### Step 6 — Configure Meta Webhook (one-time)

1. Go to [developers.facebook.com](https://developers.facebook.com) → Your App → WhatsApp → Configuration
2. **Callback URL**: `https://YOUR-CLOUDFLARE-URL/webhook`
3. **Verify Token**: value of `WABA_VERIFY_TOKEN` in your `.env` (default: `axension_verify`)
4. Click **Verify and Save** → you should see a green tick
5. Subscribe to the **messages** webhook field

Verify the webhook is reachable:
```powershell
# Windows PowerShell
Invoke-WebRequest "https://YOUR-CLOUDFLARE-URL/webhook?hub.mode=subscribe&hub.verify_token=axension_verify&hub.challenge=test123" -UseBasicParsing
# Should return: test123
```

---

### Step 7 — Get your Meta WABA Credentials

1. Go to [developers.facebook.com](https://developers.facebook.com)
2. Create an App → Add **WhatsApp** product
3. WhatsApp → API Setup
4. Copy **Temporary access token** → `WABA_TOKEN` in `.env`
5. Copy **Phone number ID** → `WABA_PHONE_ID` in `.env`
6. To test: enter your phone number in the "Send and receive messages" panel and click Send

---

## Go Live — Flip to Production

Once everything is verified with `DRY_RUN=true`, flip to real sends:

1. Open `axension-agent1/.env`
2. Change `DRY_RUN=false`
3. Restart Flask: `python -m src.whatsapp.webhook`

Logs will now show:
```
INFO Sent via WABA to=91XXXXXXXXXX msg_id=wamid.XXXXX
```
instead of `DRY_RUN send`.

---

## Owner WhatsApp Commands

Send these to your WABA number from the owner's phone:

| Command | Response |
|---|---|
| `help` | Full command menu |
| `9` | Full PO report (overdue + today + this week) |
| `status` | Quick counts overview |
| `overdue` | Only overdue POs |
| `today` | POs due today |
| `week` | POs due this week |
| `logs` | Recent agent activity |
| `run` | Manually trigger Agent 1 now |

---

## Rate Limiter

The hard cap of **3 messages per factory per day** is enforced in code — not in `.env`, not configurable without a PR.

```python
# axension-core/axension_core/messaging/rate_limiter.py
MAX_MSGS_PER_FACTORY_PER_DAY = 3  # ← lives here, not in env
```

If you hit the cap during testing, reset it:

```bash
# Windows PowerShell
cd axension-agent1
python -c "
from dotenv import load_dotenv
load_dotenv()
from axension_core.messaging import reset_factory_today
reset_factory_today('factory_001')
print('Rate limit reset')
"
```

> ⚠️ The rate limiter applies to **all** outgoing messages including owner command replies. Reset before testing if you've already sent 3+ messages today.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DB_URL` | ✅ | Supabase PostgreSQL connection string |
| `REDIS_URL` | ✅ | Redis for Celery + rate limiter |
| `WABA_TOKEN` | ✅ | Meta access token |
| `WABA_PHONE_ID` | ✅ | Meta phone number ID |
| `WABA_VERIFY_TOKEN` | ✅ | Webhook verification token |
| `OWNER_PHONE` | ✅ | Owner's WhatsApp number (E.164 without `+`) |
| `FACTORY_ID` | ✅ | e.g. `factory_001` |
| `DRY_RUN` | ✅ | `true` = simulate only, `false` = real sends |
| `WABA_VERSION` | optional | Meta API version (default: `v19.0`) |
| `MAX_MESSAGES_PER_RUN` | optional | Per-run PO cap (default: 3) |
| `AGENT1_INTERVAL_MINUTES` | optional | Dev: override beat schedule to N minutes |

**Note:** `MAX_MSGS_PER_FACTORY_PER_DAY = 3` lives in code, not in `.env`.

---

## Shared Helper — For Karthik (Agent 2) and Siddhartha (Agent 3)

Do not reimplement `send_text()`. Import from `axension-core`:

```python
from axension_core.messaging import send_agent_message

result = send_agent_message(
    factory_id="factory_001",
    to_phone="919876543210",       # E.164 without +
    template_key="agent2_stock_alert",
    template_version="v1",
    params={"item_name": "HR Sheet", "stock_qty": 5},
)
# result = {"status": "sent"|"blocked"|"failed", "message_id": ..., "logged_id": ...}
```

Install in your agent repo:
```bash
pip install -e ../axension-core
```

Every message sent through `send_agent_message()` is automatically:
- Rate-limited (3/factory/day)
- Templated + versioned
- Logged to `agent_logs`

---

## W1 → W2 Safety Rails

W2 (Day 6) flips `DRY_RUN=false` on a real factory owner's phone. Two things prevent that going wrong:

1. **Rate limiter** — no factory ever receives more than 3 messages in a day, no matter what
2. **Shared send helper** — every message is versioned and logged, no agent can bypass it

---

## Known Issues & Fixes

### ngrok interstitial blocks Meta webhook verification
**Problem:** Free ngrok accounts show a browser warning page (`ERR_NGROK_6024`) that Meta's servers can't pass through.  
**Fix:** Use cloudflared instead — `cloudflared tunnel --url http://localhost:5000`

### Rate limit hit during testing — `logs` command not replying
**Problem:** Owner command replies count against the 3/day cap.  
**Fix:** Run the reset script above before testing interactive commands.

### `DRY_RUN=true` — messages not actually delivered
**Problem:** Flask logs show `DRY_RUN send` but nothing arrives on WhatsApp.  
**Fix:** Set `DRY_RUN=false` in `.env` and restart Flask.

### `timedelta` crash in `po_scanner.py`
**Problem:** psycopg2 sometimes returns a `timedelta` for computed `days_overdue` column instead of `int`.  
**Fix:** Applied in `po_scanner.py` — handles both `timedelta.days` and `int()` gracefully.

### W1 tests failing after W2 migration
**Problem:** `test_scheduler.py` and `test_agent1.py` were patching `send_text` (W1) instead of `send_agent_message` (W2).  
**Fix:** Both test files updated — patch targets, call signatures, and return shapes corrected to W2 API.

---

*Axension AI · MVP Sprint · Day 5 — Week 1 Close · D2 — Deepak · Confidential*
