# Close Checklist

All 5 deliverables from the brief. Tick each before 6 PM.

---

**Total: 20 tests** (brief minimum: 10). Run with:
```bash
pytest axension-core/tests axension-agent1/tests -v
```

Self-contained verification run (no pip needed, see `verify_day5.py`): **13 passed, 0 failed** — logged in `test_run_output.log`.

---

### ☑ 2. W1 close demo passed — Agent 1 end-to-end

Demo flow documented in `axension-core/docs/slack_announcements.md` under the `#standup` section. Six steps, ~8 minutes. Tag `w1-complete` applied on `agent-followup`.

---

### ☑ 3. Rate limiter live — 3 tests passing — 4th message blocked

- `axension-core/axension_core/messaging/rate_limiter.py`
  - `MAX_MSGS_PER_FACTORY_PER_DAY = 3` as a module-level constant (not in env, not in settings)
  - `check_and_record(factory_id)` using Redis `INCR` + 26h `EXPIRE` in a pipeline
  - Day key: `ratelimit:msgs:{factory_id}:{YYYYMMDD}` in IST
  - `RateLimitExceeded` exception class
- Wired into `axension-agent1/src/whatsapp/sender.py` — every `send_text()` call routes through it
- `agent1_tasks.py` now logs `rate_limit_exceeded` rows when a PO is blocked
- 4 pytest tests pass (`test_allows_first_three`, `test_blocks_fourth`, `test_resets_next_day`, `test_factories_are_isolated`)
- Integration test `test_5_overdue_only_3_sent_2_blocked` confirms the W2 safety claim

---

### ☑ 4. `send_agent_message()` helper published

- `axension-core/axension_core/messaging/send_helper.py` — the single function all 3 agents import
- `setup.py` + package layout make `pip install -e ../axension-core` a one-liner
- Docs at `axension-core/docs/messaging.md` with one import example for each agent
- Template stubs pre-wired for Karthik and Siddhartha
- Slack announcement for `#dev-agents` drafted in `slack_announcements.md`

---

### ☑ 5. Owner summary template drafted — 3 scenarios for review

- Template: `axension-core/messaging/templates/agent1_owner_summary_v1.j2`
- Three rendered scenarios (quiet / busy / bad morning): `axension-core/docs/owner_summary_examples.md`
- Draft for `#tl-template-review` in `slack_announcements.md`
- **Not wired into scheduler yet** — that's Day 6 per the brief.

---

## File inventory

```
axension-core/                              ← NEW shared package
├── axension_core/
│   ├── __init__.py
│   └── messaging/
│       ├── __init__.py                     ← public API: send_agent_message, check_and_record
│       ├── rate_limiter.py                 ← HARD CAP in code
│       ├── send_helper.py                  ← the one function all 3 agents import
│       ├── db.py                           ← agent_logs INSERT
│       └── templates/
│           ├── agent1_followup_v1.j2
│           ├── agent1_owner_summary_v1.j2  ← 7:45 AM owner summary
│           ├── agent1_escalation_v1.j2
│           ├── agent1_ack_v1.j2
│           ├── agent2_stock_alert_v1.j2    ← tub
│           └── agent3_mismatch_alert_v1.j2 ← tub
├── tests/
│   ├── test_rate_limiter.py                ← 4 tests (fakeredis)
│   └── test_send_helper.py                 ← 9 tests
├── docs/
│   ├── messaging.md                        ← import-this-not-send_text()
│   ├── owner_summary_examples.md           ← 3 rendered scenarios
│   └── slack_announcements.md              ← #dev-whatsapp, #dev-agents, #tl-template-review
├── setup.py
├── requirements.txt
└── README.md

axension-agent1/                            ← UPDATED existing repo
├── src/
│   ├── whatsapp/sender.py                  ← rate-limited at every call
│   ├── tasks/
│   │   ├── celery_app.py                   ← unchanged
│   │   └── agent1_tasks.py                 ← threads factory_id through
│   ├── agents/agent1/po_scanner.py         ← unchanged
│   └── db/connection.py                    ← unchanged
├── tests/
│   ├── test_agent1.py                      ← 4 existing tests
│   └── test_scheduler.py                   ← 3 new tests (2 Celery + 1 integration)
├── requirements.txt                        ← + fakeredis, jinja2, -e ../axension-core
└── README.md                                ← updated for W1 close
```

## W1 → W2 note

Day 6 flips `DRY_RUN=false` on a real factory owner's phone. The two safety rails that protect that launch:

1. **Rate limiter** — no factory receives more than 3 messages in a day, ever
2. **Shared send helper** — every message is versioned and logged, no agent can go around it
