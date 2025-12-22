// /home/miso/dev/sp-app/sp-app/frontend/src/pages/AdminConstantsPage.tsx

import { useEffect, useMemo, useState } from "react";
import type { AppConstantsSetCreate, AppConstantsSetRead } from "../types/constants";
import {
  adminConstantsCreate,
  adminConstantsList,
  constantsCurrent,
} from "../services/adminConstantsApi";

type Jurisdiction = "RS" | "FBiH" | "BD";

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

type JsonParseResult =
  | { ok: true; value: any }
  | { ok: false; error: string };

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
  // convert 0.17 -> 17 ; keep simple formatting
  const p = n * 100;
  // trim trailing zeros (e.g., 1.5 stays 1.5)
  const s = String(p);
  return s;
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

function defaultForm(j: Jurisdiction): ConstantsForm {
  return {
    scenario_key: defaultScenarioForJurisdiction(j),

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

  const calculatedBase = (j === "RS" || j === "BD")
    ? computeCalculatedBaseBam(form.avg_gross_wage_prev_year_bam, form.contrib_base_percent_of_avg_gross)
    : null;

  const payload: any = {
    // keep scenario_key in payload for transparency/back-compat
    scenario_key: form.scenario_key,

    base: {
      currency: (form.currency || "BAM").trim() || "BAM",
    },

    vat: {
      standard_rate: vatRate, // decimal 0..1
      entry_threshold_bam: toNumOrNull(form.vat_entry_threshold_bam),
    },

    tax: {
      income_tax_rate: incomeTaxRate, // decimal 0..1
      flat_tax_monthly_amount_bam: toNumOrNull(form.flat_tax_monthly_amount_bam),
    },

    contributions: {
      pension_rate: pensionRate, // decimal 0..1
      health_rate: healthRate, // decimal 0..1
      unemployment_rate: unempRate, // decimal 0..1
      base_min_bam: toNumOrNull(form.contrib_base_min_bam),
    },

    meta: {
      source_note: (form.source_note ?? "").trim() || null,
      source_reference: (form.source_reference ?? "").trim() || null,
      updated_at_ui: new Date().toISOString(),
    },
  };

  if (j === "RS") {
    payload.base.avg_gross_wage_prev_year_bam = toNumOrNull(form.avg_gross_wage_prev_year_bam);
    payload.base.contrib_base_percent_of_avg_gross = toNumOrNull(form.contrib_base_percent_of_avg_gross); // stored as percent (audit-friendly)
    payload.base.calculated_contrib_base_bam = calculatedBase; // derived
  }

  if (j === "FBiH") {
    payload.base.monthly_contrib_base_bam = toNumOrNull(form.monthly_contrib_base_bam);
  }

  if (j === "BD") {
    payload.base.avg_gross_prev_year_bam = toNumOrNull(form.avg_gross_wage_prev_year_bam);
    payload.base.base_percent_of_avg_gross = toNumOrNull(form.contrib_base_percent_of_avg_gross); // stored as percent (audit-friendly)
    payload.base.calculated_contrib_base_bam = calculatedBase; // derived
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

  // Scenario
  const scenario_key = typeof p.scenario_key === "string" ? p.scenario_key : d.scenario_key;

  // Common
  const currency = typeof base.currency === "string" ? base.currency : d.currency;

  // Percent fields: convert decimal -> percent string
  const vat_standard_rate_percent = rateDecimalToPercentStr(vat.standard_rate) || d.vat_standard_rate_percent;
  const income_tax_rate_percent = rateDecimalToPercentStr(tax.income_tax_rate) || d.income_tax_rate_percent;
  const pension_rate_percent = rateDecimalToPercentStr(contrib.pension_rate) || d.pension_rate_percent;
  const health_rate_percent = rateDecimalToPercentStr(contrib.health_rate) || d.health_rate_percent;
  const unemployment_rate_percent = rateDecimalToPercentStr(contrib.unemployment_rate) || d.unemployment_rate_percent;

  // Amounts
  const vat_entry_threshold_bam = numToStr(vat.entry_threshold_bam);
  const flat_tax_monthly_amount_bam = numToStr(tax.flat_tax_monthly_amount_bam);
  const contrib_base_min_bam = numToStr(contrib.base_min_bam);

  // RS/BD base inputs
  let avg_gross_wage_prev_year_bam = "";
  let contrib_base_percent_of_avg_gross = "";

  if (j === "RS") {
    avg_gross_wage_prev_year_bam = numToStr(base.avg_gross_wage_prev_year_bam);
    contrib_base_percent_of_avg_gross = numToStr(base.contrib_base_percent_of_avg_gross);
  } else if (j === "BD") {
    avg_gross_wage_prev_year_bam = numToStr(base.avg_gross_prev_year_bam);
    contrib_base_percent_of_avg_gross = numToStr(base.base_percent_of_avg_gross);
  }

  // FBiH
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

function FieldLabel({ label, hint }: { label: string; hint?: string }) {
  return (
    <div className="mb-1">
      <div className="text-xs text-slate-600">{label}</div>
      {hint ? <div className="text-[11px] text-slate-400">{hint}</div> : null}
    </div>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3">
        <div className="text-sm font-semibold text-slate-900">{title}</div>
        {subtitle ? <div className="text-xs text-slate-500">{subtitle}</div> : null}
      </div>
      {children}
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
    <div>
      <FieldLabel
        label="Scenario / šema"
        hint={selected ? selected.hint : "Izaberi šemu za ovu jurisdikciju."}
      />
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border border-slate-300 rounded-md px-2 py-1 text-sm bg-white"
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

function TextInput({
  label,
  hint,
  value,
  onChange,
  placeholder,
  type = "text",
  readOnly = false,
}: {
  label: string;
  hint?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  readOnly?: boolean;
}) {
  return (
    <div>
      <FieldLabel label={label} hint={hint} />
      <input
        type={type}
        value={value}
        readOnly={readOnly}
        onChange={(e) => onChange(e.target.value)}
        className={[
          "w-full border border-slate-300 rounded-md px-2 py-1 text-sm bg-white",
          readOnly ? "bg-slate-50 text-slate-700" : "",
        ].join(" ")}
        placeholder={placeholder}
      />
    </div>
  );
}

function TextArea({
  label,
  hint,
  value,
  onChange,
  rows = 3,
  mono = false,
  placeholder,
}: {
  label: string;
  hint?: string;
  value: string;
  onChange: (v: string) => void;
  rows?: number;
  mono?: boolean;
  placeholder?: string;
}) {
  return (
    <div>
      <FieldLabel label={label} hint={hint} />
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={[
          "w-full border border-slate-300 rounded-md px-3 py-2 text-sm bg-white",
          mono ? "font-mono" : "",
        ].join(" ")}
        rows={rows}
        placeholder={placeholder}
      />
    </div>
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
    <div className="inline-flex rounded-lg border border-slate-200 bg-white p-1">
      {tabs.map((t) => {
        const active = t.key === value;
        return (
          <button
            key={t.key}
            type="button"
            onClick={() => onChange(t.key)}
            className={[
              "px-4 py-1.5 text-sm rounded-md",
              active ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-50",
            ].join(" ")}
          >
            {t.label}
          </button>
        );
      })}
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

  const calculatedBase = (isRS || isBD)
    ? computeCalculatedBaseBam(form.avg_gross_wage_prev_year_bam, form.contrib_base_percent_of_avg_gross)
    : null;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-slate-900">Payload (friendly unos)</div>
        <button
          type="button"
          onClick={() => {
            if (!advanced) setRaw(derivedPayload);
            setAdvanced(!advanced);
          }}
          className="px-3 py-1 rounded-md border border-slate-300 text-slate-700 text-xs hover:bg-slate-50"
        >
          {advanced ? "Nazad na formu" : "Advanced JSON"}
        </button>
      </div>

      {!advanced ? (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <ScenarioSelect
              jurisdiction={jurisdiction}
              value={form.scenario_key}
              onChange={(v) => setForm({ ...form, scenario_key: v })}
            />

            <TextInput
              label="Valuta"
              hint="Najčešće BAM."
              value={form.currency}
              onChange={(v) => setForm({ ...form, currency: v })}
              placeholder="BAM"
            />

            {isRS || isBD ? (
              <TextInput
                label={isRS ? "Prosječna bruto plata (prethodna godina) (KM)" : "Prosječna bruto plata (BD) – prethodna godina (KM)"}
                hint="Unos admin-a. Decimal (npr. 2000.00)."
                value={form.avg_gross_wage_prev_year_bam}
                onChange={(v) => setForm({ ...form, avg_gross_wage_prev_year_bam: v })}
                placeholder="npr. 2000.00"
              />
            ) : (
              <div />
            )}
          </div>

          {/* RS/BD: percent base + calculated */}
          {(isRS || isBD) && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              <TextInput
                label={isRS ? "Osnovica doprinosa = % prosječne bruto plate" : "Procenat prosječne bruto plate za osnovicu (%)"}
                hint="Unos u procentima (npr. 80 znači 80%)."
                value={form.contrib_base_percent_of_avg_gross}
                onChange={(v) => setForm({ ...form, contrib_base_percent_of_avg_gross: v })}
                placeholder="npr. 80"
              />
              <TextInput
                label="Izračunata osnovica doprinosa (KM)"
                hint="Read-only: avg_gross * (percent/100)."
                value={calculatedBase === null ? "" : String(calculatedBase)}
                onChange={() => {}}
                readOnly
                placeholder="automatski izračun"
              />
              <div />
            </div>
          )}

          {/* FBiH: monthly base */}
          {isFBiH && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              <TextInput
                label="Mjesečna osnovica doprinosa (KM)"
                hint="FBiH: primarni input. Decimal > 0 (npr. 1376.00)."
                value={form.monthly_contrib_base_bam}
                onChange={(v) => setForm({ ...form, monthly_contrib_base_bam: v })}
                placeholder="npr. 1376.00"
              />
              <div />
              <div />
            </div>
          )}

          {/* VAT */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <TextInput
              label="PDV stopa (%)"
              hint="Unos u procentima (npr. 17). Sistem čuva 0.17."
              value={form.vat_standard_rate_percent}
              onChange={(v) => setForm({ ...form, vat_standard_rate_percent: v })}
              placeholder="17"
            />
            <TextInput
              label="PDV prag ulaska (KM)"
              hint="Opciono; npr. 50000"
              value={form.vat_entry_threshold_bam}
              onChange={(v) => setForm({ ...form, vat_entry_threshold_bam: v })}
              placeholder="50000"
            />
            <div />
          </div>

          {/* Tax */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <TextInput
              label="Porez na dohodak (%)"
              hint="Unos u procentima (npr. 10). Sistem čuva 0.10."
              value={form.income_tax_rate_percent}
              onChange={(v) => setForm({ ...form, income_tax_rate_percent: v })}
              placeholder="10"
            />
            <TextInput
              label="Paušalni porez (KM mjesečno)"
              hint="Opciono (ako postoji fiksni mjesečni iznos)."
              value={form.flat_tax_monthly_amount_bam}
              onChange={(v) => setForm({ ...form, flat_tax_monthly_amount_bam: v })}
              placeholder="npr. 50.00"
            />
            <div />
          </div>

          {/* Contributions */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <TextInput
              label="Doprinos PIO (%)"
              hint="Unos u % (npr. 18). Sistem čuva 0.18."
              value={form.pension_rate_percent}
              onChange={(v) => setForm({ ...form, pension_rate_percent: v })}
              placeholder="18"
            />
            <TextInput
              label="Zdravstveno (%)"
              hint="Unos u % (npr. 12). Sistem čuva 0.12."
              value={form.health_rate_percent}
              onChange={(v) => setForm({ ...form, health_rate_percent: v })}
              placeholder="12"
            />
            <TextInput
              label="Nezaposlenost (%)"
              hint="Unos u % (npr. 1.5). Sistem čuva 0.015."
              value={form.unemployment_rate_percent}
              onChange={(v) => setForm({ ...form, unemployment_rate_percent: v })}
              placeholder="1.5"
            />
          </div>

          {/* Optional min base (max base is intentionally not shown; RS spec explicitly says remove/hide max) */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <TextInput
              label="Min osnovica doprinosa (KM)"
              hint="Opciono (ako imamo minimalnu osnovicu u modelu)."
              value={form.contrib_base_min_bam}
              onChange={(v) => setForm({ ...form, contrib_base_min_bam: v })}
              placeholder="npr. 1200.00"
            />
            <div />
            <div />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <TextArea
              label="Napomena / izvor (source_note)"
              hint="Kratko: odakle je uzeto (institucija/dokument)."
              value={form.source_note}
              onChange={(v) => setForm({ ...form, source_note: v })}
              rows={3}
              placeholder="npr. 'RZS / Službeni glasnik / odluka ...'"
            />
            <TextArea
              label="Referenca (source_reference)"
              hint="Link, broj službenog glasnika, naziv akta, itd."
              value={form.source_reference}
              onChange={(v) => setForm({ ...form, source_reference: v })}
              rows={3}
              placeholder="npr. 'SG RS 12/2025...' ili URL"
            />
          </div>

          <div>
            <div className="text-xs text-slate-600 mb-1">Generisani payload (preview)</div>
            <pre className="text-xs overflow-auto bg-slate-50 border border-slate-200 rounded p-2">
              {derivedPayload}
            </pre>
          </div>
        </>
      ) : (
        <>
          <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Advanced JSON je za slučajeve kad želiš dodati dodatne ključeve prije nego što ih UI dobije kao polja.
          </div>
          <TextArea
            label="payload (JSON)"
            hint="Mora biti validan JSON. Backend ga snima u app_constants_sets.payload."
            value={raw}
            onChange={setRaw}
            rows={12}
            mono
          />
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

  const [scenarioByTab, setScenarioByTab] = useState<Record<Jurisdiction, string>>({
    RS: defaultScenarioForJurisdiction("RS"),
    FBiH: defaultScenarioForJurisdiction("FBiH"),
    BD: defaultScenarioForJurisdiction("BD"),
  });

  const activeScenario = scenarioByTab[activeTab] || defaultScenarioForJurisdiction(activeTab);

  const [items, setItems] = useState<AppConstantsSetRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [curItem, setCurItem] = useState<AppConstantsSetRead | null>(null);
  const [curLoading, setCurLoading] = useState(false);

  const [effectiveFrom, setEffectiveFrom] = useState<string>(todayYmd());
  const [createdBy, setCreatedBy] = useState<string>("admin");
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
      setErr(e?.response?.data?.detail ?? e?.message ?? "Failed to load constants history.");
    } finally {
      setLoading(false);
    }
  }

  async function refreshCurrent(j: Jurisdiction, scenario_key: string) {
    setCurLoading(true);
    try {
      const res = await constantsCurrent({ jurisdiction: j, scenario_key, as_of: todayYmd() });
      if (res?.found && res?.item) {
        setCurItem(res.item);
        setForm(hydrateFormFromPayload(j, res.item.payload ?? {}));
        setScenarioByTab((prev) => ({ ...prev, [j]: res.item!.scenario_key }));
      } else {
        setCurItem(null);
        setForm({ ...defaultForm(j), scenario_key });
      }
    } catch {
      setCurItem(null);
      setForm({ ...defaultForm(j), scenario_key });
    } finally {
      setCurLoading(false);
    }
  }

  async function refreshAll(j: Jurisdiction, scenario_key: string) {
    await Promise.all([refreshHistory(j, scenario_key), refreshCurrent(j, scenario_key)]);
  }

  // on tab change
  useEffect(() => {
    setErr(null);
    setAdvanced(false);
    setPayloadRaw("");
    setEffectiveFrom(todayYmd());
    setCreatedReason("update constants");

    const scn = scenarioByTab[activeTab] || defaultScenarioForJurisdiction(activeTab);
    setForm({ ...defaultForm(activeTab), scenario_key: scn });

    refreshAll(activeTab, scn);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  // on scenario change within tab
  useEffect(() => {
    setErr(null);
    setAdvanced(false);
    setPayloadRaw("");
    setEffectiveFrom(todayYmd());
    setCreatedReason("update constants");

    setForm((prev) => ({ ...prev, scenario_key: activeScenario }));
    refreshAll(activeTab, activeScenario);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeScenario]);

  function validateSave(): string | null {
    if (!effectiveFrom) return "Effective from je obavezan.";
    if (!createdReason || createdReason.trim() === "") return "Reason je obavezan (audit).";
    if (!form.scenario_key) return "scenario_key je obavezan.";

    // percent validations (0..100)
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
      if (n === null) continue; // empty allowed (some are optional)
      if (n < 0 || n > 100) return `${f.name} mora biti u rasponu 0–100.`;
    }

    if (activeTab === "FBiH") {
      const mb = toNumOrNull(form.monthly_contrib_base_bam);
      if (mb === null || mb <= 0) return "FBiH: mjesečna osnovica doprinosa (KM) mora biti > 0.";
    }

    return null;
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
      payloadObj = parsed.value;
    } else {
      payloadObj = buildPayloadFromForm(activeTab, form);
    }

    const body: AppConstantsSetCreate = {
      jurisdiction: activeTab,
      scenario_key: form.scenario_key,
      effective_from: effectiveFrom,
      effective_to: null,
      payload: payloadObj,
      created_by: createdBy.trim() === "" ? null : createdBy,
      created_reason: createdReason,
    };

    setLoading(true);
    setErr(null);
    try {
      await adminConstantsCreate(body);
      await refreshAll(activeTab, form.scenario_key);
    } catch (e: any) {
      const detail = e?.response?.data?.detail ?? e?.message ?? "Save failed.";
      setErr(explainOverlap(detail));
    } finally {
      setLoading(false);
    }
  }

  const activeHistory = items;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Admin: Zakonske konstante</h2>
          <p className="text-sm text-slate-600">
            Tabovi po entitetu (RS / FBiH / BD) i scenariji unutar taba (V1 specifikacija).
            Snimanje radi “rollover”: novi set postaje aktivan od datuma, a prethodni (open-ended)
            se automatski zatvara za isti scenario.
          </p>

          <div className="mt-3 flex flex-wrap items-center gap-3">
            <Tabs value={activeTab} onChange={setActiveTab} />
            <div className="min-w-[320px]">
              <ScenarioSelect
                jurisdiction={activeTab}
                value={activeScenario}
                onChange={(v) => setScenarioByTab((prev) => ({ ...prev, [activeTab]: v }))}
              />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => refreshAll(activeTab, activeScenario)}
            className="px-3 py-1.5 rounded-md bg-slate-900 text-white text-sm hover:bg-slate-800 disabled:opacity-50"
            disabled={loading || curLoading}
          >
            Osvježi
          </button>
        </div>
      </div>

      {err && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {err}
        </div>
      )}

      <Section
        title={`Aktivna podešavanja (${activeTab} / ${activeScenario})`}
        subtitle="Učitava se trenutno važeći set (za današnji datum) za izabrani scenario. Snimi = kreira novi set i backend zatvara prethodni open-ended set u istom scenario-u."
      >
        <div className="flex flex-wrap items-start gap-3">
          <div className="flex-1 min-w-[280px]">
            <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
              {curLoading ? (
                <div className="text-sm text-slate-600">Učitavanje aktivnog seta...</div>
              ) : curItem ? (
                <div className="text-sm text-slate-800">
                  <div className="font-semibold">
                    Aktivno: id={curItem.id} [{curItem.effective_from}..{curItem.effective_to ?? "∞"}]
                  </div>
                  <div className="text-xs text-slate-600 mt-1">
                    Scenario: <span className="font-mono">{curItem.scenario_key}</span>
                  </div>
                  <div className="text-xs text-slate-600 mt-1">
                    Audit: created {curItem.created_by ?? "-"} / {curItem.created_reason ?? "-"}
                  </div>
                  <div className="text-xs text-slate-600">
                    Updated: {curItem.updated_by ?? "-"} / {curItem.updated_reason ?? "-"}
                  </div>
                </div>
              ) : (
                <div className="text-sm text-slate-700">
                  Nema aktivnog seta za današnji datum (u ovom scenario-u). Snimi prvi set.
                </div>
              )}
            </div>
          </div>

          <div className="flex-1 min-w-[320px]">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              <TextInput
                label="Effective from"
                hint="Od kog datuma važi novi set."
                type="date"
                value={effectiveFrom}
                onChange={setEffectiveFrom}
              />
              <TextInput
                label="created_by"
                value={createdBy}
                onChange={setCreatedBy}
                placeholder="admin"
              />
              <TextInput
                label="created_reason (obavezno)"
                value={createdReason}
                onChange={setCreatedReason}
                placeholder="npr. 'promjena stopa 2026'"
              />
            </div>

            <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
              Snimi će kreirati novi <b>open-ended</b> set (Effective to = prazno) za isti <b>scenario</b>.
              Ako postoji prethodni open-ended set u tom scenario-u, backend će ga automatski zatvoriti na <b>(Effective from - 1 dan)</b>.
            </div>

            <div className="mt-3 flex items-center justify-end">
              <button
                onClick={onSaveRollover}
                className="px-3 py-1.5 rounded-md bg-emerald-600 text-white text-sm hover:bg-emerald-700 disabled:opacity-50"
                disabled={loading || curLoading}
              >
                Snimi (rollover)
              </button>
            </div>
          </div>
        </div>

        <div className="mt-4">
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
      </Section>

      <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              Istorija setova ({activeTab} / {activeScenario})
            </h3>
            <p className="text-xs text-slate-500">
              Ovo su svi setovi za odabrani entitet i scenario. Aktivni je onaj koji pokriva današnji datum.
            </p>
          </div>
          <div className="text-xs text-slate-500">
            {loading ? "Učitavanje..." : `${activeHistory.length} item(s)`}
          </div>
        </div>

        <div className="overflow-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-left font-medium px-4 py-2">ID</th>
                <th className="text-left font-medium px-4 py-2">Effective</th>
                <th className="text-left font-medium px-4 py-2">Scenario</th>
                <th className="text-left font-medium px-4 py-2">Audit</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {activeHistory.map((row) => (
                <tr key={row.id} className="hover:bg-slate-50">
                  <td className="px-4 py-2 font-mono text-xs text-slate-700">{row.id}</td>
                  <td className="px-4 py-2 font-mono text-xs">
                    {row.effective_from}..{row.effective_to ?? "∞"}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs text-slate-700">
                    {row.scenario_key || "-"}
                  </td>
                  <td className="px-4 py-2 text-xs text-slate-600">
                    <div>
                      created: {row.created_by ?? "-"} / {row.created_reason ?? "-"}
                    </div>
                    <div>
                      updated: {row.updated_by ?? "-"} / {row.updated_reason ?? "-"}
                    </div>
                  </td>
                </tr>
              ))}
              {activeHistory.length === 0 && (
                <tr>
                  <td className="px-4 py-4 text-slate-500" colSpan={4}>
                    Nema setova za prikaz.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
