from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

class TenantCreate(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    name: str

class TenantOut(BaseModel):
    id: UUID
    code: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2: radi sa SQLAlchemy modelom
