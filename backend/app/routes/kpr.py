# /home/miso/dev/sp-app/sp-app/backend/app/routes/kpr.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO, StringIO
from typing import List, Literal, Optional
import csv
import unicodedata

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.models import Invoice
from app.schemas.kpr import KprListResponse, KprRowItem, KprSummary
from app.services.recognized_input_expenses import (
    UnsupportedInputExpenseRecognitionError,
    list_recognized_input_expenses,
)
from app.services.recognized_manual_cash import (
    UnsupportedManualCashRecognitionError,
    list_recognized_manual_cash,
)
from app.tenant_security import ensure_tenant_exists, require_tenant_code


router = APIRouter(
    prefix="/kpr",
    tags=["kpr"],
)


# ======================================================
#  TENANT HELPERS
# ======================================================


def _require_tenant(x_tenant_code: Optional[str]) -> str:
    """
    Osigurava da je X-Tenant-Code header postavljen, u skladu
    sa ostalim modulima (cash, invoices, input-invoices, tax...).
    """
    return require_tenant_code(x_tenant_code)


def _ensure_tenant(db: Session, code: str) -> None:
    """
    Pobrinemo se da existe minimalni tenant zapis u bazi.
    """
    ensure_tenant_exists(db, code)


# ======================================================
#  INTERNAL – KPR AGGREGATION
# ======================================================


def _as_decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0.00")


def _get_row_date(row: KprRowItem) -> date:
    """
    Robustan helper za dohvat datuma iz KprRowItem objekta.

    U normalnom radu koristimo polje `date` (definisano u schemi),
    ali testovi mogu kreirati instancu sa `entry_date` kao extra poljem.
    Zato prvo pokušamo `date`, a ako ga nema, padamo na `entry_date`.
    """
    d = getattr(row, "date", None)
    if d is not None:
        return d
    entry = getattr(row, "entry_date", None)
    if entry is not None:
        return entry
    # Ako baš nema ništa, vratimo "dummy" datum da ne padnemo,
    # ali u praksi do ovoga ne bi trebalo doći.
    return date.today()


def _csv_safe_text(value: str) -> str:
    """Protect free-text CSV cells without changing stored values."""
    if not value:
        return value

    # Skip leading whitespace and invisible formatting characters.
    # A leading control character is itself considered unsafe.
    index = 0
    has_control = False
    while index < len(value):
        char = value[index]
        kind = unicodedata.category(char)
        if not char.isspace() and kind not in {"Cc", "Cf"}:
            break
        if kind == "Cc":
            has_control = True
        index += 1

    first = value[index:index + 1]
    formula_starts = "=+-@\uff1d\uff0b\uff0d\uff20"
    if has_control or (first and first in formula_starts):
        return "\t" + value
    return value


