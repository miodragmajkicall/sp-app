// /home/miso/dev/sp-app/sp-app/frontend/src/pages/admin-constants/AdminConstantsRSPanel.tsx

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

  avg_gross_wage_prev_year_bam: string;
  contrib_base_percent_of_avg_gross: string;

  monthly_contrib_base_bam: string;

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

function computeCalculatedBaseBam(avgGrossStr: string, basePercentStr: string): number | null {
  const avg = toNumOrNull(avgGrossStr);
  const p = toNumOrNull(basePercentStr);
  if (avg === null || p === null) return null;
  const pct = clampPercent(p);
  return avg * (pct / 100);
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

function rsContributionMode(scenarioKey: string): "PRIMARY" | "SUPPLEMENTARY" {
  return scenarioKey === "rs_supplementary" ? "SUPPLEMENTARY" : "PRIMARY";
}

export default function AdminConstantsRSPanel({
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
  const rsMode = rsContributionMode(form.scenario_key);

  const calculatedBase = computeCalculatedBaseBam(
    form.avg_gross_wage_prev_year_bam,
    form.contrib_base_percent_of_avg_gross
  );

  const pensionAmount = computeContributionAmount(calculatedBase, form.pension_rate_percent);

  const healthAmount =
    rsMode === "PRIMARY"
      ? computeContributionAmount(calculatedBase, form.health_rate_percent)
      : null;

  const unempAmount =
    rsMode === "PRIMARY"
      ? computeContributionAmount(calculatedBase, form.unemployment_rate_percent)
      : null;

  // NEW: child protection (RS primary only)
  const [childProtectionRatePercent, setChildProtectionRatePercent] = (() => {
    const payloadAny = (form as any);
    const current =
      typeof payloadAny.child_protection_rate_percent === "string"
        ? payloadAny.child_protection_rate_percent
        : "";

    const setter = (v: string) => {
      setForm({ ...(form as any), child_protection_rate_percent: v });
    };

    return [current, setter] as const;
  })();

  const childProtectionAmount =
    rsMode === "PRIMARY"
      ? computeContributionAmount(calculatedBase, childProtectionRatePercent)
      : null;

  const totalContribAmount =
    rsMode === "SUPPLEMENTARY"
      ? computeTotalContribAmount([pensionAmount])
      : computeTotalContribAmount([
          pensionAmount,
          healthAmount,
          unempAmount,
          childProtectionAmount,
        ]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-900">
            Payload (unos kroz formu)
          </div>
          <div className="mt-1 text-sm text-slate-600">
            RS panel (osnovna + dopunska). Advanced JSON koristiš samo za privremene
            ključeve koje UI još ne podržava.
          </div>
        </div>
        <div className="shrink-0">
          <Button
            variant="secondary"
            onClick={() => {
              setAdvanced(!advanced);
            }}
          >
            {advanced ? "Nazad na formu" : "Advanced JSON"}
          </Button>
        </div>
      </div>

      {!advanced ? (
        <>
          {/* TOP GRID (aligned) */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3 items-end">
            <div>
              <FieldLabel label="Scenario / šema (read-only)" />
              <Input value={form.scenario_key} onChange={() => {}} readOnly />
            </div>

            <div>
              <FieldLabel label="Valuta" />
              <Input
                value={form.currency}
                onChange={(v) => setForm({ ...form, currency: v })}
                placeholder="BAM"
              />
            </div>

            <div>
              <FieldLabel label="Prosječna bruto plata (prethodna godina) (KM)" />
              <Input
                value={form.avg_gross_wage_prev_year_bam}
                onChange={(v) => setForm({ ...form, avg_gross_wage_prev_year_bam: v })}
                placeholder="npr. 2000.00"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 items-end">
            <div>
              <FieldLabel
                label="Osnovica doprinosa = % prosječne bruto plate"
                hint={
                  rsMode === "SUPPLEMENTARY"
                    ? "Dopunska djelatnost: default 30%."
                    : "Unos u procentima (npr. 80 znači 80%)."
                }
              />
              <Input
                value={form.contrib_base_percent_of_avg_gross}
                onChange={(v) =>
                  setForm({ ...form, contrib_base_percent_of_avg_gross: v })
                }
                placeholder={rsMode === "SUPPLEMENTARY" ? "30" : "npr. 80"}
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
          </div>

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

          <div className="pt-2">
            <SectionTitle
              title="Porez"
              subtitle="Stopa poreza i opcionalni paušalni mjesečni iznos."
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
                  onChange={(v) =>
                    setForm({ ...form, flat_tax_monthly_amount_bam: v })
                  }
                  placeholder="npr. 50.00"
                />
              </div>
            </div>
          </div>

          <div className="pt-2">
            <SectionTitle
              title="Doprinosi"
              subtitle={
                rsMode === "SUPPLEMENTARY"
                  ? "Dopunska djelatnost: samo PIO, automatski izračun iznosa u KM (osnovica × stopa)."
                  : "Osnovna djelatnost: PIO + zdravstvo + nezaposlenost + dječija zaštita (iznos u KM = osnovica × stopa)."
              }
            />

            {rsMode === "SUPPLEMENTARY" ? (
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 items-start">
                <div>
                  <FieldLabel label="Doprinos PIO (%)" hint="Unos u % (npr. 18)." />
                  <div className="grid grid-cols-2 gap-3">
                    <Input
                      value={form.pension_rate_percent}
                      onChange={(v) => setForm({ ...form, pension_rate_percent: v })}
                      placeholder="18"
                    />
                    <Input
                      value={pensionAmount === null ? "" : pensionAmount.toFixed(2)}
                      onChange={() => {}}
                      readOnly
                      placeholder="iznos (KM)"
                    />
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    Lijevo: % • Desno: iznos (KM) = osnovica × stopa.
                  </p>
                </div>

                <div>
                  <FieldLabel label="Ukupno doprinosi (KM)" hint="Za dopunsku: ukupno = PIO." />
                  <div className="grid grid-cols-2 gap-3">
                    <div className="col-span-2">
                      <Input
                        value={totalContribAmount === null ? "" : totalContribAmount.toFixed(2)}
                        onChange={() => {}}
                        readOnly
                        placeholder="ukupno"
                      />
                    </div>
                  </div>
                  <p className="mt-2 text-xs text-slate-500">
                    Read-only: ukupno (KM) = PIO iznos.
                  </p>
                </div>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
                  <div>
                    <FieldLabel
                      label="Doprinos PIO (%)"
                      hint="Unesi stopu u %. Ispod vidiš iznos u KM."
                    />
                    <div className="grid grid-cols-2 gap-3">
                      <Input
                        value={form.pension_rate_percent}
                        onChange={(v) => setForm({ ...form, pension_rate_percent: v })}
                        placeholder="18"
                      />
                      <Input
                        value={pensionAmount === null ? "" : pensionAmount.toFixed(2)}
                        onChange={() => {}}
                        readOnly
                        placeholder="iznos (KM)"
                      />
                    </div>
                    <p className="mt-2 text-xs text-slate-500">
                      Lijevo: % • Desno: iznos (KM) = osnovica × stopa.
                    </p>
                  </div>

                  <div>
                    <FieldLabel
                      label="Zdravstveno (%)"
                      hint="Unesi stopu u %. Ispod vidiš iznos u KM."
                    />
                    <div className="grid grid-cols-2 gap-3">
                      <Input
                        value={form.health_rate_percent}
                        onChange={(v) => setForm({ ...form, health_rate_percent: v })}
                        placeholder="12"
                      />
                      <Input
                        value={healthAmount === null ? "" : healthAmount.toFixed(2)}
                        onChange={() => {}}
                        readOnly
                        placeholder="iznos (KM)"
                      />
                    </div>
                    <p className="mt-2 text-xs text-slate-500">
                      Lijevo: % • Desno: iznos (KM) = osnovica × stopa.
                    </p>
                  </div>

                  <div>
                    <FieldLabel
                      label="Nezaposlenost (%)"
                      hint="Unesi stopu u %. Ispod vidiš iznos u KM."
                    />
                    <div className="grid grid-cols-2 gap-3">
                      <Input
                        value={form.unemployment_rate_percent}
                        onChange={(v) =>
                          setForm({ ...form, unemployment_rate_percent: v })
                        }
                        placeholder="0.6"
                      />
                      <Input
                        value={unempAmount === null ? "" : unempAmount.toFixed(2)}
                        onChange={() => {}}
                        readOnly
                        placeholder="iznos (KM)"
                      />
                    </div>
                    <p className="mt-2 text-xs text-slate-500">
                      Lijevo: % • Desno: iznos (KM) = osnovica × stopa.
                    </p>
                  </div>

                  <div>
                    <FieldLabel
                      label="Dječija zaštita (%)"
                      hint="Unesi stopu u %. Ispod vidiš iznos u KM."
                    />
                    <div className="grid grid-cols-2 gap-3">
                      <Input
                        value={childProtectionRatePercent}
                        onChange={setChildProtectionRatePercent}
                        placeholder="1.7"
                      />
                      <Input
                        value={
                          childProtectionAmount === null ? "" : childProtectionAmount.toFixed(2)
                        }
                        onChange={() => {}}
                        readOnly
                        placeholder="iznos (KM)"
                      />
                    </div>
                    <p className="mt-2 text-xs text-slate-500">
                      Lijevo: % • Desno: iznos (KM) = osnovica × stopa.
                    </p>
                  </div>
                </div>

                <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
                  <div>
                    <FieldLabel
                      label="Ukupno doprinosi (KM)"
                      hint="Read-only: zbir iznosa doprinosa."
                    />
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
              </>
            )}
          </div>

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
