"""
tests/test_agent1.py — 4 pytest tests for Axension AI Agent 1.

All tests use mocks — no live DB or WhatsApp connections needed.
Run with: pytest tests/test_agent1.py -v
"""

import pytest
from unittest.mock import patch, MagicMock, call
from datetime import date, timedelta


# ────────────────────────────────────────────────────────────
# Test 1: Overdue POs returned sorted by days_overdue DESC
# ────────────────────────────────────────────────────────────
@patch("src.agents.agent1.po_scanner.get_db_cursor")
def test_overdue_sorted(mock_cursor_ctx):
    """get_overdue_pos should return POs sorted by days_overdue descending."""
    from src.agents.agent1.po_scanner import get_overdue_pos

    # Mock DB rows (unsorted — the query sorts them, but we verify the output)
    mock_rows = [
        {
            "po_number": "PO-001", "supplier_name": "Supplier A",
            "supplier_phone": "9876543210", "item_name": "Item A",
            "quantity": 100, "unit": "Kg", "promised_date": date.today() - timedelta(days=5),
            "po_date": date.today() - timedelta(days=20), "status": "To Receive and Bill",
            "days_overdue": 5,
        },
        {
            "po_number": "PO-002", "supplier_name": "Supplier B",
            "supplier_phone": "9845612378", "item_name": "Item B",
            "quantity": 200, "unit": "Nos", "promised_date": date.today() - timedelta(days=1),
            "po_date": date.today() - timedelta(days=15), "status": "To Receive and Bill",
            "days_overdue": 1,
        },
        {
            "po_number": "PO-003", "supplier_name": "Supplier C",
            "supplier_phone": "9731234567", "item_name": "Item C",
            "quantity": 50, "unit": "Litre", "promised_date": date.today() - timedelta(days=3),
            "po_date": date.today() - timedelta(days=10), "status": "To Receive and Bill",
            "days_overdue": 3,
        },
    ]

    # Sort mock rows the way the DB query would (DESC by days_overdue)
    mock_rows_sorted = sorted(mock_rows, key=lambda x: x["days_overdue"], reverse=True)

    # Setup mock cursor context manager
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = mock_rows_sorted
    mock_cursor_ctx.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor_ctx.return_value.__exit__ = MagicMock(return_value=False)

    result = get_overdue_pos("factory_001")

    assert len(result) == 3
    assert result[0]["days_overdue"] == 5  # Most overdue first
    assert result[1]["days_overdue"] == 3
    assert result[2]["days_overdue"] == 1  # Least overdue last


# ────────────────────────────────────────────────────────────
# Test 2: days_overdue is always an integer
# ────────────────────────────────────────────────────────────
@patch("src.agents.agent1.po_scanner.get_db_cursor")
def test_days_overdue_is_int(mock_cursor_ctx):
    """days_overdue must always be returned as a Python int."""
    from src.agents.agent1.po_scanner import get_overdue_pos

    mock_rows = [
        {
            "po_number": "PO-010", "supplier_name": "Ravi Steel",
            "supplier_phone": "9876543210", "item_name": "HR Sheet",
            "quantity": 500, "unit": "Kg",
            "promised_date": date.today() - timedelta(days=5),
            "po_date": date.today() - timedelta(days=20),
            "status": "To Receive and Bill",
            "days_overdue": timedelta(days=5),  # psycopg2 might return timedelta
        },
    ]

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = mock_rows
    mock_cursor_ctx.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor_ctx.return_value.__exit__ = MagicMock(return_value=False)

    result = get_overdue_pos("factory_001")

    assert len(result) == 1
    assert result[0]["days_overdue"] == 5
    assert isinstance(result[0]["days_overdue"], int)


# ────────────────────────────────────────────────────────────
# Test 3: Hard cap — only 3 send_text calls even with 10 POs
# ────────────────────────────────────────────────────────────
@patch("src.tasks.agent1_tasks.log_to_agent_logs")
@patch("src.tasks.agent1_tasks.send_agent_message")
@patch("src.tasks.agent1_tasks.get_pos_due_today")
@patch("src.tasks.agent1_tasks.get_overdue_pos")
def test_message_cap_enforced(mock_overdue, mock_today, mock_send, mock_log):
    """Hard cap: even with 10 overdue POs, only 3 supplier messages should be sent."""
    from src.tasks.agent1_tasks import daily_supplier_followup

    # Generate 10 fake overdue POs, all with valid phone numbers
    mock_pos = []
    for i in range(10):
        mock_pos.append({
            "po_number": f"PO-{i:03d}",
            "supplier_name": f"Supplier {i}",
            "supplier_phone": f"98765432{i:02d}",
            "item_name": f"Item {i}",
            "quantity": 100,
            "unit": "Nos",
            "promised_date": date.today() - timedelta(days=10 - i),
            "po_date": date.today() - timedelta(days=20),
            "status": "To Receive and Bill",
            "days_overdue": 10 - i,
        })

    mock_overdue.return_value = mock_pos
    mock_today.return_value = []
    mock_send.return_value = {"status": "sent", "message_id": "wamid_test", "logged_id": "log_test"}

    # Call the task directly (not via Celery)
    result = daily_supplier_followup()

    # Count only supplier_followup calls (exclude owner_summary call)
    supplier_calls = [
        c for c in mock_send.call_args_list
        if c.kwargs.get("template_key") == "agent1_followup"
    ]

    # Hard cap is 3 supplier messages
    assert len(supplier_calls) == 3
    assert result["messages_sent"] == 3
    assert result["hard_cap"] == 3


# ────────────────────────────────────────────────────────────
# Test 4: Message template contains required fields
# ────────────────────────────────────────────────────────────
def test_message_contains_required_fields():
    """The rendered template must include supplier name, PO number, and days overdue."""
    from axension_core.messaging.send_helper import _render_template

    message = _render_template("agent1_followup", "v1", {
        "supplier_name": "Ravi Steel Traders",
        "po_number": "PUR-ORD-2026-00011",
        "item_name": "HR Sheet 2mm",
        "promised_date": "15-Mar-2026",
        "days_overdue": 31,
    })


    assert "Ravi Steel Traders" in message
    assert "PUR-ORD-2026-00011" in message
    assert "HR Sheet 2mm" in message
    assert "31" in message
    assert "15-Mar-2026" in message
    assert "Axension AI" in message