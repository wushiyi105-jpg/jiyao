"""0001 建表：meetings / decisions / actions / jobs。"""

from __future__ import annotations

from alembic import op

from jiyao.adapters.store import Base

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(op.get_bind())
