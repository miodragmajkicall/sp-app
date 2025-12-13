// /home/miso/dev/sp-app/sp-app/frontend/src/services/settingsApi.ts
import { apiClient } from "./apiClient";
import type {
  ProfileSettingsRead,
  ProfileSettingsUpsert,
  TaxProfileSettingsRead,
  TaxProfileSettingsUpsert,
  SubscriptionSettingsRead,
  SubscriptionSettingsUpsert,
} from "../types/settings";

/* =========================
 * PROFILE
 * ========================= */

export async function getProfileSettings(): Promise<ProfileSettingsRead> {
  const res = await apiClient.get<ProfileSettingsRead>("/settings/profile");
  return normalizeProfile(res.data);
}

export async function putProfileSettings(
  payload: ProfileSettingsUpsert,
): Promise<ProfileSettingsRead> {
  const res = await apiClient.put<ProfileSettingsRead>("/settings/profile", {
    business_name: payload.business_name,
    address: payload.address ?? null,
    tax_id: payload.tax_id ?? null,
    logo_attachment_id: payload.logo_attachment_id ?? null,
  });
  return normalizeProfile(res.data);
}

function normalizeProfile(r: any): ProfileSettingsRead {
  return {
    tenant_code: String(r.tenant_code),
    business_name: String(r.business_name ?? ""),
    address: r.address ?? null,
    tax_id: r.tax_id ?? null,
    logo_attachment_id:
      r.logo_attachment_id == null ? null : Number(r.logo_attachment_id),
  };
}

/* =========================
 * TAX PROFILE
 * ========================= */

export async function getTaxProfileSettings(): Promise<TaxProfileSettingsRead> {
  const res = await apiClient.get<TaxProfileSettingsRead>("/settings/tax");
  return normalizeTaxProfile(res.data);
}

export async function putTaxProfileSettings(
  payload: TaxProfileSettingsUpsert,
): Promise<TaxProfileSettingsRead> {
  const res = await apiClient.put<TaxProfileSettingsRead>("/settings/tax", {
    entity: payload.entity,
    regime: payload.regime,
    has_additional_activity: payload.has_additional_activity,
    monthly_pension: payload.monthly_pension ?? null,
    monthly_health: payload.monthly_health ?? null,
    monthly_unemployment: payload.monthly_unemployment ?? null,
  });
  return normalizeTaxProfile(res.data);
}

function normalizeTaxProfile(r: any): TaxProfileSettingsRead {
  return {
    tenant_code: String(r.tenant_code),
    entity: (r.entity ?? "RS") as any,
    regime: (r.regime ?? "pausal") as any,
    has_additional_activity: Boolean(r.has_additional_activity),
    monthly_pension:
      r.monthly_pension == null ? null : Number(r.monthly_pension),
    monthly_health: r.monthly_health == null ? null : Number(r.monthly_health),
    monthly_unemployment:
      r.monthly_unemployment == null ? null : Number(r.monthly_unemployment),
  };
}

/* =========================
 * SUBSCRIPTION
 * ========================= */

export async function getSubscriptionSettings(): Promise<SubscriptionSettingsRead> {
  const res = await apiClient.get<SubscriptionSettingsRead>(
    "/settings/subscription",
  );
  return normalizeSubscription(res.data);
}

export async function putSubscriptionSettings(
  payload: SubscriptionSettingsUpsert,
): Promise<SubscriptionSettingsRead> {
  const res = await apiClient.put<SubscriptionSettingsRead>(
    "/settings/subscription",
    { plan: payload.plan },
  );
  return normalizeSubscription(res.data);
}

function normalizeSubscription(r: any): SubscriptionSettingsRead {
  return {
    tenant_code: String(r.tenant_code),
    plan: (r.plan ?? "Basic") as any,
  };
}
