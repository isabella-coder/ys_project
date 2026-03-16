"""baseline migration placeholder

Revision ID: 20260311_0001
Revises: 
Create Date: 2026-03-11 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa  # noqa: F401


# revision identifiers, used by Alembic.
revision = "20260311_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing environments may already have tables created by init_db().
    # Keep baseline migration as a no-op and generate structural changes in later revisions.
    pass


def downgrade() -> None:
    pass
