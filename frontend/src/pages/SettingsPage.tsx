// /home/miso/dev/sp-app/sp-app/frontend/src/pages/SettingsPage.tsx
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  ProfileSettingsRead,
  TaxProfileSettingsRead,
  SubscriptionSettingsRead,
  SubscriptionPlan,
  TenantEntity,
  TaxRegime,
} from "../types/settings";
import {
  getProfileSettings,
  putProfileSettings,
  getTaxProfileSettings,
  putTaxProfileSettings,
  getSubscriptionSettings,
  putSubscriptionSettings,
} from "../services/settingsApi";

function toNumberOrNull(value: string): number | null {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const n = Number(trimmed);
  if (!Number.isFinite(n)) return null;
  return n;
}

function formatTenantLabel(tenantCode?: string | null): string {
  if (!tenantCode) return "t-demo";
  return tenantCode;
}

export default function SettingsPage() {
  const queryClient = useQueryClient();

  const profileQuery = useQuery<ProfileSettingsRead, Error>({
    queryKey: ["settings", "profile"],
    queryFn: getProfileSettings,
  });

  const taxQuery = useQuery<TaxProfileSettingsRead, Error>({
    queryKey: ["settings", "tax"],
    queryFn: getTaxProfileSettings,
  });

  const subQuery = useQuery<SubscriptionSettingsRead, Error>({
    queryKey: ["settings", "subscription"],
    queryFn: getSubscriptionSettings,
  });

  const [profileForm, setProfileForm] = useState({
    business_name: "",
    address: "",
    tax_id: "",
    logo_attachment_id: "",
  });

  const [taxForm, setTaxForm] = useState<{
    entity: TenantEntity;
    regime: TaxRegime;
    has_additional_activity: boolean;
    monthly_pension: string;
    monthly_health: string;
    monthly_unemployment: string;
  }>({
    entity: "RS",
    regime: "pausal",
    has_additional_activity: false,
    monthly_pension: "",
    monthly_health: "",
    monthly_unemployment: "",
  });

  const [subForm, setSubForm] = useState<{ plan: SubscriptionPlan }>({
    plan: "Basic",
  });

  // init forms when queries load (do not overwrite while saving)
  useEffect(() => {
    if (!profileQuery.data) return;
    const p = profileQuery.data;
    setProfileForm({
      business_name: p.business_name ?? "",
      address: p.address ?? "",
      tax_id: p.tax_id ?? "",
      logo_attachment_id:
        p.logo_attachment_id == null ? "" : String(p.logo_attachment_id),
    });
  }, [profileQuery.data]);

  useEffect(() => {
    if (!taxQuery.data) return;
    const t = taxQuery.data;
    setTaxForm({
      entity: t.entity,
      regime: t.regime,
      has_additional_activity: t.has_additional_activity,
      monthly_pension: t.monthly_pension == null ? "" : String(t.monthly_pension),
      monthly_health: t.monthly_health == null ? "" : String(t.monthly_health),
      monthly_unemployment:
        t.monthly_unemployment == null ? "" : String(t.monthly_unemployment),
    });
  }, [taxQuery.data]);

  useEffect(() => {
    if (!subQuery.data) return;
    setSubForm({ plan: subQuery.data.plan });
  }, [subQuery.data]);

  const tenantCode = useMemo(() => {
    return (
      profileQuery.data?.tenant_code ||
      taxQuery.data?.tenant_code ||
      subQuery.data?.tenant_code ||
      "t-demo"
    );
  }, [profileQuery.data, taxQuery.data, subQuery.data]);

  /* =========================
   * Mutations
   * ========================= */
  const profileMutation = useMutation({
    mutationFn: async () => {
      if (!profileForm.business_name.trim()) {
        throw new Error("Naziv poslovanja (business name) je obavezan.");
      }
      return putProfileSettings({
        business_name: profileForm.business_name.trim(),
        address: profileForm.address.trim() ? profileForm.address.trim() : null,
        tax_id: profileForm.tax_id.trim() ? profileForm.tax_id.trim() : null,
        logo_attachment_id: toNumberOrNull(profileForm.logo_attachment_id),
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings", "profile"] });
    },
  });

  const taxMutation = useMutation({
    mutationFn: async () => {
      return putTaxProfileSettings({
        entity: taxForm.entity,
        regime: taxForm.regime,
        has_additional_activity: taxForm.has_additional_activity,
        monthly_pension: toNumberOrNull(taxForm.monthly_pension),
        monthly_health: toNumberOrNull(taxForm.monthly_health),
        monthly_unemployment: toNumberOrNull(taxForm.monthly_unemployment),
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings", "tax"] });
    },
  });

  const subMutation = useMutation({
    mutationFn: async () => {
      return putSubscriptionSettings({ plan: subForm.plan });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["settings", "subscription"],
      });
    },
  });

  const anyLoading =
    profileQuery.isLoading || taxQuery.isLoading || subQuery.isLoading;
  const anyError = profileQuery.isError || taxQuery.isError || subQuery.isError;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-1">
        <h2 className="text-xl font-semibold text-slate-800">Postavke</h2>
        <p className="text-xs text-slate-500">
          Parametri koje korisnik unosi ovdje biće korišteni u ostalim modulima
          (tax/kpr/izvještaji), ali integraciju radimo u narednoj sesiji.
        </p>
        <p className="text-[11px] text-slate-400">
          Tenant:{" "}
          <span className="font-mono text-slate-600">
            {formatTenantLabel(tenantCode)}
          </span>
        </p>
      </div>

      {/* Loading / Error */}
      {anyLoading && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-sm">
          Učitavam postavke...
        </div>
      )}

      {anyError && (
        <div className="rounded-xl border border-red-200 bg-white p-4 text-sm text-red-700 shadow-sm">
          <p className="font-medium">Greška pri učitavanju postavki.</p>
          <ul className="mt-2 list-disc pl-5 text-xs">
            {profileQuery.error?.message && (
              <li>Profil: {profileQuery.error.message}</li>
            )}
            {taxQuery.error?.message && <li>Tax: {taxQuery.error.message}</li>}
            {subQuery.error?.message && (
              <li>Pretplata: {subQuery.error.message}</li>
            )}
          </ul>

          <button
            type="button"
            onClick={() => {
              profileQuery.refetch();
              taxQuery.refetch();
              subQuery.refetch();
            }}
            className="mt-3 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            Pokušaj ponovo
          </button>
        </div>
      )}

      {/* Content */}
      {!anyLoading && !anyError && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* PROFILE */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3">
              <h3 className="text-sm font-semibold text-slate-800">Profil</h3>
              <p className="mt-1 text-[11px] text-slate-500">
                Osnovni podaci o poslovanju (za zaglavlja, izvještaje, PDF).
              </p>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                  Naziv poslovanja
                </label>
                <input
                  value={profileForm.business_name}
                  onChange={(e) =>
                    setProfileForm((p) => ({ ...p, business_name: e.target.value }))
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-xs text-slate-700 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  placeholder="npr. SP Mišo"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                  Adresa
                </label>
                <input
                  value={profileForm.address}
                  onChange={(e) =>
                    setProfileForm((p) => ({ ...p, address: e.target.value }))
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-xs text-slate-700 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  placeholder="Ulica i broj, grad"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                  PIB/JIB
                </label>
                <input
                  value={profileForm.tax_id}
                  onChange={(e) =>
                    setProfileForm((p) => ({ ...p, tax_id: e.target.value }))
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-xs text-slate-700 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  placeholder="npr. 123456789"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                  Logo attachment ID (opciono)
                </label>
                <input
                  value={profileForm.logo_attachment_id}
                  onChange={(e) =>
                    setProfileForm((p) => ({
                      ...p,
                      logo_attachment_id: e.target.value,
                    }))
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-xs text-slate-700 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  placeholder="npr. 12"
                />
                <p className="mt-1 text-[11px] text-slate-400">
                  Trenutno samo kao broj (kasnije možemo povezati sa upload modulom).
                </p>
              </div>

              {profileMutation.error && (
                <p className="text-xs text-red-600">
                  {profileMutation.error instanceof Error
                    ? profileMutation.error.message
                    : "Greška pri snimanju."}
                </p>
              )}

              <button
                type="button"
                onClick={() => profileMutation.mutate()}
                disabled={profileMutation.isPending}
                className="mt-1 inline-flex w-full items-center justify-center rounded-md bg-slate-900 px-3 py-2 text-xs font-medium text-white shadow-sm hover:bg-slate-800 disabled:opacity-60"
              >
                {profileMutation.isPending ? "Snima se..." : "Sačuvaj profil"}
              </button>
            </div>
          </div>

          {/* TAX PROFILE */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3">
              <h3 className="text-sm font-semibold text-slate-800">
                Poreski profil
              </h3>
              <p className="mt-1 text-[11px] text-slate-500">
                Odabir entiteta i režima + opcioni mjesečni iznosi.
              </p>
            </div>

            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                    Entitet
                  </label>
                  <select
                    value={taxForm.entity}
                    onChange={(e) =>
                      setTaxForm((t) => ({
                        ...t,
                        entity: e.target.value as TenantEntity,
                      }))
                    }
                    className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-xs text-slate-700 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  >
                    <option value="RS">RS</option>
                    <option value="FBiH">FBiH</option>
                    <option value="Brcko">Brčko</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                    Režim
                  </label>
                  <select
                    value={taxForm.regime}
                    onChange={(e) =>
                      setTaxForm((t) => ({
                        ...t,
                        regime: e.target.value as TaxRegime,
                      }))
                    }
                    className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-xs text-slate-700 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  >
                    <option value="pausal">Paušal</option>
                    <option value="two_percent">2% (stvarni prihod)</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                <input
                  id="has_additional_activity"
                  type="checkbox"
                  checked={taxForm.has_additional_activity}
                  onChange={(e) =>
                    setTaxForm((t) => ({
                      ...t,
                      has_additional_activity: e.target.checked,
                    }))
                  }
                />
                <label
                  htmlFor="has_additional_activity"
                  className="text-xs text-slate-700"
                >
                  Imam dodatnu djelatnost / drugi osnov
                </label>
              </div>

              <div className="grid grid-cols-1 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                    Mjesečni PIO (opciono)
                  </label>
                  <input
                    value={taxForm.monthly_pension}
                    onChange={(e) =>
                      setTaxForm((t) => ({ ...t, monthly_pension: e.target.value }))
                    }
                    className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-xs text-slate-700 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                    placeholder="npr. 250"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                    Mjesečno zdravstvo (opciono)
                  </label>
                  <input
                    value={taxForm.monthly_health}
                    onChange={(e) =>
                      setTaxForm((t) => ({ ...t, monthly_health: e.target.value }))
                    }
                    className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-xs text-slate-700 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                    placeholder="npr. 180"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                    Mjesečno nezaposlenost (opciono)
                  </label>
                  <input
                    value={taxForm.monthly_unemployment}
                    onChange={(e) =>
                      setTaxForm((t) => ({
                        ...t,
                        monthly_unemployment: e.target.value,
                      }))
                    }
                    className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-xs text-slate-700 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                    placeholder="npr. 25"
                  />
                </div>
              </div>

              {taxMutation.error && (
                <p className="text-xs text-red-600">
                  {taxMutation.error instanceof Error
                    ? taxMutation.error.message
                    : "Greška pri snimanju."}
                </p>
              )}

              <button
                type="button"
                onClick={() => taxMutation.mutate()}
                disabled={taxMutation.isPending}
                className="mt-1 inline-flex w-full items-center justify-center rounded-md bg-slate-900 px-3 py-2 text-xs font-medium text-white shadow-sm hover:bg-slate-800 disabled:opacity-60"
              >
                {taxMutation.isPending ? "Snima se..." : "Sačuvaj poreski profil"}
              </button>
            </div>
          </div>

          {/* SUBSCRIPTION */}
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3">
              <h3 className="text-sm font-semibold text-slate-800">Pretplata</h3>
              <p className="mt-1 text-[11px] text-slate-500">
                Plan određuje dostupne funkcije (Basic/Standard/Premium).
              </p>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                  Plan
                </label>
                <select
                  value={subForm.plan}
                  onChange={(e) =>
                    setSubForm({ plan: e.target.value as SubscriptionPlan })
                  }
                  className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-xs text-slate-700 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                >
                  <option value="Basic">Basic</option>
                  <option value="Standard">Standard</option>
                  <option value="Premium">Premium</option>
                </select>
              </div>

              <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
                <p className="font-medium text-slate-700">Napomena</p>
                <p className="mt-1">
                  Ovo je “feature toggle” osnova. U narednoj sesiji možemo
                  sakrivati/otključavati dijelove UI-ja i backend ponašanje po planu.
                </p>
              </div>

              {subMutation.error && (
                <p className="text-xs text-red-600">
                  {subMutation.error instanceof Error
                    ? subMutation.error.message
                    : "Greška pri snimanju."}
                </p>
              )}

              <button
                type="button"
                onClick={() => subMutation.mutate()}
                disabled={subMutation.isPending}
                className="mt-1 inline-flex w-full items-center justify-center rounded-md bg-slate-900 px-3 py-2 text-xs font-medium text-white shadow-sm hover:bg-slate-800 disabled:opacity-60"
              >
                {subMutation.isPending ? "Snima se..." : "Sačuvaj pretplatu"}
              </button>

              <button
                type="button"
                onClick={() => {
                  profileQuery.refetch();
                  taxQuery.refetch();
                  subQuery.refetch();
                }}
                className="inline-flex w-full items-center justify-center rounded-md border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                Osvježi sa servera
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
