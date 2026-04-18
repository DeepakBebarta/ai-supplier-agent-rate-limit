"""
src/db/connection.py — Supabase PostgreSQL connection manager.
Uses psycopg3 (psycopg) with context manager for safe connection handling.
"""

import logging
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from config.settings import DB_URL

logger = logging.getLogger("axension.db")


@contextmanager
def get_db_connection():
    """
    Context manager that yields a psycopg3 connection.
    Commits on success, rolls back on error, always closes.
    """
    conn = None
    try:
        conn = psycopg.connect(DB_URL)
        yield conn
        conn.commit()
    except psycopg.Error as e:
        logger.error(f"Database error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


@contextmanager
def get_db_cursor():
    """
    Context manager that yields a cursor returning dict rows.
    Handles connection lifecycle automatically.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor(row_factory=dict_row)
        try:
            yield cursor
        finally:
            cursor.close()
