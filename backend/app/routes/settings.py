# /home/miso/dev/sp-app/sp-app/backend/app/routes/settings.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple, List, Any

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    UploadFile,
    File,
    Response,
    status,
    Query,
)
from fastapi.responses import FileResponse
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.db import get_session
from app.tenant_security import require_tenant_code, ensure_tenant_exists
from app.models import (
    TenantProfileSettings,
    TenantTaxProfileSettings,
    TenantSubscriptionSettings,
    TenantAsset,
    AppConstantsSet,
)
from app.schemas.settings import (
    ProfileSettingsRead,
    ProfileSettingsUpsert,
    TaxProfileSettingsRead,
    TaxProfileSettingsUpsert,
    TaxScenarioOption,
    SubscriptionSettingsRead,
    SubscriptionSettingsUpsert,
)
from app.schemas.settings_ui import (
    TaxProfileUiSchemaResponse,
    UiScenarioOption,
    UiField,
    UiResolvedValue,
)

router = APIRouter(prefix="/settings", tags=["settings"])

TENANT_ASSETS_ROOT = Path(os.getenv("TENANT_ASSETS_DIR", "data/tenant_assets"))
MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2MB
ALLOWED_LOGO_MIME = {"image/png", "image/jpeg", "image/webp"}


def _ensure_assets_root() -> None:
    TENANT_ASSETS_ROOT.mkdir(parents=True, exist_ok=True)


def _safe_filename(original: str | None) -> str:
    if not original:
        return "uploaded-file"
    name = os.path.basename(original)
    name = name.replace("/", "_").replace("\\", "_")
    return name or "uploaded-file"


def _try_convert_logo_to_png(file_bytes: bytes) -> Tuple[bytes, str]:
    """
    Pokušava konvertovati input sliku u PNG + resize (max 512px).
    Ako Pillow nije dostupan ili konverzija padne, vraća originalne bajtove
    i content_type = 'application/octet-stream' (kasnije ćemo doraditi).
    """
    try:
        from PIL import Image  # type: ignore
        import io

        with Image.open(io.BytesIO(file_bytes)) as im:
            im = im.convert("RGBA")
            im.thumbnail((512, 512))  # in-place resize, čuva aspect ratio

            out = io.BytesIO()
            im.save(out, format="PNG", optimize=True)
            return out.getvalue(), "image/png"
    except Exception:
        return file_bytes, "application/octet-stream"


def _delete_asset_file_safely(asset: TenantAsset) -> None:
    if not asset.storage_path:
        return
    full_path = TENANT_ASSETS_ROOT / asset.storage_path
    try:
        if full_path.exists():
            full_path.unlink()
    except OSError:
        pass


def _get_or_create_profile_row(db: Session, tenant: str) -> TenantProfileSettings:
    row = db.execute(
        select(TenantProfileSettings).where(TenantProfileSettings.tenant_code == tenant)
    ).scalar_one_or_none()
    if row is None:
        row = TenantProfileSettings(
            tenant_code=tenant,
            business_name=f"Tenant {tenant}",
        )
        db.add(row)
        db.flush()
    return row


def _scenario_catalog_for(entity: str, has_additional_activity: bool) -> List[TaxScenarioOption]:
    """
    Minimalni scenario katalog (Inkrement 1).
    Kasnije (Inkrement 2) možemo ga vezati na Admin Constants i effective-dated logiku.
    """
    entity_norm = (entity or "RS").strip()

    if entity_norm == "RS":
        if has_additional_activity:
            return [
                TaxScenarioOption(
                    key="rs_supplementary",
                    label="RS – Dopunska djelatnost (uz zaposlenje)",
                    hint="Dopunska djelatnost: SP uz postojeće zaposlenje.",
                    entity="RS",
                )
            ]
        return [
            TaxScenarioOption(
                key="rs_primary",
                label="RS – Osnovna djelatnost",
                hint="Osnovna djelatnost: samostalni preduzetnik (glavna djelatnost).",
                entity="RS",
            )
        ]

    if entity_norm == "FBiH":
        return [
            TaxScenarioOption(
                key="fbih_obrt",
                label="FBiH – Obrt",
                hint="Registracija u formi obrta (osnovni poslovni režim).",
                entity="FBiH",
            ),
            TaxScenarioOption(
                key="fbih_slobodna",
                label="FBiH – Slobodna djelatnost",
                hint="Slobodno zanimanje / samostalna djelatnost u FBiH.",
                entity="FBiH",
            ),
        ]

    # Brcko / BD
    return [
        TaxScenarioOption(
            key="bd_samostalna",
            label="Brčko – Samostalna djelatnost",
            hint="Brčko distrikt: samostalni preduzetnik (osnovni režim).",
            entity="Brcko",
        )
    ]


