from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    TenantBusinessProfileSettings,
    TenantTaxProfileSettings,
)
from app.services.profile_history import (
    ProfilePeriodIntegrityError,
    get_business_profile_as_of,
    get_tax_profile_as_of,
)
from app.services.promet_dataset import (
    get_canonical_promet_date_bounds,
    list_canonical_promet_years_for_month,
)
from app.services.promet_eligibility import (
    PrometEligibility,
    PrometEligibilityStatus,
    PrometMode,
    resolve_promet_eligibility,
    resolve_tenant_promet_eligibility,
)


@dataclass(frozen=True)
class PrometDateSpan:
    start: date
    end: date


@dataclass(frozen=True)
class PrometPeriodResolution:
    eligibility: PrometEligibility
    spans: tuple[PrometDateSpan, ...]


class PrometProfileCoverageError(RuntimeError):
    def __init__(
        self,
        *,
        date_from: date,
        date_to: date,
    ) -> None:
        self.date_from = date_from
        self.date_to = date_to
        super().__init__(
            "Verified Promet profile coverage is missing for "
            f"{date_from.isoformat()}..{date_to.isoformat()}"
        )


class PrometProfileModeChangedError(RuntimeError):
    def __init__(
        self,
        *,
        date_from: date,
        date_to: date,
    ) -> None:
        self.date_from = date_from
        self.date_to = date_to
        super().__init__(
            "Promet eligibility/mode changes inside requested scope "
            f"{date_from.isoformat()}..{date_to.isoformat()}"
        )


def _month_end(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)

    return date(year, month + 1, 1) - timedelta(days=1)


def _intersect_span(
    *,
    start: date,
    end: date,
    date_from: date | None,
    date_to: date | None,
) -> PrometDateSpan | None:
    if date_from is not None:
        start = max(start, date_from)

    if date_to is not None:
        end = min(end, date_to)

    if start > end:
        return None

    return PrometDateSpan(
        start=start,
        end=end,
    )


def _resolve_requested_spans(
    db: Session,
    *,
    tenant_code: str,
    year: int | None,
    month: int | None,
    date_from: date | None,
    date_to: date | None,
) -> tuple[PrometDateSpan, ...]:
    # year određuje konkretan kalendarski scope, nezavisno od toga
    # postoje li događaji u tom periodu.
    if year is not None:
        if month is not None:
            start = date(year, month, 1)
            end = _month_end(year, month)
        else:
            start = date(year, 1, 1)
            end = date(year, 12, 31)

        span = _intersect_span(
            start=start,
            end=end,
            date_from=date_from,
            date_to=date_to,
        )

        return (span,) if span is not None else ()

    # month bez year znači isti mjesec kroz sve godine.
    # Provjeravamo samo godine u kojima canonical source stvarno postoji.
    if month is not None:
        years = list_canonical_promet_years_for_month(
            db,
            tenant_code=tenant_code,
            mode=PrometMode.RS_SMALL_ENTREPRENEUR,
            month=month,
            date_from=date_from,
            date_to=date_to,
        )

        spans: list[PrometDateSpan] = []

        for event_year in years:
            span = _intersect_span(
                start=date(event_year, month, 1),
                end=_month_end(event_year, month),
                date_from=date_from,
                date_to=date_to,
            )

            if span is not None:
                spans.append(span)

        return tuple(spans)

    # Dvostrano bounded date scope je eksplicitan čak i kada nema događaja.
    if date_from is not None and date_to is not None:
        if date_from > date_to:
            return ()

        return (
            PrometDateSpan(
                start=date_from,
                end=date_to,
            ),
        )

    # Bez year/month, ili kod jednostrano bounded date filtera,
    # istorijski scope vezujemo za stvarni canonical dataset.
    minimum_date, maximum_date = get_canonical_promet_date_bounds(
        db,
        tenant_code=tenant_code,
        mode=PrometMode.RS_SMALL_ENTREPRENEUR,
        date_from=date_from,
        date_to=date_to,
    )

    if minimum_date is None or maximum_date is None:
        return ()

    return (
        PrometDateSpan(
            start=(
                date_from
                if date_from is not None
                else minimum_date
            ),
            end=(
                date_to
                if date_to is not None
                else maximum_date
            ),
        ),
    )


def _profile_boundary_dates(
    db: Session,
    *,
    tenant_code: str,
    span: PrometDateSpan,
) -> tuple[date, ...]:
    boundaries = {
        span.start,
        span.end + timedelta(days=1),
    }

    for model in (
        TenantTaxProfileSettings,
        TenantBusinessProfileSettings,
    ):
        rows = db.execute(
            select(model).where(
                model.tenant_code == tenant_code,
                model.effective_from.is_not(None),
                model.effective_from <= span.end,
                or_(
                    model.effective_to.is_(None),
                    model.effective_to >= span.start,
                ),
            )
        ).scalars().all()

        for row in rows:
            if (
                row.effective_from is not None
                and span.start < row.effective_from <= span.end
            ):
                boundaries.add(row.effective_from)

            if (
                row.effective_to is not None
                and span.start <= row.effective_to < span.end
            ):
                boundaries.add(
                    row.effective_to + timedelta(days=1)
                )

    return tuple(sorted(boundaries))


