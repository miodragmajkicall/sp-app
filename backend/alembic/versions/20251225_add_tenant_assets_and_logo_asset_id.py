"""add tenant_assets and tenant_profile_settings.logo_asset_id

Revision ID: 9c2a8b4f1d73
Revises: 6c7a1f9e12aa
Create Date: 2025-12-25
"""

from alembic import op
import sqlalchemy as sa


revision = "9c2a8b4f1d73"
down_revision = "6c7a1f9e12aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_assets",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_code",
            sa.String(length=64),
            sa.ForeignKey("tenants.code", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="logo"),
        sa.Column("filename", sa.String(length=256), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("kind in ('logo')", name="ck_tenant_assets_kind"),
    )

    op.add_column(
        "tenant_profile_settings",
        sa.Column(
            "logo_asset_id",
            sa.BigInteger(),
            sa.ForeignKey("tenant_assets.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tenant_profile_settings", "logo_asset_id")
    op.drop_table("tenant_assets")
