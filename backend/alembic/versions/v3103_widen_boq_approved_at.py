"""v3103 — Widen BOQ approved_at column to fit ISO 8601 timestamps.

The lock handler (``lock_boq`` in ``boq/router.py``) writes
``datetime.now(UTC).isoformat()`` to ``approved_at``, producing a ~32-char
string (e.g. ``2026-05-29T10:18:38.652954+00:00``).  The column was
``String(20)``, causing a PostgreSQL ``DataError`` → HTTP 500.

Revision ID: v3103_widen_boq_approved_at
Revises: v3102_round5_merge
Create Date: 2026-05-29
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v3103_widen_boq_approved_at"
down_revision: Union[str, Sequence[str], None] = "v3102_round5_merge"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "oe_boq_boq",
        "approved_at",
        type_=sa.String(32),
        existing_type=sa.String(20),
    )


def downgrade() -> None:
    op.alter_column(
        "oe_boq_boq",
        "approved_at",
        type_=sa.String(20),
        existing_type=sa.String(32),
    )
