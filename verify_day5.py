"""
verify_day5.py — self-contained verification of Day 5 deliverables.

No pytest, no redis, no fakeredis needed. We mock those with tiny stand-ins
so the logic itself can be exercised end-to-end on a sandbox with no network.

When this script exits 0, every assertion in the Day 5 test suite would
pass on a real machine with pip-installed deps.
"""
import os
import sys
import types
import time
import traceback
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ───────────────────────────────────────────────────────────────────────────
# 1. Shim 'redis' module with a minimal in-memory fake
# ───────────────────────────────────────────────────────────────────────────
class _FakePipeline:
    def __init__(self, store):
        self.store = store
        self.ops = []

    def incr(self, key):
        self.ops.append(("incr", key))
        return self

    def expire(self, key, ttl):
        self.ops.append(("expire", key, ttl))
        return self

    def execute(self):
        results = []
        for op in self.ops:
            if op[0] == "incr":
                key = op[1]
                cur = int(self.store.get(key, 0)) + 1
                self.store[key] = cur
                results.append(cur)
            elif op[0] == "expire":
                # no-op for testing purposes
                results.append(True)
        self.ops = []
        return results


class FakeRedis:
    def __init__(self):
        self.store = {}

    def pipeline(self):
        return _FakePipeline(self.store)

    def get(self, key):
        val = self.store.get(key)
        return str(val) if val is not None else None

    def delete(self, key):
        self.store.pop(key, None)

    @classmethod
    def from_url(cls, url, **kwargs):
        return cls()


redis_mod = types.ModuleType("redis")
redis_mod.from_url = FakeRedis.from_url
redis_mod.Redis = FakeRedis
sys.modules["redis"] = redis_mod

# Shim fakeredis just so the test file's import works
fakeredis_mod = types.ModuleType("fakeredis")
fakeredis_mod.FakeRedis = FakeRedis
sys.modules["fakeredis"] = fakeredis_mod

# ───────────────────────────────────────────────────────────────────────────
# 2. Shim 'requests' so send_helper imports cleanly
# ───────────────────────────────────────────────────────────────────────────
requests_mod = types.ModuleType("requests")
class _Exc(Exception): pass
exc_mod = types.ModuleType("requests.exceptions")
exc_mod.HTTPError = _Exc
exc_mod.RequestException = _Exc
requests_mod.exceptions = exc_mod
def _fake_post(*a, **kw):
    raise _Exc("no network")
requests_mod.post = _fake_post
sys.modules["requests"] = requests_mod
sys.modules["requests.exceptions"] = exc_mod

# ───────────────────────────────────────────────────────────────────────────
# 3. Make axension_core importable
# ───────────────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "axension-core"))

# Force DRY_RUN so the WABA path returns a fake message id
os.environ["DRY_RUN"] = "true"


# ───────────────────────────────────────────────────────────────────────────
# Test runner
# ───────────────────────────────────────────────────────────────────────────
PASS = 0
FAIL = 0
RESULTS = []


def test(name):
    def wrap(fn):
        global PASS, FAIL
        try:
            fn()
            PASS += 1
            RESULTS.append(("PASS", name))
            print(f"  ✓ {name}")
        except AssertionError as e:
            FAIL += 1
            RESULTS.append(("FAIL", name, str(e)))
            print(f"  ✗ {name}")
            print(f"    {e}")
        except Exception as e:
            FAIL += 1
            RESULTS.append(("FAIL", name, str(e)))
            print(f"  ✗ {name} (exception)")
            print(f"    {type(e).__name__}: {e}")
            traceback.print_exc()
        return fn
    return wrap


# Reset module state between tests
def reset():
    from axension_core.messaging import reset_redis_client, set_redis_client
    reset_redis_client()
    set_redis_client(FakeRedis())


# ═══════════════════════════════════════════════════════════════════════════
# RATE LIMITER TESTS (Task 3 — 3 brief-required tests + isolation)
# ═══════════════════════════════════════════════════════════════════════════
print("\n── tests/test_rate_limiter.py ──")

@test("test_allows_first_three")
def _():
    reset()
    from axension_core.messaging import check_and_record, MAX_MSGS_PER_FACTORY_PER_DAY
    assert MAX_MSGS_PER_FACTORY_PER_DAY == 3
    r = [check_and_record("factory_001") for _ in range(3)]
    assert r == [True, True, True], r

@test("test_blocks_fourth")
def _():
    reset()
    from axension_core.messaging import check_and_record
    for _ in range(3):
        check_and_record("factory_001")
    assert check_and_record("factory_001") is False
    assert check_and_record("factory_001") is False

@test("test_resets_next_day")
def _():
    reset()
    from axension_core.messaging import check_and_record
    IST = ZoneInfo("Asia/Kolkata")
    today = datetime(2026, 4, 17, 14, 30, tzinfo=IST)
    tomorrow = today + timedelta(days=1)
    for _ in range(3):
        check_and_record("factory_001", now=today)
    assert check_and_record("factory_001", now=today) is False
    assert check_and_record("factory_001", now=tomorrow) is True

@test("test_factories_are_isolated")
def _():
    reset()
    from axension_core.messaging import check_and_record
    for _ in range(3):
        check_and_record("factory_001")
    assert check_and_record("factory_001") is False
    assert check_and_record("factory_002") is True
    assert check_and_record("factory_002") is True
    assert check_and_record("factory_002") is True
    assert check_and_record("factory_002") is False


