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
  logo_attachment_id: number | null;
}

export interface ProfileSettingsUpsert {
  business_name: string;
  address?: string | null;
  tax_id?: string | null;
  logo_attachment_id?: number | null;
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
