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

import AdminConstantsRSPanel from "./admin-constants/AdminConstantsRSPanel";
import AdminConstantsFBiHPanel from "./admin-constants/AdminConstantsFBiHPanel";
import AdminConstantsBDPanel from "./admin-constants/AdminConstantsBDPanel";

import {
  Badge,
  Button,
  Card,
  FieldLabel,
  Input,
  SectionTitle,
  Tabs,
} from "./admin-constants/adminConstantsUi";

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

  // RS: avg gross wage + base percent -> calculated base (KM)
  avg_gross_wage_prev_year_bam: string;
  contrib_base_percent_of_avg_gross: string;

  // FBiH + BD: fixed monthly base (KM)
  monthly_contrib_base_bam: string;

  // Optional min base (KM) (kept generic; RS primary should not show it in UI)
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
  const sk = scenario_key ?? defaultScenarioForJurisdiction(j);

  const rsIsSupplementary = j === "RS" && sk === "rs_supplementary";
  const rsBasePctDefault = rsIsSupplementary ? "30" : "80";

  return {
    scenario_key: sk,

    currency: "BAM",

    vat_standard_rate_percent: "17",
    vat_entry_threshold_bam: "",

    income_tax_rate_percent: "10",
    flat_tax_monthly_amount_bam: "",

    pension_rate_percent: "18",
    health_rate_percent: rsIsSupplementary ? "" : "12",
    unemployment_rate_percent: rsIsSupplementary ? "" : "1.5",

    avg_gross_wage_prev_year_bam: "",
    contrib_base_percent_of_avg_gross: rsBasePctDefault,

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

function computeContributionAmount(
  base: number | null,
  ratePercentStr: string
): number | null {
  if (base === null) return null;
  const p = toNumOrNull(ratePercentStr);
  if (p === null) return null;
  const pct = clampPercent(p);
  return base * (pct / 100);
}

function computeTotalContribAmount(values: Array<number | null>): number | null {
  const nums = values.filter(
    (x): x is number => typeof x === "number" && Number.isFinite(x)
  );
  if (nums.length === 0) return null;
  return nums.reduce((a, b) => a + b, 0);
}

function rsContributionMode(scenarioKey: string): "PRIMARY" | "SUPPLEMENTARY" {
  return scenarioKey === "rs_supplementary" ? "SUPPLEMENTARY" : "PRIMARY";
}

function buildPayloadFromForm(j: Jurisdiction, form: ConstantsForm): any {
  const vatRate = percentStrToRateDecimal(form.vat_standard_rate_percent);
  const incomeTaxRate = percentStrToRateDecimal(form.income_tax_rate_percent);

  const pensionRate = percentStrToRateDecimal(form.pension_rate_percent);
  const healthRate = percentStrToRateDecimal(form.health_rate_percent);
  const unempRate = percentStrToRateDecimal(form.unemployment_rate_percent);

  const isRS = j === "RS";
  const isBD = j === "BD";
  const isFBiH = j === "FBiH";

  // RS: avg gross * % ; BD: fixed base (KM) ; FBiH: fixed base (KM)
  const calculatedBase = isRS
    ? computeCalculatedBaseBam(
        form.avg_gross_wage_prev_year_bam,
        form.contrib_base_percent_of_avg_gross
      )
    : isBD
    ? toNumOrNull(form.monthly_contrib_base_bam)
    : null;

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
      pension_rate: pensionRate,

      // amounts (KM)
      pension_amount_bam: pensionAmount,
      total_contrib_amount_bam: totalContribAmount,

      // NOTE: BD više ne koristi min osnovicu u V1 (ako zatreba, vratićemo uz spec)
      base_min_bam: isFBiH ? toNumOrNull(form.contrib_base_min_bam) : null,
    },

    meta: {
      source_note: (form.source_note ?? "").trim() || null,
      source_reference: (form.source_reference ?? "").trim() || null,
      updated_at_ui: new Date().toISOString(),
    },
  };

  if (isRS) {
    payload.base.avg_gross_wage_prev_year_bam = toNumOrNull(
      form.avg_gross_wage_prev_year_bam
    );
    payload.base.contrib_base_percent_of_avg_gross = toNumOrNull(
      form.contrib_base_percent_of_avg_gross
    );
    payload.base.calculated_contrib_base_bam = calculatedBase;

    if (rsMode === "PRIMARY") {
      payload.contributions.health_rate = healthRate;
      payload.contributions.unemployment_rate = unempRate;
      payload.contributions.health_amount_bam = healthAmount;
      payload.contributions.unemployment_amount_bam = unempAmount;
    }
  }

  if (isFBiH) {
    payload.base.monthly_contrib_base_bam = toNumOrNull(
      form.monthly_contrib_base_bam
    );
  }

  if (isBD) {
    // BD: fiksna osnovica (KM)
    payload.base.monthly_contrib_base_bam = toNumOrNull(
      form.monthly_contrib_base_bam
    );
    payload.base.calculated_contrib_base_bam = calculatedBase;

    payload.contributions.health_rate = healthRate;
    payload.contributions.unemployment_rate = unempRate;
    payload.contributions.health_amount_bam = healthAmount;
    payload.contributions.unemployment_amount_bam = unempAmount;
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

  const health_rate_percent = rateDecimalToPercentStr(contrib.health_rate) || "";
  const unemployment_rate_percent =
    rateDecimalToPercentStr(contrib.unemployment_rate) || "";

  const vat_entry_threshold_bam = numToStr(vat.entry_threshold_bam);
  const flat_tax_monthly_amount_bam = numToStr(tax.flat_tax_monthly_amount_bam);

  // base_min samo za FBiH u V1
  const contrib_base_min_bam = j === "FBiH" ? numToStr(contrib.base_min_bam) : "";

  // RS fields
  let avg_gross_wage_prev_year_bam = "";
  let contrib_base_percent_of_avg_gross = "";

  if (j === "RS") {
    avg_gross_wage_prev_year_bam = numToStr(base.avg_gross_wage_prev_year_bam);
    contrib_base_percent_of_avg_gross = numToStr(
      base.contrib_base_percent_of_avg_gross
    );
  }

  // monthly base: FBiH + BD
  const monthly_contrib_base_bam =
    j === "FBiH"
      ? numToStr(base.monthly_contrib_base_bam)
      : j === "BD"
      ? numToStr(base.monthly_contrib_base_bam ?? base.calculated_contrib_base_bam)
      : "";

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

function scenarioLabelFromKey(key: string): string {
  const found = SCENARIOS.find((s) => s.key === key);
  return found ? found.label : key;
}

function ScenarioSelectLocal({
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
  const selected = options.find((s) => s.key === value) ?? options[0];

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

  const [asOf, setAsOf] = useState<string>(todayYmd());

  const [effectiveFrom, setEffectiveFrom] = useState<string>(todayYmd());
  const [createdBy, setCreatedBy] = useState<string>("");
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

  async function refreshCurrent(
    j: Jurisdiction,
    scenario_key: string,
    asOfYmd: string
  ) {
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

  useEffect(() => {
    setErr(null);
    setAdvanced(false);
    setPayloadRaw("");

    const t = todayYmd();
    setAsOf(t);
    setEffectiveFrom(t);
    setCreatedReason("update constants");

    setForm(defaultForm(activeTab, activeScenario));
    setCurItem(null);

    refreshAll(activeTab, activeScenario, t);
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
    ];

    const isRS = activeTab === "RS";
    const isBD = activeTab === "BD";
    const rsMode = isRS ? rsContributionMode(form.scenario_key) : null;

    if ((isRS && rsMode === "PRIMARY") || isBD) {
      percentFields.push({ name: "Zdravstvo (%)", value: form.health_rate_percent });
      percentFields.push({
        name: "Nezaposlenost (%)",
        value: form.unemployment_rate_percent,
      });
    }

    // RS: validacija % prosječne bruto plate (osnovica)
    if (activeTab === "RS") {
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

    if (activeTab === "BD") {
      const mb = toNumOrNull(form.monthly_contrib_base_bam);
      if (mb === null || mb <= 0)
        return "BD: osnovica doprinosa (KM) mora biti > 0.";
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

    if (
      typeof payloadObj !== "object" ||
      payloadObj === null ||
      Array.isArray(payloadObj)
    ) {
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
              <ScenarioSelectLocal
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
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 items-stretch">
          {/* LEFT column */}
          <div className="lg:col-span-5 flex flex-col min-h-0">
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

            <div className="mt-4 flex-1 min-h-0 rounded-lg border border-slate-200 bg-white px-4 py-4 overflow-hidden">
              <div className="mb-2">
                <div className="text-sm font-semibold text-slate-900">
                  Generisani payload (preview)
                </div>
                <div className="mt-1 text-sm text-slate-600">
                  Read-only prikaz payload-a koji će biti snimljen.
                </div>
              </div>

              <pre className="h-full min-h-0 max-h-[70vh] overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-800 whitespace-pre">
                {derivedPayload}
              </pre>
            </div>
          </div>

          {/* RIGHT column */}
          <div className="lg:col-span-7 min-h-0">
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
              {activeTab === "RS" ? (
                <AdminConstantsRSPanel
                  jurisdiction={activeTab}
                  form={form as any}
                  setForm={setForm as any}
                  advanced={advanced}
                  setAdvanced={setAdvanced}
                  raw={payloadRaw}
                  setRaw={setPayloadRaw}
                />
              ) : activeTab === "FBiH" ? (
                <AdminConstantsFBiHPanel
                  form={form as any}
                  setForm={setForm as any}
                  advanced={advanced}
                  setAdvanced={setAdvanced}
                  raw={payloadRaw}
                  setRaw={setPayloadRaw}
                />
              ) : (
                <AdminConstantsBDPanel
                  form={form as any}
                  setForm={setForm as any}
                  advanced={advanced}
                  setAdvanced={setAdvanced}
                  raw={payloadRaw}
                  setRaw={setPayloadRaw}
                />
              )}
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
                {activeHistory.map((row) => {
                  const scenarioKey =
                    (row as any)?.scenario_key ||
                    (row as any)?.payload?.scenario_key ||
                    "-";

                  const label =
                    scenarioKey === "-" ? "-" : scenarioLabelFromKey(String(scenarioKey));

                  return (
                    <tr key={row.id} className="hover:bg-slate-50">
                      <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-slate-700">
                        {row.id}
                      </td>

                      <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-slate-700">
                        {row.effective_from}..{row.effective_to ?? "∞"}
                      </td>

                      <td className="px-4 py-3">
                        <div
                          className="min-w-0 text-xs text-slate-700 truncate"
                          title={String(scenarioKey)}
                        >
                          {label}
                        </div>
                        {scenarioKey !== "-" ? (
                          <div className="mt-0.5 font-mono text-[11px] text-slate-500 truncate">
                            {String(scenarioKey)}
                          </div>
                        ) : null}
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
                  );
                })}

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
