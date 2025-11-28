from __future__ import annotations

from datetime import date

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
    event,
)
from sqlalchemy.orm import declarative_base, relationship, object_session

Base = declarative_base()


class FinalizedPeriodModificationError(Exception):
    """
    Business greška koja označava pokušaj izmjene ili brisanja podataka
    koji pripadaju već finalizovanom poreznom mjesecu.
    """

    def __init__(self, tenant_code: str, year: int, month: int) -> None:
        self.tenant_code = tenant_code
        self.year = year
        self.month = month
        message = (
            f"Cannot modify data for finalized tax period "
            f"{year:04d}-{month:02d} for tenant {tenant_code}."
        )
        super().__init__(message)


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

    # Status plaćanja – False = neplaćena, True = plaćena
    is_paid = Column(Boolean, nullable=False, default=False)

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
    unit_price = Column(Numeric(14, 2), nullable=False, default=0)

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
#  INVOICE ATTACHMENTS (fajlovi računa)
# ======================================================
class InvoiceAttachment(Base):
    """
    Attachment fakture/računa (skener/slika računa, PDF, itd.).
    """

    __tablename__ = "invoice_attachments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    tenant_code = Column(
        String(64),
        ForeignKey("tenants.code", ondelete="CASCADE"),
        nullable=False,
    )

    # Kada je attachment povezan sa konkretnom izlaznom fakturom
    invoice_id = Column(
        BigInteger,
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Kada je attachment povezan sa konkretnom ulaznom fakturom (račun dobavljača)
    input_invoice_id = Column(
        BigInteger,
        ForeignKey("input_invoices.id", ondelete="SET NULL"),
        nullable=True,
    )

    filename = Column(String(256), nullable=False)
    content_type = Column(String(128), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)

    # Relativna ili apsolutna putanja do fajla na disku
    storage_path = Column(Text, nullable=False)

    status = Column(
        String(32),
        nullable=False,
        default="uploaded",
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relacija ka ulaznoj fakturi (opciono)
    input_invoice = relationship("InputInvoice", back_populates="attachments")


# ======================================================
#  INPUT INVOICES (ULAZNE FAKTURE – TROŠKOVI)
# ======================================================
class InputInvoice(Base):
    """
    Ulazna faktura (račun dobavljača) kao poseban entitet.
    """

    __tablename__ = "input_invoices"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    tenant_code = Column(
        String(64),
        ForeignKey("tenants.code", ondelete="CASCADE"),
        nullable=False,
    )

    supplier_name = Column(String(128), nullable=False)
    supplier_tax_id = Column(String(64), nullable=True)
    supplier_address = Column(String(256), nullable=True)

    invoice_number = Column(String(64), nullable=False)
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=True)

    total_base = Column(Numeric(14, 2), nullable=False, default=0)
    total_vat = Column(Numeric(14, 2), nullable=False, default=0)
    total_amount = Column(Numeric(14, 2), nullable=False, default=0)

    currency = Column(String(8), nullable=False, default="BAM")
    note = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_code",
            "supplier_name",
            "invoice_number",
            name="uq_input_invoice_per_supplier_tenant",
        ),
    )

    # Attachment-i povezani sa ovom ulaznom fakturom
    attachments = relationship(
        "InvoiceAttachment",
        back_populates="input_invoice",
    )


# ======================================================
#  TAX MONTHLY RESULTS
# ======================================================
class TaxMonthlyResult(Base):
    """
    Persistirani mjesečni obračun poreza/doprinosa po tenantu.
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


# ======================================================
#  TAX MONTHLY FINALIZE HISTORY (AUDIT LOG)
# ======================================================
class TaxMonthlyFinalizeHistory(Base):
    """
    Audit log za operacije nad mjesečnim poreznim obračunom.
    """

    __tablename__ = "tax_monthly_finalize_history"

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

    action = Column(
        String(32),
        nullable=False,
        default="finalize",
    )
    triggered_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    triggered_by = Column(String(128), nullable=True)
    note = Column(Text, nullable=True)


# ======================================================
#  BUSINESS LOCKS ZA FINALIZOVANE MJESECE
# ======================================================


def _ensure_month_not_finalized(obj: object, date_value: date | None) -> None:
    """
    Provjerava da li je mjesec za dati tenant_code i datum već finalizovan
    u tabeli tax_monthly_results. Ako jeste → baca FinalizedPeriodModificationError.
    """
    if date_value is None:
        return

    sess = object_session(obj)
    if sess is None:
        return

    tenant_code = getattr(obj, "tenant_code", None)
    if not tenant_code:
        return

    year = date_value.year
    month = date_value.month

    exists = (
        sess.query(TaxMonthlyResult)
        .filter(
            TaxMonthlyResult.tenant_code == tenant_code,
            TaxMonthlyResult.year == year,
            TaxMonthlyResult.month == month,
            TaxMonthlyResult.is_final.is_(True),
        )
        .first()
        is not None
    )

    if exists:
        raise FinalizedPeriodModificationError(
            tenant_code=tenant_code,
            year=year,
            month=month,
        )


@event.listens_for(Invoice, "before_update")
def _invoice_before_update(mapper, connection, target: Invoice) -> None:
    if target.issue_date:
        _ensure_month_not_finalized(target, target.issue_date)


@event.listens_for(Invoice, "before_delete")
def _invoice_before_delete(mapper, connection, target: Invoice) -> None:
    if target.issue_date:
        _ensure_month_not_finalized(target, target.issue_date)


@event.listens_for(CashEntry, "before_update")
def _cash_entry_before_update(mapper, connection, target: CashEntry) -> None:
    if target.entry_date:
        _ensure_month_not_finalized(target, target.entry_date)


@event.listens_for(CashEntry, "before_delete")
def _cash_entry_before_delete(mapper, connection, target: CashEntry) -> None:
    if target.entry_date:
        _ensure_month_not_finalized(target, target.entry_date)
