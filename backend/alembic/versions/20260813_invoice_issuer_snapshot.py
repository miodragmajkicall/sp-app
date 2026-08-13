"""add invoice issuer snapshot

Revision ID: 20260813_invoice_issuer_snapshot
Revises: 20260812_profile_contact_bank
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260813_invoice_issuer_snapshot"
down_revision: Union[str, None] = "20260812_profile_contact_bank"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("issuer_business_name", sa.String(length=256), nullable=True))
    op.add_column("invoices", sa.Column("issuer_address", sa.String(length=256), nullable=True))
    op.add_column("invoices", sa.Column("issuer_tax_id", sa.String(length=64), nullable=True))
    op.add_column("invoices", sa.Column("issuer_phone", sa.String(length=64), nullable=True))
    op.add_column("invoices", sa.Column("issuer_email", sa.String(length=254), nullable=True))
    op.add_column("invoices", sa.Column("issuer_bank_name", sa.String(length=128), nullable=True))
    op.add_column("invoices", sa.Column("issuer_bank_account", sa.String(length=128), nullable=True))
    op.add_column("invoices", sa.Column("issuer_iban", sa.String(length=64), nullable=True))
    op.add_column("invoices", sa.Column("issuer_swift_bic", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("invoices", "issuer_swift_bic")
    op.drop_column("invoices", "issuer_iban")
    op.drop_column("invoices", "issuer_bank_account")
    op.drop_column("invoices", "issuer_bank_name")
    op.drop_column("invoices", "issuer_email")
    op.drop_column("invoices", "issuer_phone")
    op.drop_column("invoices", "issuer_tax_id")
    op.drop_column("invoices", "issuer_address")
    op.drop_column("invoices", "issuer_business_name")