# -------------------------------
# UI schema helpers (Settings Tax)
# -------------------------------

def _entity_to_jurisdiction(entity: str) -> str:
    # Admin constants koriste RS / FBiH / BD
    if entity == "RS":
        return "RS"
    if entity == "FBiH":
        return "FBiH"
    return "BD"  # Brcko -> BD


def _default_scenario_for_entity(entity: str) -> str:
    if entity == "RS":
        return "rs_primary"
    if entity == "FBiH":
        return "fbih_obrt"
    return "bd_samostalna"


def _ui_scenario_options_for_entity(entity: str) -> list[UiScenarioOption]:
    # Namjerno: vraćamo kompletan katalog po entitetu (usklađeno sa FE dropdown-om)
    if entity == "RS":
        return [
            UiScenarioOption(
                key="rs_primary",
                label="RS – Osnovna djelatnost",
                hint="Osnovna djelatnost (primary).",
                entity="RS",
            ),
            UiScenarioOption(
                key="rs_supplementary",
                label="RS – Dopunska djelatnost (uz zaposlenje)",
                hint="Dopunska djelatnost (supplementary).",
                entity="RS",
            ),
        ]
    if entity == "FBiH":
        return [
            UiScenarioOption(
                key="fbih_obrt",
                label="FBiH – Obrt",
                hint="Obrt i srodne djelatnosti.",
                entity="FBiH",
            ),
            UiScenarioOption(
                key="fbih_slobodna",
                label="FBiH – Slobodna djelatnost",
                hint="Slobodna zanimanja.",
                entity="FBiH",
            ),
        ]
    return [
        UiScenarioOption(
            key="bd_samostalna",
            label="Brčko – Samostalna djelatnost",
            hint="Jedinstvena šema za BD.",
            entity="Brcko",
        )
    ]


