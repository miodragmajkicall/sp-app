"""create tenants table

Revision ID: 0026328e0d28
Revises:
Create Date: 2025-08-11 13:08:26.974818
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0026328e0d28"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Kreira tabelu tenants u skladu sa backend/app/models.py -> Tenant.
    """
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("code", name="uq_tenants_code"),
    )


def downgrade() -> None:
    op.drop_table("tenants")
