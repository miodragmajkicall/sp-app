// /home/miso/dev/sp-app/sp-app/frontend/src/pages/admin-constants/adminConstantsDomain.ts

import type { Jurisdiction } from "../../types/constants";

export type ConstantsForm = {
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

  // Optional min base (KM) (kept generic; RS primary should not show it in UI)
  contrib_base_min_bam: string;

  // Notes / sources
  source_note: string;
  source_reference: string;
};

export type JsonParseResult = { ok: true; value: any } | { ok: false; error: string };

export function safeJsonParse(input: string): JsonParseResult {
  try {
    const v = JSON.parse(input);
    return { ok: true, value: v };
  } catch (e: any) {
    return { ok: false, error: e?.message ?? "Invalid JSON" };
  }
}

export function todayYmd(): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

export function toNumOrNull(v: string): number | null {
  const s = (v ?? "").trim();
  if (s === "") return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

export function clampPercent(n: number): number {
  if (n < 0) return 0;
  if (n > 100) return 100;
  return n;
}

export function percentStrToRateDecimal(percentStr: string): number | null {
  const n = toNumOrNull(percentStr);
  if (n === null) return null;
  const p = clampPercent(n);
  return p / 100;
}

export function rateDecimalToPercentStr(rate: any): string {
  if (rate === null || rate === undefined) return "";
  const n = typeof rate === "number" ? rate : Number(rate);
  if (!Number.isFinite(n)) return "";
  const p = n * 100;
  const fixed = p.toFixed(6);
  const trimmed = fixed.replace(/\.?0+$/, "");
  return trimmed;
}

export function numToStr(x: any): string {
  if (x === null || x === undefined) return "";
  if (typeof x === "number") return String(x);
  if (typeof x === "string") return x;
  return "";
}

// V1 Scenario katalog (spec)
export const SCENARIOS: Array<{
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

export function defaultScenarioForJurisdiction(j: Jurisdiction): string {
  if (j === "RS") return "rs_primary";
  if (j === "FBiH") return "fbih_obrt";
  return "bd_samostalna";
}

export function defaultForm(j: Jurisdiction, scenario_key?: string): ConstantsForm {
  const sk = scenario_key ?? defaultScenarioForJurisdiction(j);

  // RS defaults by scenario
  const rsIsSupplementary = j === "RS" && sk === "rs_supplementary";
  const rsBasePctDefault = rsIsSupplementary ? "30" : "80";

  return {
    scenario_key: sk,

    currency: "BAM",

    // percent input defaults (UI)
    vat_standard_rate_percent: "17",
    vat_entry_threshold_bam: "",

    income_tax_rate_percent: "10",
    flat_tax_monthly_amount_bam: "",

    // default rates
    pension_rate_percent: "18",
    health_rate_percent: rsIsSupplementary ? "" : "12",
    unemployment_rate_percent: rsIsSupplementary ? "" : "1.5",

    // RS/BD
    avg_gross_wage_prev_year_bam: "",
    contrib_base_percent_of_avg_gross: rsBasePctDefault,

    // FBiH
    monthly_contrib_base_bam: "",

    contrib_base_min_bam: "",

    source_note: "",
    source_reference: "",
  };
}

export function computeCalculatedBaseBam(
  avgGrossStr: string,
  basePercentStr: string
): number | null {
  const avg = toNumOrNull(avgGrossStr);
  const p = toNumOrNull(basePercentStr);
  if (avg === null || p === null) return null;
  const pct = clampPercent(p);
  return avg * (pct / 100);
}

export function computeContributionAmount(
  base: number | null,
  ratePercentStr: string
): number | null {
  if (base === null) return null;
  const p = toNumOrNull(ratePercentStr);
  if (p === null) return null;
  const pct = clampPercent(p);
  return base * (pct / 100);
}

export function computeTotalContribAmount(values: Array<number | null>): number | null {
  const nums = values.filter(
    (x): x is number => typeof x === "number" && Number.isFinite(x)
  );
  if (nums.length === 0) return null;
  return nums.reduce((a, b) => a + b, 0);
}

export function rsContributionMode(scenarioKey: string): "PRIMARY" | "SUPPLEMENTARY" {
  return scenarioKey === "rs_supplementary" ? "SUPPLEMENTARY" : "PRIMARY";
}

export function buildPayloadFromForm(j: Jurisdiction, form: ConstantsForm): any {
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

  const isRS = j === "RS";
  const isBD = j === "BD";

  const rsMode = isRS ? rsContributionMode(form.scenario_key) : null;

  const pensionAmount =
    isRS || isBD
      ? computeContributionAmount(calculatedBase, form.pension_rate_percent)
      : null;

  const healthAmount =
    isRS && rsMode === "PRIMARY"
      ? computeContributionAmount(calculatedBase, form.health_rate_percent)
      : isBD
      ? computeContributionAmount(calculatedBase, form.health_rate_percent)
      : null;

  const unempAmount =
    isRS && rsMode === "PRIMARY"
      ? computeContributionAmount(calculatedBase, form.unemployment_rate_percent)
      : isBD
      ? computeContributionAmount(calculatedBase, form.unemployment_rate_percent)
      : null;

  const totalContribAmount =
    isRS
      ? computeTotalContribAmount(
          rsMode === "SUPPLEMENTARY"
            ? [pensionAmount]
            : [pensionAmount, healthAmount, unempAmount]
        )
      : isBD
      ? computeTotalContribAmount([pensionAmount, healthAmount, unempAmount])
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
      // rates
      pension_rate: pensionRate,

      // amounts (KM)
      pension_amount_bam: pensionAmount,
      total_contrib_amount_bam: totalContribAmount,

      // generic optional (kept only where relevant; RS UI hides min base)
      base_min_bam: j === "FBiH" || j === "BD" ? toNumOrNull(form.contrib_base_min_bam) : null,
    },

    meta: {
      source_note: (form.source_note ?? "").trim() || null,
      source_reference: (form.source_reference ?? "").trim() || null,
      updated_at_ui: new Date().toISOString(),
    },
  };

  if (isRS) {
    payload.base.avg_gross_wage_prev_year_bam = toNumOrNull(form.avg_gross_wage_prev_year_bam);
    payload.base.contrib_base_percent_of_avg_gross = toNumOrNull(
      form.contrib_base_percent_of_avg_gross
    );
    payload.base.calculated_contrib_base_bam = calculatedBase;

    // RS: supplementary -> only PIO, primary -> PIO+health+unemp
    if (rsMode === "PRIMARY") {
      payload.contributions.health_rate = healthRate;
      payload.contributions.unemployment_rate = unempRate;
      payload.contributions.health_amount_bam = healthAmount;
      payload.contributions.unemployment_amount_bam = unempAmount;
    }
  }

  if (j === "FBiH") {
    payload.base.monthly_contrib_base_bam = toNumOrNull(form.monthly_contrib_base_bam);
  }

  if (isBD) {
    payload.base.avg_gross_prev_year_bam = toNumOrNull(form.avg_gross_wage_prev_year_bam);
    payload.base.base_percent_of_avg_gross = toNumOrNull(form.contrib_base_percent_of_avg_gross);
    payload.base.calculated_contrib_base_bam = calculatedBase;

    payload.contributions.health_rate = healthRate;
    payload.contributions.unemployment_rate = unempRate;
    payload.contributions.health_amount_bam = healthAmount;
    payload.contributions.unemployment_amount_bam = unempAmount;
  }

  return payload;
}