def _find_current_constants_set(
    *,
    db: Session,
    jurisdiction: str,
    scenario_key: str,
    as_of,  # date
) -> Optional[AppConstantsSet]:
    stmt = (
        select(AppConstantsSet)
        .where(
            AppConstantsSet.jurisdiction == jurisdiction,
            AppConstantsSet.scenario_key == scenario_key,
            AppConstantsSet.effective_from <= as_of,
            or_(AppConstantsSet.effective_to.is_(None), AppConstantsSet.effective_to >= as_of),
        )
        .order_by(AppConstantsSet.effective_from.desc(), AppConstantsSet.id.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def _payload_currency(payload: object) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    base = payload.get("base")
    if isinstance(base, dict):
        cur = base.get("currency")
        if isinstance(cur, str) and cur.strip():
            return cur.strip()
    return None


def _get_nested(payload: object, dotted_key: str) -> Any:
    if not isinstance(payload, dict):
        return None

    current: Any = payload
    for part in dotted_key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)

    return current


def _format_decimal_rate(value: Any) -> Optional[str]:
    if isinstance(value, (int, float)):
        return f"{float(value) * 100:.2f}%"
    return None


def _format_percent_value(value: Any) -> Optional[str]:
    if isinstance(value, (int, float)):
        return f"{float(value):.2f}%"
    return None


def _format_bam(value: Any) -> Optional[str]:
    if isinstance(value, (int, float)):
        return f"{float(value):.2f} BAM"
    return None


def _format_generic_value(value: Any, unit: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    if unit == "decimal":
        return _format_decimal_rate(value)

    if unit == "%":
        return _format_percent_value(value)

    if unit == "BAM":
        return _format_bam(value)

    if isinstance(value, bool):
        return "Da" if value else "Ne"

    if isinstance(value, (int, float)):
        return f"{float(value):.2f}"

    if isinstance(value, str):
        return value

    return str(value)


def _append_resolved_value(
    items: list[UiResolvedValue],
    *,
    section: str,
    key: str,
    label: str,
    value: Any,
    unit: Optional[str],
) -> None:
    formatted = _format_generic_value(value, unit)
    if formatted is None:
        return

    items.append(
        UiResolvedValue(
            key=key,
            label=label,
            value=formatted,
            unit=unit,
            section=section,  # type: ignore[arg-type]
        )
    )


def _resolved_values_from_payload(
    *,
    payload: object,
    entity: str,
    scenario_key: str,
    currency: str,
    base_fields: list[UiField],
    contrib_rate_fields: list[UiField],
    tax_fields: list[UiField],
    vat_fields: list[UiField],
) -> list[UiResolvedValue]:
    if not isinstance(payload, dict):
        return []

    resolved: list[UiResolvedValue] = []

    # Meta / currency
    _append_resolved_value(
        resolved,
        section="meta",
        key="base.currency",
        label="Valuta",
        value=currency,
        unit=None,
    )

    # Base fields defined by UI schema
    for field in base_fields:
        _append_resolved_value(
            resolved,
            section="base",
            key=field.key,
            label=field.label,
            value=_get_nested(payload, field.key),
            unit=field.unit,
        )

    # Dodatna calculated base polja ako postoje u payload-u
    calculated_base_keys = [
        ("base.calculated_contrib_base_bam", "Izračunata osnovica doprinosa", "BAM"),
        ("base.min_contrib_base_bam", "Minimalna osnovica doprinosa", "BAM"),
        ("base.max_contrib_base_bam", "Maksimalna osnovica doprinosa", "BAM"),
    ]
    for key, label, unit in calculated_base_keys:
        _append_resolved_value(
            resolved,
            section="base",
            key=key,
            label=label,
            value=_get_nested(payload, key),
            unit=unit,
        )

    # Contribution rates
    for field in contrib_rate_fields:
        _append_resolved_value(
            resolved,
            section="contributions",
            key=field.key,
            label=field.label,
            value=_get_nested(payload, field.key),
            unit=field.unit,
        )

    # Dodatni contribution amount/limit ključevi ako postoje
    contribution_extra_keys = [
        ("contributions.pension_amount_bam", "PIO iznos", "BAM"),
        ("contributions.health_amount_bam", "Zdravstvo iznos", "BAM"),
        ("contributions.unemployment_amount_bam", "Nezaposlenost iznos", "BAM"),
        ("contributions.child_amount_bam", "Dječija zaštita iznos", "BAM"),
    ]
    for key, label, unit in contribution_extra_keys:
        _append_resolved_value(
            resolved,
            section="contributions",
            key=key,
            label=label,
            value=_get_nested(payload, key),
            unit=unit,
        )

    # Tax fields
    for field in tax_fields:
        _append_resolved_value(
            resolved,
            section="tax",
            key=field.key,
            label=field.label,
            value=_get_nested(payload, field.key),
            unit=field.unit,
        )

    # VAT fields
    for field in vat_fields:
        _append_resolved_value(
            resolved,
            section="vat",
            key=field.key,
            label=field.label,
            value=_get_nested(payload, field.key),
            unit=field.unit,
        )

    # Scenario-specific polish: ako RS supplementary nema child/unemployment/puno base polja,
    # i dalje neće biti prikazana jer ih append preskače ako ih nema u payload-u.
    _ = entity
    _ = scenario_key

    return resolved


def _ui_fields_for(entity: str, scenario_key: str) -> tuple[list[str], list[UiField], list[UiField], list[UiField], list[UiField]]:
    """
    Returns:
      (components, base_fields, contrib_rate_fields, tax_fields, vat_fields)
    """
    # contribution components by scenario (align with FE payload builder)
    if entity == "RS":
        if scenario_key == "rs_supplementary":
            components = ["pension"]
            contrib_rate_fields = [
                UiField(key="contributions.pension_rate", label="PIO stopa", hint="Decimal (npr. 0.18)", unit="decimal"),
            ]
        else:
            components = ["pension", "health", "unemployment", "child"]
            contrib_rate_fields = [
                UiField(key="contributions.pension_rate", label="PIO stopa", hint="Decimal (npr. 0.18)", unit="decimal"),
                UiField(key="contributions.health_rate", label="Zdravstvo stopa", hint="Decimal (npr. 0.12)", unit="decimal"),
                UiField(key="contributions.unemployment_rate", label="Nezaposlenost stopa", hint="Decimal (npr. 0.015)", unit="decimal"),
                UiField(key="contributions.child_rate", label="Dječija zaštita stopa", hint="Decimal (npr. 0.017)", unit="decimal"),
            ]

        base_fields = [
            UiField(
                key="base.avg_gross_wage_prev_year_bam",
                label="Prosječna bruto plata (prethodna godina)",
                hint="KM. Koristi se za računanje osnovice doprinosa.",
                required=False,
                unit="BAM",
            ),
            UiField(
                key="base.contrib_base_percent_of_avg_gross",
                label="% prosječne bruto plate za osnovicu",
                hint="Procenat (0–100).",
                required=False,
                unit="%",
            ),
        ]
    elif entity == "FBiH":
        components = ["pension", "health", "unemployment"]
        base_fields = [
            UiField(
                key="base.monthly_contrib_base_bam",
                label="Mjesečna osnovica doprinosa",
                hint="KM. FBiH: fiksna mjesečna osnovica.",
                required=True,
                unit="BAM",
            )
        ]
        contrib_rate_fields = [
            UiField(key="contributions.pension_rate", label="PIO stopa", hint="Decimal (npr. 0.18)", unit="decimal"),
            UiField(key="contributions.health_rate", label="Zdravstvo stopa", hint="Decimal (npr. 0.12)", unit="decimal"),
            UiField(key="contributions.unemployment_rate", label="Nezaposlenost stopa", hint="Decimal (npr. 0.015)", unit="decimal"),
        ]
    else:
        # Brcko
        components = ["pension", "health", "unemployment"]
        base_fields = [
            UiField(
                key="base.monthly_contrib_base_bam",
                label="Mjesečna osnovica doprinosa",
                hint="KM. BD: fiksna mjesečna osnovica (V1 UI/Spec).",
                required=True,
                unit="BAM",
            )
        ]
        contrib_rate_fields = [
            UiField(key="contributions.pension_rate", label="PIO stopa", hint="Decimal (npr. 0.18)", unit="decimal"),
            UiField(key="contributions.health_rate", label="Zdravstvo stopa", hint="Decimal (npr. 0.12)", unit="decimal"),
            UiField(key="contributions.unemployment_rate", label="Nezaposlenost stopa", hint="Decimal (npr. 0.015)", unit="decimal"),
        ]

    tax_fields = [
        UiField(key="tax.income_tax_rate", label="Porez na dohodak stopa", hint="Decimal (npr. 0.10)", unit="decimal"),
        UiField(key="tax.flat_tax_monthly_amount_bam", label="Paušalni porez (mjesečno)", hint="KM (opciono)", unit="BAM"),
    ]
    vat_fields = [
        UiField(key="vat.standard_rate", label="PDV standardna stopa", hint="Decimal (npr. 0.17)", unit="decimal"),
        UiField(key="vat.entry_threshold_bam", label="PDV prag ulaska", hint="KM (opciono)", unit="BAM"),
    ]

    return components, base_fields, contrib_rate_fields, tax_fields, vat_fields


# ======================================================
#  PROFILE
# ======================================================
@router.get("/profile", response_model=ProfileSettingsRead)
def get_profile_settings(
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(get_session),
):
    tenant = require_tenant_code(x_tenant_code)
    ensure_tenant_exists(db, tenant)

    row = db.execute(
        select(TenantProfileSettings).where(TenantProfileSettings.tenant_code == tenant)
    ).scalar_one_or_none()

    if row is None:
        return ProfileSettingsRead(
            tenant_code=tenant,
            business_name=f"Tenant {tenant}",
        )

    return row


@router.put("/profile", response_model=ProfileSettingsRead)
def upsert_profile_settings(
    payload: ProfileSettingsUpsert,
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(get_session),
):
    """
    Profesionalno rješenje: zadržavamo PUT, ali opcionalna polja tretiramo patch-semantikom.
    Time sprječavamo nenamjerno nuliranje loga i drugih vrijednosti kada polje nije poslato.
    """
    tenant = require_tenant_code(x_tenant_code)
    ensure_tenant_exists(db, tenant)

    row = db.execute(
        select(TenantProfileSettings).where(TenantProfileSettings.tenant_code == tenant)
    ).scalar_one_or_none()

    fields_set = payload.model_fields_set  # pydantic v2: koja su polja eksplicitno poslata

    if row is None:
        row = TenantProfileSettings(
            tenant_code=tenant,
            business_name=payload.business_name,
        )
        db.add(row)

        # Opcionalna polja postavljamo samo ako su poslata u payload-u
        if "address" in fields_set:
            row.address = payload.address
        if "tax_id" in fields_set:
            row.tax_id = payload.tax_id
        if "logo_attachment_id" in fields_set:
            row.logo_attachment_id = payload.logo_attachment_id
        if "logo_asset_id" in fields_set:
            row.logo_asset_id = payload.logo_asset_id

        db.commit()
        db.refresh(row)
        return row

    # business_name je obavezno i uvijek se setuje
    row.business_name = payload.business_name

    # Opcionalna polja: mijenjamo samo ako su eksplicitno poslata
    if "address" in fields_set:
        row.address = payload.address
    if "tax_id" in fields_set:
        row.tax_id = payload.tax_id

    # Back-compat (staro):
    if "logo_attachment_id" in fields_set:
        row.logo_attachment_id = payload.logo_attachment_id

    # Novo:
    if "logo_asset_id" in fields_set:
        row.logo_asset_id = payload.logo_asset_id

    db.commit()
    db.refresh(row)
    return row


# ---------------- PROFILE LOGO (upload/preview/delete) ----------------

@router.post(
    "/profile/logo",
    response_model=ProfileSettingsRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload logo za profil tenanta",
)
def upload_profile_logo(
    db: Session = Depends(get_session),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    file: UploadFile = File(..., description="Logo slika (PNG/JPG/WebP)"),
) -> ProfileSettingsRead:
    tenant = require_tenant_code(x_tenant_code)
    ensure_tenant_exists(db, tenant)

    if file is None:
        raise HTTPException(status_code=400, detail="File is required")

    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_LOGO_MIME:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content_type '{content_type}'. Allowed: png/jpeg/webp",
        )

    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if len(file_bytes) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=400, detail="Logo file is too large (max 2MB)")

    _ensure_assets_root()
    profile = _get_or_create_profile_row(db, tenant)

    # ako postoji prethodni logo_asset_id, izbriši ga (DB + fajl) nakon kreiranja novog
    prev_asset: TenantAsset | None = None
    if profile.logo_asset_id is not None:
        prev_asset = db.execute(
            select(TenantAsset).where(
                TenantAsset.id == profile.logo_asset_id,
                TenantAsset.tenant_code == tenant,
            )
        ).scalar_one_or_none()

    original_name = _safe_filename(file.filename)

    # konvertuj u PNG ako je moguće
    converted_bytes, converted_ct = _try_convert_logo_to_png(file_bytes)
    store_ct = converted_ct if converted_ct != "application/octet-stream" else content_type
    store_bytes = converted_bytes
    store_name = "logo.png" if store_ct == "image/png" else original_name

    # 1) kreiraj asset red sa TEMP path
    asset = TenantAsset(
        tenant_code=tenant,
        kind="logo",
        filename=store_name,
        content_type=store_ct,
        size_bytes=len(store_bytes),
        storage_path="__TEMP__",
    )
    db.add(asset)
    db.flush()  # dobije ID

    tenant_dir = TENANT_ASSETS_ROOT / tenant
    tenant_dir.mkdir(parents=True, exist_ok=True)

    relative_path = f"{tenant}/{asset.id}_{store_name}"
    full_path = TENANT_ASSETS_ROOT / relative_path

    try:
        full_path.write_bytes(store_bytes)
    except OSError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to store logo file: {exc}") from exc

    asset.storage_path = str(relative_path)
    profile.logo_asset_id = asset.id

    # opcionalno: ako želiš potpuno prebacivanje na novo, možeš obrisati stari logo_attachment_id
    # profile.logo_attachment_id = None

    db.commit()
    db.refresh(profile)

    # sada brišemo prethodni asset (ako postoji)
    if prev_asset is not None:
        _delete_asset_file_safely(prev_asset)
        db.delete(prev_asset)
        db.commit()

    return profile


