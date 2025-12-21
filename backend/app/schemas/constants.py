# /home/miso/dev/sp-app/sp-app/backend/app/schemas/constants.py
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


BaseConfig = ConfigDict(from_attributes=True)


class AppConstantsSetRead(BaseModel):
    model_config = BaseConfig

    id: int
    jurisdiction: str
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
    """
    jurisdiction: str = Field(..., min_length=1, max_length=16, examples=["RS"])
    effective_from: date
    effective_to: Optional[date] = None

    payload: dict[str, Any] = Field(..., description="JSON payload zakonskih parametara")

    created_by: Optional[str] = Field(None, max_length=128)
    created_reason: str = Field(..., min_length=3, max_length=2000)

    @model_validator(mode="after")
    def _validate_dates(self):
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be >= effective_from")
        return self


class AppConstantsSetUpdate(BaseModel):
    """
    Admin update.

    updated_reason je obavezan (audit).
    Sva ostala polja opciona.
    """
    jurisdiction: Optional[str] = Field(None, min_length=1, max_length=16, examples=["RS"])
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None

    payload: Optional[dict[str, Any]] = None

    updated_by: Optional[str] = Field(None, max_length=128)
    updated_reason: str = Field(..., min_length=3, max_length=2000)

    @model_validator(mode="after")
    def _validate_dates(self):
        # Pošto su polja opcionalna, ovdje validiramo samo ako su oba poslata.
        if self.effective_from is not None and self.effective_to is not None:
            if self.effective_to < self.effective_from:
                raise ValueError("effective_to must be >= effective_from")
        return self


class AppConstantsSetListResponse(BaseModel):
    items: list[AppConstantsSetRead]


class AppConstantsCurrentResponse(BaseModel):
    jurisdiction: str
    as_of: date
    found: bool
    item: Optional[AppConstantsSetRead] = None
