# /home/miso/dev/sp-app-sp-app/backend/app/routes/promet.py
from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session as _get_session_dep
from app.models import Tenant
from app.schemas.promet import (
    PrometListResponse,
    PrometRow,
    PrometSummary,
)
from app.services.csv_security import csv_safe_text
from app.services.promet_dataset import (
    CanonicalPrometEvent,
    UnsupportedPrometDatasetModeError,
    list_canonical_promet_events,
    query_canonical_promet_page,
)
from app.services.promet_eligibility import (
    PrometEligibilityStatus,
    PrometMode,
    resolve_tenant_promet_eligibility,
)
from app.tenant_security import require_tenant_code

router = APIRouter(
    tags=["promet"],
)


# ======================================================
#  TENANT HELPERI
# ======================================================


def _require_tenant(x_tenant_code: Optional[str]) -> str:
    return require_tenant_code(x_tenant_code)


def _require_existing_tenant(db: Session, code: str) -> None:
    existing = db.execute(
        select(Tenant.code).where(Tenant.code == code)
    ).scalar_one_or_none()

    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )


def _resolve_promet_mode_or_raise(
    db: Session,
    tenant: str,
) -> PrometMode:
    eligibility = resolve_tenant_promet_eligibility(
        db=db,
        tenant_code=tenant,
    )

    if eligibility.status is PrometEligibilityStatus.NEEDS_CONFIGURATION:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "promet_needs_configuration",
                "reason_code": eligibility.reason_code,
                "blocking_fields": list(eligibility.blocking_fields),
            },
        )

    if eligibility.status is PrometEligibilityStatus.NOT_APPLICABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "promet_not_applicable",
                "reason_code": eligibility.reason_code,
            },
        )

    if eligibility.mode is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Applicable Promet capability has no resolved mode",
        )

    return eligibility.mode


def _canonical_event_to_promet_row(
    event: CanonicalPrometEvent,
) -> PrometRow:
    # Promet projekcija semantički prazne tekstualne vrijednosti prikazuje
    # kao odsutne, bez izmjene izvornog CashEntry/Invoice podatka.
    counterparty_name = (
        event.counterparty_name
        if event.counterparty_name is not None
        and event.counterparty_name.strip()
        else None
    )
    description = (
        event.description
        if event.description is not None
        and event.description.strip()
        else None
    )

    # Za linked invoice prikazujemo stvarnog kupca. Ako partner ne postoji,
    # kod manualnog prihoda opis događaja služi kao prikazani naziv.
    partner_name = counterparty_name or description

    note = (
        description
        if counterparty_name is not None
        else None
    )

    return PrometRow(
        date=event.event_date,
        document_number=event.document_number,
        partner_name=partner_name,
        amount=event.amount,
        note=note,
    )


# ======================================================
#  LISTA ZA UI – /promet
# ======================================================


