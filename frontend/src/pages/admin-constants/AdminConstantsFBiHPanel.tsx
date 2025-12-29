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
  contrib_base_min_bam: string;

  source_note: string;
  source_reference: string;
};

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
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-900">
            Payload (unos kroz formu)
          </div>
          <div className="mt-1 text-sm text-slate-600">
            FBiH panel (obrt i srodne djelatnosti / slobodna zanimanja).
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
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
            <div>
              <FieldLabel label="Scenario / šema (read-only)" />
              <Input value={form.scenario_key} onChange={() => {}} readOnly />
            </div>

            <div>
              <FieldLabel label="Valuta" />
              <Input
                value={form.currency}
                onChange={(v) => setForm({ ...form, currency: v })}
              />
            </div>

            <div>
              <FieldLabel
                label="Mjesečna osnovica doprinosa (KM)"
                hint="FBiH: obavezno, mora biti > 0."
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
          </div>

          <div className="pt-2">
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

          <div className="pt-2">
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
              <div>
                <FieldLabel label="Paušalni porez (KM mjesečno)" />
                <Input
                  value={form.flat_tax_monthly_amount_bam}
                  onChange={(v) =>
                    setForm({ ...form, flat_tax_monthly_amount_bam: v })
                  }
                />
              </div>
            </div>
          </div>

          <div className="pt-2">
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
                  onChange={(v) =>
                    setForm({ ...form, source_reference: v })
                  }
                />
              </div>
            </div>
          </div>
        </>
      ) : (
        <>
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Advanced JSON (FBiH).
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
