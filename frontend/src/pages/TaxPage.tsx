// frontend/src/pages/TaxPage.tsx
import { useEffect, useMemo, useState } from "react";

type MonthlyTaxSummary = {
  year: number;
  month: number;
  tenant_code: string;
  total_income: string;
  total_expense: string;
  taxable_base: string;
  income_tax: string;
  contributions_total: string;
  total_due: string;
  is_final: boolean;
  currency: string;
};

const API_BASE_URL = "http://127.0.0.1:8000";
const DEMO_TENANT = "t-demo";

export default function TaxPage() {
  const today = useMemo(() => new Date(), []);
  const [year, setYear] = useState<number>(today.getFullYear());
  const [month, setMonth] = useState<number>(today.getMonth() + 1);

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [summary, setSummary] = useState<MonthlyTaxSummary | null>(null);
  const [rawJson, setRawJson] = useState<string>("");

  async function fetchAutoMonthly() {
    setLoading(true);
    setErrorMsg(null);

    try {
      const url = new URL("/tax/monthly/auto", API_BASE_URL);
      url.searchParams.set("year", String(year));
      url.searchParams.set("month", String(month));

      const res = await fetch(url.toString(), {
        method: "GET",
        headers: {
          "X-Tenant-Code": DEMO_TENANT,
        },
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Request failed with status code ${res.status}${text ? ` – ${text}` : ""}`);
      }

      const data = (await res.json()) as MonthlyTaxSummary;
      setSummary(data);
      setRawJson(JSON.stringify(data, null, 2));
    } catch (err: any) {
      console.error("Failed to load monthly tax auto:", err);
      setSummary(null);
      setRawJson("");
      setErrorMsg(err?.message ?? "Greška pri učitavanju mjesečnog preview-a.");
    } finally {
      setLoading(false);
    }
  }

  // Učitaj odmah za trenutni mjesec
  useEffect(() => {
    fetchAutoMonthly().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const monthName = useMemo(() => {
    return new Date(year, month - 1, 1).toLocaleDateString("sr-Latn-BA", {
      month: "long",
    });
  }, [year, month]);

  function formatAmount(value: string | null | undefined) {
    if (value == null) return "-";
    const num = Number(value);
    if (!Number.isFinite(num)) return value;
    return `${num.toFixed(2)} ${summary?.currency ?? "BAM"}`;
  }

  return (
    <div className="space-y-5">
      {/* Naslov / header */}
      <div>
        <h2 className="text-xl font-semibold text-slate-800">
          Porezi &amp; doprinosi – mjesečni pregled
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          Tenant <span className="font-mono">{DEMO_TENANT}</span> · backend TAX
          modul (dummy logika u ovoj fazi).
        </p>
      </div>

      {/* Error banner */}
      {errorMsg && (
        <div className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          <p className="font-semibold mb-1">
            Greška pri učitavanju mjesečnog preview-a
          </p>
          <p className="text-xs">{errorMsg}</p>
        </div>
      )}

      {/* Filteri: godina / mjesec + dugme */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-600">Godina</label>
            <select
              className="input w-28"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
            >
              {Array.from({ length: 5 }).map((_, idx) => {
                const y = today.getFullYear() - 2 + idx;
                return (
                  <option key={y} value={y}>
                    {y}
                  </option>
                );
              })}
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-600">Mjesec</label>
            <select
              className="input w-32"
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
            >
              {Array.from({ length: 12 }).map((_, idx) => {
                const m = idx + 1;
                const label = new Date(2025, idx, 1).toLocaleDateString(
                  "sr-Latn-BA",
                  { month: "2-digit" }
                );
                return (
                  <option key={m} value={m}>
                    {label} ({m})
                  </option>
                );
              })}
            </select>
          </div>

          <button
            type="button"
            onClick={fetchAutoMonthly}
            disabled={loading}
            className="btn-primary h-9 px-4 text-xs"
          >
            {loading ? "Učitavam..." : "Osvježi preview (auto obračun)"}
          </button>
        </div>

        <div className="text-xs text-slate-500 md:text-right">
          <p>
            Odabrani period:{" "}
            <span className="font-semibold">
              {monthName} {year}.
            </span>
          </p>
          <p>
            Izvor podataka:{" "}
            <span className="font-mono">
              invoices + cash_entries + input_invoices
            </span>
          </p>
        </div>
      </div>

      {/* Kartice sa sažetkom */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="bg-white border rounded-lg p-4 space-y-2">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
            Status mjeseca
          </p>
          <p className="text-xs text-slate-600">
            {summary
              ? summary.is_final
                ? "Zaključan (finalizovan obračun)"
                : "Još nije finalizovan (DUMMY obračun)"
              : loading
              ? "Čeka učitavanje..."
              : "-"}
          </p>
          <p className="text-[11px] text-slate-400">
            Ovaj status dolazi iz polja <span className="font-mono">is_final</span>.
          </p>
        </div>

        <div className="bg-white border rounded-lg p-4 space-y-2">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
            Prihodi (bruto)
          </p>
          <p className="text-lg font-semibold text-slate-800">
            {summary ? formatAmount(summary.total_income) : "-"}
          </p>
          <p className="text-[11px] text-slate-400">
            Zbir <span className="font-mono">Invoice.total_amount</span> + kasa
            prihodi.
          </p>
        </div>

        <div className="bg-white border rounded-lg p-4 space-y-2">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
            Rashodi (bruto)
          </p>
          <p className="text-lg font-semibold text-slate-800">
            {summary ? formatAmount(summary.total_expense) : "-"}
          </p>
          <p className="text-[11px] text-slate-400">
            Zbir ulaznih faktura + kasa rashodi.
          </p>
        </div>

        <div className="bg-white border rounded-lg p-4 space-y-2">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
            Poreska osnovica
          </p>
          <p className="text-lg font-semibold text-slate-800">
            {summary ? formatAmount(summary.taxable_base) : "-"}
          </p>
          <p className="text-[11px] text-slate-400">
            Računato po DUMMY formuli u backend-u.
          </p>
        </div>
      </div>

      {/* Drugi red kartica: porez, doprinosi, ukupno */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="bg-white border rounded-lg p-4 space-y-2">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
            Porez
          </p>
          <p className="text-lg font-semibold text-slate-800">
            {summary ? formatAmount(summary.income_tax) : "-"}
          </p>
          <p className="text-[11px] text-slate-400">
            Polje <span className="font-mono">income_tax</span>.
          </p>
        </div>

        <div className="bg-white border rounded-lg p-4 space-y-2">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
            Doprinosi
          </p>
          <p className="text-lg font-semibold text-slate-800">
            {summary ? formatAmount(summary.contributions_total) : "-"}
          </p>
          <p className="text-[11px] text-slate-400">
            Zbir PIO + zdravstveno + nezaposlenost (dummy).
          </p>
        </div>

        <div className="bg-white border rounded-lg p-4 space-y-2">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
            Ukupno za uplatu
          </p>
          <p className="text-lg font-semibold text-slate-800">
            {summary ? formatAmount(summary.total_due) : "-"}
          </p>
          <p className="text-[11px] text-slate-400">
            Polje <span className="font-mono">total_due</span> (porez + doprinosi).
          </p>
        </div>
      </div>

      {/* Auto obračun kartica (opis) */}
      <div className="bg-white border rounded-lg p-4 space-y-2">
        <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
          Auto obračun za odabrani mjesec
        </p>
        <p className="text-xs text-slate-600">
          Poziva <span className="font-mono">GET /tax/monthly/auto</span> sa
          parametrima <span className="font-mono">year</span> i{" "}
          <span className="font-mono">month</span>, te osvježava preview.
        </p>
        <div className="mt-3 flex justify-end">
          <button
            type="button"
            onClick={fetchAutoMonthly}
            disabled={loading}
            className="text-xs px-4 py-2 rounded border border-slate-300 hover:bg-slate-50 disabled:opacity-60"
          >
            {loading ? "Računam..." : "Auto obračun & osvježi"}
          </button>
        </div>
      </div>

      {/* Raw JSON debug */}
      <div className="bg-white border rounded-lg p-4 space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
            Raw rezultat (debug) – /tax/monthly/auto
          </p>
          <p className="text-[11px] text-slate-400">
            Korisno da uvijek vidiš tačan ugovor backend ↔ frontend.
          </p>
        </div>

        <pre className="mt-2 max-h-72 overflow-auto text-xs bg-slate-900 text-slate-100 rounded-md p-3">
{rawJson || "// Nema podataka – pokreni auto obračun za odabrani mjesec."}
        </pre>
      </div>
    </div>
  );
}
