// /home/miso/dev/sp-app/sp-app/frontend/src/types/settings.ts

export type TenantEntity = "RS" | "FBiH" | "Brcko";
export type TaxRegime = "pausal" | "two_percent";
export type SubscriptionPlan = "Basic" | "Standard" | "Premium";

export type ScenarioKey =
  | "rs_primary"
  | "rs_supplementary"
  | "fbih_obrt"
  | "fbih_slobodna"
  | "bd_samostalna";

/* =========================
 * PROFILE
 * ========================= */
export interface ProfileSettingsRead {
  tenant_code: string;
  business_name: string;
  address: string | null;
  tax_id: string | null;

  // Back-compat (staro)
  logo_attachment_id: number | null;

  // Novo (tenant_assets)
  logo_asset_id: number | null;
}

export interface ProfileSettingsUpsert {
  business_name: string;
  address?: string | null;
  tax_id?: string | null;

  // Zadržano radi kompatibilnosti sa backendom:
  // VAŽNO: backend u PUT /settings/profile trenutno uvijek setuje row.logo_asset_id = payload.logo_asset_id,
  // pa moramo slati trenutnu vrijednost da se logo ne "obriše" nenamjerno.
  logo_attachment_id?: number | null;
  logo_asset_id?: number | null;
}

/* =========================
 * TAX PROFILE
 * ========================= */
export interface TaxProfileSettingsRead {
  tenant_code: string;
  entity: TenantEntity;
  regime: TaxRegime;
  scenario_key: ScenarioKey | null;
  has_additional_activity: boolean;
  monthly_pension: number | null;
  monthly_health: number | null;
  monthly_unemployment: number | null;
}

export interface TaxProfileSettingsUpsert {
  entity: TenantEntity;
  regime: TaxRegime;
  scenario_key?: ScenarioKey | null;
  has_additional_activity: boolean;
  monthly_pension?: number | null;
  monthly_health?: number | null;
  monthly_unemployment?: number | null;
}

/* =========================
 * SUBSCRIPTION
 * ========================= */
export interface SubscriptionSettingsRead {
  tenant_code: string;
  plan: SubscriptionPlan;
}

export interface SubscriptionSettingsUpsert {
  plan: SubscriptionPlan;
}