@router.get(
    "/profile/logo",
    response_class=FileResponse,
    summary="Preuzmi/preview logo za profil tenanta",
)
def get_profile_logo(
    db: Session = Depends(get_session),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
) -> FileResponse:
    tenant = require_tenant_code(x_tenant_code)
    ensure_tenant_exists(db, tenant)

    profile = db.execute(
        select(TenantProfileSettings).where(TenantProfileSettings.tenant_code == tenant)
    ).scalar_one_or_none()

    if profile is None or profile.logo_asset_id is None:
        raise HTTPException(status_code=404, detail="Logo not set")

    asset = db.execute(
        select(TenantAsset).where(
            TenantAsset.id == profile.logo_asset_id,
            TenantAsset.tenant_code == tenant,
        )
    ).scalar_one_or_none()

    if asset is None or not asset.storage_path:
        raise HTTPException(status_code=404, detail="Logo not found")

    full_path = TENANT_ASSETS_ROOT / asset.storage_path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Logo file not found")

    return FileResponse(
        path=full_path,
        media_type=asset.content_type or "application/octet-stream",
        filename=asset.filename or "logo.bin",
    )


@router.delete(
    "/profile/logo",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Obriši logo za profil tenanta",
)
def delete_profile_logo(
    db: Session = Depends(get_session),
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
) -> Response:
    tenant = require_tenant_code(x_tenant_code)
    ensure_tenant_exists(db, tenant)

    profile = db.execute(
        select(TenantProfileSettings).where(TenantProfileSettings.tenant_code == tenant)
    ).scalar_one_or_none()

    if profile is None or profile.logo_asset_id is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    asset = db.execute(
        select(TenantAsset).where(
            TenantAsset.id == profile.logo_asset_id,
            TenantAsset.tenant_code == tenant,
        )
    ).scalar_one_or_none()

    # nuliraj u profilu
    profile.logo_asset_id = None
    db.commit()

    if asset is not None:
        _delete_asset_file_safely(asset)
        db.delete(asset)
        db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ======================================================
