import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Date, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# --- CashEntry ORM model (za /cash/ rute) ---
class CashEntry(Base):
    __tablename__ = "cash_entries"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True)
    tenant_code = Column(String, nullable=False)
    entry_date = Column(Date, nullable=False)
    kind = Column(String, nullable=False)
    amount = Column(Numeric, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
