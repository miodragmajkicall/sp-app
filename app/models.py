from sqlalchemy.orm import declarative_base
from sqlalchemy import (
    Column, BigInteger, String, Date, Numeric, Text, DateTime, func
)

Base = declarative_base()

class CashEntry(Base):
    __tablename__ = "cash_entries"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_code = Column(String(64), nullable=False, index=True)
    entry_date = Column(Date, nullable=False)
    kind = Column(String(16), nullable=False)  # 'income' / 'expense'
    amount = Column(Numeric(12, 2), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<CashEntry id={self.id} tenant={self.tenant_code} {self.entry_date} {self.kind} {self.amount}>"