#  TAX PROFILE
# ======================================================
@router.get("/tax", response_model=TaxProfileSettingsRead)
def get_tax_profile(
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(get_session),
):
    tenant = require_tenant_code(x_tenant_code)
    ensure_tenant_exists(db, tenant)

    row = db.execute(
        select(TenantTaxProfileSettings).where(
            TenantTaxProfileSettings.tenant_code == tenant
        )
    ).scalar_one_or_none()

    if row is None:
        return TaxProfileSettingsRead(
            tenant_code=tenant,
            entity="RS",
            regime="pausal",
            scenario_key=None,
            has_additional_activity=False,
        )

    return row


@router.put("/tax", response_model=TaxProfileSettingsRead)
def upsert_tax_profile(
    payload: TaxProfileSettingsUpsert,
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(get_session),
):
    tenant = require_tenant_code(x_tenant_code)
    ensure_tenant_exists(db, tenant)

    row = db.execute(
        select(TenantTaxProfileSettings).where(
            TenantTaxProfileSettings.tenant_code == tenant
        )
    ).scalar_one_or_none()

    if row is None:
        row = TenantTaxProfileSettings(
            tenant_code=tenant,
            entity=payload.entity,
            regime=payload.regime,
        )
        db.add(row)

    row.entity = payload.entity
    row.regime = payload.regime
    row.has_additional_activity = payload.has_additional_activity
    row.monthly_pension = payload.monthly_pension
    row.monthly_health = payload.monthly_health
    row.monthly_unemployment = payload.monthly_unemployment

    # Novo: scenario_key (back-compat: može biti None)
    row.scenario_key = payload.scenario_key

    db.commit()
    db.refresh(row)
    return row


