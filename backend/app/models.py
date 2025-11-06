from sqlalchemy import Column, BigInteger, String, Date, Numeric, Text, DateTime, CheckConstraint, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class CashEntry(Base):
    __tablename__ = "cash_entries"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_code = Column(String(64), nullable=False)

    entry_date = Column(Date, nullable=False)
    kind = Column(String(16), nullable=False)  # 'income' | 'expense'
    amount = Column(Numeric(12, 2), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("kind IN ('income','expense')", name="ck_cash_kind"),
    )
