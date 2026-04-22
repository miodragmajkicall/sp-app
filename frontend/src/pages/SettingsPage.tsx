// /home/miso/dev/sp-app/sp-app/frontend/src/pages/SettingsPage.tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type {
  ProfileSettingsRead,
  TaxProfileSettingsRead,
  SubscriptionSettingsRead,
  SubscriptionPlan,
  TenantEntity,
  TaxRegime,
  ScenarioKey,
  TaxProfileUiSchemaResponse,
} from "../types/settings";

import {
  getProfileSettings,
  putProfileSettings,
  getTaxProfileSettings,
  putTaxProfileSettings,
  getSubscriptionSettings,
  fetchProfileLogoBlob,
  getTaxProfileUiSchema,
  uploadProfileLogo,
  deleteProfileLogo,
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

function formatRegimeLabel(regime: TaxRegime): string {
  return regime === "pausal" ? "Paušal" : "2% (stvarni prihod)";
}

function formatPlanLabel(plan: SubscriptionPlan): string {
  return plan;
}

function notifyProfileSettingsUpdated() {
  window.dispatchEvent(new CustomEvent("profile-settings-updated"));
}

const SCENARIOS_BY_ENTITY: Record<TenantEntity, ScenarioKey[]> = {
  RS: ["rs_primary", "rs_supplementary"],
  FBiH: ["fbih_obrt", "fbih_slobodna"],
  Brcko: ["bd_samostalna"],
};

const SCENARIO_META: Record<
  ScenarioKey,
  { label: string; hint: string; entity: TenantEntity }
> = {
  rs_primary: {
    label: "RS – Osnovna djelatnost",
    hint: "Osnovna djelatnost (primary).",
    entity: "RS",
  },
  rs_supplementary: {
    label: "RS – Dopunska djelatnost (uz zaposlenje)",
    hint: "Dopunska djelatnost (supplementary).",
    entity: "RS",
  },
  fbih_obrt: {
    label: "FBiH – Obrt",
    hint: "Obrt i srodne djelatnosti.",
    entity: "FBiH",
  },
  fbih_slobodna: {
    label: "FBiH – Slobodna djelatnost",
    hint: "Slobodna zanimanja.",
    entity: "FBiH",
  },
  bd_samostalna: {
    label: "Brčko – Samostalna djelatnost",
    hint: "Jedinstvena šema za Brčko distrikt.",
    entity: "Brcko",
  },
};

function isScenarioValidForEntity(
  entity: TenantEntity,
  scenario: ScenarioKey | null,
): boolean {
  if (!scenario) return false;
  return SCENARIOS_BY_ENTITY[entity].includes(scenario);
}

function getDefaultScenarioForEntity(entity: TenantEntity): ScenarioKey {
  return SCENARIOS_BY_ENTITY[entity][0];
}

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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
  });

  const [taxForm, setTaxForm] = useState<{
    entity: TenantEntity;
    regime: TaxRegime;
    scenario_key: ScenarioKey | "";
    has_additional_activity: boolean;
    monthly_pension: string;
    monthly_health: string;
    monthly_unemployment: string;
  }>({
    entity: "RS",
    regime: "pausal",
    scenario_key: "",
    has_additional_activity: false,
    monthly_pension: "",
    monthly_health: "",
    monthly_unemployment: "",
  });

  const [selectedLogoName, setSelectedLogoName] = useState<string>("");
  const [logoObjectUrl, setLogoObjectUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!profileQuery.data) return;
    const p = profileQuery.data;

    setProfileForm({
      business_name: p.business_name ?? "",
      address: p.address ?? "",
      tax_id: p.tax_id ?? "",
    });
  }, [profileQuery.data]);

  useEffect(() => {
    if (!taxQuery.data) return;
    const t = taxQuery.data;

    const entity = t.entity;
    const rawScenario = (t.scenario_key ?? null) as ScenarioKey | null;

    const scenarioToUse = isScenarioValidForEntity(entity, rawScenario)
      ? (rawScenario as ScenarioKey)
      : getDefaultScenarioForEntity(entity);

    setTaxForm({
      entity,
      regime: t.regime,
      scenario_key: scenarioToUse,
      has_additional_activity:
        entity === "RS"
          ? scenarioToUse === "rs_supplementary"
          : t.has_additional_activity,
      monthly_pension: t.monthly_pension == null ? "" : String(t.monthly_pension),
      monthly_health: t.monthly_health == null ? "" : String(t.monthly_health),
      monthly_unemployment:
        t.monthly_unemployment == null ? "" : String(t.monthly_unemployment),
    });
  }, [taxQuery.data]);

  useEffect(() => {
    const entity = taxForm.entity;
    const current = taxForm.scenario_key
      ? (taxForm.scenario_key as ScenarioKey)
      : null;

    if (current && isScenarioValidForEntity(entity, current)) {
      return;
    }

    setTaxForm((t) => ({
      ...t,
      scenario_key: getDefaultScenarioForEntity(entity),
      has_additional_activity:
        entity === "RS"
          ? getDefaultScenarioForEntity(entity) === "rs_supplementary"
          : false,
    }));
  }, [taxForm.entity]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (taxForm.entity !== "RS") return;

    const expectedScenario = taxForm.has_additional_activity
      ? "rs_supplementary"
      : "rs_primary";

    if (taxForm.scenario_key === expectedScenario) return;

    setTaxForm((t) => ({
      ...t,
      scenario_key: expectedScenario,
    }));
  }, [taxForm.entity, taxForm.has_additional_activity]); // eslint-disable-line react-hooks/exhaustive-deps

  const tenantCode = useMemo(() => {
    return (
      profileQuery.data?.tenant_code ||
      taxQuery.data?.tenant_code ||
      subQuery.data?.tenant_code ||
      "t-demo"
    );
  }, [profileQuery.data, taxQuery.data, subQuery.data]);

  const hasTaxProfileMinimum = useMemo(() => {
    return Boolean(taxForm.scenario_key);
  }, [taxForm.scenario_key]);

  const currentPlan: SubscriptionPlan = (subQuery.data?.plan ??
    "Basic") as SubscriptionPlan;

  const profileHasLogo = useMemo(() => {
    return profileQuery.data?.logo_asset_id != null;
  }, [profileQuery.data]);

  const logoAssetIdForReload = useMemo(() => {
    return profileQuery.data?.logo_asset_id ?? null;
  }, [profileQuery.data]);

  const taxUiSchemaQuery = useQuery<TaxProfileUiSchemaResponse, Error>({
    queryKey: ["settings", "tax-ui-schema"],
    queryFn: async () => {
      return getTaxProfileUiSchema();
    },
    enabled: !taxQuery.isLoading && !taxQuery.isError,
    staleTime: 15_000,
  });

  const uiScenarioOptions = useMemo(() => {
    return SCENARIOS_BY_ENTITY[taxForm.entity].map((key) => ({
      key,
      label: SCENARIO_META[key].label,
      hint: SCENARIO_META[key].hint,
      entity: SCENARIO_META[key].entity,
    }));
  }, [taxForm.entity]);

  useEffect(() => {
    if (taxForm.entity !== "RS") return;
    if (!taxForm.scenario_key) return;

    const shouldBeSupplementary = taxForm.scenario_key === "rs_supplementary";
    if (taxForm.has_additional_activity === shouldBeSupplementary) return;

    setTaxForm((t) => ({
      ...t,
      has_additional_activity: shouldBeSupplementary,
    }));
  }, [taxForm.entity, taxForm.scenario_key]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let isActive = true;

    async function loadLogo() {
      if (!profileHasLogo) {
        setLogoObjectUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return null;
        });
        return;
      }

      try {
        const blob = await fetchProfileLogoBlob();
        if (!isActive) return;

        const nextUrl = URL.createObjectURL(blob);

        setLogoObjectUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return nextUrl;
        });
      } catch {
        if (!isActive) return;
        setLogoObjectUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return null;
        });
      }
    }

    loadLogo();

    return () => {
      isActive = false;
    };
  }, [profileHasLogo, logoAssetIdForReload]);

  useEffect(() => {
    return () => {
      if (logoObjectUrl) URL.revokeObjectURL(logoObjectUrl);
    };
  }, [logoObjectUrl]);

  const profileMutation = useMutation({
    mutationFn: async () => {
      if (!profileForm.business_name.trim()) {
        throw new Error("Naziv poslovanja je obavezan.");
      }
      return putProfileSettings({
        business_name: profileForm.business_name.trim(),
        address: profileForm.address.trim() ? profileForm.address.trim() : null,
        tax_id: profileForm.tax_id.trim() ? profileForm.tax_id.trim() : null,
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings", "profile"] });
      notifyProfileSettingsUpdated();
    },
  });

  const taxMutation = useMutation({
    mutationFn: async () => {
      if (!taxForm.scenario_key) {
        throw new Error("Odaberite šemu obračuna (scenario).");
      }

      return putTaxProfileSettings({
        entity: taxForm.entity,
        regime: taxForm.regime,
        scenario_key: taxForm.scenario_key as ScenarioKey,
        has_additional_activity: taxForm.has_additional_activity,
        monthly_pension: toNumberOrNull(taxForm.monthly_pension),
        monthly_health: toNumberOrNull(taxForm.monthly_health),
        monthly_unemployment: toNumberOrNull(taxForm.monthly_unemployment),
      });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings", "tax"] });
      await queryClient.invalidateQueries({
        queryKey: ["settings", "tax-ui-schema"],
      });
    },
  });

  const logoUploadMutation = useMutation({
    mutationFn: async (file: File) => {
      return uploadProfileLogo(file);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings", "profile"] });
      notifyProfileSettingsUpdated();

      if (fileInputRef.current) fileInputRef.current.value = "";
      setSelectedLogoName("");
    },
  });

  const logoDeleteMutation = useMutation({
    mutationFn: async () => {
      await deleteProfileLogo();
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings", "profile"] });
      notifyProfileSettingsUpdated();

      if (fileInputRef.current) fileInputRef.current.value = "";
      setSelectedLogoName("");
    },
  });

  const anyLoading =
    profileQuery.isLoading || taxQuery.isLoading || subQuery.isLoading;
  const anyError = profileQuery.isError || taxQuery.isError || subQuery.isError;

  const taxUiSchemaBanner = useMemo(() => {
    const d = taxUiSchemaQuery.data;
    if (!d) return null;

    const parts: string[] = [];
    if (d.constants_set_id != null) parts.push(`Set #${d.constants_set_id}`);
    if (d.constants_effective_from) parts.push(`od ${d.constants_effective_from}`);
    if (d.constants_effective_to) parts.push(`do ${d.constants_effective_to}`);
    if (d.constants_currency) parts.push(`valuta ${d.constants_currency}`);

    if (!parts.length) return null;
    return parts.join(" • ");
  }, [taxUiSchemaQuery.data]);

  const taxUiSummary = useMemo(() => {
    const d = taxUiSchemaQuery.data;
    if (!d) return [];

    const sections: Array<{ title: string; items: string[] }> = [];

    const makeItems = (
      rows?: Array<{
        key: string;
        label: string;
        hint?: string | null;
        unit?: string | null;
      }>,
    ) => {
      return (rows ?? []).map((row) => {
        const suffix = row.unit ? ` (${row.unit})` : "";
        return `${row.label}${suffix}`;
      });
    };

    const components = (d.contribution_components ?? []).map((item) =>
      String(item),
    );

    if (components.length) {
      sections.push({
        title: "Komponente doprinosa",
        items: components,
      });
    }

    const baseFields = makeItems(d.base_fields);
    if (baseFields.length) {
      sections.push({
        title: "Osnovica / bazna polja",
        items: baseFields,
      });
    }

    const contribRateFields = makeItems(d.contribution_rate_fields);
    if (contribRateFields.length) {
      sections.push({
        title: "Stope doprinosa",
        items: contribRateFields,
      });
    }

    const taxFields = makeItems(d.tax_fields);
    if (taxFields.length) {
      sections.push({
        title: "Porez",
        items: taxFields,
      });
    }

    const vatFields = makeItems(d.vat_fields);
    if (vatFields.length) {
      sections.push({
        title: "PDV",
        items: vatFields,
      });
    }

    return sections;
  }, [taxUiSchemaQuery.data]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-800">Postavke</h2>
            <p className="mt-1 text-xs text-slate-500">
              Podešavanja firme, poreskog profila i pretplate.
            </p>
          </div>

          <div className="text-right">
            <div className="text-[11px] text-slate-400">Tenant</div>
            <div className="mt-0.5 inline-flex items-center rounded-full border border-slate-200 bg-white px-2 py-0.5 font-mono text-[11px] text-slate-700 shadow-sm">
              {formatTenantLabel(tenantCode)}
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-700 shadow-sm">
          <div className="font-medium text-slate-800">
            Postavke firme i poreskog profila
          </div>
          <p className="mt-1 text-xs text-slate-600">
            Podaci koje unesete ovdje koriste se u obračunima doprinosa i poreza,
            kao i u izvještajima i PDF dokumentima. Preporuka je da prvo završite
            poreski profil, pa tek onda unosite fakture i promet.
          </p>

          {!hasTaxProfileMinimum && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Poreski profil nije podešen. Da bi obračuni bili tačni, odaberite
              entitet i šemu u sekciji “Poreski profil”.
            </div>
          )}
        </div>
      </div>

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
            {taxQuery.error?.message && <li>Porezi: {taxQuery.error.message}</li>}
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

      {!anyLoading && !anyError && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3">
              <h3 className="text-sm font-semibold text-slate-800">Profil firme</h3>
              <p className="mt-1 text-[11px] text-slate-500">
                Osnovni podaci za zaglavlja, izvještaje i PDF dokumente.
              </p>
            </div>

            <div className="space-y-4">
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

              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                  Logo
                </div>
                <p className="mt-1 text-[11px] text-slate-600">
                  Upload logotipa (PNG/JPG/WebP). Sistem automatski konvertuje u
                  PNG i smanjuje na max 512px.
                </p>

                <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
                    <div className="flex justify-center sm:block">
                      <div className="grid h-32 w-40 place-items-center overflow-hidden rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
                        {logoObjectUrl ? (
                          <img
                            src={logoObjectUrl}
                            alt="Logo preview"
                            className="max-h-full max-w-full object-contain"
                            onError={() => {
                              setLogoObjectUrl((prev) => {
                                if (prev) URL.revokeObjectURL(prev);
                                return null;
                              });
                            }}
                          />
                        ) : (
                          <span className="text-[11px] text-slate-400">nema loga</span>
                        )}
                      </div>
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <input
                          ref={fileInputRef}
                          type="file"
                          accept="image/png,image/jpeg,image/webp"
                          className="block w-full text-xs text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-white hover:file:bg-slate-800 sm:w-auto"
                          onChange={(e) => {
                            const f = e.target.files?.[0];
                            if (!f) return;
                            setSelectedLogoName(f.name);
                            logoUploadMutation.mutate(f);
                          }}
                          disabled={logoUploadMutation.isPending}
                        />

                        {profileHasLogo && (
                          <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
                            Aktivni logo
                          </span>
                        )}
                      </div>

                      {selectedLogoName && (
                        <div className="mt-2 truncate text-[11px] text-slate-500">
                          Odabran fajl:{" "}
                          <span className="font-medium">{selectedLogoName}</span>
                        </div>
                      )}

                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          onClick={() => logoDeleteMutation.mutate()}
                          disabled={!profileHasLogo || logoDeleteMutation.isPending}
                          className="rounded-md border border-red-200 bg-white px-3 py-1.5 text-[11px] font-medium text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {logoDeleteMutation.isPending ? "Briše se..." : "Obriši logo"}
                        </button>
                      </div>

                      {logoUploadMutation.error && (
                        <p className="mt-2 text-[11px] text-red-600">
                          {logoUploadMutation.error instanceof Error
                            ? logoUploadMutation.error.message
                            : "Greška pri upload-u."}
                        </p>
                      )}
                      {logoDeleteMutation.error && (
                        <p className="mt-2 text-[11px] text-red-600">
                          {logoDeleteMutation.error instanceof Error
                            ? logoDeleteMutation.error.message
                            : "Greška pri brisanju."}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
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
                className="inline-flex w-full items-center justify-center rounded-md bg-slate-900 px-3 py-2 text-xs font-medium text-white shadow-sm hover:bg-slate-800 disabled:opacity-60"
              >
                {profileMutation.isPending ? "Snima se..." : "Sačuvaj profil"}
              </button>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3">
              <h3 className="text-sm font-semibold text-slate-800">Poreski profil</h3>
              <p className="mt-1 text-[11px] text-slate-500">
                Birate entitet i šemu obračuna. EVIDENT će automatski povlačiti
                parametre iz Admin konstanti.
              </p>

              {taxUiSchemaBanner && (
                <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-700">
                  <span className="font-medium">Admin konstante:</span>{" "}
                  {taxUiSchemaBanner}
                </div>
              )}

              {taxUiSchemaQuery.isError && (
                <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-800">
                  UI schema nije dostupna ({taxUiSchemaQuery.error?.message}). Koristim
                  fallback vrijednosti.
                </div>
              )}
            </div>

            <div className="space-y-4">
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
                    Šema obračuna (scenario)
                  </label>
                  <select
                    value={taxForm.scenario_key}
                    onChange={(e) =>
                      setTaxForm((t) => ({
                        ...t,
                        scenario_key: e.target.value as ScenarioKey,
                      }))
                    }
                    className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-xs text-slate-700 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                  >
                    <option value="">Odaberi…</option>
                    {uiScenarioOptions.map((s) => (
                      <option key={String(s.key)} value={String(s.key)}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                  <p className="mt-1 text-[11px] text-slate-400">
                    Šema određuje koji set Admin konstanti se primjenjuje za obračun.
                  </p>
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                  Režim oporezivanja (legacy; kasnije se uklanja iz UI)
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

              <div className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                <input
                  id="has_additional_activity"
                  type="checkbox"
                  checked={taxForm.has_additional_activity}
                  disabled={taxForm.entity !== "RS"}
                  onChange={(e) =>
                    setTaxForm((t) => ({
                      ...t,
                      has_additional_activity: e.target.checked,
                    }))
                  }
                />
                <label htmlFor="has_additional_activity" className="text-xs text-slate-700">
                  Dopunska djelatnost / drugi osnov
                  {taxForm.entity !== "RS" && (
                    <span className="ml-1 text-slate-400">(primjenjuje se samo za RS)</span>
                  )}
                </label>
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Parametri iz Admin konstanti
                </div>
                <p className="mt-2 text-[11px] text-slate-600">
                  Za izabrani entitet i scenario sistem koristi aktivni set iz Admin
                  konstanti. Ručni unos doprinosa više nije primarni workflow na ovoj
                  stranici.
                </p>

                {taxUiSummary.length > 0 ? (
                  <div className="mt-4 space-y-3">
                    {taxUiSummary.map((section) => (
                      <div
                        key={section.title}
                        className="rounded-md border border-slate-200 bg-white p-3"
                      >
                        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                          {section.title}
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {section.items.map((item) => (
                            <span
                              key={item}
                              className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-700"
                            >
                              {item}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="mt-3 rounded-md border border-slate-200 bg-white px-3 py-2 text-[11px] text-slate-600">
                    Nema dodatnih UI schema detalja za prikaz.
                  </div>
                )}

                <div className="mt-4 rounded-md border border-slate-200 bg-white px-3 py-2 text-[11px] text-slate-600">
                  Trenutni legacy režim:{" "}
                  <span className="font-medium text-slate-800">
                    {formatRegimeLabel(taxForm.regime)}
                  </span>
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
                className="inline-flex w-full items-center justify-center rounded-md bg-slate-900 px-3 py-2 text-xs font-medium text-white shadow-sm hover:bg-slate-800 disabled:opacity-60"
              >
                {taxMutation.isPending ? "Snima se..." : "Sačuvaj poreski profil"}
              </button>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3">
              <h3 className="text-sm font-semibold text-slate-800">Pretplata</h3>
              <p className="mt-1 text-[11px] text-slate-500">
                Ovdje se prikazuje status pretplate. Promjena plana ide kroz naplatu
                (Billing).
              </p>
            </div>

            <div className="space-y-3">
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                      Trenutni plan
                    </div>
                    <div className="mt-1 text-sm font-semibold text-slate-900">
                      {formatPlanLabel(currentPlan)}
                    </div>
                  </div>

                  <div className="text-right">
                    <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                      Status
                    </div>
                    <div className="mt-1 inline-flex items-center rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] font-medium text-slate-700">
                      Aktivno (dev)
                    </div>
                  </div>
                </div>

                <p className="mt-2 text-[11px] text-slate-600">
                  U sljedećem koraku dodajemo Billing stranicu i Stripe (ili drugi
                  provider) za nadogradnju/obnovu plana.
                </p>
              </div>

              <button
                type="button"
                onClick={() => {
                  window.location.href = "/billing";
                }}
                className="mt-1 inline-flex w-full items-center justify-center rounded-md bg-slate-900 px-3 py-2 text-xs font-medium text-white shadow-sm hover:bg-slate-800"
              >
                Upravljaj pretplatom
              </button>

              <button
                type="button"
                onClick={() => {
                  profileQuery.refetch();
                  taxQuery.refetch();
                  subQuery.refetch();
                  taxUiSchemaQuery.refetch();
                  notifyProfileSettingsUpdated();
                }}
                className="inline-flex w-full items-center justify-center rounded-md border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                Osvježi sa servera
              </button>

              <div className="rounded-md border border-slate-200 bg-white p-3 text-xs text-slate-600">
                <p className="font-medium text-slate-700">Napomena</p>
                <p className="mt-1">
                  Backend trenutno podržava “plan” kao feature-toggle. UI ovdje više
                  ne nudi ručnu promjenu plana, da se izbjegne pogrešna očekivanja u
                  produkciji.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}