@router.get(
    "/tax/scenarios",
    response_model=list[TaxScenarioOption],
    summary="Scenario katalog za Settings (dropdown)",
)
def get_tax_scenarios_catalog(
    entity: str = Query("RS", description="RS | FBiH | Brcko"),
    has_additional_activity: bool = Query(False, description="Za RS razlikuje osnovnu i dopunsku djelatnost"),
) -> list[TaxScenarioOption]:
    return _scenario_catalog_for(entity=entity, has_additional_activity=has_additional_activity)


@router.get(
    "/tax/ui-schema",
    response_model=TaxProfileUiSchemaResponse,
    summary="UI schema za Settings -> Poreski profil (povezano sa Admin Constants)",
)
def get_tax_profile_ui_schema(
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    as_of: Optional[str] = Query(None, description="YYYY-MM-DD (opciono). Default = danas (server)."),
    db: Session = Depends(get_session),
) -> TaxProfileUiSchemaResponse:
    """
    Vraća informaciju UI-u:
    - koji su validni scenariji za entitet
    - koja polja imaju smisla (base / contribution components)
    - meta o trenutno aktivnom Admin Constants setu (ako postoji)
    - konkretne resolved vrijednosti iz payload-a aktivnog constants seta
    """
    tenant = require_tenant_code(x_tenant_code)
    ensure_tenant_exists(db, tenant)

    # učitaj tenant tax settings (ako nema, default)
    row = db.execute(
        select(TenantTaxProfileSettings).where(TenantTaxProfileSettings.tenant_code == tenant)
    ).scalar_one_or_none()

    entity = (row.entity if row is not None else "RS") or "RS"
    scenario_key = (row.scenario_key if row is not None else None)
    if not scenario_key:
        scenario_key = _default_scenario_for_entity(entity)

    # parse as_of
    from datetime import date as _date  # local import to avoid clutter
    if as_of:
        try:
            as_of_date = _date.fromisoformat(as_of)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid as_of. Expected YYYY-MM-DD.") from exc
    else:
        as_of_date = _date.today()

    jurisdiction = _entity_to_jurisdiction(entity)
    cur_set = _find_current_constants_set(
        db=db,
        jurisdiction=jurisdiction,
        scenario_key=scenario_key,
        as_of=as_of_date,
    )

    payload = cur_set.payload if cur_set is not None else None
    currency = _payload_currency(payload) or "BAM"

    components, base_fields, contrib_rate_fields, tax_fields, vat_fields = _ui_fields_for(
        entity=entity,
        scenario_key=scenario_key,
    )

    resolved_values = _resolved_values_from_payload(
        payload=payload,
        entity=entity,
        scenario_key=scenario_key,
        currency=currency,
        base_fields=base_fields,
        contrib_rate_fields=contrib_rate_fields,
        tax_fields=tax_fields,
        vat_fields=vat_fields,
    )

    return TaxProfileUiSchemaResponse(
        entity=entity,  # type: ignore[arg-type]
        scenario_key=scenario_key,
        allowed_regimes=["pausal", "two_percent"],
        scenario_options=_ui_scenario_options_for_entity(entity),
        contribution_components=components,
        base_fields=base_fields,
        contribution_rate_fields=contrib_rate_fields,
        tax_fields=tax_fields,
        vat_fields=vat_fields,
        resolved_values=resolved_values,
        constants_set_id=(cur_set.id if cur_set is not None else None),
        constants_effective_from=(cur_set.effective_from.isoformat() if cur_set is not None else None),
        constants_effective_to=(cur_set.effective_to.isoformat() if (cur_set is not None and cur_set.effective_to is not None) else None),
        constants_currency=currency,
    )


