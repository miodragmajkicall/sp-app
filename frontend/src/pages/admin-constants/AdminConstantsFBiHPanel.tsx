// /home/miso/dev/sp-app/sp-app/frontend/src/pages/admin-constants/AdminConstantsFBiHPanel.tsx

import { FieldLabel, Input, SectionTitle, TextArea, Button } from "./adminConstantsUi";

type ConstantsForm = {
  scenario_key: string;
  currency: string;

  vat_standard_rate_percent: string;
  vat_entry_threshold_bam: string;

  income_tax_rate_percent: string;
  flat_tax_monthly_amount_bam: string;

  pension_rate_percent: string;
  health_rate_percent: string;
  unemployment_rate_percent: string;

  monthly_contrib_base_bam: string;

  // NOTE: Ostavljamo u tipu radi kompatibilnosti sa ostatkom frontenda/payload mapiranja,
  // ali ga uklanjamo iz UI forme (ne prikazujemo ga).
  contrib_base_min_bam: string;

  source_note: string;
  source_reference: string;
};

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

function computeContributionAmount(base: number | null, ratePercentStr: string): number | null {
  if (base === null) return null;
  const p = toNumOrNull(ratePercentStr);
  if (p === null) return null;
  const pct = clampPercent(p);
  return base * (pct / 100);
}

function computeTotalContribAmount(values: Array<number | null>): number | null {
  const nums = values.filter((x): x is number => typeof x === "number" && Number.isFinite(x));
  if (nums.length === 0) return null;
  return nums.reduce((a, b) => a + b, 0);
}

function LabeledHeader({
  label,
  hint,
}: {
  label: string;
  hint?: string;
}) {
  // Fiksiramo visinu "header" dijela da inputi u istom redu budu u istoj ravni.
  // (label + hint mogu varirati; ovo amortizuje razliku)
  return (
    <div className="min-h-[52px]">
      <div className="text-sm font-medium text-slate-900">{label}</div>
      {hint ? <div className="mt-1 text-xs text-slate-500 leading-snug">{hint}</div> : null}
    </div>
  );
}

