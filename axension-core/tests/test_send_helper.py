"""
tests/test_send_helper.py — Day 5 / Task 4
─────────────────────────────────────────────
Tests for the shared send_agent_message() helper.

Coverage:
  - 4 template rendering tests (agent1_followup, agent1_owner_summary,
    agent2_stock_alert, agent3_mismatch_alert)
  - 2 send_helper integration tests (sent path + blocked-by-rate-limit path)
  - 2 webhook / WABA client tests (DRY_RUN message_id format, agent_id parsing)

Run:
    pytest tests/test_send_helper.py -v
"""

import os
import pytest
import fakeredis
from unittest.mock import patch

from axension_core.messaging import (
    send_agent_message,
    set_redis_client,
    reset_redis_client,
)
from axension_core.messaging.send_helper import (
    _render_template,
    _agent_id_from_template_key,
    _send_via_waba,
)


# ───────────────────────────────────────────────────────────────────────────
# Fixtures
# ───────────────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _swap_redis():
    fake = fakeredis.FakeRedis(decode_responses=True)
    set_redis_client(fake)
    yield fake
    reset_redis_client()


@pytest.fixture(autouse=True)
def _dry_run_env(monkeypatch):
    """All tests run in DRY_RUN mode — no real WABA calls."""
    monkeypatch.setenv("DRY_RUN", "true")


@pytest.fixture(autouse=True)
def _stub_db(monkeypatch):
    """Stub out the agent_logs INSERT so tests don't need psycopg/DB."""
    def _noop(**kwargs):
        return None
    # Patch the late import target
    import axension_core.messaging.send_helper as sh
    monkeypatch.setattr(sh, "_log_to_agent_logs",
                        lambda **kw: "logged-uuid-stub")


# ═══════════════════════════════════════════════════════════════════════════
# 4 TEMPLATE RENDERING TESTS
# ═══════════════════════════════════════════════════════════════════════════
def test_template_agent1_followup_renders():
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


def test_template_agent1_owner_summary_renders():
    body = _render_template("agent1_owner_summary", "v1", {
        "date_str": "17-Apr-2026",
        "followed_up": 8,
        "replied": 5,
        "no_reply": 3,
        "escalations": [
            {"supplier_name": "Ravi Steel", "po_number": "PO-101", "days_overdue": 7},
        ],
        "stock_summary": {"critical": 1, "warning": 2},
    })
    assert "17-Apr-2026" in body
    assert "8" in body
    assert "Ravi Steel" in body
    assert "PO-101" in body
    assert "1 critical" in body


def test_template_agent2_stock_alert_renders():
    body = _render_template("agent2_stock_alert", "v1", {
        "severity": "critical",
        "item_name": "HR Sheet 2mm",
        "current_qty": 45,
        "unit": "Kg",
        "critical_threshold": 100,
        "warning_threshold": 250,
        "last_consumed_date": "16-Apr-2026",
        "avg_daily": 22,
    })
    assert "CRITICAL" in body
    assert "HR Sheet 2mm" in body
    assert "45 Kg" in body
    assert "Immediate reorder required" in body


def test_template_agent3_mismatch_alert_renders():
    body = _render_template("agent3_mismatch_alert", "v1", {
        "po_number": "PO-101",
        "invoice_number": "INV-A-2204",
        "supplier_name": "Ravi Steel",
        "po_amount": "1,25,000",
        "invoice_amount": "1,38,500",
        "variance": "13,500",
        "variance_pct": "10.8",
        "line_items_diff": [
            {"item": "HR Sheet 2mm", "po_qty": 500, "inv_qty": 540},
        ],
    })
    assert "PO-101" in body
    assert "INV-A-2204" in body
    assert "13,500" in body
    assert "10.8" in body


# ═══════════════════════════════════════════════════════════════════════════
# 2 SEND HELPER INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════
def test_send_agent_message_happy_path():
    """First message goes through — status='sent', message_id present."""
    res = send_agent_message(
        factory_id="factory_001",
        to_phone="918121444200",
        template_key="agent1_followup",
        template_version="v1",
        params={
            "supplier_name": "Ravi Steel",
            "po_number": "PO-001",
            "item_name": "HR Sheet",
            "promised_date": "10-Apr-2026",
            "days_overdue": 7,
        },
    )
    assert res["status"] == "sent"
    assert res["message_id"].startswith("wamid.DRYRUN_")
    assert res["logged_id"] is not None


def test_send_agent_message_blocks_at_cap():
    """4th send for the same factory in one day returns status='blocked'."""
    params = {
        "supplier_name": "Ravi Steel", "po_number": "PO-001",
        "item_name": "HR Sheet", "promised_date": "10-Apr-2026",
        "days_overdue": 7,
    }

    # First 3 succeed
    for _ in range(3):
        r = send_agent_message("factory_001", "918121444200",
                               "agent1_followup", "v1", params)
        assert r["status"] == "sent"

    # 4th is blocked
    r4 = send_agent_message("factory_001", "918121444200",
                            "agent1_followup", "v1", params)
    assert r4["status"] == "blocked"
    assert "rate_limit_exceeded" in r4["reason"]
    assert r4["message_id"] is None


# ═══════════════════════════════════════════════════════════════════════════
# 2 CLIENT-LEVEL TESTS (WABA send + agent_id parsing)
# ═══════════════════════════════════════════════════════════════════════════
def test_dry_run_send_returns_fake_message_id(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    res = _send_via_waba("918121444200", "hello")
    assert res["success"] is True
    assert res["message_id"].startswith("wamid.DRYRUN_")
    assert res["error"] is None


def test_agent_id_inferred_from_template_key():
    assert _agent_id_from_template_key("agent1_followup") == "agent1"
    assert _agent_id_from_template_key("agent2_stock_alert") == "agent2"
    assert _agent_id_from_template_key("agent3_mismatch_alert") == "agent3"
    with pytest.raises(ValueError):
        _agent_id_from_template_key("foo_bar")


# ═══════════════════════════════════════════════════════════════════════════
# Bonus — template_not_found returns failed status (not raises)
# ═══════════════════════════════════════════════════════════════════════════
def test_missing_template_returns_failed():
    res = send_agent_message(
        factory_id="factory_001",
        to_phone="918121444200",
        template_key="agent1_doesnotexist",
        template_version="v1",
        params={},
    )
    assert res["status"] == "failed"
    assert "template_not_found" in res["reason"]