# ======================================================
#  SUBSCRIPTION
# ======================================================
@router.get("/subscription", response_model=SubscriptionSettingsRead)
def get_subscription(
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(get_session),
):
    tenant = require_tenant_code(x_tenant_code)
    ensure_tenant_exists(db, tenant)

    row = db.execute(
        select(TenantSubscriptionSettings).where(
            TenantSubscriptionSettings.tenant_code == tenant
        )
    ).scalar_one_or_none()

    if row is None:
        return SubscriptionSettingsRead(
            tenant_code=tenant,
            plan="Basic",
        )

    return row


@router.put("/subscription", response_model=SubscriptionSettingsRead)
def upsert_subscription(
    payload: SubscriptionSettingsUpsert,
    x_tenant_code: Optional[str] = Header(None, alias="X-Tenant-Code"),
    db: Session = Depends(get_session),
):
    tenant = require_tenant_code(x_tenant_code)
    ensure_tenant_exists(db, tenant)

    row = db.execute(
        select(TenantSubscriptionSettings).where(
            TenantSubscriptionSettings.tenant_code == tenant
        )
    ).scalar_one_or_none()

    if row is None:
        row = TenantSubscriptionSettings(
            tenant_code=tenant,
            plan=payload.plan,
        )
        db.add(row)

    row.plan = payload.plan

    db.commit()
    db.refresh(row)
    return row