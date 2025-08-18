import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Date, Numeric, Text, DateTime, ForeignKey, func

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class CashEntry(Base):
    __tablename__ = "cash_entries"

    id = Column(String(36), primary_key=True)
    tenant_code = Column(String(64), ForeignKey("tenants.code", ondelete="CASCADE"), nullable=False, index=True)
    entry_date = Column(Date, nullable=False, index=True)
    kind = Column(String(10), nullable=False)  # 'income' | 'expense'
    amount = Column(Numeric(12, 2), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
