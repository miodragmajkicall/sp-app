# /home/miso/dev/sp-app/sp-app/backend/app/schemas/constants.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


BaseConfig = ConfigDict(from_attributes=True)

# Central catalog (backend validation)
# V1 scenario katalog po tehničkim zahtjevima:
# RS: osnovna + dopunska
# FBiH: obrt + slobodna zanimanja
# BD: samostalna djelatnost
ALLOWED_SCENARIOS: dict[str, set[str]] = {
    "RS": {"rs_primary", "rs_supplementary"},
    "FBiH": {"fbih_obrt", "fbih_slobodna"},
    "BD": {"bd_samostalna"},
}


def _validate_scenario_for_jurisdiction(jurisdiction: str, scenario_key: str) -> None:
    allowed = ALLOWED_SCENARIOS.get(jurisdiction)
    if not allowed:
        raise ValueError(f"Unsupported jurisdiction: {jurisdiction}")
    if scenario_key not in allowed:
        raise ValueError(
            f"Invalid scenario_key '{scenario_key}' for jurisdiction '{jurisdiction}'. "
            f"Allowed: {sorted(list(allowed))}"
        )


CANONICAL_LEGAL_CONSTANTS_SCHEMA_VERSION = "legal-constants-v1"


def _finite_decimal(value: Decimal | None, field_name: str) -> Decimal | None:
    if value is None:
        return None
    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return value


class LegalConstantsBaseV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: Optional[str] = None

    avg_gross_wage_prev_year_bam: Optional[Decimal] = None
    contrib_base_percent_of_avg_gross: Optional[Decimal] = None
    calculated_contrib_base_bam: Optional[Decimal] = None

    monthly_contrib_base_bam: Optional[Decimal] = None

    avg_gross_prev_year_bam: Optional[Decimal] = None
    base_percent_of_avg_gross: Optional[Decimal] = None

    @field_validator(
        "avg_gross_wage_prev_year_bam",
        "calculated_contrib_base_bam",
        "monthly_contrib_base_bam",
        "avg_gross_prev_year_bam",
    )
    @classmethod
    def _validate_nonnegative_amount(
        cls,
        value: Decimal | None,
        info,
    ) -> Decimal | None:
        value = _finite_decimal(value, info.field_name)
        if value is not None and value < 0:
            raise ValueError(f"{info.field_name} must be >= 0")
        return value

    @field_validator(
        "contrib_base_percent_of_avg_gross",
        "base_percent_of_avg_gross",
    )
    @classmethod
    def _validate_percent(
        cls,
        value: Decimal | None,
        info,
    ) -> Decimal | None:
        value = _finite_decimal(value, info.field_name)
        if value is not None and not Decimal("0") <= value <= Decimal("100"):
            raise ValueError(f"{info.field_name} must be between 0 and 100")
        return value

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("currency must not be blank")
        return value


class LegalConstantsVatV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    standard_rate: Optional[Decimal] = None
    entry_threshold_bam: Optional[Decimal] = None

    @field_validator("standard_rate")
    @classmethod
    def _validate_rate(cls, value: Decimal | None) -> Decimal | None:
        value = _finite_decimal(value, "standard_rate")
        if value is not None and not Decimal("0") <= value <= Decimal("1"):
            raise ValueError("standard_rate must be between 0 and 1")
        return value

    @field_validator("entry_threshold_bam")
    @classmethod
    def _validate_threshold(cls, value: Decimal | None) -> Decimal | None:
        value = _finite_decimal(value, "entry_threshold_bam")
        if value is not None and value < 0:
            raise ValueError("entry_threshold_bam must be >= 0")
        return value


class LegalConstantsTaxV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    income_tax_rate: Optional[Decimal] = None
    flat_costs_rate: Optional[Decimal] = None
    flat_tax_monthly_amount_bam: Optional[Decimal] = None

    @field_validator("income_tax_rate", "flat_costs_rate")
    @classmethod
    def _validate_rate(
        cls,
        value: Decimal | None,
        info,
    ) -> Decimal | None:
        value = _finite_decimal(value, info.field_name)
        if value is not None and not Decimal("0") <= value <= Decimal("1"):
            raise ValueError(f"{info.field_name} must be between 0 and 1")
        return value

    @field_validator("flat_tax_monthly_amount_bam")
    @classmethod
    def _validate_amount(cls, value: Decimal | None) -> Decimal | None:
        value = _finite_decimal(value, "flat_tax_monthly_amount_bam")
        if value is not None and value < 0:
            raise ValueError("flat_tax_monthly_amount_bam must be >= 0")
        return value