@router.get(
    "/promet",
    response_model=PrometListResponse,
    summary="Lista Knjige prometa za UI tabelu",
    description=(
        "UI-friendly lista za tenant-specifičnu Knjigu prometa.\n\n"
        "Podržani filteri:\n"
        "- `year` i `month` – filtriranje po godini/mjesecu događaja,\n"
        "- `date_from` / `date_to` – uključivi opseg datuma događaja,\n"
        "- `partner_query` – filter po partneru ili opisu (substring, case-insensitive).\n\n"
        "Paginacija:\n"
        "- Može se koristiti `page` + `page_size` (1-based), ili direktno `limit` + `offset`.\n"
        "- Ako je `page` zadat, `limit`/`offset` se ignorišu.\n\n"
        "Summary:\n"
        "- `summary` se računa nad svim stavkama nakon filtera, "
        "prije paginacije."
    ),
    responses={
        200: {
            "description": "Uspješno vraćena lista prometa.",
        },
        400: {
            "description": "Nedostaje `X-Tenant-Code` header ili su filter parametri nevalidni.",
        },
    },
)
def list_promet(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
    ),
    year: Optional[int] = Query(None, ge=1900, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    date_from: Optional[date] = Query(
        None,
        description="Početni datum opsega (entry_date >= date_from).",
    ),
    date_to: Optional[date] = Query(
        None,
        description="Završni datum opsega (entry_date <= date_to).",
    ),
    partner_query: Optional[str] = Query(
        None,
        description="Filter po opisu (case-insensitive, substring).",
    ),
    page: Optional[int] = Query(
        None,
        ge=1,
        description="Broj stranice (1-based). Ako je zadat, koristi se zajedno sa `page_size`.",
    ),
    page_size: Optional[int] = Query(
        None,
        ge=1,
        le=200,
        description="Broj stavki po stranici kada se koristi `page`.",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=500,
        description="Maksimalan broj stavki u odgovoru (koristi se ako `page` nije zadat).",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Offset za rezultate (koristi se ako `page` nije zadat).",
    ),
) -> PrometListResponse:
    tenant = _require_tenant(x_tenant_code)

    # GET /promet je read-only: nepoznat tenant se ne kreira.
    _require_existing_tenant(db, tenant)

    mode = _resolve_promet_mode_or_raise(db, tenant)

    partner_needle = (
        partner_query.strip().casefold()
        if partner_query and partner_query.strip()
        else None
    )

    # Ako je page zadat, zadržavamo postojeću page/page_size semantiku.
    if page is not None:
        effective_page_size = page_size or limit
        query_limit = effective_page_size
        query_offset = (page - 1) * effective_page_size
    else:
        query_limit = limit
        query_offset = offset

    # Bez stvarnog partner filtera koristimo SQL-optimizovani canonical path.
    # Whitespace-only partner_query semantički je isto što i bez filtera.
    if partner_needle is None:
        try:
            result = query_canonical_promet_page(
                db,
                tenant_code=tenant,
                mode=mode,
                year=year,
                month=month,
                date_from=date_from,
                date_to=date_to,
                limit=query_limit,
                offset=query_offset,
            )
        except UnsupportedPrometDatasetModeError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "promet_dataset_not_implemented",
                    "mode": mode.value,
                },
            ) from exc

        summary = PrometSummary(
            total_amount=result.total_amount,
            cash_amount=result.cash_amount,
            bank_amount=result.bank_amount,
        )

        promet_items = [
            _canonical_event_to_promet_row(event)
            for event in result.items
        ]

        return PrometListResponse(
            total=result.total,
            summary=summary,
            items=promet_items,
        )

    # Partner filter namjerno ostaje na postojećem Python path-u:
    # literal substring + casefold semantika mora ostati nepromijenjena.
    try:
        events = list_canonical_promet_events(
            db,
            tenant_code=tenant,
            mode=mode,
            date_from=date_from,
            date_to=date_to,
        )
    except UnsupportedPrometDatasetModeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "promet_dataset_not_implemented",
                "mode": mode.value,
            },
        ) from exc

    filtered_events: list[CanonicalPrometEvent] = []

    for event in events:
        if year is not None and event.event_date.year != year:
            continue

        if month is not None and event.event_date.month != month:
            continue

        searchable_values = (
            event.counterparty_name,
            event.description,
        )
        if not any(
            partner_needle in value.casefold()
            for value in searchable_values
            if value
        ):
            continue

        filtered_events.append(event)

    # Partner fallback zadržava postojeći newest-first contract.
    filtered_events.sort(
        key=lambda event: (
            event.event_date,
            event.source_id,
        ),
        reverse=True,
    )

    total = len(filtered_events)

    cash_amount = sum(
        (
            event.amount
            for event in filtered_events
            if event.payment_channel == "cash"
        ),
        Decimal("0.00"),
    )
    bank_amount = sum(
        (
            event.amount
            for event in filtered_events
            if event.payment_channel == "bank"
        ),
        Decimal("0.00"),
    )

    summary = PrometSummary(
        total_amount=cash_amount + bank_amount,
        cash_amount=cash_amount,
        bank_amount=bank_amount,
    )

    page_events = filtered_events[
        query_offset:query_offset + query_limit
    ]

    promet_items = [
        _canonical_event_to_promet_row(event)
        for event in page_events
    ]

    return PrometListResponse(
        total=total,
        summary=summary,
        items=promet_items,
    )


# ======================================================
#  EXPORT – /promet/export (CSV)
# ======================================================