def _collect_kpr_rows(
    db: Session,
    tenant_code: str,
    year: Optional[int],
    month: Optional[int],
) -> List[KprRowItem]:
    """
    Sakuplja sve stavke za KPR za datog tenanta i opcioni year/month filter.

    Izvori:
    - Invoice      → prihodi,
    - InputInvoice → rashodi,
    - CashEntry    → dodatni prihodi/rashodi koji nisu pokriveni fakturama.
    """
    rows: List[KprRowItem] = []

    # ---------------------------
    # 1) Izlazne fakture (Invoice) – income
    # ---------------------------
    inv_filters = [Invoice.tenant_code == tenant_code]
    if year is not None:
        inv_filters.append(func.extract("year", Invoice.issue_date) == year)
    if month is not None:
        inv_filters.append(func.extract("month", Invoice.issue_date) == month)

    inv_stmt = (
        select(Invoice)
        .where(*inv_filters)
        .order_by(Invoice.issue_date.asc(), Invoice.id.asc())
    )
    for inv in db.execute(inv_stmt).scalars().all():
        rows.append(
            KprRowItem(
                date=inv.issue_date,
                kind="income",
                category="invoice",
                counterparty=getattr(inv, "buyer_name", None),
                document_number=getattr(inv, "invoice_number", None),
                description=None,
                amount=_as_decimal(getattr(inv, "total_amount", 0)),
                currency="BAM",
                tax_deductible=False,
                source="invoice",
                source_id=inv.id,
            )
        )

    # ---------------------------
    # 2) Ulazne fakture (InputInvoice) – expense
    # ---------------------------
    date_from = None
    date_to = None
    if year is not None and month is not None:
        date_from = date(year, month, 1)
        date_to = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    elif year is not None:
        date_from = date(year, 1, 1)
        date_to = date(year + 1, 1, 1)

    try:
        recognized_input_expenses = list_recognized_input_expenses(
            db,
            tenant_code=tenant_code,
            date_from=date_from,
            date_to=date_to,
            month=month if year is None else None,
        )
    except UnsupportedInputExpenseRecognitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    for inp in recognized_input_expenses:
        if month is not None and year is None and inp.recognition_date.month != month:
            continue
        rows.append(
            KprRowItem(
                date=inp.recognition_date,
                kind="expense",
                category="input_invoice",
                counterparty=getattr(inp, "supplier_name", None),
                document_number=getattr(inp, "invoice_number", None),
                description=getattr(inp, "note", None),
                amount=_as_decimal(inp.amount),
                currency=inp.currency,
                tax_deductible=inp.is_tax_deductible,
                source="input_invoice",
                source_id=inp.invoice_id,
            )
        )

    # ---------------------------
    # 3) Manual cash – recognized business activity
    # ---------------------------
    try:
        recognized_manual_cash = list_recognized_manual_cash(
            db,
            tenant_code=tenant_code,
            date_from=date_from,
            date_to=date_to,
            month=month if year is None else None,
        )
    except UnsupportedManualCashRecognitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    for cash in recognized_manual_cash:
        if month is not None and year is None and cash.recognition_date.month != month:
            continue
        rows.append(
            KprRowItem(
                date=cash.recognition_date,
                kind=cash.kind,
                category="cash",
                counterparty=None,
                document_number=None,
                description=cash.description,
                amount=cash.amount,
                currency="BAM",
                tax_deductible=(
                    cash.kind == "expense"
                    and cash.tax_treatment == "deductible"
                ),
                tax_treatment=cash.tax_treatment,
                source="cash",
                source_id=cash.cash_entry_id,
            )
        )

    # Stabilan globalni redoslijed prije paginacije.
    rows.sort(key=lambda row: (row.entry_date, row.source, row.source_id))
    return rows


# ======================================================
#  LIST – /kpr
# ======================================================


@router.get(
    "",
    response_model=KprListResponse,
    summary="Lista KPR stavki (knjiga prihoda i rashoda)",
    description=(
        "Vraća objedinjenu listu prihoda i rashoda (KPR) za jednog tenanta.\n\n"
        "Podržani filteri:\n"
        "- `year` i `month` – filtriranje po datumu priznavanja / entry_date,\n"
        "- `limit` i `offset` – jednostavna paginacija nad agregiranom listom.\n\n"
        "Svaka stavka ima polja: `date`, `kind`, `category`, `amount`, "
        "`source`, `source_id` i prateća meta polja."
    ),
)
def list_kpr(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta čiju KPR evidenciju vraćamo.",
    ),
    year: Optional[int] = Query(
        None,
        ge=1900,
        le=2100,
        description="Godina za filter po datumu (npr. 2025).",
    ),
    month: Optional[int] = Query(
        None,
        ge=1,
        le=12,
        description="Mjesec za filter po datumu (1–12).",
    ),
    kind: Optional[Literal["income", "expense"]] = Query(
        None,
        description="Vrsta stavke: income ili expense.",
    ),
    limit: int = Query(
        1000,
        ge=1,
        le=10_000,
        description="Maksimalan broj stavki u odgovoru.",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Broj stavki koje preskačemo (paginacija).",
    ),
) -> KprListResponse:
    tenant = _require_tenant(x_tenant_code)
    _ensure_tenant(db, tenant)

    all_rows = _collect_kpr_rows(db, tenant_code=tenant, year=year, month=month)

    income = sum(
        (row.amount for row in all_rows if row.kind == "income"),
        Decimal("0.00"),
    )
    expense = sum(
        (row.amount for row in all_rows if row.kind == "expense"),
        Decimal("0.00"),
    )
    summary = KprSummary(
        income=income,
        expense=expense,
        net=income - expense,
    )

    if kind is not None:
        all_rows = [row for row in all_rows if row.kind == kind]
    total = len(all_rows)

    # Paginacija na Python strani – za V1 je sasvim dovoljna
    paged_rows = all_rows[offset : offset + limit]

    return KprListResponse(
        total=total,
        summary=summary,
        items=paged_rows,
    )


# ======================================================
#  PDF EXPORT – /kpr/export
# ======================================================


