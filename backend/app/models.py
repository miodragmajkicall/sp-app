from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# ======================================================
#  TENANTS
# ======================================================
class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String(32), primary_key=True)
    code = Column(String(64), nullable=False, unique=True)
    name = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("code", name="uq_tenants_code"),
    )

    # Relacija za listu faktura (nije obavezna u logici, ali korisna)
    invoices = relationship("Invoice", back_populates="tenant", cascade="all,delete")


# ======================================================
#  CASH ENTRIES
# ======================================================
class CashEntry(Base):
    __tablename__ = "cash_entries"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_code = Column(String(64), nullable=False)

    entry_date = Column(Date, nullable=False)
    kind = Column(String(16), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)

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


# ======================================================
#  INVOICES (zaglavlje fakture)
# ======================================================
class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Tenant iz headera X-Tenant-Code
    tenant_code = Column(
        String(64),
        ForeignKey("tenants.code", ondelete="CASCADE"),
        nullable=False,
    )

    # Broj fakture po tenant-u (npr. 2025-00001)
    invoice_number = Column(String(32), nullable=False)

    # Datumi
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=True)

    # Podaci o kupcu
    buyer_name = Column(String(128), nullable=False)
    buyer_address = Column(String(256), nullable=True)

    # Sume – server izračunava
    total_base = Column(Numeric(14, 2), nullable=False, default=0)
    total_vat = Column(Numeric(14, 2), nullable=False, default=0)
    total_amount = Column(Numeric(14, 2), nullable=False, default=0)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_code",
            "invoice_number",
            name="uq_invoice_number_per_tenant",
        ),
    )

    # Relacija prema stavkama
    items = relationship(
        "InvoiceItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )

    # Relacija prema tenantu
    tenant = relationship("Tenant", back_populates="invoices")


# ======================================================
#  INVOICE ITEMS (stavke)
# ======================================================
class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    invoice_id = Column(
        BigInteger,
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )

    description = Column(Text, nullable=False)

    quantity = Column(Numeric(12, 2), nullable=False, default=1)
    unit_price = Column(Numeric(12, 2), nullable=False, default=0)

    # PDV stopa – npr. 0.17 = 17%
    vat_rate = Column(Numeric(5, 4), nullable=False, default=0)

    # Izračunate vrijednosti za osnovicu i PDV stavke
    base_amount = Column(Numeric(14, 2), nullable=False, default=0)
    vat_amount = Column(Numeric(14, 2), nullable=False, default=0)
    total_amount = Column(Numeric(14, 2), nullable=False, default=0)

    invoice = relationship("Invoice", back_populates="items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_item_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_item_unit_price_nonneg"),
        CheckConstraint("vat_rate >= 0", name="ck_item_vat_rate_nonneg"),
    )


# ======================================================
#  TAX MONTHLY RESULTS
# ======================================================
class TaxMonthlyResult(Base):
    """
    Persistirani mjesečni obračun poreza/doprinosa po tenantu.

    Svaka kombinacija (tenant_code, year, month) može postojati
    maksimalno jednom – jedinstven ključ služi i kao mehanizam
    zaključavanja finalizovanog mjeseca.
    """

    __tablename__ = "tax_monthly_results"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    tenant_code = Column(
        String(64),
        ForeignKey("tenants.code", ondelete="CASCADE"),
        nullable=False,
    )

    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)

    total_income = Column(Numeric(14, 2), nullable=False)
    total_expense = Column(Numeric(14, 2), nullable=False)
    taxable_base = Column(Numeric(14, 2), nullable=False)
    income_tax = Column(Numeric(14, 2), nullable=False)
    contributions_total = Column(Numeric(14, 2), nullable=False)
    total_due = Column(Numeric(14, 2), nullable=False)

    currency = Column(String(8), nullable=False, default="BAM")

    # Za budućnost – trenutno uvijek snimamo finalizovan obračun,
    # ali polje ostavljamo kao bool flag radi fleksibilnosti.
    is_final = Column(Boolean, nullable=False, default=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_code",
            "year",
            "month",
            name="uq_tax_monthly_results_tenant_year_month",
        ),
    )


# ======================================================
#  TAX YEARLY RESULTS
# ======================================================
class TaxYearlyResult(Base):
    """
    Persistirani GODIŠNJI obračun poreza/doprinosa po tenantu.

    Svaka kombinacija (tenant_code, year) može postojati maksimalno jednom.
    Ovaj zapis predstavlja zaključani godišnji rezultat, izveden iz
    finalizovanih mjeseci u `tax_monthly_results`.
    """

    __tablename__ = "tax_yearly_results"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    tenant_code = Column(
        String(64),
        ForeignKey("tenants.code", ondelete="CASCADE"),
        nullable=False,
    )

    year = Column(Integer, nullable=False)
    months_included = Column(Integer, nullable=False)

    total_income = Column(Numeric(14, 2), nullable=False)
    total_expense = Column(Numeric(14, 2), nullable=False)
    taxable_base = Column(Numeric(14, 2), nullable=False)
    income_tax = Column(Numeric(14, 2), nullable=False)
    contributions_total = Column(Numeric(14, 2), nullable=False)
    total_due = Column(Numeric(14, 2), nullable=False)

    currency = Column(String(8), nullable=False, default="BAM")

    # Godišnji rezultat je uvijek finalan – flag ostavljamo radi konzistentnosti.
    is_final = Column(Boolean, nullable=False, default=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_code",
            "year",
            name="uq_tax_yearly_results_tenant_year",
        ),
    )
