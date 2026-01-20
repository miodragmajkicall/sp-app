# /home/miso/dev/sp-app/sp-app/backend/app/routes/settings.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple, List

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
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.tenant_security import require_tenant_code, ensure_tenant_exists
from app.models import (
    TenantProfileSettings,
    TenantTaxProfileSettings,
    TenantSubscriptionSettings,
    TenantAsset,
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
