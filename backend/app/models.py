from __future__ import annotations

import uuid
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Date,
    Numeric,
    Text,
    BigInteger,
    CheckConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CashEntry(Base):
    __tablename__ = "cash_entries"
    __table_args__ = (
        CheckConstraint("kind IN ('income','expense')", name="ck_cash_entries_kind"),
        Index("ix_cash_entries_tenant_date_id", "tenant_code", "entry_date", "id"),
    )

    # BIGINT autoincrement/identity primarni ključ
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Tenant iz headera X-Tenant-Code (obavezno)
    tenant_code = Column(String(64), nullable=False, index=True)

    # Datum knjiženja
    entry_date = Column(Date, nullable=False)

    # Vrsta unosa
    kind = Column(String(16), nullable=False)

    # Iznos (2 decimale)
    amount = Column(Numeric(14, 2), nullable=False)

    # Napomena / opis
    description = Column(Text, nullable=True)

    # Vrijeme kreiranja (server default, timezone-aware)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<CashEntry id={self.id} tenant={self.tenant_code} date={self.entry_date} kind={self.kind} amount={self.amount}>"
