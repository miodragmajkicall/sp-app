# /home/miso/dev/sp-app/sp-app/backend/app/routes/kpr.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO, StringIO
from typing import List, Optional
import csv

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.models import CashEntry, Invoice, InputInvoice
from app.schemas.kpr import KprListResponse, KprRowItem
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
    in_filters = [InputInvoice.tenant_code == tenant_code]
    if year is not None:
        in_filters.append(func.extract("year", InputInvoice.issue_date) == year)
    if month is not None:
        in_filters.append(func.extract("month", InputInvoice.issue_date) == month)

    in_stmt = (
        select(InputInvoice)
        .where(*in_filters)
        .order_by(InputInvoice.issue_date.asc(), InputInvoice.id.asc())
    )
    for inp in db.execute(in_stmt).scalars().all():
        rows.append(
            KprRowItem(
                date=inp.issue_date,
                kind="expense",
                category="input_invoice",
                counterparty=getattr(inp, "supplier_name", None),
                document_number=getattr(inp, "invoice_number", None),
                description=getattr(inp, "note", None),
                amount=_as_decimal(getattr(inp, "total_amount", 0)),
                currency=getattr(inp, "currency", "BAM") or "BAM",
                tax_deductible=True,  # V1: sve rashode tretiramo kao poreski priznate
                source="input_invoice",
                source_id=inp.id,
            )
        )

    # ---------------------------
    # 3) CashEntry – income/expense
    # ---------------------------
    cash_filters = [CashEntry.tenant_code == tenant_code]
    if year is not None:
        cash_filters.append(func.extract("year", CashEntry.entry_date) == year)
    if month is not None:
        cash_filters.append(func.extract("month", CashEntry.entry_date) == month)

    cash_stmt = (
        select(CashEntry)
        .where(*cash_filters)
        .order_by(CashEntry.entry_date.asc(), CashEntry.id.asc())
    )
    for ce in db.execute(cash_stmt).scalars().all():
        amount = _as_decimal(getattr(ce, "amount", 0))
        kind = getattr(ce, "kind", "income")
        rows.append(
            KprRowItem(
                date=ce.entry_date,
                kind="income" if kind == "income" else "expense",
                category="cash",
                counterparty=None,
                document_number=None,
                description=getattr(ce, "note", None),
                amount=amount,
                currency="BAM",
                tax_deductible=(kind == "expense"),
                source="cash",
                source_id=ce.id,
            )
        )

    # Ne forsiramo dodatno globalno sortiranje po r.date
    # – već smo po pojedinačnim upitima sortirali po datumu + ID.
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
        "- `year` i `month` – filtriranje po datumu (issue_date / entry_date),\n"
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
    total = len(all_rows)

    # Paginacija na Python strani – za V1 je sasvim dovoljna
    paged_rows = all_rows[offset : offset + limit]

    return KprListResponse(
        total=total,
        items=paged_rows,
    )


# ======================================================
#  PDF EXPORT – /kpr/export
# ======================================================


def _escape_pdf_text(text: str) -> str:
    translit_map = str.maketrans(
        {
            "č": "c",
            "ć": "c",
            "š": "s",
            "đ": "d",
            "ž": "z",
            "Č": "C",
            "Ć": "C",
            "Š": "S",
            "Đ": "D",
            "Ž": "Z",
        }
    )
    text = text.translate(translit_map)
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


