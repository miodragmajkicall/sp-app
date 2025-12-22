# /home/miso/dev/sp-app/sp-app/backend/app/schemas/constants.py
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
