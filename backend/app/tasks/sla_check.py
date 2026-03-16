"""SLA inspection task skeleton.

This module provides a callable job entry for future scheduler integration.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.db import get_db_context
from app.models import Lead


def run_sla_check_job() -> dict:
    """Count pending leads that exceed 1/3/10 minute SLA windows."""
    now = datetime.utcnow()

    with get_db_context() as db:
        overdue_1m = (
            db.query(Lead)
            .filter(Lead.sla_1m_status == "pending", Lead.created_at < now - timedelta(minutes=1))
            .count()
        )
        overdue_3m = (
            db.query(Lead)
            .filter(Lead.sla_3m_status == "pending", Lead.created_at < now - timedelta(minutes=3))
            .count()
        )
        overdue_10m = (
            db.query(Lead)
            .filter(Lead.sla_10m_status == "pending", Lead.created_at < now - timedelta(minutes=10))
            .count()
        )

    return {
        "checkedAt": now.isoformat(),
        "overdue1m": int(overdue_1m),
        "overdue3m": int(overdue_3m),
        "overdue10m": int(overdue_10m),
    }
