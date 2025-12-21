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

  // base/common
  currency: string;
  avg_gross_wage_prev_year: string;

  // VAT
  vat_standard_rate: string;
  vat_entry_threshold: string;

  // Tax (income tax / flat tax)
  income_tax_rate: string;
  flat_tax_monthly_amount: string;

  // Contributions
  pension_rate: string;
  health_rate: string;
  unemployment_rate: string;

  // Contribution base constraints
  contrib_base_min: string;
  contrib_base_max: string;

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

function defaultScenarioForJurisdiction(j: Jurisdiction): string {
  if (j === "RS") return "rs_pausal";
  if (j === "FBiH") return "fbih_knjige";
  return "bd_knjige";
}

function defaultForm(j: Jurisdiction): ConstantsForm {
  return {
    scenario_key: defaultScenarioForJurisdiction(j),

    currency: "BAM",
    avg_gross_wage_prev_year: "",

    vat_standard_rate: "0.17",
    vat_entry_threshold: "",

    income_tax_rate: "0.10",
    flat_tax_monthly_amount: "",

    pension_rate: "0.18",
    health_rate: "0.12",
    unemployment_rate: "0.015",

    contrib_base_min: "",
    contrib_base_max: "",

    source_note: "",
    source_reference: "",
  };
}

function buildPayloadFromForm(form: ConstantsForm): any {
  return {
    scenario_key: form.scenario_key,
    base: {
      currency: form.currency || "BAM",
      avg_gross_wage_prev_year: toNumOrNull(form.avg_gross_wage_prev_year),
    },
    vat: {
      standard_rate: toNumOrNull(form.vat_standard_rate),
      entry_threshold: toNumOrNull(form.vat_entry_threshold),
    },
    tax: {
      income_tax_rate: toNumOrNull(form.income_tax_rate),
      flat_tax_monthly_amount: toNumOrNull(form.flat_tax_monthly_amount),
    },
    contributions: {
      pension_rate: toNumOrNull(form.pension_rate),
      health_rate: toNumOrNull(form.health_rate),
      unemployment_rate: toNumOrNull(form.unemployment_rate),
      base_min: toNumOrNull(form.contrib_base_min),
      base_max: toNumOrNull(form.contrib_base_max),
    },
    meta: {
      source_note: (form.source_note ?? "").trim() || null,
      source_reference: (form.source_reference ?? "").trim() || null,
      updated_at_ui: new Date().toISOString(),
    },
  };
}

