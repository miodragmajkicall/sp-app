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

  const [finalizing, setFinalizing] = useState(false);
  const [finalizeError, setFinalizeError] = useState<string | null>(null);

  const [history, setHistory] = useState<MonthlyTaxSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

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
        throw new Error(
          `Request failed with status code ${res.status}${
            text ? ` – ${text}` : ""
          }`,
        );
      }

      const data = (await res.json()) as MonthlyTaxSummary;
      setSummary(data);
      setRawJson(JSON.stringify(data, null, 2));
    } catch (err: any) {
      console.error("Failed to load monthly tax auto:", err);
      setSummary(null);
      setRawJson("");
      setErrorMsg(
        err?.message ?? "Greška pri učitavanju mjesečnog preview-a.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function finalizeMonthly() {
    if (
      !window.confirm(
        `Da li sigurno želiš FINALIZOVATI obračun za ${monthName} ${year}.?\n\n` +
          "Nakon finalizacije, mjesec se smatra zaključenim i backend može blokirati izmjene povezanih dokumenata.",
      )
    ) {
      return;
    }

    setFinalizeError(null);
    setFinalizing(true);

    try {
      const url = new URL("/tax/monthly/finalize", API_BASE_URL);

      const res = await fetch(url.toString(), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Tenant-Code": DEMO_TENANT,
        },
        body: JSON.stringify({
          year,
          month,
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(
          `Finalize failed with status code ${res.status}${
            text ? ` – ${text}` : ""
          }`,
        );
      }

      const data = (await res.json()) as MonthlyTaxSummary;

      // osvježi glavni sažetak + raw JSON
      setSummary(data);
      setRawJson(JSON.stringify(data, null, 2));
    } catch (err: any) {
      console.error("Failed to finalize monthly tax:", err);
      setFinalizeError(
        err?.message ?? "Greška pri finalizaciji mjesečnog obračuna.",
      );
    } finally {
      setFinalizing(false);
    }
  }

  async function fetchHistoryForYear() {
    setHistoryLoading(true);
    setHistoryError(null);

    try {
      const url = new URL("/tax/monthly/history", API_BASE_URL);
      url.searchParams.set("year", String(year));

      const res = await fetch(url.toString(), {
        method: "GET",
        headers: {
          "X-Tenant-Code": DEMO_TENANT,
        },
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(
          `History request failed with status code ${res.status}${
            text ? ` – ${text}` : ""
          }`,
        );
      }

      const data = (await res.json()) as MonthlyTaxSummary[] | {
        items?: MonthlyTaxSummary[];
      };

      const list = Array.isArray(data)
        ? data
        : Array.isArray((data as any).items)
        ? ((data as any).items as MonthlyTaxSummary[])
        : [];

      setHistory(list);
    } catch (err: any) {
      console.error("Failed to load tax history:", err);
      setHistory([]);
      setHistoryError(
        err?.message ?? "Greška pri učitavanju istorije obračuna.",
      );
    } finally {
      setHistoryLoading(false);
    }
  }

  // Učitaj odmah za trenutni mjesec (auto preview)
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

  function formatHistoryAmount(
    item: MonthlyTaxSummary,
    field: keyof MonthlyTaxSummary,
  ) {
    const raw = item[field];
    if (typeof raw !== "string") return "-";
    const num = Number(raw);
    if (!Number.isFinite(num)) return raw;
    return `${num.toFixed(2)} ${item.currency ?? "BAM"}`;
  }

  function formatHistoryMonth(y: number, m: number) {
    return new Date(y, m - 1, 1).toLocaleDateString("sr-Latn-BA", {
      month: "2-digit",
    });
  }

  function toNumberSafe(value: unknown): number {
    if (value == null) return 0;
    if (typeof value === "number") {
      if (!Number.isFinite(value)) return 0;
      return value;
    }
    if (typeof value === "string") {
      const num = Number(value);
      return Number.isFinite(num) ? num : 0;
    }
    return 0;
  }

  function getMonthlyFieldAsNumber(
    item: MonthlyTaxSummary,
    field: keyof MonthlyTaxSummary,
  ): number {
    return toNumberSafe(item[field]);
  }

  const sortedHistory = useMemo(
    () => [...history].sort((a, b) => a.month - b.month),
    [history],
  );

  const monthlyChartData = useMemo(() => {
    const months = Array.from({ length: 12 }, (_, idx) => idx + 1);
    return months.map((m) => {
      const found = sortedHistory.find((h) => h.month === m);
      const totalDue = found ? getMonthlyFieldAsNumber(found, "total_due") : 0;
      return {
        month: m,
        totalDue,
        isFinal: found ? found.is_final : false,
        currency: found?.currency ?? "BAM",
      };
    });
  }, [sortedHistory]);

  const {
    yearTotalDue,
    yearTaxTotal,
    yearContribTotal,
    maxMonth,
    minMonthNonZero,
  } = useMemo(() => {
    let totalDue = 0;
    let totalTax = 0;
    let totalContrib = 0;

    let maxVal = 0;
    let maxItem: MonthlyTaxSummary | null = null;

    let minValNonZero: number | null = null;
    let minItemNonZero: MonthlyTaxSummary | null = null;

    for (const item of history) {
      const due = getMonthlyFieldAsNumber(item, "total_due");
      const tax = getMonthlyFieldAsNumber(item, "income_tax");
      const contrib = getMonthlyFieldAsNumber(item, "contributions_total");

      totalDue += due;
      totalTax += tax;
      totalContrib += contrib;

      if (due > maxVal) {
        maxVal = due;
        maxItem = item;
      }

      if (due > 0 && (minValNonZero === null || due < minValNonZero)) {
        minValNonZero = due;
        minItemNonZero = item;
      }
    }

    return {
      yearTotalDue: totalDue,
      yearTaxTotal: totalTax,
      yearContribTotal: totalContrib,
      maxMonth: maxItem,
      minMonthNonZero: minItemNonZero,
    };
  }, [history]);

  const maxChartValue = useMemo(() => {
    const vals = monthlyChartData.map((m) => m.totalDue);
    const max = Math.max(...vals, 0);
    return max > 0 ? max : 0;
  }, [monthlyChartData]);

  function formatYearAmount(
    value: number,
    currency: string | undefined = "BAM",
  ) {
    if (!Number.isFinite(value)) return "-";
    return `${value.toFixed(2)} ${currency}`;
  }

  function formatMonthLabel(item: MonthlyTaxSummary | null) {
    if (!item) return "-";
    const d = new Date(item.year, item.month - 1, 1);
    if (Number.isNaN(d.getTime())) return `${item.year}-${item.month}`;
    return d.toLocaleDateString("sr-Latn-BA", {
      month: "long",
      year: "numeric",
    });
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

      {/* Error banner za preview */}
      {errorMsg && (
        <div className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          <p className="font-semibold mb-1">
            Greška pri učitavanju mjesečnog preview-a
          </p>
          <p className="text-xs">{errorMsg}</p>
        </div>
      )}

      {/* Filteri: godina / mjesec + dugmad */}
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
                  { month: "2-digit" },
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

        <div className="text-xs text-slate-500 md:text-right space-y-1">
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
            Ovaj status dolazi iz polja{" "}
            <span className="font-mono">is_final</span>.
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
            Polje <span className="font-mono">total_due</span> (porez +
            doprinosi).
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

      {/* Finalizacija mjeseca */}
      <div className="bg-white border rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
              Zaključavanje (finalizacija) mjeseca
            </p>
            <p className="text-xs text-slate-600">
              Finalizacija zaključava obračun za odabrani mjesec. Backend može
              koristiti ovaj status da blokira naknadne izmjene dokumenata koji
              utiču na obračun.
            </p>
          </div>
          <button
            type="button"
            onClick={finalizeMonthly}
            disabled={
              finalizing || loading || (summary ? summary.is_final : false)
            }
            className="btn-primary h-9 px-4 text-xs disabled:opacity-60"
          >
            {finalizing
              ? "Finalizujem..."
              : summary && summary.is_final
              ? "Mjesec je zaključan"
              : "Finalizuj ovaj mjesec"}
          </button>
        </div>

        {finalizeError && (
          <p className="text-[11px] text-red-600">{finalizeError}</p>
        )}

        <p className="text-[11px] text-slate-400">
          Poslije finalizacije, očekuje se da izmjene faktura / kase za ovaj
          period budu onemogućene ili posebno kontrolisane (logika na backend-u).
        </p>
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

      {/* Istorija obračuna za godinu */}
      <div className="bg-white border rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
              Istorija mjesečnih obračuna
            </p>
            <p className="text-xs text-slate-600">
              Pregled svih mjeseci za odabranu godinu. Podaci dolaze sa{" "}
              <span className="font-mono">GET /tax/monthly/history</span>.
            </p>
          </div>
          <button
            type="button"
            onClick={fetchHistoryForYear}
            disabled={historyLoading}
            className="text-xs px-4 py-2 rounded border border-slate-300 hover:bg-slate-50 disabled:opacity-60"
          >
            {historyLoading ? "Učitavam..." : `Osvježi istoriju za ${year}.`}
          </button>
        </div>

        {historyError && (
          <p className="text-[11px] text-red-600">{historyError}</p>
        )}

        <div className="text-[11px] text-slate-500">
          <p>
            Godina: <span className="font-semibold">{year}.</span> · broj
            zapisa:{" "}
            <span className="font-semibold">{history.length || 0}</span>
          </p>
        </div>

        <div className="mt-2 overflow-x-auto">
          <table className="min-w-full text-[11px] border border-slate-200 rounded-md overflow-hidden">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-2 py-1 text-left font-semibold">Mjesec</th>
                <th className="px-2 py-1 text-left font-semibold">Status</th>
                <th className="px-2 py-1 text-right font-semibold">
                  Ukupno za uplatu
                </th>
                <th className="px-2 py-1 text-right font-semibold">Porez</th>
                <th className="px-2 py-1 text-right font-semibold">
                  Doprinosi
                </th>
              </tr>
            </thead>
            <tbody>
              {history.length === 0 ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-2 py-3 text-center text-slate-400"
                  >
                    Nema zapisa za prikaz – učitaj istoriju ili nema obračuna za
                    ovu godinu.
                  </td>
                </tr>
              ) : (
                history.map((item) => (
                  <tr
                    key={`${item.year}-${item.month}`}
                    className="border-t border-slate-100"
                  >
                    <td className="px-2 py-1">
                      {formatHistoryMonth(item.year, item.month)} (
                      {item.month})
                    </td>
                    <td className="px-2 py-1">
                      {item.is_final
                        ? "Finalizovan (zaključan)"
                        : "Draft / nije finalizovan"}
                    </td>
                    <td className="px-2 py-1 text-right">
                      {formatHistoryAmount(item, "total_due")}
                    </td>
                    <td className="px-2 py-1 text-right">
                      {formatHistoryAmount(item, "income_tax")}
                    </td>
                    <td className="px-2 py-1 text-right">
                      {formatHistoryAmount(item, "contributions_total")}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <p className="text-[11px] text-slate-400 mt-1">
          Ovaj blok će kasnije biti baza za SAM pregled (12 mjeseci grafikon +
          sumarni box).
        </p>
      </div>

      {/* SAM pregled – godišnji zbir + grafikon 12 mjeseci */}
      <div className="bg-white border rounded-lg p-4 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
              SAM pregled – porezi + doprinosi za {year}.
            </p>
            <p className="text-xs text-slate-600">
              Na osnovu istorije mjesečnih obračuna izračunavamo godišnji zbir i
              prikazujemo trend za 12 mjeseci.
            </p>
          </div>
        </div>

        {/* Summary box */}
        <div className="grid gap-3 md:grid-cols-4 text-[11px]">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1">
            <p className="font-semibold text-slate-600">
              Godišnji zbir – ukupno za uplatu
            </p>
            <p className="text-sm font-bold text-slate-900">
              {formatYearAmount(
                yearTotalDue,
                history[0]?.currency ?? "BAM",
              )}
            </p>
            <p className="text-slate-500">
              Zbir svih polja <span className="font-mono">total_due</span> za
              ovu godinu.
            </p>
          </div>

          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1">
            <p className="font-semibold text-slate-600">Godišnji porez</p>
            <p className="text-sm font-bold text-slate-900">
              {formatYearAmount(
                yearTaxTotal,
                history[0]?.currency ?? "BAM",
              )}
            </p>
            <p className="text-slate-500">
              Zbir <span className="font-mono">income_tax</span> svih mjeseci.
            </p>
          </div>

          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1">
            <p className="font-semibold text-slate-600">
              Godišnji doprinosi (PIO, zdravstvo itd.)
            </p>
            <p className="text-sm font-bold text-slate-900">
              {formatYearAmount(
                yearContribTotal,
                history[0]?.currency ?? "BAM",
              )}
            </p>
            <p className="text-slate-500">
              Zbir <span className="font-mono">contributions_total</span>.
            </p>
          </div>

          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1">
            <p className="font-semibold text-slate-600">Najveći / najmanji mjesec</p>
            <p className="text-xs text-slate-700">
              Najveći:{" "}
              <span className="font-semibold">
                {formatMonthLabel(maxMonth)}
              </span>
            </p>
            <p className="text-xs text-slate-700">
              Najmanji (≠ 0):{" "}
              <span className="font-semibold">
                {formatMonthLabel(minMonthNonZero)}
              </span>
            </p>
            <p className="text-slate-500">
              Poredi se polje{" "}
              <span className="font-mono">total_due</span> po mjesecima.
            </p>
          </div>
        </div>

        {/* Jednostavan bar grafikon za 12 mjeseci */}
        <div className="space-y-2">
          <p className="text-[11px] font-semibold text-slate-600">
            Trend obaveza po mjesecima (total_due)
          </p>
          <div className="h-40 flex items-end gap-1 border border-slate-200 rounded-lg px-2 py-3 bg-slate-50">
            {monthlyChartData.map((item) => {
              const heightPercent =
                maxChartValue > 0
                  ? Math.max(5, (item.totalDue / maxChartValue) * 100)
                  : 0; // min 5% da se nešto vidi

              return (
                <div
                  key={item.month}
                  className="flex-1 flex flex-col items-center justify-end gap-1"
                  title={`Mjesec ${item.month} – ${item.totalDue.toFixed(
                    2,
                  )} ${item.currency}${
                    item.isFinal ? " (finalizovan)" : ""
                  }`}
                >
                  <div
                    className={
                      "w-3 rounded-t-md " +
                      (item.isFinal
                        ? "bg-emerald-500"
                        : "bg-slate-400 opacity-80")
                    }
                    style={{
                      height: maxChartValue > 0 ? `${heightPercent}%` : "0%",
                    }}
                  ></div>
                  <span className="text-[9px] text-slate-600">
                    {String(item.month).padStart(2, "0")}
                  </span>
                </div>
              );
            })}
          </div>
          <p className="text-[10px] text-slate-500">
            Zeleni stubići označavaju finalizovane mjesece, sivi su nacrti /
            mjeseci bez finalizacije. Visina je proporcionalna iznosu{" "}
            <span className="font-mono">total_due</span>.
          </p>
        </div>
      </div>
    </div>
  );
}
