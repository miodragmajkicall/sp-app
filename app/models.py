from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Date,
    Numeric,
    Text,
    BigInteger,
    CheckConstraint,
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


# --- CashEntry ORM model (za /cash/ rute) ---
class CashEntry(Base):
    __tablename__ = "cash_entries"
    __table_args__ = (
        # Ako je migracija već postavila CHECK, ovo neće smetati (extend_existing=True implicitno kroz model mapiranje).
        CheckConstraint("kind IN ('income','expense')", name="ck_cash_entries_kind"),
    )

    # Primarni ključ kao autoincrement/identity BIGINT (usklađeno s alembic migracijom koju si imao).
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Tenant code iz headera "X-Tenant-Code"
    tenant_code = Column(String(64), nullable=False, index=True)

    # Datum unosa
    entry_date = Column(Date, nullable=False)

    # 'income' ili 'expense'
    kind = Column(String(16), nullable=False)

    # Iznos s dvije decimale
    amount = Column(Numeric(14, 2), nullable=False)

    # Opcionalni opis / napomena (mapiramo iz input polja "note")
    description = Column(Text, nullable=True)

    # Server-side default vrijeme kreiranja (timezone aware)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<CashEntry id={self.id} tenant={self.tenant_code} date={self.entry_date} kind={self.kind} amount={self.amount}>"