function hydrateFormFromPayload(j: Jurisdiction, payload: any): ConstantsForm {
  const d = defaultForm(j);
  const p = payload ?? {};

  const base = p.base ?? {};
  const vat = p.vat ?? {};
  const tax = p.tax ?? {};
  const contrib = p.contributions ?? {};
  const meta = p.meta ?? {};

  function numToStr(x: any): string {
    if (x === null || x === undefined) return "";
    if (typeof x === "number") return String(x);
    if (typeof x === "string") return x;
    return "";
  }

  return {
    scenario_key: typeof p.scenario_key === "string" ? p.scenario_key : d.scenario_key,

    currency: typeof base.currency === "string" ? base.currency : d.currency,
    avg_gross_wage_prev_year: numToStr(base.avg_gross_wage_prev_year),

    vat_standard_rate: numToStr(vat.standard_rate) || d.vat_standard_rate,
    vat_entry_threshold: numToStr(vat.entry_threshold),

    income_tax_rate: numToStr(tax.income_tax_rate) || d.income_tax_rate,
    flat_tax_monthly_amount: numToStr(tax.flat_tax_monthly_amount),

    pension_rate: numToStr(contrib.pension_rate) || d.pension_rate,
    health_rate: numToStr(contrib.health_rate) || d.health_rate,
    unemployment_rate: numToStr(contrib.unemployment_rate) || d.unemployment_rate,

    contrib_base_min: numToStr(contrib.base_min),
    contrib_base_max: numToStr(contrib.base_max),

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

const SCENARIOS: Array<{ key: string; label: string; hint: string }> = [
  { key: "rs_pausal", label: "RS – Paušal", hint: "Paušalni režim (parametri se kasnije fino mapiraju u obračun)." },
  { key: "rs_knjige", label: "RS – Knjige (stvarni rashodi)", hint: "Vođenje evidencija + obračun po osnovici." },
  { key: "fbih_knjige", label: "FBiH – Knjige", hint: "FBiH samostalna djelatnost (detalji kasnije)." },
  { key: "bd_knjige", label: "BD – Knjige", hint: "Brčko distrikt (detalji kasnije)." },
];

function ScenarioSelect({
  value,
  onChange,
  id,
}: {
  value: string;
  onChange: (v: string) => void;
  id?: string;
}) {
  const selected = SCENARIOS.find((s) => s.key === value);
  return (
    <div>
      <FieldLabel
        label="Scenario / šema (scenario_key)"
        hint={selected ? selected.hint : "Izaberi režim obračuna koji će korisnik birati u Settings."}
      />
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border border-slate-300 rounded-md px-2 py-1 text-sm bg-white"
      >
        {SCENARIOS.map((s) => (
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
}: {
  label: string;
  hint?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <div>
      <FieldLabel label={label} hint={hint} />
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border border-slate-300 rounded-md px-2 py-1 text-sm bg-white"
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
  form,
  setForm,
  derivedPayload,
  advanced,
  setAdvanced,
  raw,
  setRaw,
}: {
  form: ConstantsForm;
  setForm: (next: ConstantsForm) => void;
  derivedPayload: string;
  advanced: boolean;
  setAdvanced: (v: boolean) => void;
  raw: string;
  setRaw: (v: string) => void;
}) {
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

            <TextInput
              label="Prosječna bruto plata (prethodna godina)"
              hint="Unosi admin (npr. iz zvanične statistike). Opciono u V1."
              value={form.avg_gross_wage_prev_year}
              onChange={(v) => setForm({ ...form, avg_gross_wage_prev_year: v })}
              placeholder="npr. 1900.00"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <TextInput
              label="PDV stopa (standard_rate)"
              hint="npr. 0.17"
              value={form.vat_standard_rate}
              onChange={(v) => setForm({ ...form, vat_standard_rate: v })}
              placeholder="0.17"
            />
            <TextInput
              label="PDV prag ulaska (entry_threshold)"
              hint="Opciono; npr. 50000"
              value={form.vat_entry_threshold}
              onChange={(v) => setForm({ ...form, vat_entry_threshold: v })}
              placeholder="50000"
            />
            <div />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <TextInput
              label="Porez na dohodak (income_tax_rate)"
              hint="npr. 0.10"
              value={form.income_tax_rate}
              onChange={(v) => setForm({ ...form, income_tax_rate: v })}
              placeholder="0.10"
            />
            <TextInput
              label="Paušalni porez (flat_tax_monthly_amount)"
              hint="Ako je šema fiksna po mjesecu (KM). Opciono."
              value={form.flat_tax_monthly_amount}
              onChange={(v) => setForm({ ...form, flat_tax_monthly_amount: v })}
              placeholder="npr. 50.00"
            />
            <div />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <TextInput
              label="Doprinos PIO (pension_rate)"
              hint="npr. 0.18"
              value={form.pension_rate}
              onChange={(v) => setForm({ ...form, pension_rate: v })}
              placeholder="0.18"
            />
            <TextInput
              label="Zdravstveno (health_rate)"
              hint="npr. 0.12"
              value={form.health_rate}
              onChange={(v) => setForm({ ...form, health_rate: v })}
              placeholder="0.12"
            />
            <TextInput
              label="Nezaposlenost (unemployment_rate)"
              hint="npr. 0.015"
              value={form.unemployment_rate}
              onChange={(v) => setForm({ ...form, unemployment_rate: v })}
              placeholder="0.015"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <TextInput
              label="Min osnovica doprinosa (contrib_base_min)"
              hint="Opciono (zavisi od scenarija)."
              value={form.contrib_base_min}
              onChange={(v) => setForm({ ...form, contrib_base_min: v })}
              placeholder="npr. 1200.00"
            />
            <TextInput
              label="Max osnovica doprinosa (contrib_base_max)"
              hint="Opciono (zavisi od scenarija)."
              value={form.contrib_base_max}
              onChange={(v) => setForm({ ...form, contrib_base_max: v })}
              placeholder="npr. 5000.00"
            />
            <div />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <TextArea
              label="Napomena / izvor (source_note)"
              hint="Kratko: odakle je uzeto (institucija/dokument)."
              value={form.source_note}
              onChange={(v) => setForm({ ...form, source_note: v })}
              rows={3}
              placeholder="npr. 'RZS RS objava 2025-01; prosječna bruto plata 2024...'"
            />
            <TextArea
              label="Referenca (source_reference)"
              hint="Link, broj službenog glasnika, naziv akta, itd."
              value={form.source_reference}
              onChange={(v) => setForm({ ...form, source_reference: v })}
              rows={3}
              placeholder="npr. 'SG RS 12/2025, član ...' ili URL"
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
  // Backend poruka je OK, ali je korisniku bolje objasniti šta znači.
  if ((detail ?? "").toLowerCase().includes("overlapping")) {
    return (
      "Ne može snimiti jer postoji set sa preklapajućim datumima. " +
      "Za rollover koristi: novi set treba biti open-ended (Effective to prazno), " +
      "i Effective from mora biti POSLIJE trenutnog active seta. " +
      `Detalj: ${detail}`
    );
  }
  return detail;
}

export default function AdminConstantsPage() {
  const [activeTab, setActiveTab] = useState<Jurisdiction>("RS");

  // history list (per tab)
  const [items, setItems] = useState<AppConstantsSetRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // current (active as of today)
  const [curItem, setCurItem] = useState<AppConstantsSetRead | null>(null);
  const [curLoading, setCurLoading] = useState(false);

  // editor (this is THE screen: edit "current" then save -> creates new set -> rollover)
  const [effectiveFrom, setEffectiveFrom] = useState<string>(todayYmd());
  const [createdBy, setCreatedBy] = useState<string>("admin");
  const [createdReason, setCreatedReason] = useState<string>("update constants");

  const [form, setForm] = useState<ConstantsForm>(() => defaultForm("RS"));

  const [advanced, setAdvanced] = useState(false);
  const [payloadRaw, setPayloadRaw] = useState<string>("");

  const derivedPayload = useMemo(() => {
    const payload = buildPayloadFromForm(form);
    return JSON.stringify(payload, null, 2);
  }, [form]);

  async function refreshHistory(j: Jurisdiction) {
    setLoading(true);
    setErr(null);
    try {
      const data = await adminConstantsList({ jurisdiction: j });
      setItems(data.items);
    } catch (e: any) {
      setErr(e?.response?.data?.detail ?? e?.message ?? "Failed to load constants history.");
    } finally {
      setLoading(false);
    }
  }

  async function refreshCurrent(j: Jurisdiction) {
    setCurLoading(true);
    try {
      const res = await constantsCurrent({ jurisdiction: j, as_of: todayYmd() });
      if (res?.found && res?.item) {
        setCurItem(res.item);
        // prefill form from active payload (this is what user wants to see in the tab)
        setForm(hydrateFormFromPayload(j, res.item.payload ?? {}));
      } else {
        setCurItem(null);
        setForm(defaultForm(j));
      }
    } catch {
      // if current endpoint fails, keep UX usable
      setCurItem(null);
      setForm(defaultForm(j));
    } finally {
      setCurLoading(false);
    }
  }

  async function refreshAll(j: Jurisdiction) {
    await Promise.all([refreshHistory(j), refreshCurrent(j)]);
  }

  useEffect(() => {
    // on tab change: switch to that region, load last active, show history
    setErr(null);
    setAdvanced(false);
    setPayloadRaw("");
    setEffectiveFrom(todayYmd());
    setCreatedReason("update constants");
    setForm(defaultForm(activeTab));

    refreshAll(activeTab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  function validateSave(): string | null {
    if (!effectiveFrom) return "Effective from je obavezan.";
    if (!createdReason || createdReason.trim() === "") return "Reason je obavezan (audit).";
    if (!form.scenario_key) return "scenario_key je obavezan.";
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
      payloadObj = buildPayloadFromForm(form);
    }

    // Rollover semantics:
    // - we create a NEW open-ended set (effective_to = null)
    // - backend closes previous open-ended set automatically
    const body: AppConstantsSetCreate = {
      jurisdiction: activeTab,
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
      await refreshAll(activeTab);
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
            Tabovi po entitetu (RS / FBiH / BD). Snimanje radi “rollover”: novi set postaje aktivan od datuma, a prethodni se automatski zatvara (audit ostaje).
          </p>

          <div className="mt-3">
            <Tabs value={activeTab} onChange={setActiveTab} />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => refreshAll(activeTab)}
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

      {/* Active info + editor */}
      <Section
        title={`Aktivna podešavanja (${activeTab})`}
        subtitle="Ovdje vidiš trenutno važeći set (za današnji datum) i možeš odmah unijeti izmjene. Snimi = kreira novi set (open-ended) i backend zatvara prethodni."
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
                    Audit: created {curItem.created_by ?? "-"} / {curItem.created_reason ?? "-"}
                  </div>
                  <div className="text-xs text-slate-600">
                    Updated: {curItem.updated_by ?? "-"} / {curItem.updated_reason ?? "-"}
                  </div>
                </div>
              ) : (
                <div className="text-sm text-slate-700">
                  Nema aktivnog seta za današnji datum. Snimi prvi set za ovaj entitet.
                </div>
              )}
            </div>
          </div>

          <div className="flex-1 min-w-[320px]">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              <TextInput
                label="Effective from"
                hint="Od kog datuma važi novi set (preporuka: datum promjene)."
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
              Snimi će kreirati novi <b>open-ended</b> set (Effective to = prazno). Ako postoji prethodni open-ended set, backend će ga automatski zatvoriti na <b>(Effective from - 1 dan)</b>.
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

      {/* History list */}
      <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Istorija setova ({activeTab})</h3>
            <p className="text-xs text-slate-500">
              Ovo su svi setovi za odabrani entitet. Aktivni je onaj koji pokriva današnji datum.
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
              {activeHistory.map((row) => {
                const scenarioKey =
                  (row.payload as any)?.scenario_key ??
                  (row.payload as any)?.scenario ??
                  "";
                return (
                  <tr key={row.id} className="hover:bg-slate-50">
                    <td className="px-4 py-2 font-mono text-xs text-slate-700">{row.id}</td>
                    <td className="px-4 py-2 font-mono text-xs">
                      {row.effective_from}..{row.effective_to ?? "∞"}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs text-slate-700">
                      {scenarioKey || "-"}
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
                );
              })}
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