export function hydrateFormFromPayload(j: Jurisdiction, payload: any): ConstantsForm {
  const d = defaultForm(j);
  const p = payload ?? {};

  const base = p.base ?? {};
  const vat = p.vat ?? {};
  const tax = p.tax ?? {};
  const contrib = p.contributions ?? {};
  const meta = p.meta ?? {};

  const scenario_key = typeof p.scenario_key === "string" ? p.scenario_key : d.scenario_key;

  const currency = typeof base.currency === "string" ? base.currency : d.currency;

  const vat_standard_rate_percent =
    rateDecimalToPercentStr(vat.standard_rate) || d.vat_standard_rate_percent;
  const income_tax_rate_percent =
    rateDecimalToPercentStr(tax.income_tax_rate) || d.income_tax_rate_percent;

  const pension_rate_percent = rateDecimalToPercentStr(contrib.pension_rate) || d.pension_rate_percent;

  // For RS supplementary we intentionally allow blanks; if payload doesn't have these, keep empty.
  const health_rate_percent = rateDecimalToPercentStr(contrib.health_rate) || "";
  const unemployment_rate_percent = rateDecimalToPercentStr(contrib.unemployment_rate) || "";

  const vat_entry_threshold_bam = numToStr(vat.entry_threshold_bam);
  const flat_tax_monthly_amount_bam = numToStr(tax.flat_tax_monthly_amount_bam);
  const contrib_base_min_bam = numToStr(contrib.base_min_bam);

  let avg_gross_wage_prev_year_bam = "";
  let contrib_base_percent_of_avg_gross = "";

  if (j === "RS") {
    avg_gross_wage_prev_year_bam = numToStr(base.avg_gross_wage_prev_year_bam);
    contrib_base_percent_of_avg_gross = numToStr(base.contrib_base_percent_of_avg_gross);
  } else if (j === "BD") {
    avg_gross_wage_prev_year_bam = numToStr(base.avg_gross_prev_year_bam);
    contrib_base_percent_of_avg_gross = numToStr(base.base_percent_of_avg_gross);
  }

  const monthly_contrib_base_bam = j === "FBiH" ? numToStr(base.monthly_contrib_base_bam) : "";

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
    source_reference: typeof meta.source_reference === "string" ? meta.source_reference : "",
  };
}

export function explainOverlap(detail: string): string {
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