def _eligibility_as_of(
    db: Session,
    *,
    tenant_code: str,
    as_of: date,
    requested_span: PrometDateSpan,
) -> PrometEligibility:
    try:
        tax_profile = get_tax_profile_as_of(
            db,
            tenant_code,
            as_of,
        )
    except ProfilePeriodIntegrityError as exc:
        raise PrometProfileCoverageError(
            date_from=requested_span.start,
            date_to=requested_span.end,
        ) from exc

    # Tax profil je osnovni tenant classification source.
    # Bez verified Tax coverage istorijski scope nije dokaziv.
    if tax_profile is None:
        raise PrometProfileCoverageError(
            date_from=requested_span.start,
            date_to=requested_span.end,
        )

    tax_only = resolve_promet_eligibility(
        entity=tax_profile.entity,
        regime=tax_profile.regime,
        scenario_key=tax_profile.scenario_key,
        has_additional_activity=tax_profile.has_additional_activity,
    )

    # Neke eligibility odluke su potpuno određene Tax profilom.
    # Primjer: RS small entrepreneur i RS books.
    #
    # Business history ne smije uticati na scenario koji njegove činjenice
    # uopšte ne koristi.
    business_fields = {
        "sales_locations_count",
        "sells_to_consumers",
        "daily_cash_turnover_covered_elsewhere",
        "has_noncash_sales_to_legal_entities",
    }

    needs_business = (
        tax_only.status is PrometEligibilityStatus.NEEDS_CONFIGURATION
        and any(
            field in business_fields
            for field in tax_only.blocking_fields
        )
    )

    if not needs_business:
        return tax_only

    try:
        business_profile = get_business_profile_as_of(
            db,
            tenant_code,
            as_of,
        )
    except ProfilePeriodIntegrityError as exc:
        raise PrometProfileCoverageError(
            date_from=requested_span.start,
            date_to=requested_span.end,
        ) from exc

    return resolve_promet_eligibility(
        entity=tax_profile.entity,
        regime=tax_profile.regime,
        scenario_key=tax_profile.scenario_key,
        has_additional_activity=tax_profile.has_additional_activity,
        sales_locations_count=(
            business_profile.sales_locations_count
            if business_profile is not None
            else None
        ),
        sells_to_consumers=(
            business_profile.sells_to_consumers
            if business_profile is not None
            else None
        ),
        daily_cash_turnover_covered_elsewhere=(
            business_profile.daily_cash_turnover_covered_elsewhere
            if business_profile is not None
            else None
        ),
        has_noncash_sales_to_legal_entities=(
            business_profile.has_noncash_sales_to_legal_entities
            if business_profile is not None
            else None
        ),
    )


def _eligibility_identity(
    eligibility: PrometEligibility,
) -> tuple[str, ...]:
    if eligibility.status is PrometEligibilityStatus.APPLICABLE:
        return (
            eligibility.status.value,
            (
                eligibility.mode.value
                if eligibility.mode is not None
                else ""
            ),
        )

    return (
        eligibility.status.value,
        eligibility.reason_code,
        *sorted(eligibility.blocking_fields),
    )


def resolve_promet_period(
    db: Session,
    *,
    tenant_code: str,
    year: int | None = None,
    month: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> PrometPeriodResolution:
    """
    Resolve one Promet request against effective-dated tenant profile history.

    Explicit bounded scopes require verified historical coverage.
    Unbounded/month-only scopes derive their historical spans from the
    canonical Promet source. If no historical span exists, current eligibility
    remains authoritative for the empty/current request.
    """
    spans = _resolve_requested_spans(
        db,
        tenant_code=tenant_code,
        year=year,
        month=month,
        date_from=date_from,
        date_to=date_to,
    )

    if not spans:
        return PrometPeriodResolution(
            eligibility=resolve_tenant_promet_eligibility(
                db=db,
                tenant_code=tenant_code,
            ),
            spans=(),
        )

    resolved: list[PrometEligibility] = []

    for span in spans:
        boundaries = _profile_boundary_dates(
            db,
            tenant_code=tenant_code,
            span=span,
        )

        # Posljednji boundary je end + 1 i nije početak segmenta.
        for segment_start in boundaries[:-1]:
            resolved.append(
                _eligibility_as_of(
                    db,
                    tenant_code=tenant_code,
                    as_of=segment_start,
                    requested_span=span,
                )
            )

    if not resolved:
        return PrometPeriodResolution(
            eligibility=resolve_tenant_promet_eligibility(
                db=db,
                tenant_code=tenant_code,
            ),
            spans=spans,
        )

    identities = {
        _eligibility_identity(eligibility)
        for eligibility in resolved
    }

    if len(identities) != 1:
        raise PrometProfileModeChangedError(
            date_from=spans[0].start,
            date_to=spans[-1].end,
        )

    return PrometPeriodResolution(
        eligibility=resolved[0],
        spans=spans,
    )
