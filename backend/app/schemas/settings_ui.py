# /home/miso/dev/sp-app/sp-app/backend/app/schemas/settings_ui.py
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


TenantEntity = Literal["RS", "FBiH", "Brcko"]
TaxRegime = Literal["pausal", "two_percent"]


class UiField(BaseModel):
    """
    Jedno polje koje UI može prikazati (base / contributions / tax).
    """
    key: str
    label: str
    hint: Optional[str] = None
    required: bool = False
    unit: Optional[str] = None  # npr. "BAM", "%", "decimal"


class UiScenarioOption(BaseModel):
    key: str
    label: str
    hint: Optional[str] = None
    entity: TenantEntity


class UiResolvedValue(BaseModel):
    """
    Jedna resolved vrijednost iz aktivnog Admin Constants seta,
    pripremljena za direktan prikaz u UI-u.
    """
    key: str
    label: str
    value: Optional[str] = None
    unit: Optional[str] = None
    section: Literal["base", "contributions", "tax", "vat", "meta"]


class TaxProfileUiSchemaResponse(BaseModel):
    """
    UI schema za Settings -> Tax profile, derivirano iz:
    - scenario_key (izabran)
    - admin constants payload (aktivni set za taj scenario)
    """
    entity: TenantEntity
    scenario_key: str

    # UI: koji režimi se nude
    allowed_regimes: list[TaxRegime] = Field(default_factory=list)

    # UI: scenariji koji su validni za izabrani entitet
    scenario_options: list[UiScenarioOption] = Field(default_factory=list)

    # UI: koje komponente doprinosa su relevantne (prikazati)
    contribution_components: list[str] = Field(default_factory=list)
    # npr. ["pension", "health", "unemployment", "child"]

    # UI: “osnovica” polja koja imaju smisla za scenario
    base_fields: list[UiField] = Field(default_factory=list)

    # UI: doprinos stope polja (ako postoje u scenariju)
    contribution_rate_fields: list[UiField] = Field(default_factory=list)

    # UI: porezi / PDV
    tax_fields: list[UiField] = Field(default_factory=list)
    vat_fields: list[UiField] = Field(default_factory=list)

    # Novo: konkretne resolved vrijednosti iz aktivnog Admin Constants seta
    resolved_values: list[UiResolvedValue] = Field(default_factory=list)

    # Meta: da UI može prikazati “izvor konstanti”
    constants_set_id: Optional[int] = None
    constants_effective_from: Optional[str] = None
    constants_effective_to: Optional[str] = None
    constants_currency: Optional[str] = None