@router.get(
    "/export",
    summary="PDF export Knjige prihoda i rashoda (KPR)",
    response_class=StreamingResponse,
    description=(
        "Generiše jednostavan PDF prikaz Knjige prihoda i rashoda za traženi period.\n\n"
        "Tipično se koristi za:\n"
        "- štampu KPR-e za knjigovodstvo ili poresku upravu,\n"
        "- arhivu u PDF formatu.\n"
    ),
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
    tenant = _require_tenant(x_tenant_code)
    _ensure_tenant(db, tenant)

    rows = _collect_kpr_rows(db, tenant_code=tenant, year=year, month=month)

    # -----------------------------
    # 1) Tekstualne linije za PDF
    # -----------------------------
    lines: List[str] = []
    lines.append("Knjiga prihoda i rashoda (KPR)")
    lines.append(f"Tenant: {tenant}")
    lines.append(f"Godina: {year}")
    if month is not None:
        lines.append(f"Mjesec: {month:02d}")
    lines.append("")

    if not rows:
        lines.append("Nema evidentiranih stavki za odabrani period.")
    else:
        lines.append(
            "Datum       Vrsta     Kategorija       Iznos (BAM)  Izvor  ID"
        )
        lines.append(
            "--------------------------------------------------------------"
        )
        for r in rows:
            kind = "PRIHOD" if r.kind == "income" else "RASHOD"
            row_date = _get_row_date(r)
            line = (
                f"{row_date.isoformat()}  "
                f"{kind:<8} "
                f"{r.category:<14} "
                f"{_as_decimal(r.amount):10.2f}  "
                f"{r.source:<7} "
                f"{r.source_id}"
            )
            lines.append(line)

    # -----------------------------
    # 2) Pretvaranje u PDF stream
    # -----------------------------
    stream_lines: List[str] = []
    stream_lines.append("BT")
    stream_lines.append("/F1 11 Tf")
    stream_lines.append("50 800 Td")

    first = True
    for line in lines:
        text = _escape_pdf_text(line)
        if first:
            first = False
        else:
            stream_lines.append("0 -14 Td")
        stream_lines.append(f"({text}) Tj")

    stream_lines.append("ET")
    stream_data_str = "\n".join(stream_lines) + "\n"
    stream_data = stream_data_str.encode("latin-1")
    stream_len = len(stream_data)

    objs: List[bytes] = []

    def add_obj(body: str) -> int:
        index = len(objs) + 1
        obj_bytes = f"{index} 0 obj\n{body}\nendobj\n".encode("latin-1")
        objs.append(obj_bytes)
        return index

    # 1 – Catalog
    add_obj("<< /Type /Catalog /Pages 2 0 R >>")

    # 2 – Pages
    add_obj("<< /Type /Pages /Kids [3 0 R] /Count 1 >>")

    # 3 – Page
    add_obj(
        "<< /Type /Page /Parent 2 0 R "
        "/MediaBox [0 0 595 842] "
        "/Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>"
    )

    # 4 – Contents
    contents_body = (
        f"<< /Length {stream_len} >>\nstream\n"
        f"{stream_data_str}"
        "endstream"
    )
    add_obj(contents_body)

    # 5 – Font
    add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    buffer = BytesIO()
    header = "%PDF-1.4\n%\xE2\xE3\xCF\xD3\n"
    buffer.write(header.encode("latin-1"))

    offsets = [0]
    for obj in objs:
        offsets.append(buffer.tell())
        buffer.write(obj)

    xref_pos = buffer.tell()
    obj_count = len(objs) + 1

    buffer.write(f"xref\n0 {obj_count}\n".encode("latin-1"))
    buffer.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        buffer.write(f"{off:010d} 00000 n \n".encode("latin-1"))

    trailer = (
        "trailer\n"
        f"<< /Size {obj_count} /Root 1 0 R >>\n"
        "startxref\n"
        f"{xref_pos}\n"
        "%%EOF\n"
    )
    buffer.write(trailer.encode("latin-1"))

    pdf_bytes = buffer.getvalue()
    buffer.close()

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
        "opis, iznos, valuta, poreski_priznat, source, source_id.\n"
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
    writer = csv.writer(buffer)

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
            "source",
            "source_id",
        ]
    )

    for r in rows:
        row_date = _get_row_date(r).isoformat()
        vrsta = "PRIHOD" if r.kind == "income" else "RASHOD"
        kategorija = r.category or ""
        kupac = r.counterparty or ""
        dok_broj = r.document_number or ""
        opis = r.description or ""
        iznos = str(_as_decimal(r.amount))
        valuta = getattr(r, "currency", "BAM") or "BAM"
        poreski = "DA" if r.tax_deductible else "NE"
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
