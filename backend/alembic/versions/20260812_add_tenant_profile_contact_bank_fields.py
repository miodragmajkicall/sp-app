"""add tenant profile contact and bank fields

Revision ID: 20260812_profile_contact_bank
Revises: 20260812_invoice_buyer_type
Create Date: 2026-08-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260812_profile_contact_bank"
down_revision: Union[str, None] = "20260812_invoice_buyer_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenant_profile_settings", sa.Column("phone", sa.String(length=64), nullable=True))
    op.add_column("tenant_profile_settings", sa.Column("email", sa.String(length=254), nullable=True))
    op.add_column("tenant_profile_settings", sa.Column("bank_name", sa.String(length=128), nullable=True))
    op.add_column("tenant_profile_settings", sa.Column("bank_account", sa.String(length=128), nullable=True))
    op.add_column("tenant_profile_settings", sa.Column("iban", sa.String(length=64), nullable=True))
    op.add_column("tenant_profile_settings", sa.Column("swift_bic", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("tenant_profile_settings", "swift_bic")
    op.drop_column("tenant_profile_settings", "iban")
    op.drop_column("tenant_profile_settings", "bank_account")
    op.drop_column("tenant_profile_settings", "bank_name")
    op.drop_column("tenant_profile_settings", "email")
    op.drop_column("tenant_profile_settings", "phone")
