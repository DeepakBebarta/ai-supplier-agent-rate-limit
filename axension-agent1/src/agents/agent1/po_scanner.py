"""
src/agents/agent1/po_scanner.py — Overdue PO scanner for Agent 1.

Reads live purchase order data from Supabase PostgreSQL and identifies:
- Overdue POs (promised_date < today, status not Completed)
- POs due today
- POs due this week (next 7 days)
"""

import logging
from typing import List, Dict, Any

from src.db.connection import get_db_cursor

logger = logging.getLogger("axension.agent1.scanner")


def get_overdue_pos(factory_id: str) -> List[Dict[str, Any]]:
    """
    Fetch all overdue purchase orders for a factory.
    Returns list of dicts sorted by days_overdue descending (most urgent first).
    Only includes POs with status 'To Receive and Bill' (i.e., still open).
    """
    query = """
        SELECT po_number, supplier_name, supplier_phone,
               item_name, quantity, unit, promised_date, po_date, status,
               (CURRENT_DATE - promised_date::date) AS days_overdue
        FROM {schema}.purchase_orders
        WHERE status = 'To Receive and Bill'
          AND promised_date::date < CURRENT_DATE
        ORDER BY days_overdue DESC
    """.format(schema=factory_id)

    try:
        with get_db_cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            results = []
            for row in rows:
                record = dict(row)
                # Ensure days_overdue is int
                val = record["days_overdue"]
                record["days_overdue"] = val.days if hasattr(val, "days") else int(val)
                results.append(record)
            logger.info(f"[{factory_id}] Found {len(results)} overdue POs")
            return results
    except Exception as e:
        logger.error(f"[{factory_id}] Error fetching overdue POs: {e}")
        return []


def get_pos_due_today(factory_id: str) -> List[Dict[str, Any]]:
    """
    Fetch POs with promised_date = today that are still open.
    """
    query = """
        SELECT po_number, supplier_name, supplier_phone,
               item_name, quantity, unit, promised_date, po_date, status,
               0 AS days_overdue
        FROM {schema}.purchase_orders
        WHERE status = 'To Receive and Bill'
          AND promised_date::date = CURRENT_DATE
        ORDER BY supplier_name
    """.format(schema=factory_id)

    try:
        with get_db_cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            results = [dict(row) for row in rows]
            logger.info(f"[{factory_id}] Found {len(results)} POs due today")
            return results
    except Exception as e:
        logger.error(f"[{factory_id}] Error fetching POs due today: {e}")
        return []


def get_pos_due_this_week(factory_id: str) -> List[Dict[str, Any]]:
    """
    Fetch POs due in the next 7 days (including today) that are still open.
    """
    query = """
        SELECT po_number, supplier_name, supplier_phone,
               item_name, quantity, unit, promised_date, po_date, status,
               (promised_date::date - CURRENT_DATE) AS days_until_due
        FROM {schema}.purchase_orders
        WHERE status = 'To Receive and Bill'
          AND promised_date::date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
        ORDER BY promised_date ASC
    """.format(schema=factory_id)

    try:
        with get_db_cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            results = []
            for row in rows:
                record = dict(row)
                record["days_until_due"] = int(record["days_until_due"])
                results.append(record)
            logger.info(f"[{factory_id}] Found {len(results)} POs due this week")
            return results
    except Exception as e:
        logger.error(f"[{factory_id}] Error fetching POs due this week: {e}")
        return []