export default function AdminConstantsFBiHPanel({
  form,
  setForm,
  advanced,
  setAdvanced,
  raw,
  setRaw,
}: {
  form: ConstantsForm;
  setForm: (next: ConstantsForm) => void;
  advanced: boolean;
  setAdvanced: (v: boolean) => void;
  raw: string;
  setRaw: (v: string) => void;
}) {
  const monthlyBase = toNumOrNull(form.monthly_contrib_base_bam);

  const pensionAmount = computeContributionAmount(monthlyBase, form.pension_rate_percent);
  const healthAmount = computeContributionAmount(monthlyBase, form.health_rate_percent);
  const unempAmount = computeContributionAmount(monthlyBase, form.unemployment_rate_percent);

  const totalContribAmount = computeTotalContribAmount([pensionAmount, healthAmount, unempAmount]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-900">Payload (unos kroz formu)</div>
          <div className="mt-1 text-sm text-slate-600">
            FBiH panel (obrt i srodne djelatnosti / slobodna zanimanja). Advanced JSON koristiš samo
            za privremene ključeve koje UI još ne podržava.
          </div>
        </div>
        <div className="shrink-0">
          <Button variant="secondary" onClick={() => setAdvanced(!advanced)}>
            {advanced ? "Nazad na formu" : "Advanced JSON"}
          </Button>
        </div>
      </div>

      {!advanced ? (
        <>
          {/* TOP GRID */}
          {/* Poravnanje: fiksna visina label/hint bloka => inputi u istoj ravni */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div>
              <LabeledHeader
                label="Scenario / šema (read-only)"
                hint="Odabrani FBiH scenario iz drop-down-a iznad."
              />
              <Input value={form.scenario_key} onChange={() => {}} readOnly />
            </div>

            <div>
              <LabeledHeader
                label="Valuta"
                hint="Tipično BAM (konvertibilna marka)."
              />
              <Input
                value={form.currency}
                onChange={(v) => setForm({ ...form, currency: v })}
                placeholder="BAM"
              />
            </div>

            <div>
              <LabeledHeader
                label="Mjesečna osnovica doprinosa"
                hint="FBiH: obavezno. Iznos u KM (mora biti > 0)."
              />
              <Input
                value={form.monthly_contrib_base_bam}
                onChange={(v) => setForm({ ...form, monthly_contrib_base_bam: v })}
                placeholder="npr. 1376.00"
              />
            </div>
          </div>

          {/* PDV */}
          <div className="pt-2">
            <SectionTitle title="PDV" subtitle="Stopa i prag ulaska u PDV sistem." />
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div>
                <FieldLabel
                  label="PDV stopa (%)"
                  hint="Unos u procentima (npr. 17). Sistem čuva 0.17."
                />
                <Input
                  value={form.vat_standard_rate_percent}
                  onChange={(v) => setForm({ ...form, vat_standard_rate_percent: v })}
                  placeholder="17"
                />
              </div>
              <div>
                <FieldLabel label="PDV prag ulaska (KM)" hint="Opciono; npr. 50000" />
                <Input
                  value={form.vat_entry_threshold_bam}
                  onChange={(v) => setForm({ ...form, vat_entry_threshold_bam: v })}
                  placeholder="50000"
                />
              </div>
            </div>
          </div>

          {/* POREZ */}
          <div className="pt-2">
            <SectionTitle
              title="Porez"
              subtitle="Stopa poreza i opcionalni paušalni mjesečni iznos (ako se primjenjuje)."
            />
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div>
                <FieldLabel
                  label="Porez na dohodak (%)"
                  hint="Unos u procentima (npr. 10). Sistem čuva 0.10."
                />
                <Input
                  value={form.income_tax_rate_percent}
                  onChange={(v) => setForm({ ...form, income_tax_rate_percent: v })}
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
                  onChange={(v) => setForm({ ...form, flat_tax_monthly_amount_bam: v })}
                  placeholder="npr. 50.00"
                />
              </div>
            </div>
          </div>

          {/* DOPRINOSI */}
          <div className="pt-2">
            <SectionTitle
              title="Doprinosi"
              subtitle="FBiH: iznos u KM = mjesečna osnovica × stopa. Unosiš % stope; UI prikazuje iznose i zbir."
            />

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <div>
                <FieldLabel label="Doprinos PIO (%)" hint="Unesi stopu u %. Ispod vidiš iznos u KM." />
                <div className="grid grid-cols-2 gap-3">
                  <Input
                    value={form.pension_rate_percent}
                    onChange={(v) => setForm({ ...form, pension_rate_percent: v })}
                    placeholder="npr. 18"
                  />
                  <Input
                    value={pensionAmount === null ? "" : pensionAmount.toFixed(2)}
                    onChange={() => {}}
                    readOnly
                    placeholder="iznos (KM)"
                  />
                </div>
                <p className="mt-2 text-xs text-slate-500">Lijevo: % • Desno: iznos (KM) = osnovica × stopa.</p>
              </div>

              <div>
                <FieldLabel label="Zdravstveno (%)" hint="Unesi stopu u %. Ispod vidiš iznos u KM." />
                <div className="grid grid-cols-2 gap-3">
                  <Input
                    value={form.health_rate_percent}
                    onChange={(v) => setForm({ ...form, health_rate_percent: v })}
                    placeholder="npr. 12"
                  />
                  <Input
                    value={healthAmount === null ? "" : healthAmount.toFixed(2)}
                    onChange={() => {}}
                    readOnly
                    placeholder="iznos (KM)"
                  />
                </div>
                <p className="mt-2 text-xs text-slate-500">Lijevo: % • Desno: iznos (KM) = osnovica × stopa.</p>
              </div>

              <div>
                <FieldLabel label="Nezaposlenost (%)" hint="Unesi stopu u %. Ispod vidiš iznos u KM." />
                <div className="grid grid-cols-2 gap-3">
                  <Input
                    value={form.unemployment_rate_percent}
                    onChange={(v) => setForm({ ...form, unemployment_rate_percent: v })}
                    placeholder="npr. 1.5"
                  />
                  <Input
                    value={unempAmount === null ? "" : unempAmount.toFixed(2)}
                    onChange={() => {}}
                    readOnly
                    placeholder="iznos (KM)"
                  />
                </div>
                <p className="mt-2 text-xs text-slate-500">Lijevo: % • Desno: iznos (KM) = osnovica × stopa.</p>
              </div>
            </div>

            <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
              <div>
                <FieldLabel label="Ukupno doprinosi (KM)" hint="Read-only: zbir iznosa doprinosa." />
                <Input
                  value={totalContribAmount === null ? "" : totalContribAmount.toFixed(2)}
                  onChange={() => {}}
                  readOnly
                  placeholder="ukupno"
                />
              </div>
              <div className="hidden lg:block" />
              <div className="hidden lg:block" />
            </div>
          </div>

          {/* IZVORI */}
          <div className="pt-2">
            <SectionTitle title="Izvori" subtitle="Napomena i referenca (audit-friendly)." />
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
                  placeholder="npr. 'Porezna uprava FBiH / SG FBiH / odluka ...'"
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
                  placeholder="npr. 'SG FBiH xx/2025...' ili URL"
                />
              </div>
            </div>
          </div>
        </>
      ) : (
        <>
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Advanced JSON je za slučajeve kad želiš dodati dodatne ključeve prije nego što ih UI dobije kao polja.
          </div>
          <div>
            <FieldLabel
              label="payload (JSON)"
              hint="Mora biti validan JSON. Backend ga snima u app_constants_sets.payload."
            />
            <TextArea value={raw} onChange={setRaw} rows={12} mono placeholder='{ "example": true }' />
          </div>
        </>
      )}
    </div>
  );
}
