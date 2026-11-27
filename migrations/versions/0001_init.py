"""0001：meetings / decisions / actions / jobs，显式建表。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meetings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("transcript", sa.String(), nullable=False),
        sa.Column("created_on", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=500), nullable=False),
        sa.Column("quote", sa.String(length=500), nullable=False),
        sa.Column("offset", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_decisions_meeting_id", "decisions", ["meeting_id"])
    op.create_table(
        "actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=500), nullable=False),
        sa.Column("assignee", sa.String(length=40), nullable=False),
        sa.Column("due", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_actions_meeting_id", "actions", ["meeting_id"])
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("created_on", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_index("ix_actions_meeting_id", table_name="actions")
    op.drop_table("actions")
    op.drop_index("ix_decisions_meeting_id", table_name="decisions")
    op.drop_table("decisions")
    op.drop_table("meetings")