class LegalConstantsContributionsV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pension_rate: Optional[Decimal] = None
    health_rate: Optional[Decimal] = None
    unemployment_rate: Optional[Decimal] = None

    pension_amount_bam: Optional[Decimal] = None
    health_amount_bam: Optional[Decimal] = None
    unemployment_amount_bam: Optional[Decimal] = None
    total_contrib_amount_bam: Optional[Decimal] = None
    base_min_bam: Optional[Decimal] = None

    @field_validator(
        "pension_rate",
        "health_rate",
        "unemployment_rate",
    )
    @classmethod
    def _validate_rate(
        cls,
        value: Decimal | None,
        info,
    ) -> Decimal | None:
        value = _finite_decimal(value, info.field_name)
        if value is not None and not Decimal("0") <= value <= Decimal("1"):
            raise ValueError(f"{info.field_name} must be between 0 and 1")
        return value

    @field_validator(
        "pension_amount_bam",
        "health_amount_bam",
        "unemployment_amount_bam",
        "total_contrib_amount_bam",
        "base_min_bam",
    )
    @classmethod
    def _validate_amount(
        cls,
        value: Decimal | None,
        info,
    ) -> Decimal | None:
        value = _finite_decimal(value, info.field_name)
        if value is not None and value < 0:
            raise ValueError(f"{info.field_name} must be >= 0")
        return value


class LegalConstantsMetaV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_note: Optional[str] = None
    source_reference: Optional[str] = None
    updated_at_ui: Optional[str] = None


class LegalConstantsPayloadV1(BaseModel):
    """Canonical typed legal-constants payload.

    This model validates structure and primitive semantics only.
    Scenario-specific legal completeness is a separate policy layer and
    must not be invented by this generic schema.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["legal-constants-v1"]
    scenario_key: str = Field(..., min_length=1, max_length=64)

    base: LegalConstantsBaseV1
    tax: LegalConstantsTaxV1
    contributions: LegalConstantsContributionsV1

    vat: Optional[LegalConstantsVatV1] = None
    meta: Optional[LegalConstantsMetaV1] = None


def validate_legal_constants_payload(
    *,
    jurisdiction: str,
    scenario_key: str,
    payload: Any,
) -> LegalConstantsPayloadV1 | None:
    """Validate canonical payloads while preserving explicit legacy separation.

    Returns:
      - LegalConstantsPayloadV1 for canonical `legal-constants-v1`
      - None for payloads without schema_version (legacy/unverified)

    A payload that declares any unsupported schema_version is invalid.
    """
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")

    schema_version = payload.get("schema_version")

    if schema_version is None:
        return None

    if schema_version != CANONICAL_LEGAL_CONSTANTS_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported legal constants schema_version: {schema_version!r}"
        )

    _validate_scenario_for_jurisdiction(jurisdiction, scenario_key)

    try:
        parsed = LegalConstantsPayloadV1.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    if parsed.scenario_key != scenario_key:
        raise ValueError(
            "payload.scenario_key must match outer scenario_key "
            f"({parsed.scenario_key!r} != {scenario_key!r})"
        )

    return parsed


class AppConstantsSetRead(BaseModel):
    model_config = BaseConfig

    id: int
    jurisdiction: str
    scenario_key: str
    effective_from: date
    effective_to: Optional[date] = None

    payload: dict[str, Any]

    created_at: datetime
    updated_at: datetime

    created_by: Optional[str] = None
    created_reason: Optional[str] = None

    updated_by: Optional[str] = None
    updated_reason: Optional[str] = None


class AppConstantsSetCreate(BaseModel):
    """
    Admin create.

    created_reason je obavezan (audit).
    scenario_key je obavezan i mora pripadati jurisdikciji.
    """

    jurisdiction: str = Field(..., min_length=1, max_length=16, examples=["RS"])
    scenario_key: str = Field(..., min_length=1, max_length=64, examples=["rs_primary"])
    effective_from: date
    effective_to: Optional[date] = None

    payload: dict[str, Any] = Field(..., description="JSON payload zakonskih parametara")

    created_by: Optional[str] = Field(None, max_length=128)
    created_reason: str = Field(..., min_length=3, max_length=2000)

    @model_validator(mode="after")
    def _validate_all(self):
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be >= effective_from")
        _validate_scenario_for_jurisdiction(self.jurisdiction, self.scenario_key)
        return self


class AppConstantsSetUpdate(BaseModel):
    """
    Admin update.

    updated_reason je obavezan (audit).
    Sva ostala polja opciona.
    """

    jurisdiction: Optional[str] = Field(None, min_length=1, max_length=16, examples=["RS"])
    scenario_key: Optional[str] = Field(None, min_length=1, max_length=64, examples=["rs_primary"])
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None

    payload: Optional[dict[str, Any]] = None

    updated_by: Optional[str] = Field(None, max_length=128)
    updated_reason: str = Field(..., min_length=3, max_length=2000)

    @model_validator(mode="after")
    def _validate_dates(self):
        if self.effective_from is not None and self.effective_to is not None:
            if self.effective_to < self.effective_from:
                raise ValueError("effective_to must be >= effective_from")
        # If both are provided, validate combo
        if self.jurisdiction and self.scenario_key:
            _validate_scenario_for_jurisdiction(self.jurisdiction, self.scenario_key)
        return self


class AppConstantsSetListResponse(BaseModel):
    items: list[AppConstantsSetRead]


class AppConstantsCurrentResponse(BaseModel):
    jurisdiction: str
    scenario_key: str
    as_of: date
    found: bool
    item: Optional[AppConstantsSetRead] = None
