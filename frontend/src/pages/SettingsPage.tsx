// /home/miso/dev/sp-app/sp-app/frontend/src/pages/SettingsPage.tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";

import type {
  ProfileSettingsRead,
  TaxProfileSettingsRead,
  SubscriptionSettingsRead,
  SubscriptionPlan,
  TenantEntity,
  TaxRegime,
  ScenarioKey,
  TaxProfileUiSchemaResponse,
  UiResolvedValue,
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

function isValidOptionalEmail(value: string): boolean {
  const email = value.trim();
  if (!email) return true;
  if (/\s/.test(email)) return false;
  if ((email.match(/@/g) ?? []).length !== 1) return false;

  const [local, domain] = email.split("@");
  return Boolean(
    local &&
      domain &&
      domain.includes(".") &&
      !domain.startsWith(".") &&
      !domain.endsWith("."),
  );
}

function getProfileSaveErrorMessage(error: unknown): string {
  if (
    error instanceof Error &&
    (error.message === "Naziv poslovanja je obavezan." ||
      error.message === "Unesite ispravnu email adresu.")
  ) {
    return error.message;
  }

  if (axios.isAxiosError(error) && error.response?.status === 422) {
    const detail = error.response.data?.detail;
    if (
      Array.isArray(detail) &&
      detail.some(
        (item) =>
          Array.isArray(item?.loc) && item.loc[item.loc.length - 1] === "email",
      )
    ) {
      return "Unesite ispravnu email adresu.";
    }
  }

  return "Profil nije moguće sačuvati. Pokušajte ponovo.";
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

function formatDateLabel(value?: string | null): string {
  if (!value) return "nije ograničeno";
  return value;
}

function notifyProfileSettingsUpdated() {
  window.dispatchEvent(new CustomEvent("profile-settings-updated"));
}

function getResolvedSectionTitle(section: UiResolvedValue["section"]): string {
  switch (section) {
    case "meta":
      return "Opšte";
    case "base":
      return "Osnovica";
    case "contributions":
      return "Doprinosi";
    case "tax":
      return "Porez";
    case "vat":
      return "PDV";
    default:
      return "Parametri";
  }
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
    phone: "",
    email: "",
    bank_name: "",
    bank_account: "",
    iban: "",
    swift_bic: "",
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
      phone: p.phone ?? "",
      email: p.email ?? "",
      bank_name: p.bank_name ?? "",
      bank_account: p.bank_account ?? "",
      iban: p.iban ?? "",
      swift_bic: p.swift_bic ?? "",
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
    queryKey: [
      "settings",
      "tax-ui-schema",
      taxForm.entity,
      taxForm.scenario_key,
    ],
    queryFn: async () => {
      return getTaxProfileUiSchema();
    },
    enabled:
      !taxQuery.isLoading &&
      !taxQuery.isError &&
      Boolean(taxForm.scenario_key),
    staleTime: 0,
    refetchOnWindowFocus: false,
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
      if (!isValidOptionalEmail(profileForm.email)) {
        throw new Error("Unesite ispravnu email adresu.");
      }
      return putProfileSettings({
        business_name: profileForm.business_name.trim(),
        address: profileForm.address.trim() ? profileForm.address.trim() : null,
        tax_id: profileForm.tax_id.trim() ? profileForm.tax_id.trim() : null,
        phone: profileForm.phone,
        email: profileForm.email,
        bank_name: profileForm.bank_name,
        bank_account: profileForm.bank_account,
        iban: profileForm.iban,
        swift_bic: profileForm.swift_bic,
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
      await taxUiSchemaQuery.refetch();
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

    if (d.constants_set_id == null) {
      return "Nema aktivnog seta Admin konstanti za izabrani scenario.";
    }

    return `Set #${d.constants_set_id} • važi od ${formatDateLabel(
      d.constants_effective_from,
    )} do ${formatDateLabel(d.constants_effective_to)} • valuta ${
      d.constants_currency ?? "BAM"
    }`;
  }, [taxUiSchemaQuery.data]);

  const hasActiveConstantsSet = useMemo(() => {
    return taxUiSchemaQuery.data?.constants_set_id != null;
  }, [taxUiSchemaQuery.data]);

  const resolvedValueSections = useMemo(() => {
    const values = taxUiSchemaQuery.data?.resolved_values ?? [];
    const visible = values.filter(
      (item) => item.value != null && String(item.value).trim() !== "",
    );

    const orderedSections: UiResolvedValue["section"][] = [
      "meta",
      "base",
      "contributions",
      "tax",
      "vat",
    ];

    return orderedSections
      .map((section) => ({
        section,
        title: getResolvedSectionTitle(section),
        items: visible.filter((item) => item.section === section),
      }))
      .filter((section) => section.items.length > 0);
  }, [taxUiSchemaQuery.data]);

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 px-5 py-6 text-white sm:px-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-300">
                Evident · konfiguracija sistema
              </p>

              <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
                Postavke
              </h1>

              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
                Podešavanja firme, poreskog profila, logotipa i pretplate.
                Ovi podaci se koriste u obračunima, izvještajima i dokumentima.
              </p>

              <div className="mt-4 flex flex-wrap items-center gap-2 text-[11px] text-slate-300">
                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1">
                  Tenant:{" "}
                  <span className="font-mono font-semibold text-white">
                    {formatTenantLabel(tenantCode)}
                  </span>
                </span>

                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1">
                  Plan:{" "}
                  <span className="font-semibold text-white">
                    {formatPlanLabel(currentPlan)}
                  </span>
                </span>

                <span
                  className={
                    hasTaxProfileMinimum
                      ? "rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-emerald-200"
                      : "rounded-full border border-amber-400/20 bg-amber-400/10 px-3 py-1 text-amber-200"
                  }
                >
                  Poreski profil:{" "}
                  <span className="font-semibold">
                    {hasTaxProfileMinimum ? "podešen" : "nije podešen"}
                  </span>
                </span>
              </div>
            </div>

            <div className="grid gap-2 sm:grid-cols-2 lg:min-w-[360px]">
              <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
                <p className="text-xs text-slate-300">Firma</p>
                <p className="mt-1 truncate text-lg font-semibold text-white">
                  {profileForm.business_name || "Nije uneseno"}
                </p>
                <p className="mt-1 text-[11px] text-slate-400">
                  Naziv za dokumente i izvještaje.
                </p>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
                <p className="text-xs text-slate-300">Poreska šema</p>
                <p className="mt-1 truncate text-lg font-semibold text-white">
                  {taxForm.scenario_key
                    ? SCENARIO_META[taxForm.scenario_key].label
                    : "Nije odabrana"}
                </p>
                <p className="mt-1 text-[11px] text-slate-400">
                  Izvor obračunskih pravila.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {!hasTaxProfileMinimum && (
        <div className="rounded-3xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 shadow-sm">
          <p className="font-semibold">Poreski profil nije podešen.</p>
          <p className="mt-1 text-xs">
            Da bi obračuni bili tačni, odaberite entitet i šemu u sekciji
            “Poreski profil”, zatim sačuvajte promjene.
          </p>
        </div>
      )}

      {anyLoading && (
        <div className="rounded-3xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">
          Učitavam postavke...
        </div>
      )}

      {anyError && (
        <div className="rounded-3xl border border-red-200 bg-red-50 p-5 text-sm text-red-700 shadow-sm">
          <p className="font-semibold">Greška pri učitavanju postavki.</p>
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
            className="mt-4 rounded-2xl border border-red-200 bg-white px-4 py-2 text-xs font-semibold text-red-700 hover:bg-red-50"
          >
            Pokušaj ponovo
          </button>
        </div>
      )}

      {!anyLoading && !anyError && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_1.25fr_0.85fr]">
          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                Profil firme
              </p>
              <h2 className="mt-1 text-lg font-semibold text-slate-900">
                Osnovni podaci i logo
              </h2>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Koristi se za zaglavlja, izvještaje, PDF dokumente i globalni
                prikaz firme u aplikaciji.
              </p>
            </div>

            <div className="space-y-4">
              <label className="space-y-1 text-xs font-medium text-slate-600">
                Naziv poslovanja
                <input
                  value={profileForm.business_name}
                  onChange={(e) =>
                    setProfileForm((p) => ({
                      ...p,
                      business_name: e.target.value,
                    }))
                  }
                  className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                  placeholder="npr. SP Mišo"
                />
              </label>

              <label className="space-y-1 text-xs font-medium text-slate-600">
                Adresa
                <input
                  value={profileForm.address}
                  onChange={(e) =>
                    setProfileForm((p) => ({ ...p, address: e.target.value }))
                  }
                  className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                  placeholder="Ulica i broj, grad"
                />
              </label>

              <label className="space-y-1 text-xs font-medium text-slate-600">
                PIB/JIB
                <input
                  value={profileForm.tax_id}
                  onChange={(e) =>
                    setProfileForm((p) => ({ ...p, tax_id: e.target.value }))
                  }
                  className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                  placeholder="npr. 123456789"
                />
              </label>

              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-1 text-xs font-medium text-slate-600">
                  Telefon
                  <input
                    value={profileForm.phone}
                    onChange={(e) =>
                      setProfileForm((p) => ({ ...p, phone: e.target.value }))
                    }
                    maxLength={64}
                    className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                    placeholder="+387..."
                  />
                </label>
                <label className="space-y-1 text-xs font-medium text-slate-600">
                  Email
                  <input
                    type="email"
                    value={profileForm.email}
                    onChange={(e) =>
                      setProfileForm((p) => ({ ...p, email: e.target.value }))
                    }
                    maxLength={254}
                    className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                    placeholder="firma@example.com"
                  />
                </label>
              </div>

              <label className="space-y-1 text-xs font-medium text-slate-600">
                Naziv banke
                <input
                  value={profileForm.bank_name}
                  onChange={(e) =>
                    setProfileForm((p) => ({ ...p, bank_name: e.target.value }))
                  }
                  maxLength={128}
                  className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                />
              </label>

              <label className="space-y-1 text-xs font-medium text-slate-600">
                Broj bankovnog računa
                <input
                  value={profileForm.bank_account}
                  onChange={(e) =>
                    setProfileForm((p) => ({ ...p, bank_account: e.target.value }))
                  }
                  maxLength={128}
                  className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                />
              </label>

              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-1 text-xs font-medium text-slate-600">
                  IBAN
                  <input
                    value={profileForm.iban}
                    onChange={(e) =>
                      setProfileForm((p) => ({ ...p, iban: e.target.value }))
                    }
                    maxLength={64}
                    className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                  />
                </label>
                <label className="space-y-1 text-xs font-medium text-slate-600">
                  SWIFT/BIC
                  <input
                    value={profileForm.swift_bic}
                    onChange={(e) =>
                      setProfileForm((p) => ({ ...p, swift_bic: e.target.value }))
                    }
                    maxLength={32}
                    className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                  />
                </label>
              </div>

              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                      Logo
                    </p>
                    <p className="mt-1 text-xs leading-5 text-slate-600">
                      PNG/JPG/WebP. Backend konvertuje u PNG i smanjuje na max
                      512px.
                    </p>
                  </div>

                  {profileHasLogo && (
                    <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-[11px] font-semibold text-emerald-700">
                      Aktivno
                    </span>
                  )}
                </div>

                <div className="mt-4 grid gap-4">
                  <div className="mx-auto grid aspect-square w-full max-w-48 place-items-center overflow-hidden rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                    {logoObjectUrl ? (
                      <img
                        src={logoObjectUrl}
                        alt="Logo preview"
                        className="h-full w-full object-contain object-center"
                        onError={() => {
                          setLogoObjectUrl((prev) => {
                            if (prev) URL.revokeObjectURL(prev);
                            return null;
                          });
                        }}
                      />
                    ) : (
                      <span className="text-xs text-slate-400">nema loga</span>
                    )}
                  </div>

                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    className="block w-full text-xs text-slate-600 file:mr-3 file:rounded-xl file:border-0 file:bg-slate-950 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-white hover:file:bg-slate-800"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (!f) return;
                      setSelectedLogoName(f.name);
                      logoUploadMutation.mutate(f);
                    }}
                    disabled={logoUploadMutation.isPending}
                  />

                  {selectedLogoName && (
                    <div className="truncate text-[11px] text-slate-500">
                      Odabran fajl:{" "}
                      <span className="font-medium">{selectedLogoName}</span>
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={() => logoDeleteMutation.mutate()}
                    disabled={!profileHasLogo || logoDeleteMutation.isPending}
                    className="rounded-2xl border border-red-200 bg-white px-4 py-2 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {logoDeleteMutation.isPending ? "Briše se..." : "Obriši logo"}
                  </button>

                  {logoUploadMutation.error && (
                    <p className="text-xs text-red-600">
                      {logoUploadMutation.error instanceof Error
                        ? logoUploadMutation.error.message
                        : "Greška pri upload-u."}
                    </p>
                  )}

                  {logoDeleteMutation.error && (
                    <p className="text-xs text-red-600">
                      {logoDeleteMutation.error instanceof Error
                        ? logoDeleteMutation.error.message
                        : "Greška pri brisanju."}
                    </p>
                  )}
                </div>
              </div>

              {profileMutation.isSuccess && (
                <p className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs font-medium text-emerald-800">
                  Profil je uspješno sačuvan.
                </p>
              )}

              {profileMutation.error && (
                <p className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-xs font-medium text-red-700">
                  {getProfileSaveErrorMessage(profileMutation.error)}
                </p>
              )}

              <button
                type="button"
                onClick={() => profileMutation.mutate()}
                disabled={profileMutation.isPending}
                className="inline-flex w-full items-center justify-center rounded-2xl bg-slate-950 px-4 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {profileMutation.isPending ? "Snima se..." : "Sačuvaj profil"}
              </button>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                Poreski profil
              </p>
              <h2 className="mt-1 text-lg font-semibold text-slate-900">
                Entitet, scenario i aktivne konstante
              </h2>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                EVIDENT automatski povlači obračunske parametre iz Admin
                konstanti za izabrani scenario.
              </p>

              {taxUiSchemaBanner && (
                <div
                  className={
                    hasActiveConstantsSet
                      ? "mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs text-emerald-800"
                      : "mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800"
                  }
                >
                  <span className="font-semibold">Admin konstante:</span>{" "}
                  {taxUiSchemaBanner}
                </div>
              )}

              {taxUiSchemaQuery.isError && (
                <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">
                  UI schema nije dostupna ({taxUiSchemaQuery.error?.message}).
                  Koristim fallback vrijednosti.
                </div>
              )}
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <label className="space-y-1 text-xs font-medium text-slate-600">
                  Entitet
                  <select
                    value={taxForm.entity}
                    onChange={(e) =>
                      setTaxForm((t) => ({
                        ...t,
                        entity: e.target.value as TenantEntity,
                      }))
                    }
                    className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                  >
                    <option value="RS">RS</option>
                    <option value="FBiH">FBiH</option>
                    <option value="Brcko">Brčko</option>
                  </select>
                </label>

                <label className="space-y-1 text-xs font-medium text-slate-600">
                  Šema obračuna
                  <select
                    value={taxForm.scenario_key}
                    onChange={(e) =>
                      setTaxForm((t) => ({
                        ...t,
                        scenario_key: e.target.value as ScenarioKey,
                      }))
                    }
                    className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                  >
                    <option value="">Odaberi…</option>
                    {uiScenarioOptions.map((s) => (
                      <option key={String(s.key)} value={String(s.key)}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_auto]">
                <label className="space-y-1 text-xs font-medium text-slate-600">
                  Režim oporezivanja
                  <select
                    value={taxForm.regime}
                    onChange={(e) =>
                      setTaxForm((t) => ({
                        ...t,
                        regime: e.target.value as TaxRegime,
                      }))
                    }
                    className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                  >
                    <option value="pausal">Paušal</option>
                    <option value="two_percent">2% (stvarni prihod)</option>
                  </select>
                </label>

                <label className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-700">
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
                  <span>
                    Dopunska djelatnost
                    {taxForm.entity !== "RS" && (
                      <span className="ml-1 text-slate-400">(samo RS)</span>
                    )}
                  </span>
                </label>
              </div>

              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                      Aktivni obračunski parametri
                    </p>
                    <p className="mt-1 text-xs leading-5 text-slate-600">
                      Vrijednosti dolaze iz aktivnog seta Admin konstanti za
                      trenutno sačuvani poreski scenario.
                    </p>
                  </div>

                  {taxUiSchemaQuery.data?.constants_set_id != null && (
                    <div className="shrink-0 rounded-full border border-emerald-200 bg-white px-3 py-1 text-xs font-semibold text-emerald-700">
                      Set #{taxUiSchemaQuery.data.constants_set_id}
                    </div>
                  )}
                </div>

                {taxUiSchemaQuery.isLoading && (
                  <div className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs text-slate-600">
                    Učitavam aktivne obračunske parametre...
                  </div>
                )}

                {!taxUiSchemaQuery.isLoading && resolvedValueSections.length > 0 && (
                  <div className="mt-4 space-y-4">
                    {resolvedValueSections.map((section) => (
                      <div
                        key={section.section}
                        className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
                      >
                        <div className="mb-3 flex items-center justify-between gap-3">
                          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                            {section.title}
                          </div>
                          <div className="text-[11px] text-slate-400">
                            {section.items.length} param.
                          </div>
                        </div>

                        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                          {section.items.map((item) => (
                            <div
                              key={item.key}
                              className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2"
                            >
                              <div className="text-[11px] leading-snug text-slate-500">
                                {item.label}
                              </div>
                              <div className="mt-1 break-words text-sm font-semibold text-slate-900">
                                {item.value}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}

                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs text-emerald-800">
                      Sistem koristi ove vrijednosti automatski. Ručni unos stopa
                      i osnovica ovdje više nije potreban dok postoji validan
                      Admin Constants set.
                    </div>
                  </div>
                )}

                {!taxUiSchemaQuery.isLoading &&
                  resolvedValueSections.length === 0 && (
                    <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">
                      Za trenutno odabrani scenario nema aktivnih obračunskih
                      parametara za prikaz. Provjeri da li je poreski profil
                      sačuvan i da li u Admin Constants postoji aktivan set za
                      ovaj entitet i scenario.
                    </div>
                  )}

                <div className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs text-slate-600">
                  Režim:{" "}
                  <span className="font-semibold text-slate-800">
                    {formatRegimeLabel(taxForm.regime)}
                  </span>
                  <span className="ml-1 text-slate-400">
                    — čuva se radi kompatibilnosti sa postojećim backend modelom.
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
                className="inline-flex w-full items-center justify-center rounded-2xl bg-slate-950 px-4 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {taxMutation.isPending ? "Snima se..." : "Sačuvaj poreski profil"}
              </button>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                Pretplata
              </p>
              <h2 className="mt-1 text-lg font-semibold text-slate-900">
                Plan i sistemski status
              </h2>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Status pretplate i budući Billing ulaz. Promjena plana kasnije
                ide kroz Billing modul.
              </p>
            </div>

            <div className="space-y-4">
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                      Trenutni plan
                    </div>
                    <div className="mt-1 text-lg font-semibold text-slate-900">
                      {formatPlanLabel(currentPlan)}
                    </div>
                  </div>

                  <div className="text-right">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                      Status
                    </div>
                    <div className="mt-1 inline-flex items-center rounded-full border border-emerald-200 bg-white px-3 py-1 text-xs font-semibold text-emerald-700">
                      Aktivno
                    </div>
                  </div>
                </div>

                <p className="mt-3 text-xs leading-5 text-slate-600">
                  Backend trenutno podržava plan kao feature-toggle. UI ne nudi
                  ručnu promjenu plana da se izbjegnu pogrešna očekivanja u
                  produkciji.
                </p>
              </div>

              <button
                type="button"
                onClick={() => {
                  window.location.href = "/billing";
                }}
                className="inline-flex w-full items-center justify-center rounded-2xl bg-slate-950 px-4 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-slate-800"
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
                className="inline-flex w-full items-center justify-center rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
              >
                Osvježi sa servera
              </button>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 text-xs leading-5 text-slate-600">
                <p className="font-semibold text-slate-800">Napomena</p>
                <p className="mt-1">
                  Billing stranica i stvarna integracija plaćanja dolaze kasnije.
                  Ova sekcija sada služi kao pregled sistemskog statusa i plana.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}