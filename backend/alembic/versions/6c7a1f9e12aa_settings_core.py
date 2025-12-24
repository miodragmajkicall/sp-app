"""settings core (profile, tax profile, subscription)

Revision ID: 6c7a1f9e12aa
Revises: 5a9f2c1d8e77
Create Date: 2025-12-13

"""
from alembic import op
import sqlalchemy as sa


revision = "6c7a1f9e12aa"
down_revision = "5a9f2c1d8e77"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --------------------------------------------------
    # tenant_profile_settings
    # --------------------------------------------------
    op.create_table(
        "tenant_profile_settings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_code",
            sa.String(64),
            sa.ForeignKey("tenants.code", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("business_name", sa.String(256), nullable=False),
        sa.Column("address", sa.String(256), nullable=True),
        sa.Column("tax_id", sa.String(64), nullable=True),
        sa.Column(
            "logo_attachment_id",
            sa.BigInteger(),
            sa.ForeignKey("invoice_attachments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --------------------------------------------------
    # tenant_tax_profile_settings
    # --------------------------------------------------
    op.create_table(
        "tenant_tax_profile_settings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_code",
            sa.String(64),
            sa.ForeignKey("tenants.code", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "entity",
            sa.String(16),
            nullable=False,  # RS / FBiH / Brcko
        ),
        sa.Column(
            "regime",
            sa.String(32),
            nullable=False,  # pausal / two_percent
        ),
        sa.Column(
            "has_additional_activity",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("monthly_pension", sa.Numeric(14, 2), nullable=True),
        sa.Column("monthly_health", sa.Numeric(14, 2), nullable=True),
        sa.Column("monthly_unemployment", sa.Numeric(14, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --------------------------------------------------
    # tenant_subscription_settings
    # --------------------------------------------------
    op.create_table(
        "tenant_subscription_settings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_code",
            sa.String(64),
            sa.ForeignKey("tenants.code", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "plan",
            sa.String(32),
            nullable=False,  # Basic / Standard / Premium
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("tenant_subscription_settings")
    op.drop_table("tenant_tax_profile_settings")
    op.drop_table("tenant_profile_settings")
