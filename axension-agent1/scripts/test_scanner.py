"""
scripts/test_scanner.py — Manual test: print live PO data from Supabase.

Run with:
    python -m scripts.test_scanner

This verifies that po_scanner.py can connect to live Supabase and return real data.
"""

import sys
import os
import json
from datetime import date, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.agents.agent1.po_scanner import (
    get_overdue_pos,
    get_pos_due_today,
    get_pos_due_this_week,
)


def default_serializer(obj):
    """JSON serializer for date objects."""
    if isinstance(obj, (date,)):
        return obj.isoformat()
    if isinstance(obj, timedelta):
        return obj.days
    raise TypeError(f"Type {type(obj)} not serializable")


def main():
    factory_id = os.environ.get("FACTORY_ID", "factory_001")
    print(f"\n{'═' * 60}")
    print(f"  Axension AI — Agent 1 PO Scanner Test")
    print(f"  Factory: {factory_id}")
    print(f"  Date: {date.today().isoformat()}")
    print(f"{'═' * 60}\n")

    # ── Overdue POs ──
    print("── OVERDUE POs ──")
    overdue = get_overdue_pos(factory_id)
    if overdue:
        for po in overdue:
            print(
                f"  {po['po_number']} | {po['supplier_name']:25s} | "
                f"{po['item_name']:20s} | {po['days_overdue']} days overdue | "
                f"Phone: {po.get('supplier_phone', 'N/A')}"
            )
    else:
        print("  (none found)")

    # ── Due Today ──
    print("\n── POs DUE TODAY ──")
    today = get_pos_due_today(factory_id)
    if today:
        for po in today:
            print(
                f"  {po['po_number']} | {po['supplier_name']:25s} | "
                f"{po['item_name']:20s} | Phone: {po.get('supplier_phone', 'N/A')}"
            )
    else:
        print("  (none found)")

    # ── Due This Week ──
    print("\n── POs DUE THIS WEEK ──")
    week = get_pos_due_this_week(factory_id)
    if week:
        for po in week:
            print(
                f"  {po['po_number']} | {po['supplier_name']:25s} | "
                f"{po['item_name']:20s} | Due in {po.get('days_until_due', '?')} days"
            )
    else:
        print("  (none found)")

    # ── Summary ──
    print(f"\n{'─' * 60}")
    print(f"  Summary: {len(overdue)} overdue, {len(today)} due today, "
          f"{len(week)} due this week")
    print(f"{'─' * 60}\n")


if __name__ == "__main__":
    main()
