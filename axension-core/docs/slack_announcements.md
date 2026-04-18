# Day 5 Slack Announcements — Deepak

Ready to post once the PR merges.

---

## `#dev-whatsapp` — Task 3 announcement

> 🛡️ **Rate limiter live.** `axension_core.messaging.rate_limiter.check_and_record()` is merged.
>
> - Hard cap: **3 messages per factory per IST day**
> - Constant lives in code (`MAX_MSGS_PER_FACTORY_PER_DAY = 3`), **not in `.env`**. Changing it needs a code change + PR review.
> - Every `send_text()` call now routes through this. If the cap is hit, the call returns `{success: False, error: "rate_limit_exceeded"}` and the Twilio API is never touched.
> - 3 unit tests pass (fakeredis) + integration test confirms 4th message is blocked when 5 overdue POs are queued.
>
> Karthik and Siddhartha — your shared helper (task 4) already wires this. You should never need to call `check_and_record` yourself.

---

## `#dev-agents` — Task 4 announcement

> 📬 **`send_agent_message()` is live in `axension-core/messaging`.** Import it from your agent code. **Do not reimplement `send_text()`.**
>
> ```python
> from axension_core.messaging import send_agent_message
>
> send_agent_message(
>     factory_id="factory_001",
>     to_phone="918121444200",
>     template_key="agent2_stock_alert",   # or agent3_mismatch_alert
>     template_version="v1",
>     params={...},
> )
> ```
>
> The function handles rate limiting, template versioning, Jinja2 rendering, WABA send, and the `agent_logs` insert. It returns `{"status": "sent"|"blocked"|"failed", "message_id": ..., "logged_id": ...}`.
>
> Install it: `pip install -e ../axension-core` in your agent repo's `requirements-dev.txt`.
>
> Template stubs for you are already in `axension-core/messaging/templates/`:
> - `agent2_stock_alert_v1.j2` (Karthik)
> - `agent3_mismatch_alert_v1.j2` (Siddhartha)
>
> Tweak the template contents to suit your agent, bump the version if you change the body structurally, and message me if you need a new template category.
>
> Full docs: `axension-core/docs/messaging.md`.

---

## `#tl-template-review` — Task 5 post

> 📝 **Draft: Agent 1 owner 7:45 AM summary (v1)** — for your review, @Sakeena, before Day 6 wires it in.
>
> Rendered 3 scenarios so you can see the range:
> - **A — Quiet morning:** 2 followed up, all replied, no stock alerts
> - **B — Busy morning:** 8 followed up, 5 replied, 1 critical stock alert
> - **C — Bad morning:** 12 followed up, 10 silent, 3 escalations, 3 critical stock
>
> See `axension-core/docs/owner_summary_examples.md` for the three rendered messages side-by-side.
>
> Once approved I'll commit `agent1_owner_summary_v1.j2` to `axension-core` and add it to `approved-templates.md`.

---

## `#standup` — 9:30 AM demo agenda

> **Day 5 / W1 close demo — Agent 1 end-to-end (≈ 8 min)**
>
> 1. Celery beat log → `daily_supplier_followup` registered for 8 AM IST
> 2. Manual trigger → "Fetched N overdue POs, drafted messages, sending…"
> 3. WhatsApp delivered on my phone in <30s
> 4. Supabase `factory_001.agent_logs` → 3 new rows with `template_version`, `status=sent`
> 5. 4th message attempt → `status=rate_limit_exceeded`, no WhatsApp sent
> 6. `pytest -v` → 13+ tests green
>
> Asking for sign-off to tag `w1-complete` and merge the PR.
