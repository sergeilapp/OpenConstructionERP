# DDC-CWICR-OE: DataDrivenConstruction · OpenConstructionERP
# Copyright (c) 2026 Artem Boiko / DataDrivenConstruction
"""Widen changeorder timestamp columns from VARCHAR(20) to VARCHAR(40).

ISO-8601 timestamps with microseconds and timezone offset
(e.g. "2026-06-04T11:28:59.016119+00:00") are 35 characters, overflowing
the original VARCHAR(20) columns. This caused StringDataRightTruncationError
on the partner-pack demo install and any CO with fractional-second timestamps.

Affected columns:
  - oe_changeorders_order.submitted_at
  - oe_changeorders_order.approved_at
  - oe_changeorders_order.rejected_at

Revision ID: v3154_widen_changeorder_timestamps
Revises: v3153_clash_source_links
Create Date: 2026-06-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v3154_widen_changeorder_timestamps"
down_revision = "v3153_clash_source_links"
branch_labels = None
depends_on = None

_COLUMNS = ("submitted_at", "approved_at", "rejected_at")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table = "oe_changeorders_order"
    if table not in set(inspector.get_table_names()):
        return
    existing_cols = {c["name"] for c in inspector.get_columns(table)}
    for col in _COLUMNS:
        if col in existing_cols:
            op.alter_column(table, col, type_=sa.String(length=40))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table = "oe_changeorders_order"
    if table not in set(inspector.get_table_names()):
        return
    existing_cols = {c["name"] for c in inspector.get_columns(table)}
    for col in _COLUMNS:
        if col in existing_cols:
            op.alter_column(table, col, type_=sa.String(length=20))
