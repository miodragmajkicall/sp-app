from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


# -------------------------------
# Tenants
# -------------------------------
class Tenant(Base):
    __tablename__ = "tenants"

    # Napomena: testovi očekuju da POST /tenants vrati objekat sa poljima: id, code, name.
    # id možemo čuvati kao string (UUID ili generisan u ruti).
    id = Column(String(32), primary_key=True)
    code = Column(String(64), nullable=False, unique=True)
    name = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("code", name="uq_tenants_code"),
    )


# -------------------------------
# Cash Entries
# -------------------------------
class CashEntry(Base):
    __tablename__ = "cash_entries"

    # Važno: testovi koriste autoincrement BIGINT i očekuju da se vraća brojčani id.
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # U ruti se tenant uzima iz X-Tenant-Code headera i upisuje ovde:
    tenant_code = Column(String(64), nullable=False)

    entry_date = Column(Date, nullable=False)

    # kind mora biti 'income' ili 'expense' (testovi to proveravaju)
    kind = Column(String(16), nullable=False)

    # iznos sa 2 decimale – u testu se šalje string "12.34", SQLAlchemy Numeric to podržava
    amount = Column(Numeric(12, 2), nullable=False)

    # Test ruta pretvara "note" -> "description", pa kolona mora postojati:
    description = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "kind in ('income','expense')",
            name="ck_cash_entries_kind",
        ),
    )
