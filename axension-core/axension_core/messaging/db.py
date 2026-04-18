"""
axension-core/messaging/db.py
Lightweight DB helper for the shared messaging layer.

Only one job: INSERT a row into {factory_id}.agent_logs.
We keep this isolated so the unit tests of send_helper / rate_limiter
don't have to import psycopg.
"""

import logging
import os
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger("axension.messaging.db")


@contextmanager
def _cursor():
    """psycopg3 cursor with dict rows. Reads DB_URL from env."""
    import psycopg
    from psycopg.rows import dict_row

    db_url = os.environ.get("DB_URL", "")
    if not db_url:
        raise RuntimeError("DB_URL not set — cannot insert into agent_logs")

    conn = psycopg.connect(db_url)
    try:
        cur = conn.cursor(row_factory=dict_row)
        try:
            yield cur
            conn.commit()
        finally:
            cur.close()
    finally:
        conn.close()


def insert_agent_log(
    *,
    factory_id: str,
    agent_id: str,
    to_phone: str,
    template_key: str,
    template_version: str,
    message_text: str,
    message_id: Optional[str],
    status: str,
    logged_id: str,
) -> None:
    """
    INSERT a row into {factory_id}.agent_logs.

    The schema is the one defined in
        axension-agent1/scripts/create_agent_logs_table.sql
    plus the W2 additions: template_key, template_version, message_id, logged_id.

    Make sure the table has been ALTERed before W2 launch:
        ALTER TABLE factory_001.agent_logs
            ADD COLUMN IF NOT EXISTS template_key     VARCHAR(80),
            ADD COLUMN IF NOT EXISTS template_version VARCHAR(20),
            ADD COLUMN IF NOT EXISTS message_id       VARCHAR(120),
            ADD COLUMN IF NOT EXISTS logged_id        VARCHAR(64);
    """
    sql = """
        INSERT INTO {schema}.agent_logs
            (agent_id, factory_id, supplier_phone,
             message_type, message_preview, sent_at, status,
             template_key, template_version, message_id, logged_id)
        VALUES
            (%s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s)
    """.format(schema=factory_id)

    with _cursor() as cur:
        cur.execute(sql, (
            agent_id,
            factory_id,
            to_phone,
            template_key,                # message_type kept for legacy reads
            message_text[:500],
            status,
            template_key,
            template_version,
            message_id,
            logged_id,
        ))
    logger.info(
        "agent_logs INSERT factory=%s agent=%s status=%s template=%s_%s",
        factory_id, agent_id, status, template_key, template_version,
    )
