// /home/miso/dev/sp-app/sp-app/frontend/src/pages/admin-constants/AdminConstantsBDPanel.tsx

import {
  FieldLabel,
  Input,
  SectionTitle,
  TextArea,
  Button,
} from "./adminConstantsUi";

type ConstantsForm = {
  scenario_key: string;
  currency: string;

  // VAT
  vat_standard_rate_percent: string;
  vat_entry_threshold_bam: string;

  // Tax
  income_tax_rate_percent: string;
  flat_tax_monthly_amount_bam: string;

  // Contributions
  pension_rate_percent: string;
  health_rate_percent: string;
  unemployment_rate_percent: string;

  // BD: fixed base in KM (reuse generic field used for FBiH)
  monthly_contrib_base_bam: string;

  // legacy fields (kept in type to avoid breaking parent form typing)
  avg_gross_wage_prev_year_bam: string;
  contrib_base_percent_of_avg_gross: string;
  contrib_base_min_bam: string;

  // Sources
  source_note: string;
  source_reference: string;
};

function FixedLabel({
  label,
  hint,
}: {
  label: string;
  hint?: string;
}) {
  return (
    <div className="h-[44px] flex items-end">
      <FieldLabel label={label} hint={hint} />
    </div>
  );
}

export default function AdminConstantsBDPanel({
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
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-900">
            Payload (unos kroz formu)
          </div>
          <div className="mt-1 text-sm text-slate-600">
            Brčko distrikt – samostalna djelatnost.
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
          <SectionTitle
            title="Osnovica doprinosa"
            subtitle="BD: osnovica se u praksi propisuje kao fiksan iznos u KM (odlukom) i admin unosi taj iznos. Kod promjene odluke: snimi novi set (rollover)."
          />

          {/* 4 kolone poravnate: inputi uvijek na istoj visini */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
            <div className="flex flex-col">
              <FixedLabel label="Scenario / šema" hint="Read-only." />
              <Input value={form.scenario_key} readOnly />
            </div>

            <div className="flex flex-col">
              <FixedLabel label="Valuta" hint="BD V1: fiksno BAM." />
              <Input value="BAM" readOnly />
            </div>

            <div className="flex flex-col lg:col-span-2">
              <FixedLabel
                label="Osnovica doprinosa (KM)"
                hint="Fiksan iznos iz odluke BD (npr. 1200)."
              />
              <Input
                value={form.monthly_contrib_base_bam}
                onChange={(v) =>
                  setForm({ ...form, monthly_contrib_base_bam: v })
                }
                placeholder="npr. 1200"
              />
            </div>
          </div>

          <div className="pt-4">
            <SectionTitle title="Doprinosi" />
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <div>
                <FieldLabel label="PIO (%)" />
                <Input
                  value={form.pension_rate_percent}
                  onChange={(v) => setForm({ ...form, pension_rate_percent: v })}
                />
              </div>

              <div>
                <FieldLabel label="Zdravstvo (%)" />
                <Input
                  value={form.health_rate_percent}
                  onChange={(v) => setForm({ ...form, health_rate_percent: v })}
                />
              </div>

              <div>
                <FieldLabel label="Nezaposlenost (%)" />
                <Input
                  value={form.unemployment_rate_percent}
                  onChange={(v) =>
                    setForm({ ...form, unemployment_rate_percent: v })
                  }
                />
              </div>
            </div>
          </div>

          <div className="pt-4">
            <SectionTitle title="Porez" />
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div>
                <FieldLabel label="Porez na dohodak (%)" />
                <Input
                  value={form.income_tax_rate_percent}
                  onChange={(v) =>
                    setForm({ ...form, income_tax_rate_percent: v })
                  }
                />
              </div>

              {/* BD V1: paušal ne prikazujemo (nije potreban); ostaje u formi samo radi kompatibilnosti */}
            </div>
          </div>

          <div className="pt-4">
            <SectionTitle title="PDV" />
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div>
                <FieldLabel label="PDV stopa (%)" />
                <Input
                  value={form.vat_standard_rate_percent}
                  onChange={(v) =>
                    setForm({ ...form, vat_standard_rate_percent: v })
                  }
                />
              </div>
              <div>
                <FieldLabel label="PDV prag ulaska (KM)" />
                <Input
                  value={form.vat_entry_threshold_bam}
                  onChange={(v) =>
                    setForm({ ...form, vat_entry_threshold_bam: v })
                  }
                />
              </div>
            </div>
          </div>

          <div className="pt-4">
            <SectionTitle title="Izvori" />
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div>
                <FieldLabel label="Napomena / izvor" />
                <TextArea
                  value={form.source_note}
                  onChange={(v) => setForm({ ...form, source_note: v })}
                />
              </div>
              <div>
                <FieldLabel label="Referenca" />
                <TextArea
                  value={form.source_reference}
                  onChange={(v) => setForm({ ...form, source_reference: v })}
                />
              </div>
            </div>
          </div>
        </>
      ) : (
        <>
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Advanced JSON (BD).
          </div>
          <TextArea
            value={raw}
            onChange={setRaw}
            rows={12}
            mono
            placeholder='{ "example": true }'
          />
        </>
      )}
    </div>
  );
}
