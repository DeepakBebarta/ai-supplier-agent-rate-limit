# WhatsApp Supplier Follow-Up

**Transport: Meta WhatsApp Cloud API .**

---

## What changed from W1

Twilio has been completely removed. All WhatsApp messages now go through
Meta WhatsApp Cloud API directly via `send_agent_message()` from `axension-core`.

| Before (W1) | After (W2) |
|---|---|
| Twilio REST API | Meta Graph API |
| `twilio` Python package | `requests` + Meta WABA |
| 50 message/day sandbox limit | 1000 conversations/month free |
| `whatsapp:+14155238886` from number | Your own WABA phone number |
| `TwiML` response format | JSON POST to Meta API |
| `twilio.twiml.messaging_response` | Plain Flask JSON responses |

---

## Quick start

### 1. Install dependencies

```bash
pip install -e ../axension-core
pip install -r requirements.txt
```

### 2. Set up `.env`

```bash
cp .env.example .env
# Fill in: DB_URL, REDIS_URL, WABA_TOKEN, WABA_PHONE_ID, OWNER_PHONE
```

### 3. Start Redis

```bash
docker run -d --name redis -p 6379:6379 redis:alpine
redis-cli ping   # → PONG
```

### 4. Run tests

```bash
pytest ../axension-core/tests -v
pytest tests/ -v
```

### 5. Start the stack (3 terminals)

```bash
# Terminal 1 — Celery worker
celery -A src.tasks.celery_app worker --loglevel=info --pool=solo

# Terminal 2 — Flask webhook + tunnel
python -m src.whatsapp.webhook

# Terminal 3 — expose to internet
cloudflared tunnel --url http://localhost:5000
# OR
ngrok http 5000
```

### 6. Configure Meta webhook (one-time)

1. Go to https://developers.facebook.com → Your App → WhatsApp → Configuration
2. Set **Callback URL**: `https://YOUR-TUNNEL-URL/webhook`
3. Set **Verify Token**: `axension_verify` (or whatever is in your `.env`)
4. Click **Verify and Save**
5. Subscribe to the **messages** field

---

## How to get your Meta WABA credentials

1. Go to https://developers.facebook.com
2. Create an App → Add **WhatsApp** product
3. WhatsApp → API Setup
4. Copy **Temporary access token** → `WABA_TOKEN` in `.env`
5. Copy **Phone number ID** → `WABA_PHONE_ID` in `.env`
6. To test: enter your phone number in the "Send and receive messages" panel, click Send — you'll receive a test message immediately

---

## Owner WhatsApp commands

Send these to your WABA number from the owner's phone:

| Command | Response |
|---|---|
| `9` | Full PO report (overdue + today + this week) |
| `status` | Quick counts |
| `overdue` | Only overdue POs |
| `today` | POs due today |
| `week` | POs due this week |
| `logs` | Recent agent activity |
| `run` | Manually trigger Agent 1 |
| `help` | This menu |

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DB_URL` | ✅ | Supabase PostgreSQL connection string |
| `REDIS_URL` | ✅ | Redis for Celery + rate limiter |
| `WABA_TOKEN` | ✅ | Meta access token |
| `WABA_PHONE_ID` | ✅ | Meta phone number ID |
| `WABA_VERIFY_TOKEN` | ✅ | Webhook verification token |
| `OWNER_PHONE` | ✅ | Owner's WhatsApp number (E.164 no '+') |
| `FACTORY_ID` | ✅ | e.g. `factory_001` |
| `DRY_RUN` | ✅ | `true` = no real sends, `false` = production |
| `WABA_VERSION` | optional | Meta API version (default: `v19.0`) |
| `MAX_MESSAGES_PER_RUN` | optional | Per-run PO cap (default: 3) |
| `AGENT1_INTERVAL_MINUTES` | optional | Dev: override beat schedule to N minutes |

**Note:** `MAX_MSGS_PER_FACTORY_PER_DAY = 3` (the hard daily cap) lives in code, not in `.env`.