@router.get(
    "/promet/export",
    summary="Export Knjige prometa (CSV za Excel)",
    response_class=StreamingResponse,
    description=(
        "Export tenant-specifične Knjige prometa u CSV format koji se može "
        "direktno otvoriti u Excel-u.\n\n"
        "Podržani filteri su isti canonical filteri kao za `/promet`:\n"
        "- `year`, `month`, `date_from`, `date_to`, `partner_query`.\n\n"
        "Format: delimiter `;`, UTF-8 sa BOM radi korektnog prikaza u Excel-u."
    ),
)
def export_promet(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
    ),
    year: Optional[int] = Query(None, ge=1900, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    partner_query: Optional[str] = Query(None),
) -> StreamingResponse:
    tenant = _require_tenant(x_tenant_code)

    # Export koristi isti read-only tenant/eligibility contract kao GET /promet.
    _require_existing_tenant(db, tenant)
    mode = _resolve_promet_mode_or_raise(db, tenant)

    partner_needle = (
        partner_query.strip().casefold()
        if partner_query and partner_query.strip()
        else None
    )

    try:
        events = list_canonical_promet_events(
            db,
            tenant_code=tenant,
            mode=mode,
            date_from=date_from,
            date_to=date_to,
        )
    except UnsupportedPrometDatasetModeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "promet_dataset_not_implemented",
                "mode": mode.value,
            },
        ) from exc

    filtered_events: list[CanonicalPrometEvent] = []

    for event in events:
        if year is not None and event.event_date.year != year:
            continue

        if month is not None and event.event_date.month != month:
            continue

        if partner_needle is not None:
            searchable_values = (
                event.counterparty_name,
                event.description,
            )
            if not any(
                partner_needle in value.casefold()
                for value in searchable_values
                if value
            ):
                continue

        filtered_events.append(event)

    # CSV knjiga je hronološka; isti datum razrješava canonical source_id.
    filtered_events.sort(
        key=lambda event: (
            event.event_date,
            event.source_id,
        )
    )

    output = io.StringIO(newline="")
    writer = csv.writer(
        output,
        delimiter=";",
        quoting=csv.QUOTE_ALL,
    )

    writer.writerow(
        [
            "Datum",
            "Broj dokumenta",
            "Partner",
            "Iznos",
            "Napomena",
        ]
    )

    for event in filtered_events:
        row = _canonical_event_to_promet_row(event)

        writer.writerow(
            [
                row.date.isoformat(),
                csv_safe_text(row.document_number or ""),
                csv_safe_text(row.partner_name or ""),
                f"{row.amount:.2f}",
                csv_safe_text(row.note or ""),
            ]
        )

    csv_bytes = output.getvalue().encode("utf-8-sig")
    output.close()

    filename = "promet-export.csv"

    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# ======================================================
#  PDF EXPORT – /promet/export-pdf
# ======================================================


@router.get(
    "/promet/export-pdf",
    summary="PDF export Knjige prometa",
    response_class=StreamingResponse,
    description=(
        "Generiše informativni PDF Knjige prometa koristeći isti "
        "tenant, eligibility, canonical dataset i filter contract "
        "kao `/promet` i `/promet/export`."
    ),
)
def export_promet_pdf(
    db: Session = Depends(_get_session_dep),
    x_tenant_code: Optional[str] = Header(
        None,
        alias="X-Tenant-Code",
    ),
    year: Optional[int] = Query(None, ge=1900, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    partner_query: Optional[str] = Query(None),
) -> StreamingResponse:
    from app.services.pdf_invoice import UnsupportedPdfGlyphError
    from app.services.pdf_promet import render_promet_pdf

    tenant = _require_tenant(x_tenant_code)

    _require_existing_tenant(db, tenant)
    mode = _resolve_promet_mode_or_raise(db, tenant)

    partner_needle = (
        partner_query.strip().casefold()
        if partner_query and partner_query.strip()
        else None
    )

    try:
        events = list_canonical_promet_events(
            db,
            tenant_code=tenant,
            mode=mode,
            date_from=date_from,
            date_to=date_to,
        )
    except UnsupportedPrometDatasetModeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "promet_dataset_not_implemented",
                "mode": mode.value,
            },
        ) from exc

    filtered_events: list[CanonicalPrometEvent] = []

    for event in events:
        if year is not None and event.event_date.year != year:
            continue

        if month is not None and event.event_date.month != month:
            continue

        if partner_needle is not None:
            searchable_values = (
                event.counterparty_name,
                event.description,
            )
            if not any(
                partner_needle in value.casefold()
                for value in searchable_values
                if value
            ):
                continue

        filtered_events.append(event)

    filtered_events.sort(
        key=lambda event: (
            event.event_date,
            event.source_id,
        )
    )

    rows = [
        _canonical_event_to_promet_row(event)
        for event in filtered_events
    ]

    filter_parts: list[str] = []

    if year is not None:
        filter_parts.append(f"Godina: {year}")

    if month is not None:
        filter_parts.append(f"Mjesec: {month:02d}")

    if date_from is not None:
        filter_parts.append(
            f"Od: {date_from.isoformat()}"
        )

    if date_to is not None:
        filter_parts.append(
            f"Do: {date_to.isoformat()}"
        )

    if partner_query and partner_query.strip():
        filter_parts.append(
            f"Partner/opis: {partner_query.strip()}"
        )

    filter_label = (
        "; ".join(filter_parts)
        if filter_parts
        else "Bez dodatnih filtera"
    )

    try:
        pdf_bytes = render_promet_pdf(
            tenant_code=tenant,
            rows=rows,
            filter_label=filter_label,
        )
    except UnsupportedPdfGlyphError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Promet PDF cannot be generated because the document contains "
                "characters unsupported by the PDF font"
            ),
        ) from exc

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                'attachment; filename="promet-export.pdf"'
            ),
        },
    )
