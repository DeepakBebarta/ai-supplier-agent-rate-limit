# Agent 1 — Owner Summary Template (v1) — Rendered Scenarios

Drafted Day 5 by Deepak. Posted to `#tl-template-review` for Sakeena's approval before wiring into the scheduler on Day 6.

Template file: `axension-core/messaging/templates/agent1_owner_summary_v1.j2`

---

## Scenario A — Quiet morning

**Inputs:**
```python
date_str = '17-Apr-2026'
followed_up = 2
replied = 2
no_reply = 0
escalations = []
stock_summary = None
```

**Rendered WhatsApp body:**

```
🌅 *Good morning. Axension AI — 17-Apr-2026*

Yesterday's supplier follow-ups: *2*
   ✅ Replied: 2
   ⏳ No reply: 0

Reply *9* for full PO report.
```


## Scenario B — Busy morning

**Inputs:**
```python
date_str = '17-Apr-2026'
followed_up = 8
replied = 5
no_reply = 3
escalations = []
stock_summary = {'critical': 1, 'warning': 2}
```

**Rendered WhatsApp body:**

```
🌅 *Good morning. Axension AI — 17-Apr-2026*

Yesterday's supplier follow-ups: *8*
   ✅ Replied: 5
   ⏳ No reply: 3

📦 Stock alerts today: *1 critical*, 2 warning

Reply *9* for full PO report.
```


## Scenario C — Bad morning

**Inputs:**
```python
date_str = '17-Apr-2026'
followed_up = 12
replied = 2
no_reply = 10
escalations = [{'supplier_name': 'Ravi Steel Traders', 'po_number': 'PUR-ORD-2026-00011', 'days_overdue': 14}, {'supplier_name': 'Sangam Polymers', 'po_number': 'PUR-ORD-2026-00018', 'days_overdue': 9}, {'supplier_name': 'Krishna Industries', 'po_number': 'PUR-ORD-2026-00022', 'days_overdue': 6}]
stock_summary = {'critical': 3, 'warning': 5}
```

**Rendered WhatsApp body:**

```
🌅 *Good morning. Axension AI — 17-Apr-2026*

Yesterday's supplier follow-ups: *12*
   ✅ Replied: 2
   ⏳ No reply: 10

🚨 *Escalations (5+ days overdue):*
   • Ravi Steel Traders — PO #PUR-ORD-2026-00011 (14d)
   • Sangam Polymers — PO #PUR-ORD-2026-00018 (9d)
   • Krishna Industries — PO #PUR-ORD-2026-00022 (6d)

📦 Stock alerts today: *3 critical*, 5 warning

Reply *9* for full PO report.
```

---

**Review checklist for Sakeena:**
- [ ] Tone is appropriate for a factory owner's first WhatsApp of the day
- [ ] Quiet morning (A) isn't noisy when there's nothing to report
- [ ] Busy morning (B) shows stock alerts cleanly when available
- [ ] Bad morning (C) escalations list doesn't overwhelm the owner
- [ ] Approve → Deepak commits v1 and adds to `approved-templates.md`