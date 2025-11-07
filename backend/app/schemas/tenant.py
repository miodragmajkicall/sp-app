from __future__ import annotations

from pydantic import BaseModel, Field

class TenantCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1)

class TenantRead(BaseModel):
    id: str
    code: str
    name: str

class TenantUpdate(BaseModel):
    name: str | None = None
