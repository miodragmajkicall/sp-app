# /home/miso/dev/sp-app/sp-app/backend/app/models.py
from __future__ import annotations

from datetime import date
from decimal import Decimal


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

    Trenutno se ova greška podiže kroz SQLAlchemy event hook-ove na modelima:
    - CashEntry     (before_update, before_delete)
    - Invoice       (before_update, before_delete)
    - InputInvoice  (before_update, before_delete)

    To znači da, nakon što je mjesec finalizovan u `tax_monthly_results`
    (is_final = True), nije dozvoljeno:
    - mijenjati osnovne podatke zapisa (npr. datum, iznos) u tom mjesecu
    - brisati zapise koji pripadaju tom mjesecu.

    Cilj je da poreski period bude poslovno zaključan i da se ne može tiho
    mijenjati osnovica nakon finalizacije.
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

    account = Column(String(16), nullable=False, default="cash")

    invoice_id = Column(
        BigInteger,
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
    )

    input_invoice_id = Column(
        BigInteger,
        ForeignKey("input_invoices.id", ondelete="SET NULL"),
        nullable=True,
    )

    description = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "kind in ('income','expense')",
            name="ck_cash_entries_kind",
        ),
        CheckConstraint(
            "account in ('cash','bank')",
            name="ck_cash_entries_account",
        ),
    )


# ======================================================
#  INVOICES (zaglavlje fakture)
# ======================================================
class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    tenant_code = Column(
        String(64),
        ForeignKey("tenants.code", ondelete="CASCADE"),
        nullable=False,
    )

    invoice_number = Column(String(32), nullable=False)

    issue_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=True)

    buyer_name = Column(String(128), nullable=False)
    buyer_address = Column(String(256), nullable=True)

    note = Column(Text, nullable=True)

    total_base = Column(Numeric(14, 2), nullable=False, default=0)
    total_vat = Column(Numeric(14, 2), nullable=False, default=0)
    total_amount = Column(Numeric(14, 2), nullable=False, default=0)

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

    items = relationship(
        "InvoiceItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
    )

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

    vat_rate = Column(Numeric(5, 4), nullable=False, default=0)

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

    invoice_id = Column(
        BigInteger,
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
    )

    input_invoice_id = Column(
        BigInteger,
        ForeignKey("input_invoices.id", ondelete="SET NULL"),
        nullable=True,
    )

    filename = Column(String(256), nullable=False)
    content_type = Column(String(128), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)

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

    input_invoice = relationship("InputInvoice", back_populates="attachments")


# ======================================================
#  INPUT INVOICES (ULAZNE FAKTURE – TROŠKOVI)
# ======================================================
class InputInvoice(Base):
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
    posting_date = Column(Date, nullable=True)

    expense_category = Column(String(64), nullable=True)

    is_tax_deductible = Column(Boolean, nullable=False, default=True)
    is_paid = Column(Boolean, nullable=False, default=False)

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

    attachments = relationship(
        "InvoiceAttachment",
        back_populates="input_invoice",
    )


# ======================================================
#  TAX SETTINGS (per-tenant stope)
# ======================================================
class TaxSettings(Base):
    """
    Podesive stope za TAX modul po tenantu.

    Ovo nam omogućava da:
    - /tax/monthly/* koristi realne (ili bar podesive) stope,
    - UI može imati jednostavan blok “Stope” bez dodatnih menija,
    - zadržimo sistem jak, ali jednostavan.
    """

    __tablename__ = "tax_settings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    tenant_code = Column(
        String(64),
        ForeignKey("tenants.code", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    income_tax_rate = Column(Numeric(6, 4), nullable=False, default=Decimal("0.10"))
    pension_contribution_rate = Column(
        Numeric(6, 4), nullable=False, default=Decimal("0.18")
    )
    health_contribution_rate = Column(
        Numeric(6, 4), nullable=False, default=Decimal("0.12")
    )
    unemployment_contribution_rate = Column(
        Numeric(6, 4), nullable=False, default=Decimal("0.015")
    )
    flat_costs_rate = Column(Numeric(6, 4), nullable=False, default=Decimal("0.30"))

    currency = Column(String(8), nullable=False, default="BAM")

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("tenant_code", name="uq_tax_settings_tenant_code"),
    )


# ======================================================
#  TAX MONTHLY PAYMENTS (status uplate + datum uplate)
# ======================================================
class TaxMonthlyPayment(Base):
    """
    Evidencija uplate za mjesečne obaveze.

    Namjerno odvojeno od TaxMonthlyResult:
    - TaxMonthlyResult = "račun / obračun" (finalize/history/locks)
    - TaxMonthlyPayment = "uplatio / nije uplatio + datum"
    """

    __tablename__ = "tax_monthly_payments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    tenant_code = Column(
        String(64),
        ForeignKey("tenants.code", ondelete="CASCADE"),
        nullable=False,
    )

    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)

    is_paid = Column(Boolean, nullable=False, default=False)
    paid_at = Column(Date, nullable=True)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_code",
            "year",
            "month",
            name="uq_tax_monthly_payments_tenant_year_month",
        ),
    )


# ======================================================
#  TAX MONTHLY RESULTS
# ======================================================
class TaxMonthlyResult(Base):
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
        DateTime(timezone=True), nullable=False, server_default=func.now()
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
        DateTime(timezone=True), nullable=False, server_default=func.now()
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


@event.listens_for(InputInvoice, "before_update")
def _input_invoice_before_update(mapper, connection, target: InputInvoice) -> None:
    if target.issue_date:
        _ensure_month_not_finalized(target, target.issue_date)


@event.listens_for(InputInvoice, "before_delete")
def _input_invoice_before_delete(mapper, connection, target: InputInvoice) -> None:
    if target.issue_date:
        _ensure_month_not_finalized(target, target.issue_date)
