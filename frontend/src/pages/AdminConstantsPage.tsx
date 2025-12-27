// /home/miso/dev/sp-app/sp-app/frontend/src/pages/AdminConstantsPage.tsx

import { useEffect, useMemo, useState } from "react";
import type {
  AppConstantsSetCreate,
  AppConstantsSetRead,
  Jurisdiction,
} from "../types/constants";
import {
  adminConstantsCreate,
  adminConstantsList,
  constantsCurrent,
} from "../services/adminConstantsApi";

type ConstantsForm = {
  scenario_key: string;

  // common
  currency: string;

  // VAT (percent input in UI)
  vat_standard_rate_percent: string;
  vat_entry_threshold_bam: string;

  // Tax (percent input in UI) + optional monthly flat amount (KM)
  income_tax_rate_percent: string;
  flat_tax_monthly_amount_bam: string;

  // Contributions (percent input in UI)
  pension_rate_percent: string;
  health_rate_percent: string;
  unemployment_rate_percent: string;

  // RS + BD: avg gross wage + base percent -> calculated base (KM)
  avg_gross_wage_prev_year_bam: string;
  contrib_base_percent_of_avg_gross: string;

  // FBiH: monthly base (KM)
  monthly_contrib_base_bam: string;

  // Optional min base (KM) (kept as generic; max is intentionally removed from UI per spec)
  contrib_base_min_bam: string;

  // Notes / sources
  source_note: string;
  source_reference: string;
};

type JsonParseResult = { ok: true; value: any } | { ok: false; error: string };

function safeJsonParse(input: string): JsonParseResult {
  try {
    const v = JSON.parse(input);
    return { ok: true, value: v };
  } catch (e: any) {
    return { ok: false, error: e?.message ?? "Invalid JSON" };
  }
}