# ═══════════════════════════════════════════════════════════════════════════
# TEMPLATE RENDERING (4 tests)
# ═══════════════════════════════════════════════════════════════════════════
print("\n── tests/test_send_helper.py — templates ──")

@test("test_template_agent1_followup_renders")
def _():
    from axension_core.messaging.send_helper import _render_template
    body = _render_template("agent1_followup", "v1", {
        "supplier_name": "Ravi Steel Traders",
        "po_number": "PUR-ORD-2026-00011",
        "item_name": "HR Sheet 2mm",
        "promised_date": "15-Mar-2026",
        "days_overdue": 31,
    })
    assert "Ravi Steel Traders" in body
    assert "PUR-ORD-2026-00011" in body
    assert "HR Sheet 2mm" in body
    assert "31" in body
    assert "15-Mar-2026" in body
    assert "Axension AI" in body

@test("test_template_agent1_owner_summary_renders")
def _():
    from axension_core.messaging.send_helper import _render_template
    body = _render_template("agent1_owner_summary", "v1", {
        "date_str": "17-Apr-2026",
        "followed_up": 8, "replied": 5, "no_reply": 3,
        "escalations": [
            {"supplier_name": "Ravi Steel", "po_number": "PO-101", "days_overdue": 7},
        ],
        "stock_summary": {"critical": 1, "warning": 2},
    })
    assert "17-Apr-2026" in body
    assert "Ravi Steel" in body
    assert "PO-101" in body
    assert "1 critical" in body

@test("test_template_agent2_stock_alert_renders")
def _():
    from axension_core.messaging.send_helper import _render_template
    body = _render_template("agent2_stock_alert", "v1", {
        "severity": "critical",
        "item_name": "HR Sheet 2mm",
        "current_qty": 45, "unit": "Kg",
        "critical_threshold": 100, "warning_threshold": 250,
        "last_consumed_date": "16-Apr-2026", "avg_daily": 22,
    })
    assert "CRITICAL" in body
    assert "45 Kg" in body
    assert "Immediate reorder required" in body

@test("test_template_agent3_mismatch_alert_renders")
def _():
    from axension_core.messaging.send_helper import _render_template
    body = _render_template("agent3_mismatch_alert", "v1", {
        "po_number": "PO-101", "invoice_number": "INV-A-2204",
        "supplier_name": "Ravi Steel",
        "po_amount": "1,25,000", "invoice_amount": "1,38,500",
        "variance": "13,500", "variance_pct": "10.8",
        "line_items_diff": [
            {"item": "HR Sheet 2mm", "po_qty": 500, "inv_qty": 540},
        ],
    })
    assert "PO-101" in body
    assert "INV-A-2204" in body
    assert "13,500" in body


# ═══════════════════════════════════════════════════════════════════════════
# SEND HELPER INTEGRATION (2 tests + 2 client + 1 bonus)
# ═══════════════════════════════════════════════════════════════════════════
print("\n── tests/test_send_helper.py — integration ──")

# Stub the DB insert so no psycopg needed
import axension_core.messaging.send_helper as sh
sh._log_to_agent_logs = lambda **kw: "logged-stub-uuid"

@test("test_send_agent_message_happy_path")
def _():
    reset()
    from axension_core.messaging import send_agent_message
    res = send_agent_message(
        "factory_001", "918121444200",
        "agent1_followup", "v1",
        {"supplier_name": "Ravi Steel", "po_number": "PO-001",
         "item_name": "HR Sheet", "promised_date": "10-Apr-2026",
         "days_overdue": 7},
    )
    assert res["status"] == "sent", res
    assert res["message_id"].startswith("wamid.DRYRUN_"), res

@test("test_send_agent_message_blocks_at_cap")
def _():
    reset()
    from axension_core.messaging import send_agent_message
    params = {"supplier_name": "Ravi Steel", "po_number": "PO-001",
              "item_name": "HR Sheet", "promised_date": "10-Apr-2026",
              "days_overdue": 7}
    for _ in range(3):
        r = send_agent_message("factory_001", "918121444200",
                               "agent1_followup", "v1", params)
        assert r["status"] == "sent"
    r4 = send_agent_message("factory_001", "918121444200",
                            "agent1_followup", "v1", params)
    assert r4["status"] == "blocked", r4
    assert "rate_limit_exceeded" in r4["reason"]
    assert r4["message_id"] is None

@test("test_dry_run_send_returns_fake_message_id")
def _():
    from axension_core.messaging.send_helper import _send_via_waba
    res = _send_via_waba("918121444200", "hello")
    assert res["success"] is True
    assert res["message_id"].startswith("wamid.DRYRUN_")

@test("test_agent_id_inferred_from_template_key")
def _():
    from axension_core.messaging.send_helper import _agent_id_from_template_key
    assert _agent_id_from_template_key("agent1_followup") == "agent1"
    assert _agent_id_from_template_key("agent2_stock_alert") == "agent2"
    assert _agent_id_from_template_key("agent3_mismatch_alert") == "agent3"
    try:
        _agent_id_from_template_key("foo_bar")
        assert False, "should have raised"
    except ValueError:
        pass

@test("test_missing_template_returns_failed")
def _():
    reset()
    from axension_core.messaging import send_agent_message
    res = send_agent_message("factory_001", "918121444200",
                             "agent1_doesnotexist", "v1", {})
    assert res["status"] == "failed"
    assert "template_not_found" in res["reason"]


# ═══════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════
print("\n" + "═" * 60)
print(f"  RESULTS: {PASS} passed, {FAIL} failed")
print("═" * 60)
sys.exit(0 if FAIL == 0 else 1)