@router.get(
    "/export",
    summary="PDF export Knjige prihoda i rashoda (KPR)",
    response_class=StreamingResponse,
    description="Generiše informativni PDF izvještaj za odabrani period.",
)
def export_kpr_pdf(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta za kojeg se eksportuje KPR.",
    ),
    year: int = Query(
        ...,
        ge=1900,
        le=2100,
        description="Godina za KPR export (obavezno).",
    ),
    month: Optional[int] = Query(
        None,
        ge=1,
        le=12,
        description="Mjesec za KPR export (opciono). Ako nije zadat, eksportuje se cijela godina.",
    ),
) -> StreamingResponse:
    from app.services.pdf_invoice import UnsupportedPdfGlyphError
    from app.services.pdf_kpr import KprPeriod, render_kpr_pdf

    tenant = _require_tenant(x_tenant_code)
    _ensure_tenant(db, tenant)

    rows = _collect_kpr_rows(db, tenant_code=tenant, year=year, month=month)
    try:
        pdf_bytes = render_kpr_pdf(
            tenant_code=tenant,
            period=KprPeriod(year=year, month=month),
            rows=rows,
        )
    except UnsupportedPdfGlyphError as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                "KPR PDF cannot be generated because the document contains "
                "characters unsupported by the PDF font"
            ),
        ) from exc

    filename = f"kpr-{tenant}-{year}"
    if month is not None:
        filename += f"-{month:02d}"
    filename += ".pdf"

    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
    }
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers=headers,
    )


# ======================================================
#  EXCEL / CSV EXPORT – /kpr/export-excel
# ======================================================


@router.get(
    "/export-excel",
    summary="Excel/CSV export Knjige prihoda i rashoda (KPR)",
    response_class=StreamingResponse,
    description=(
        "Generiše CSV fajl (kompatibilan sa Excel-om) za Knjigu prihoda i rashoda "
        "za traženi period.\n\n"
        "CSV sadrži kolone: datum, vrsta, kategorija, kupac/dobavljač, dok_broj, "
        "opis, iznos, valuta, poreski_priznat, tax_treatment, source, source_id.\n"
    ),
)
def export_kpr_excel(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
        description="Šifra tenanta za kojeg se eksportuje KPR.",
    ),
    year: int = Query(
        ...,
        ge=1900,
        le=2100,
        description="Godina za KPR export (obavezno).",
    ),
    month: Optional[int] = Query(
        None,
        ge=1,
        le=12,
        description="Mjesec za KPR export (opciono). Ako nije zadat, eksportuje se cijela godina.",
    ),
) -> StreamingResponse:
    tenant = _require_tenant(x_tenant_code)
    _ensure_tenant(db, tenant)

    rows = _collect_kpr_rows(db, tenant_code=tenant, year=year, month=month)

    buffer = StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)

    # Header
    writer.writerow(
        [
            "datum",
            "vrsta",
            "kategorija",
            "kupac_dobavljac",
            "dok_broj",
            "opis",
            "iznos",
            "valuta",
            "poreski_priznat",
            "tax_treatment",
            "source",
            "source_id",
        ]
    )

    for r in rows:
        row_date = _get_row_date(r).isoformat()
        vrsta = "PRIHOD" if r.kind == "income" else "RASHOD"
        kategorija = r.category or ""
        kupac = _csv_safe_text(r.counterparty or "")
        dok_broj = _csv_safe_text(r.document_number or "")
        opis = _csv_safe_text(r.description or "")
        iznos = str(_as_decimal(r.amount))
        valuta = getattr(r, "currency", "BAM") or "BAM"
        poreski = "DA" if r.tax_deductible else "NE"
        tax_treatment = r.tax_treatment or ""
        source = r.source or ""
        source_id = r.source_id

        writer.writerow(
            [
                row_date,
                vrsta,
                kategorija,
                kupac,
                dok_broj,
                opis,
                iznos,
                valuta,
                poreski,
                tax_treatment,
                source,
                source_id,
            ]
        )

    csv_text = buffer.getvalue()
    buffer.close()

    # UTF-8 sa BOM da Excel na Windowsu pravilno prepozna encoding
    data = csv_text.encode("utf-8-sig")

    filename = f"kpr-{tenant}-{year}"
    if month is not None:
        filename += f"-{month:02d}"
    filename += ".csv"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
    }

    return StreamingResponse(
        BytesIO(data),
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )
