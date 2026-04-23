// /home/miso/dev/sp-app/sp-app/frontend/src/services/settingsApi.ts
import { apiClient } from "./apiClient";
import type {
  ProfileSettingsRead,
  ProfileSettingsUpsert,
  TaxProfileSettingsRead,
  TaxProfileSettingsUpsert,
  TaxProfileUiSchemaResponse,
  SubscriptionSettingsRead,
  SubscriptionSettingsUpsert,
  UiResolvedValue,
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
  // Profesionalno: šaljemo samo polja koja su eksplicitno definisana.
  // Time ne možemo nenamjerno "nulirati" logo_* vrijednosti.
  const body: Record<string, any> = {
    business_name: payload.business_name,
    address: payload.address ?? null,
    tax_id: payload.tax_id ?? null,
  };

  // Opciona polja (legacy/new) uključujemo samo ako su eksplicitno poslata
  if (payload.logo_attachment_id !== undefined) {
    body.logo_attachment_id = payload.logo_attachment_id;
  }
  if (payload.logo_asset_id !== undefined) {
    body.logo_asset_id = payload.logo_asset_id;
  }

  const res = await apiClient.put<ProfileSettingsRead>("/settings/profile", body);
  return normalizeProfile(res.data);
}

export async function uploadProfileLogo(file: File): Promise<ProfileSettingsRead> {
  const form = new FormData();
  form.append("file", file);

  const res = await apiClient.post<ProfileSettingsRead>(
    "/settings/profile/logo",
    form,
    {
      headers: {
        // override JSON header; browser sets correct multipart boundary
        "Content-Type": "multipart/form-data",
      },
    },
  );
  return normalizeProfile(res.data);
}

export async function deleteProfileLogo(): Promise<void> {
  await apiClient.delete("/settings/profile/logo");
}

export async function fetchProfileLogoBlob(): Promise<Blob> {
  const res = await apiClient.get("/settings/profile/logo", {
    responseType: "blob",
  });
  return res.data as Blob;
}

function normalizeProfile(r: any): ProfileSettingsRead {
  return {
    tenant_code: String(r.tenant_code),
    business_name: String(r.business_name ?? ""),
    address: r.address ?? null,
    tax_id: r.tax_id ?? null,
    logo_attachment_id:
      r.logo_attachment_id == null ? null : Number(r.logo_attachment_id),
    logo_asset_id: r.logo_asset_id == null ? null : Number(r.logo_asset_id),
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
    scenario_key: payload.scenario_key ?? null,
    has_additional_activity: payload.has_additional_activity,
    monthly_pension: payload.monthly_pension ?? null,
    monthly_health: payload.monthly_health ?? null,
    monthly_unemployment: payload.monthly_unemployment ?? null,
  });
  return normalizeTaxProfile(res.data);
}

export async function getTaxProfileUiSchema(params?: {
  asOf?: string; // YYYY-MM-DD
}): Promise<TaxProfileUiSchemaResponse> {
  const res = await apiClient.get<TaxProfileUiSchemaResponse>("/settings/tax/ui-schema", {
    params: params?.asOf ? { as_of: params.asOf } : undefined,
  });

  // backend već vraća shape koji FE može direktno koristiti;
  // ovdje samo osiguramo default-e da UI ne puca na undefined.
  const r: any = res.data ?? {};

  const resolvedValues: UiResolvedValue[] = Array.isArray(r.resolved_values)
    ? r.resolved_values.map((item: any) => ({
        key: String(item?.key ?? ""),
        label: String(item?.label ?? ""),
        value: item?.value == null ? null : String(item.value),
        unit: item?.unit ?? null,
        section: item?.section ?? "meta",
      }))
    : [];

  return {
    entity: (r.entity ?? "RS") as any,
    scenario_key: r.scenario_key ?? "",
    allowed_regimes: Array.isArray(r.allowed_regimes) ? r.allowed_regimes : [],
    scenario_options: Array.isArray(r.scenario_options) ? r.scenario_options : [],
    contribution_components: Array.isArray(r.contribution_components)
      ? r.contribution_components
      : [],
    base_fields: Array.isArray(r.base_fields) ? r.base_fields : [],
    contribution_rate_fields: Array.isArray(r.contribution_rate_fields)
      ? r.contribution_rate_fields
      : [],
    tax_fields: Array.isArray(r.tax_fields) ? r.tax_fields : [],
    vat_fields: Array.isArray(r.vat_fields) ? r.vat_fields : [],
    resolved_values: resolvedValues,
    constants_set_id: r.constants_set_id ?? null,
    constants_effective_from: r.constants_effective_from ?? null,
    constants_effective_to: r.constants_effective_to ?? null,
    constants_currency: r.constants_currency ?? null,
  };
}

function normalizeTaxProfile(r: any): TaxProfileSettingsRead {
  return {
    tenant_code: String(r.tenant_code),
    entity: (r.entity ?? "RS") as any,
    regime: (r.regime ?? "pausal") as any,
    scenario_key: r.scenario_key ?? null,
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