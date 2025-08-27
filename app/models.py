from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from app.db import Base  # koristimo zajednički Base


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CashEntry(Base):
    __tablename__ = "cash_entries"
    __table_args__ = (
        CheckConstraint("kind in ('income','expense')", name="cash_entries_kind_ck"),
        {"schema": "public"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_code = Column(String(64), nullable=False)
    entry_date = Column(Date, nullable=False)
    kind = Column(String(10), nullable=False)  # 'income' | 'expense'
    amount = Column(Numeric(14, 2), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<CashEntry id={self.id} tenant={self.tenant_code} {self.entry_date} {self.kind} {self.amount}>"
