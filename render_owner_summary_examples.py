"""
render_owner_summary_examples.py — Task 5 deliverable.

Renders the agent1_owner_summary_v1.j2 template in 3 realistic scenarios
for Sakeena's review in #tl-template-review.

Scenarios:
  (a) Quiet morning  — 2 followed up, all replied
  (b) Busy morning   — 8 followed up, 5 replied, 3 no-reply, 1 critical stock alert
  (c) Bad morning    — 12 followed up, 2 replied, 10 silent, 3 critical escalations
"""
import os, sys, types
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "axension-core"))

# Shim redis + requests so the module imports without those deps
sys.modules.setdefault("redis", types.SimpleNamespace(
    from_url=lambda *a, **k: None, Redis=object,
))
_exc = types.ModuleType("requests.exceptions")
_exc.HTTPError = Exception
_exc.RequestException = Exception
sys.modules.setdefault("requests", types.SimpleNamespace(
    post=lambda *a, **k: None, exceptions=_exc,
))
sys.modules.setdefault("requests.exceptions", _exc)

from axension_core.messaging.send_helper import _render_template

SCENARIOS = {
    "A — Quiet morning": {
        "date_str": "17-Apr-2026",
        "followed_up": 2,
        "replied": 2,
        "no_reply": 0,
        "escalations": [],
        "stock_summary": None,
    },
    "B — Busy morning": {
        "date_str": "17-Apr-2026",
        "followed_up": 8,
        "replied": 5,
        "no_reply": 3,
        "escalations": [],
        "stock_summary": {"critical": 1, "warning": 2},
    },
    "C — Bad morning": {
        "date_str": "17-Apr-2026",
        "followed_up": 12,
        "replied": 2,
        "no_reply": 10,
        "escalations": [
            {"supplier_name": "Ravi Steel Traders",
             "po_number": "PUR-ORD-2026-00011", "days_overdue": 14},
            {"supplier_name": "Sangam Polymers",
             "po_number": "PUR-ORD-2026-00018", "days_overdue": 9},
            {"supplier_name": "Krishna Industries",
             "po_number": "PUR-ORD-2026-00022", "days_overdue": 6},
        ],
        "stock_summary": {"critical": 3, "warning": 5},
    },
}

out = []
out.append("# Agent 1 — Owner Summary Template (v1) — Rendered Scenarios")
out.append("")
out.append("Drafted Day 5 by Deepak. Posted to `#tl-template-review` for "
           "Sakeena's approval before wiring into the scheduler on Day 6.")
out.append("")
out.append(f"Template file: `axension-core/messaging/templates/agent1_owner_summary_v1.j2`")
out.append("")
out.append("---")

for label, params in SCENARIOS.items():
    rendered = _render_template("agent1_owner_summary", "v1", params)
    out.append(f"\n## Scenario {label}\n")
    out.append("**Inputs:**")
    out.append("```python")
    for k, v in params.items():
        out.append(f"{k} = {v!r}")
    out.append("```")
    out.append("\n**Rendered WhatsApp body:**\n")
    out.append("```")
    out.append(rendered)
    out.append("```")
    out.append("")

out.append("---")
out.append("")
out.append("**Review checklist for Sakeena:**")
out.append("- [ ] Tone is appropriate for a factory owner's first WhatsApp of the day")
out.append("- [ ] Quiet morning (A) isn't noisy when there's nothing to report")
out.append("- [ ] Busy morning (B) shows stock alerts cleanly when available")
out.append("- [ ] Bad morning (C) escalations list doesn't overwhelm the owner")
out.append("- [ ] Approve → Deepak commits v1 and adds to `approved-templates.md`")

content = "\n".join(out)
dst = os.path.join(ROOT, "axension-core/docs/owner_summary_examples.md")
with open(dst, "w") as f:
    f.write(content)

print(content)
print(f"\n→ Written to: {dst}")