function todayYmd(): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function toNumOrNull(v: string): number | null {
  const s = (v ?? "").trim();
  if (s === "") return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function clampPercent(n: number): number {
  if (n < 0) return 0;
  if (n > 100) return 100;
  return n;
}

function percentStrToRateDecimal(percentStr: string): number | null {
  const n = toNumOrNull(percentStr);
  if (n === null) return null;
  const p = clampPercent(n);
  return p / 100;
}

function rateDecimalToPercentStr(rate: any): string {
  if (rate === null || rate === undefined) return "";
  const n = typeof rate === "number" ? rate : Number(rate);
  if (!Number.isFinite(n)) return "";
  const p = n * 100;
  const fixed = p.toFixed(6);
  const trimmed = fixed.replace(/\.?0+$/, "");
  return trimmed;
}

function numToStr(x: any): string {
  if (x === null || x === undefined) return "";
  if (typeof x === "number") return String(x);
  if (typeof x === "string") return x;
  return "";
}

// V1 Scenario katalog (spec)
const SCENARIOS: Array<{
  key: string;
  label: string;
  hint: string;
  jurisdiction: Jurisdiction;
}> = [
  {
    key: "rs_primary",
    label: "RS – Osnovna djelatnost",
    hint: "V1: osnovna djelatnost (primary).",
    jurisdiction: "RS",
  },
  {
    key: "rs_supplementary",
    label: "RS – Dopunska djelatnost (uz zaposlenje)",
    hint: "V1: dopunska djelatnost (supplementary).",
    jurisdiction: "RS",
  },

  {
    key: "fbih_obrt",
    label: "FBiH – Obrt i srodne djelatnosti",
    hint: "V1: zanati/usluge (frizer, automehaničar, električar, servisi…).",
    jurisdiction: "FBiH",
  },
  {
    key: "fbih_slobodna",
    label: "FBiH – Slobodna zanimanja",
    hint: "V1: IT/dizajn/konsalting/freelance i sl.",
    jurisdiction: "FBiH",
  },

  {
    key: "bd_samostalna",
    label: "BD – Samostalna djelatnost",
    hint: "V1: jedinstvena šema za BD (zanati/usluge/IT/freelance).",
    jurisdiction: "BD",
  },
];

function defaultScenarioForJurisdiction(j: Jurisdiction): string {
  if (j === "RS") return "rs_primary";
  if (j === "FBiH") return "fbih_obrt";
  return "bd_samostalna";
}

function defaultForm(j: Jurisdiction, scenario_key?: string): ConstantsForm {
  return {
    scenario_key: scenario_key ?? defaultScenarioForJurisdiction(j),

    currency: "BAM",

    // percent input defaults (UI)
    vat_standard_rate_percent: "17",
    vat_entry_threshold_bam: "",

    income_tax_rate_percent: "10",
    flat_tax_monthly_amount_bam: "",

    pension_rate_percent: "18",
    health_rate_percent: "12",
    unemployment_rate_percent: "1.5",

    // RS/BD
    avg_gross_wage_prev_year_bam: "",
    contrib_base_percent_of_avg_gross: "",

    // FBiH
    monthly_contrib_base_bam: "",

    contrib_base_min_bam: "",

    source_note: "",
    source_reference: "",
  };
}

function computeCalculatedBaseBam(
  avgGrossStr: string,
  basePercentStr: string
): number | null {
  const avg = toNumOrNull(avgGrossStr);
  const p = toNumOrNull(basePercentStr);
  if (avg === null || p === null) return null;
  const pct = clampPercent(p);
  return avg * (pct / 100);
}

function buildPayloadFromForm(j: Jurisdiction, form: ConstantsForm): any {
  const vatRate = percentStrToRateDecimal(form.vat_standard_rate_percent);
  const incomeTaxRate = percentStrToRateDecimal(form.income_tax_rate_percent);
  const pensionRate = percentStrToRateDecimal(form.pension_rate_percent);
  const healthRate = percentStrToRateDecimal(form.health_rate_percent);
  const unempRate = percentStrToRateDecimal(form.unemployment_rate_percent);

  const calculatedBase =
    j === "RS" || j === "BD"
      ? computeCalculatedBaseBam(
          form.avg_gross_wage_prev_year_bam,
          form.contrib_base_percent_of_avg_gross
        )
      : null;

  const payload: any = {
    scenario_key: form.scenario_key,

    base: {
      currency: (form.currency || "BAM").trim() || "BAM",
    },

    vat: {
      standard_rate: vatRate,
      entry_threshold_bam: toNumOrNull(form.vat_entry_threshold_bam),
    },

    tax: {
      income_tax_rate: incomeTaxRate,
      flat_tax_monthly_amount_bam: toNumOrNull(form.flat_tax_monthly_amount_bam),
    },

    contributions: {
      pension_rate: pensionRate,
      health_rate: healthRate,
      unemployment_rate: unempRate,
      base_min_bam: toNumOrNull(form.contrib_base_min_bam),
    },

    meta: {
      source_note: (form.source_note ?? "").trim() || null,
      source_reference: (form.source_reference ?? "").trim() || null,
      updated_at_ui: new Date().toISOString(),
    },
  };

  if (j === "RS") {
    payload.base.avg_gross_wage_prev_year_bam = toNumOrNull(
      form.avg_gross_wage_prev_year_bam
    );
    payload.base.contrib_base_percent_of_avg_gross = toNumOrNull(
      form.contrib_base_percent_of_avg_gross
    );
    payload.base.calculated_contrib_base_bam = calculatedBase;
  }

  if (j === "FBiH") {
    payload.base.monthly_contrib_base_bam = toNumOrNull(
      form.monthly_contrib_base_bam
    );
  }

  if (j === "BD") {
    payload.base.avg_gross_prev_year_bam = toNumOrNull(
      form.avg_gross_wage_prev_year_bam
    );
    payload.base.base_percent_of_avg_gross = toNumOrNull(
      form.contrib_base_percent_of_avg_gross
    );
    payload.base.calculated_contrib_base_bam = calculatedBase;
  }

  return payload;
}

function hydrateFormFromPayload(j: Jurisdiction, payload: any): ConstantsForm {
  const d = defaultForm(j);
  const p = payload ?? {};

  const base = p.base ?? {};
  const vat = p.vat ?? {};
  const tax = p.tax ?? {};
  const contrib = p.contributions ?? {};
  const meta = p.meta ?? {};

  const scenario_key =
    typeof p.scenario_key === "string" ? p.scenario_key : d.scenario_key;

  const currency = typeof base.currency === "string" ? base.currency : d.currency;

  const vat_standard_rate_percent =
    rateDecimalToPercentStr(vat.standard_rate) || d.vat_standard_rate_percent;
  const income_tax_rate_percent =
    rateDecimalToPercentStr(tax.income_tax_rate) || d.income_tax_rate_percent;
  const pension_rate_percent =
    rateDecimalToPercentStr(contrib.pension_rate) || d.pension_rate_percent;
  const health_rate_percent =
    rateDecimalToPercentStr(contrib.health_rate) || d.health_rate_percent;
  const unemployment_rate_percent =
    rateDecimalToPercentStr(contrib.unemployment_rate) ||
    d.unemployment_rate_percent;

  const vat_entry_threshold_bam = numToStr(vat.entry_threshold_bam);
  const flat_tax_monthly_amount_bam = numToStr(tax.flat_tax_monthly_amount_bam);
  const contrib_base_min_bam = numToStr(contrib.base_min_bam);

  let avg_gross_wage_prev_year_bam = "";
  let contrib_base_percent_of_avg_gross = "";

  if (j === "RS") {
    avg_gross_wage_prev_year_bam = numToStr(base.avg_gross_wage_prev_year_bam);
    contrib_base_percent_of_avg_gross = numToStr(
      base.contrib_base_percent_of_avg_gross
    );
  } else if (j === "BD") {
    avg_gross_wage_prev_year_bam = numToStr(base.avg_gross_prev_year_bam);
    contrib_base_percent_of_avg_gross = numToStr(base.base_percent_of_avg_gross);
  }

  const monthly_contrib_base_bam =
    j === "FBiH" ? numToStr(base.monthly_contrib_base_bam) : "";

  return {
    scenario_key,

    currency,

    vat_standard_rate_percent,
    vat_entry_threshold_bam,

    income_tax_rate_percent,
    flat_tax_monthly_amount_bam,

    pension_rate_percent,
    health_rate_percent,
    unemployment_rate_percent,

    avg_gross_wage_prev_year_bam,
    contrib_base_percent_of_avg_gross,

    monthly_contrib_base_bam,

    contrib_base_min_bam,

    source_note: typeof meta.source_note === "string" ? meta.source_note : "",
    source_reference:
      typeof meta.source_reference === "string" ? meta.source_reference : "",
  };
}

/**
 * Tailwind UI-like primitives (labels, inputs, cards)
 */

function FieldLabel({
  label,
  hint,
  htmlFor,
}: {
  label: string;
  hint?: string;
  htmlFor?: string;
}) {
  return (
    <div className="mb-1">
      <label
        htmlFor={htmlFor}
        className="block text-sm font-medium text-slate-700"
      >
        {label}
      </label>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

function Card({
  title,
  subtitle,
  right,
  children,
}: {
  title: string;
  subtitle?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-4 py-4 sm:px-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-slate-900 truncate">
              {title}
            </h3>
            {subtitle ? (
              <p className="mt-1 text-sm text-slate-600">{subtitle}</p>
            ) : null}
          </div>
          {right ? <div className="shrink-0">{right}</div> : null}
        </div>
      </div>
      <div className="px-4 py-5 sm:px-6">{children}</div>
    </div>
  );
}

function SectionTitle({
  title,
  subtitle,
}: {
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="mb-4">
      <h4 className="text-sm font-semibold text-slate-900">{title}</h4>
      {subtitle ? <p className="mt-1 text-sm text-slate-600">{subtitle}</p> : null}
    </div>
  );
}

function Input({
  id,
  value,
  onChange,
  placeholder,
  type = "text",
  readOnly = false,
}: {
  id?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  readOnly?: boolean;
}) {
  return (
    <input
      id={id}
      type={type}
      value={value}
      readOnly={readOnly}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={[
        "block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm",
        "placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200",
        readOnly ? "bg-slate-50 text-slate-700" : "",
      ].join(" ")}
    />
  );
}

function TextArea({
  id,
  value,
  onChange,
  rows = 3,
  mono = false,
  placeholder,
}: {
  id?: string;
  value: string;
  onChange: (v: string) => void;
  rows?: number;
  mono?: boolean;
  placeholder?: string;
}) {
  return (
    <textarea
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      rows={rows}
      placeholder={placeholder}
      className={[
        "block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm",
        "placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200",
        mono ? "font-mono" : "",
      ].join(" ")}
    />
  );
}

function Button({
  children,
  onClick,
  disabled,
  variant = "primary",
  type = "button",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  type?: "button" | "submit";
}) {
  const base =
    "inline-flex items-center justify-center rounded-md px-3 py-2 text-sm font-semibold shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2";
  const variants: Record<string, string> = {
    primary:
      "bg-slate-900 text-white hover:bg-slate-800 focus:ring-slate-300",
    secondary:
      "bg-white text-slate-900 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 focus:ring-slate-200",
    ghost:
      "bg-transparent text-slate-700 hover:bg-slate-100 focus:ring-slate-200",
    danger:
      "bg-rose-600 text-white hover:bg-rose-700 focus:ring-rose-300",
  };

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={[
        base,
        variants[variant],
        disabled ? "opacity-50 cursor-not-allowed" : "",
      ].join(" ")}
    >
      {children}
    </button>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700">
      {children}
    </span>
  );
}

function Tabs({
  value,
  onChange,
}: {
  value: Jurisdiction;
  onChange: (v: Jurisdiction) => void;
}) {
  const tabs: Array<{ key: Jurisdiction; label: string }> = [
    { key: "RS", label: "RS" },
    { key: "FBiH", label: "FBiH" },
    { key: "BD", label: "Brčko (BD)" },
  ];

  return (
    <div className="flex w-full max-w-xl rounded-lg bg-slate-100 p-1">
      {tabs.map((t) => {
        const active = t.key === value;
        return (
          <button
            key={t.key}
            type="button"
            onClick={() => onChange(t.key)}
            className={[
              "flex-1 rounded-md px-3 py-2 text-sm font-medium",
              active
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-700 hover:text-slate-900",
            ].join(" ")}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

function ScenarioSelect({
  jurisdiction,
  value,
  onChange,
  id,
}: {
  jurisdiction: Jurisdiction;
  value: string;
  onChange: (v: string) => void;
  id?: string;
}) {
  const options = SCENARIOS.filter((s) => s.jurisdiction === jurisdiction);
  const selected = options.find((s) => s.key === value);

  return (
    <div className="w-full">
      <FieldLabel
        htmlFor={id}
        label="Scenario / šema"
        hint={selected ? selected.hint : "Izaberi šemu za ovu jurisdikciju."}
      />
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={[
          "block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm",
          "focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200",
        ].join(" ")}
      >
        {options.map((s) => (
          <option key={s.key} value={s.key}>
            {s.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function FriendlyPayloadEditor({
  jurisdiction,
  form,
  setForm,
  derivedPayload,
  advanced,
  setAdvanced,
  raw,
  setRaw,
}: {
  jurisdiction: Jurisdiction;
  form: ConstantsForm;
  setForm: (next: ConstantsForm) => void;
  derivedPayload: string;
  advanced: boolean;
  setAdvanced: (v: boolean) => void;
  raw: string;
  setRaw: (v: string) => void;
}) {
  const isRS = jurisdiction === "RS";
  const isFBiH = jurisdiction === "FBiH";
  const isBD = jurisdiction === "BD";

  const calculatedBase =
    isRS || isBD
      ? computeCalculatedBaseBam(
          form.avg_gross_wage_prev_year_bam,
          form.contrib_base_percent_of_avg_gross
        )
      : null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-900">
            Payload (unos kroz formu)
          </div>
          <div className="mt-1 text-sm text-slate-600">
            Standardni unos kroz polja. Advanced JSON koristiš samo za privremene
            ključeve koje UI još ne podržava.
          </div>
        </div>
        <div className="shrink-0">
          <Button
            variant="secondary"
            onClick={() => {
              if (!advanced) setRaw(derivedPayload);
              setAdvanced(!advanced);
            }}
          >
            {advanced ? "Nazad na formu" : "Advanced JSON"}
          </Button>
        </div>
      </div>

      {!advanced ? (
        <>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div>
              <FieldLabel
                label="Scenario / šema (read-only)"
                hint="Scenario se bira iznad. Promjena scenarija automatski učitava aktivni set."
              />
              <Input value={form.scenario_key} onChange={() => {}} readOnly />
            </div>

            <div>
              <FieldLabel label="Valuta" hint="Najčešće BAM." />
              <Input
                value={form.currency}
                onChange={(v) => setForm({ ...form, currency: v })}
                placeholder="BAM"
              />
            </div>

            {isRS || isBD ? (
              <div>
                <FieldLabel
                  label={
                    isRS
                      ? "Prosječna bruto plata (prethodna godina) (KM)"
                      : "Prosječna bruto plata (BD) – prethodna godina (KM)"
                  }
                  hint="Decimal (npr. 2000.00)."
                />
                <Input
                  value={form.avg_gross_wage_prev_year_bam}
                  onChange={(v) =>
                    setForm({ ...form, avg_gross_wage_prev_year_bam: v })
                  }
                  placeholder="npr. 2000.00"
                />
              </div>
            ) : (
              <div className="hidden lg:block" />
            )}
          </div>

          {(isRS || isBD) && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <div>
                <FieldLabel
                  label={
                    isRS
                      ? "Osnovica doprinosa = % prosječne bruto plate"
                      : "Procenat prosječne bruto plate za osnovicu (%)"
                  }
                  hint="Unos u procentima (npr. 80 znači 80%)."
                />
                <Input
                  value={form.contrib_base_percent_of_avg_gross}
                  onChange={(v) =>
                    setForm({ ...form, contrib_base_percent_of_avg_gross: v })
                  }
                  placeholder="npr. 80"
                />
              </div>
              <div>
                <FieldLabel
                  label="Izračunata osnovica doprinosa (KM)"
                  hint="Read-only: avg_gross * (percent/100)."
                />
                <Input
                  value={calculatedBase === null ? "" : calculatedBase.toFixed(2)}
                  onChange={() => {}}
                  readOnly
                  placeholder="automatski izračun"
                />
              </div>
              <div className="hidden lg:block" />
            </div>
          )}

          {isFBiH && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <div>
                <FieldLabel
                  label="Mjesečna osnovica doprinosa (KM)"
                  hint="FBiH: primarni input. Decimal > 0 (npr. 1376.00)."
                />
                <Input
                  value={form.monthly_contrib_base_bam}
                  onChange={(v) =>
                    setForm({ ...form, monthly_contrib_base_bam: v })
                  }
                  placeholder="npr. 1376.00"
                />
              </div>
              <div className="hidden lg:block" />
              <div className="hidden lg:block" />
            </div>
          )}

          <div className="pt-2">
            <SectionTitle title="PDV" subtitle="Stopa i prag ulaska u PDV sistem." />
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <div>
                <FieldLabel
                  label="PDV stopa (%)"
                  hint="Unos u procentima (npr. 17). Sistem čuva 0.17."
                />
                <Input
                  value={form.vat_standard_rate_percent}
                  onChange={(v) =>
                    setForm({ ...form, vat_standard_rate_percent: v })
                  }
                  placeholder="17"
                />
              </div>
              <div>
                <FieldLabel
                  label="PDV prag ulaska (KM)"
                  hint="Opciono; npr. 50000"
                />
                <Input
                  value={form.vat_entry_threshold_bam}
                  onChange={(v) =>
                    setForm({ ...form, vat_entry_threshold_bam: v })
                  }
                  placeholder="50000"
                />
              </div>
              <div className="hidden lg:block" />
            </div>
          </div>

          <div className="pt-2">
            <SectionTitle
              title="Porez"
              subtitle="Stopa poreza i opcionalni paušalni mjesečni iznos."
            />
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <div>
                <FieldLabel
                  label="Porez na dohodak (%)"
                  hint="Unos u procentima (npr. 10). Sistem čuva 0.10."
                />
                <Input
                  value={form.income_tax_rate_percent}
                  onChange={(v) =>
                    setForm({ ...form, income_tax_rate_percent: v })
                  }
                  placeholder="10"
                />
              </div>
              <div>
                <FieldLabel
                  label="Paušalni porez (KM mjesečno)"
                  hint="Opciono (ako postoji fiksni mjesečni iznos)."
                />
                <Input
                  value={form.flat_tax_monthly_amount_bam}
                  onChange={(v) =>
                    setForm({ ...form, flat_tax_monthly_amount_bam: v })
                  }
                  placeholder="npr. 50.00"
                />
              </div>
              <div className="hidden lg:block" />
            </div>
          </div>

          <div className="pt-2">
            <SectionTitle
              title="Doprinosi"
              subtitle="Stope doprinosa (u procentima) i minimalna osnovica."
            />
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <div>
                <FieldLabel
                  label="Doprinos PIO (%)"
                  hint="Unos u % (npr. 18). Sistem čuva 0.18."
                />
                <Input
                  value={form.pension_rate_percent}
                  onChange={(v) => setForm({ ...form, pension_rate_percent: v })}
                  placeholder="18"
                />
              </div>
              <div>
                <FieldLabel
                  label="Zdravstveno (%)"
                  hint="Unos u % (npr. 12). Sistem čuva 0.12."
                />
                <Input
                  value={form.health_rate_percent}
                  onChange={(v) => setForm({ ...form, health_rate_percent: v })}
                  placeholder="12"
                />
              </div>
              <div>
                <FieldLabel
                  label="Nezaposlenost (%)"
                  hint="Unos u % (npr. 1.5). Sistem čuva 0.015."
                />
                <Input
                  value={form.unemployment_rate_percent}
                  onChange={(v) =>
                    setForm({ ...form, unemployment_rate_percent: v })
                  }
                  placeholder="1.5"
                />
              </div>
            </div>

            <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
              <div>
                <FieldLabel
                  label="Min osnovica doprinosa (KM)"
                  hint="Opciono (ako imamo minimalnu osnovicu u modelu)."
                />
                <Input
                  value={form.contrib_base_min_bam}
                  onChange={(v) => setForm({ ...form, contrib_base_min_bam: v })}
                  placeholder="npr. 1200.00"
                />
              </div>
              <div className="hidden lg:block" />
              <div className="hidden lg:block" />
            </div>
          </div>

          <div className="pt-2">
            <SectionTitle
              title="Izvori"
              subtitle="Napomena i referenca (audit-friendly)."
            />
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div>
                <FieldLabel
                  label="Napomena / izvor (source_note)"
                  hint="Kratko: odakle je uzeto (institucija/dokument)."
                />
                <TextArea
                  value={form.source_note}
                  onChange={(v) => setForm({ ...form, source_note: v })}
                  rows={3}
                  placeholder="npr. 'RZS / Službeni glasnik / odluka ...'"
                />
              </div>
              <div>
                <FieldLabel
                  label="Referenca (source_reference)"
                  hint="Link, broj službenog glasnika, naziv akta, itd."
                />
                <TextArea
                  value={form.source_reference}
                  onChange={(v) => setForm({ ...form, source_reference: v })}
                  rows={3}
                  placeholder="npr. 'SG RS 12/2025...' ili URL"
                />
              </div>
            </div>
          </div>

          <div className="pt-2">
            <SectionTitle title="Generisani payload (preview)" />
            <pre className="max-h-80 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-800">
              {derivedPayload}
            </pre>
          </div>
        </>
      ) : (
        <>
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Advanced JSON je za slučajeve kad želiš dodati dodatne ključeve prije
            nego što ih UI dobije kao polja.
          </div>
          <div>
            <FieldLabel
              label="payload (JSON)"
              hint="Mora biti validan JSON. Backend ga snima u app_constants_sets.payload."
            />
            <TextArea
              value={raw}
              onChange={setRaw}
              rows={12}
              mono
              placeholder='{ "example": true }'
            />
          </div>
        </>
      )}
    </div>
  );
}

function explainOverlap(detail: string): string {
  if ((detail ?? "").toLowerCase().includes("overlapping")) {
    return (
      "Ne može snimiti jer postoji set sa preklapajućim datumima za isti scenario. " +
      "Za rollover: novi set treba biti open-ended (Effective to prazno), " +
      "i Effective from mora biti POSLIJE trenutnog active seta u istom scenario-u. " +
      `Detalj: ${detail}`
    );
  }
  return detail;
}

export default function AdminConstantsPage() {
  const [activeTab, setActiveTab] = useState<Jurisdiction>("RS");

  const [scenarioByTab, setScenarioByTab] = useState<Record<Jurisdiction, string>>(
    {
      RS: defaultScenarioForJurisdiction("RS"),
      FBiH: defaultScenarioForJurisdiction("FBiH"),
      BD: defaultScenarioForJurisdiction("BD"),
    }
  );

  const activeScenario =
    scenarioByTab[activeTab] || defaultScenarioForJurisdiction(activeTab);

  const [items, setItems] = useState<AppConstantsSetRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [curItem, setCurItem] = useState<AppConstantsSetRead | null>(null);
  const [curLoading, setCurLoading] = useState(false);

  // "As of" za lookup aktivnog seta (default: danas)
  const [asOf, setAsOf] = useState<string>(todayYmd());

  const [effectiveFrom, setEffectiveFrom] = useState<string>(todayYmd());
  const [createdBy, setCreatedBy] = useState<string>(""); // audit-friendly default
  const [createdReason, setCreatedReason] = useState<string>("update constants");

  const [form, setForm] = useState<ConstantsForm>(() => defaultForm("RS"));

  const [advanced, setAdvanced] = useState(false);
  const [payloadRaw, setPayloadRaw] = useState<string>("");

  const derivedPayload = useMemo(() => {
    const payload = buildPayloadFromForm(activeTab, form);
    return JSON.stringify(payload, null, 2);
  }, [activeTab, form]);

  async function refreshHistory(j: Jurisdiction, scenario_key: string) {
    setLoading(true);
    setErr(null);
    try {
      const data = await adminConstantsList({ jurisdiction: j, scenario_key });
      setItems(data.items);
    } catch (e: any) {
      setErr(
        e?.response?.data?.detail ??
          e?.message ??
          "Failed to load constants history."
      );
    } finally {
      setLoading(false);
    }
  }

  async function refreshCurrent(j: Jurisdiction, scenario_key: string, asOfYmd: string) {
    setCurLoading(true);
    try {
      const res = await constantsCurrent({
        jurisdiction: j,
        scenario_key: scenario_key as any,
        as_of: asOfYmd,
      });
      if (res?.found && res?.item) {
        setCurItem(res.item);
        setForm(hydrateFormFromPayload(j, res.item.payload ?? {}));
      } else {
        setCurItem(null);
        setForm(defaultForm(j, scenario_key));
      }
    } catch {
      setCurItem(null);
      setForm(defaultForm(j, scenario_key));
    } finally {
      setCurLoading(false);
    }
  }

  async function refreshAll(j: Jurisdiction, scenario_key: string, asOfYmd: string) {
    await Promise.all([
      refreshHistory(j, scenario_key),
      refreshCurrent(j, scenario_key, asOfYmd),
    ]);
  }

  // Jedan efekat: tab + scenario
  useEffect(() => {
    setErr(null);
    setAdvanced(false);
    setPayloadRaw("");

    setAsOf(todayYmd());
    setEffectiveFrom(todayYmd());
    setCreatedReason("update constants");

    setForm(defaultForm(activeTab, activeScenario));
    setCurItem(null);

    refreshAll(activeTab, activeScenario, todayYmd());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, activeScenario]);

  function validateSave(): string | null {
    if (!effectiveFrom) return "Effective from je obavezan.";
    if (!createdReason || createdReason.trim() === "")
      return "Reason je obavezan (audit).";
    if (!form.scenario_key) return "scenario_key je obavezan.";

    const percentFields: Array<{ name: string; value: string }> = [
      { name: "PDV stopa (%)", value: form.vat_standard_rate_percent },
      { name: "Porez na dohodak (%)", value: form.income_tax_rate_percent },
      { name: "PIO (%)", value: form.pension_rate_percent },
      { name: "Zdravstvo (%)", value: form.health_rate_percent },
      { name: "Nezaposlenost (%)", value: form.unemployment_rate_percent },
    ];

    if (activeTab === "RS" || activeTab === "BD") {
      percentFields.push({
        name: "% prosječne bruto plate za osnovicu",
        value: form.contrib_base_percent_of_avg_gross,
      });
    }

    for (const f of percentFields) {
      const n = toNumOrNull(f.value);
      if (n === null) continue;
      if (n < 0 || n > 100) return `${f.name} mora biti u rasponu 0–100.`;
    }

    if (activeTab === "FBiH") {
      const mb = toNumOrNull(form.monthly_contrib_base_bam);
      if (mb === null || mb <= 0)
        return "FBiH: mjesečna osnovica doprinosa (KM) mora biti > 0.";
    }

    return null;
  }

  async function onRefresh() {
    await refreshAll(activeTab, activeScenario, asOf);
  }

  async function onLoadActiveIntoForm() {
    if (!curItem) return;
    setForm(hydrateFormFromPayload(activeTab, curItem.payload ?? {}));
  }

  function onResetForm() {
    setForm(defaultForm(activeTab, activeScenario));
    setAdvanced(false);
    setPayloadRaw("");
  }

  async function onSaveRollover() {
    const v = validateSave();
    if (v) {
      setErr(v);
      return;
    }

    let payloadObj: any;
    if (advanced) {
      const parsed = safeJsonParse(payloadRaw);
      if (!parsed.ok) {
        setErr(`Payload JSON error: ${parsed.error}`);
        return;
      }
      payloadObj = parsed.value ?? {};
    } else {
      payloadObj = buildPayloadFromForm(activeTab, form);
    }

    // Uvijek forsiramo scenario_key konzistentnost (i za advanced JSON).
    if (typeof payloadObj !== "object" || payloadObj === null || Array.isArray(payloadObj)) {
      setErr("Payload mora biti JSON objekat.");
      return;
    }

    const payloadScenario =
      typeof payloadObj.scenario_key === "string" ? payloadObj.scenario_key : null;

    if (payloadScenario !== null && payloadScenario !== form.scenario_key) {
      setErr(
        `payload.scenario_key ('${payloadScenario}') mora odgovarati izabranom scenario_key ('${form.scenario_key}').`
      );
      return;
    }

    payloadObj.scenario_key = form.scenario_key;

    const body: AppConstantsSetCreate = {
      jurisdiction: activeTab,
      scenario_key: form.scenario_key as any,
      effective_from: effectiveFrom,
      effective_to: null,
      payload: payloadObj,
      created_by: createdBy.trim() === "" ? null : createdBy.trim(),
      created_reason: createdReason,
    };

    setLoading(true);
    setErr(null);
    try {
      await adminConstantsCreate(body);
      await refreshAll(activeTab, form.scenario_key, asOf);
    } catch (e: any) {
      const detail = e?.response?.data?.detail ?? e?.message ?? "Save failed.";
      setErr(explainOverlap(detail));
    } finally {
      setLoading(false);
    }
  }

  const activeHistory = items;
  const titleScenario =
    SCENARIOS.find((s) => s.key === activeScenario)?.label ?? activeScenario;

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <h2 className="text-xl font-semibold text-slate-900">
            Admin Constants
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Upravljanje effective-dated setovima zakonskih konstanti po entitetu i
            scenariju. Snimanje radi “rollover”: novi set postaje aktivan od
            datuma, a prethodni open-ended set se automatski zatvara.
          </p>

          <div className="mt-4 flex flex-col gap-4 lg:flex-row lg:items-end">
            <div className="w-full lg:w-auto">
              <Tabs value={activeTab} onChange={setActiveTab} />
            </div>

            <div className="w-full lg:max-w-xl">
              <ScenarioSelect
                jurisdiction={activeTab}
                value={activeScenario}
                onChange={(v) =>
                  setScenarioByTab((prev) => ({ ...prev, [activeTab]: v }))
                }
                id="scenario"
              />
            </div>

            <div className="flex items-center gap-2 lg:ml-auto">
              <Button
                variant="secondary"
                onClick={onRefresh}
                disabled={loading || curLoading}
              >
                Osvježi
              </Button>
              <Badge>{activeTab}</Badge>
            </div>
          </div>
        </div>
      </div>

      {err ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {err}
        </div>
      ) : null}

      <Card
        title={`Aktivni set: ${activeTab} / ${titleScenario}`}
        subtitle="Učitava se trenutno važeći set za izabrani datum. Snimi = kreira novi open-ended set i backend zatvara prethodni open-ended set u istom scenario-u."
        right={
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              onClick={onLoadActiveIntoForm}
              disabled={!curItem || loading || curLoading}
            >
              Učitaj aktivni u formu
            </Button>
            <Button
              variant="secondary"
              onClick={onResetForm}
              disabled={loading || curLoading}
            >
              Reset formu
            </Button>
            <Button
              variant="primary"
              onClick={onSaveRollover}
              disabled={loading || curLoading}
            >
              Snimi (rollover)
            </Button>
          </div>
        }
      >
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Current card */}
          <div className="lg:col-span-5">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              {curLoading ? (
                <div className="text-sm text-slate-700">
                  Učitavanje aktivnog seta...
                </div>
              ) : curItem ? (
                <div className="space-y-2 text-sm text-slate-800">
                  <div className="min-w-0">
                    <div className="text-xs text-slate-500">Aktivno</div>
                    <div className="mt-1 flex min-w-0 flex-wrap items-center gap-2">
                      <span className="font-semibold text-slate-900">
                        id={curItem.id}
                      </span>
                      <Badge>
                        <span className="font-mono">
                          {curItem.effective_from}..{curItem.effective_to ?? "∞"}
                        </span>
                      </Badge>
                    </div>
                  </div>

                  <div className="min-w-0">
                    <div className="text-xs text-slate-500">Scenario</div>
                    <div
                      className="mt-1 min-w-0 font-mono text-xs text-slate-800 truncate"
                      title={curItem.scenario_key}
                    >
                      {curItem.scenario_key}
                    </div>
                  </div>

                  <div className="pt-2 border-t border-slate-200">
                    <div className="text-xs text-slate-500">Audit</div>
                    <div className="mt-1 space-y-1 text-xs text-slate-700">
                      <div
                        className="min-w-0 truncate"
                        title={`${curItem.created_by ?? "-"} / ${
                          curItem.created_reason ?? "-"
                        }`}
                      >
                        created: {curItem.created_by ?? "-"} /{" "}
                        {curItem.created_reason ?? "-"}
                      </div>
                      <div
                        className="min-w-0 truncate"
                        title={`${curItem.updated_by ?? "-"} / ${
                          curItem.updated_reason ?? "-"
                        }`}
                      >
                        updated: {curItem.updated_by ?? "-"} /{" "}
                        {curItem.updated_reason ?? "-"}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-sm text-slate-700">
                  Nema aktivnog seta za izabrani datum (u ovom scenario-u). Snimi
                  prvi set.
                </div>
              )}
            </div>

            <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
              Snimi kreira <b>open-ended</b> set (Effective to = prazno). Ako
              postoji prethodni open-ended set u istom scenario-u, backend ga
              zatvara na <b>(Effective from - 1 dan)</b>.
            </div>

            <div className="mt-4 rounded-lg border border-slate-200 bg-white px-4 py-4">
              <SectionTitle
                title="Lookup aktivnog seta"
                subtitle="Biraj datum za koji želiš provjeriti koji set je aktivan."
              />
              <div className="grid grid-cols-1 gap-4">
                <div>
                  <FieldLabel label="as_of" hint="Datum za koji tražimo aktivni set." />
                  <Input type="date" value={asOf} onChange={setAsOf} />
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    onClick={() => refreshCurrent(activeTab, activeScenario, asOf)}
                    disabled={loading || curLoading}
                  >
                    Učitaj aktivni za as_of
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      const t = todayYmd();
                      setAsOf(t);
                      refreshCurrent(activeTab, activeScenario, t);
                    }}
                    disabled={loading || curLoading}
                  >
                    Danas
                  </Button>
                </div>
              </div>
            </div>
          </div>

          {/* Save inputs */}
          <div className="lg:col-span-7">
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <div>
                <FieldLabel label="Effective from" hint="Od kog datuma važi novi set." />
                <Input type="date" value={effectiveFrom} onChange={setEffectiveFrom} />
              </div>
              <div>
                <FieldLabel label="created_by" hint="Opciono (audit)." />
                <Input
                  value={createdBy}
                  onChange={setCreatedBy}
                  placeholder="npr. 'miso' ili prazno"
                />
              </div>
              <div>
                <FieldLabel
                  label="created_reason (obavezno)"
                  hint="Audit razlog izmjene."
                />
                <Input
                  value={createdReason}
                  onChange={setCreatedReason}
                  placeholder="npr. 'promjena stopa 2026'"
                />
              </div>
            </div>

            <div className="mt-6">
              <FriendlyPayloadEditor
                jurisdiction={activeTab}
                form={form}
                setForm={setForm}
                derivedPayload={derivedPayload}
                advanced={advanced}
                setAdvanced={setAdvanced}
                raw={payloadRaw}
                setRaw={setPayloadRaw}
              />
            </div>
          </div>
        </div>
      </Card>

      <Card
        title={`Istorija setova: ${activeTab} / ${titleScenario}`}
        subtitle="Svi setovi za odabrani entitet i scenario. Aktivni je onaj koji pokriva izabrani datum (as_of)."
        right={
          <div className="text-sm text-slate-600">
            {loading ? "Učitavanje..." : `${activeHistory.length} item(s)`}
          </div>
        }
      >
        <div className="overflow-hidden rounded-lg border border-slate-200">
          <div className="overflow-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700">
                    ID
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700">
                    Effective
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700">
                    Scenario
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold text-slate-700">
                    Audit
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 bg-white">
                {activeHistory.map((row) => (
                  <tr key={row.id} className="hover:bg-slate-50">
                    <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-slate-700">
                      {row.id}
                    </td>

                    <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-slate-700">
                      {row.effective_from}..{row.effective_to ?? "∞"}
                    </td>

                    <td className="px-4 py-3">
                      <div
                        className="min-w-0 font-mono text-xs text-slate-700 truncate"
                        title={row.scenario_key || "-"}
                      >
                        {row.scenario_key || "-"}
                      </div>
                    </td>

                    <td className="px-4 py-3 text-xs text-slate-600">
                      <div
                        className="min-w-0 truncate"
                        title={`${row.created_by ?? "-"} / ${
                          row.created_reason ?? "-"
                        }`}
                      >
                        created: {row.created_by ?? "-"} /{" "}
                        {row.created_reason ?? "-"}
                      </div>
                      <div
                        className="min-w-0 truncate"
                        title={`${row.updated_by ?? "-"} / ${
                          row.updated_reason ?? "-"
                        }`}
                      >
                        updated: {row.updated_by ?? "-"} /{" "}
                        {row.updated_reason ?? "-"}
                      </div>
                    </td>
                  </tr>
                ))}

                {activeHistory.length === 0 && (
                  <tr>
                    <td className="px-4 py-10 text-sm text-slate-500" colSpan={4}>
                      Nema setova za prikaz.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </Card>
    </div>
  );
}
