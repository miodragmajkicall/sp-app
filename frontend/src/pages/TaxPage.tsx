// /home/miso/dev/sp-app/sp-app/frontend/src/pages/TaxPage.tsx
import { useEffect, useMemo, useState } from "react";
import { apiClient, getApiBaseUrl } from "../services/apiClient";
import {
  MonthlyTaxSummaryRead,
  TaxYearlyMode,
  YearlyTaxSummaryRead,
  fetchTaxMonthlyAuto,
  fetchTaxMonthlyHistory,
  fetchTaxYearlyPreview,
  finalizeTaxMonthly,
  finalizeTaxYearly,
} from "../services/taxApi";

type TaxTab = "monthly" | "yearly";

function toNumberSafe(value: unknown): number {
  if (value == null) return 0;
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  if (typeof value === "string") {
    const n = Number(value);
    return Number.isFinite(n) ? n : 0;
  }
  return 0;
}

function formatMoney(value: number, currency = "BAM") {
  if (!Number.isFinite(value)) return "-";
  return `${value.toFixed(2)} ${currency}`;
}

function formatMonthLabelSr(y: number, m: number) {
  const d = new Date(y, m - 1, 1);
  if (Number.isNaN(d.getTime())) return `${y}-${m}`;
  return d.toLocaleDateString("sr-Latn-BA", { month: "long", year: "numeric" });
}

function formatMonthShort(y: number, m: number) {
  return new Date(y, m - 1, 1).toLocaleDateString("sr-Latn-BA", { month: "2-digit" });
}

function getMonthlyFieldAsNumber(
  item: MonthlyTaxSummaryRead,
  field: keyof MonthlyTaxSummaryRead,
): number {
  return toNumberSafe(item[field]);
}

function parseFilenameFromContentDisposition(cd?: string | null): string | null {
  if (!cd) return null;

  // content-disposition: attachment; filename="xyz.csv"
  const match = /filename\*?=(?:UTF-8'')?("?)([^";]+)\1/i.exec(cd);
  if (!match) return null;

  try {
    return decodeURIComponent(match[2]);
  } catch {
    return match[2];
  }
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function openBlobInNewTab(blob: Blob) {
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank", "noopener,noreferrer");
  // Ne revoke odmah; pusti tab da učita. Možeš revoke kasnije ako želiš.
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export default function TaxPage() {
  const today = useMemo(() => new Date(), []);
  const apiBaseUrl = useMemo(() => getApiBaseUrl(), []);

  const [tab, setTab] = useState<TaxTab>("monthly");

  const [year, setYear] = useState<number>(today.getFullYear());
  const [month, setMonth] = useState<number>(today.getMonth() + 1);

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [summary, setSummary] = useState<MonthlyTaxSummaryRead | null>(null);

  const [finalizing, setFinalizing] = useState(false);
  const [finalizeError, setFinalizeError] = useState<string | null>(null);

  const [history, setHistory] = useState<MonthlyTaxSummaryRead[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const [yearlyLoading, setYearlyLoading] = useState(false);
  const [yearlyError, setYearlyError] = useState<string | null>(null);
  const [yearlySummary, setYearlySummary] = useState<YearlyTaxSummaryRead | null>(null);

  const [yearlyMode, setYearlyMode] = useState<TaxYearlyMode>(() => {
    const raw = window.localStorage.getItem("spapp.tax.yearlyMode");
    return raw === "two_percent" ? "two_percent" : "pausal";
  });

  useEffect(() => {
    window.localStorage.setItem("spapp.tax.yearlyMode", yearlyMode);
  }, [yearlyMode]);

  const currency =
    yearlySummary?.currency ?? history[0]?.currency ?? summary?.currency ?? "BAM";

  const monthName = useMemo(() => {
    return new Date(year, month - 1, 1).toLocaleDateString("sr-Latn-BA", {
      month: "long",
    });
  }, [year, month]);

  async function fetchAutoMonthly() {
    setLoading(true);
    setErrorMsg(null);

    try {
      const data = await fetchTaxMonthlyAuto({ year, month });
      setSummary(data);
    } catch (err: any) {
      console.error("Failed to load monthly tax auto:", err);
      setSummary(null);
      setErrorMsg(err?.message ?? "Greška pri učitavanju mjesečnog auto obračuna.");
    } finally {
      setLoading(false);
    }
  }

  async function finalizeMonthly() {
    if (
      !window.confirm(
        `Da li sigurno želiš FINALIZOVATI obračun za ${monthName} ${year}.?\n\n` +
          "Nakon finalizacije, mjesec se smatra zaključenim i backend blokira izmjene povezanih dokumenata.",
      )
    ) {
      return;
    }

    setFinalizeError(null);
    setFinalizing(true);

    try {
      const data = await finalizeTaxMonthly({ year, month });
      setSummary(data);

      fetchHistoryForYear().catch(() => {});
      fetchYearlyPreview().catch(() => {});
    } catch (err: any) {
      console.error("Failed to finalize monthly tax:", err);
      setFinalizeError(err?.message ?? "Greška pri finalizaciji mjesečnog obračuna.");
    } finally {
      setFinalizing(false);
    }
  }

  async function fetchHistoryForYear() {
    setHistoryLoading(true);
    setHistoryError(null);

    try {
      const list = await fetchTaxMonthlyHistory({ year });
      setHistory(list);
    } catch (err: any) {
      console.error("Failed to load tax history:", err);
      setHistory([]);
      setHistoryError(err?.message ?? "Greška pri učitavanju istorije obračuna.");
    } finally {
      setHistoryLoading(false);
    }
  }

  async function fetchYearlyPreview() {
    setYearlyLoading(true);
    setYearlyError(null);

    try {
      const data = await fetchTaxYearlyPreview({ year });
      setYearlySummary(data);
    } catch (err: any) {
      console.error("Failed to load yearly tax preview:", err);
      setYearlySummary(null);
      setYearlyError(err?.message ?? "Greška pri učitavanju godišnjeg pregleda.");
    } finally {
      setYearlyLoading(false);
    }
  }

  async function finalizeYearly() {
    if (
      !window.confirm(
        `Da li sigurno želiš FINALIZOVATI GODIŠNJI obračun za ${year}.?\n\n` +
          "Backend će snimiti godišnji rezultat (na osnovu finalizovanih mjeseci).",
      )
    ) {
      return;
    }

    setYearlyError(null);
    setYearlyLoading(true);

    try {
      const data = await finalizeTaxYearly({ year });
      setYearlySummary(data);

      fetchHistoryForYear().catch(() => {});
    } catch (err: any) {
      console.error("Failed to finalize yearly tax:", err);
      setYearlyError(err?.message ?? "Greška pri finalizaciji godišnjeg obračuna.");
    } finally {
      setYearlyLoading(false);
    }
  }

  /**
   * Export helper:
   * - radi preko apiClient (nosí X-Tenant-Code header),
   * - responseType: blob,
   * - izvuče filename iz Content-Disposition ako postoji.
   */
  async function exportFile(opts: {
    path: string;
    params: Record<string, any>;
    defaultFilename: string;
    mode: "download" | "open";
  }) {
    try {
      const res = await apiClient.get(opts.path, {
        params: opts.params,
        responseType: "blob",
      });

      const cd = (res.headers?.["content-disposition"] as string | undefined) ?? null;
      const filename = parseFilenameFromContentDisposition(cd) ?? opts.defaultFilename;

      const blob = new Blob([res.data], {
        type:
          (res.headers?.["content-type"] as string | undefined) ??
          "application/octet-stream",
      });

      if (opts.mode === "open") {
        openBlobInNewTab(blob);
      } else {
        triggerDownload(blob, filename);
      }
    } catch (err: any) {
      console.error("Export failed:", err);
      const msg =
        err?.response?.data?.detail ??
        err?.message ??
        "Greška pri exportu. Provjeri da li backend radi i da li je tenant header prisutan.";
      alert(String(msg));
    }
  }

  useEffect(() => {
    fetchAutoMonthly().catch(() => {});
    fetchHistoryForYear().catch(() => {});
    fetchYearlyPreview().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchHistoryForYear().catch(() => {});
    fetchYearlyPreview().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year]);

  const sortedHistory = useMemo(
    () => [...history].sort((a, b) => a.month - b.month),
    [history],
  );

  const monthlyChartData = useMemo(() => {
    const months = Array.from({ length: 12 }, (_, idx) => idx + 1);
    return months.map((m) => {
      const found = sortedHistory.find((h) => h.month === m);
      const totalDue = found ? getMonthlyFieldAsNumber(found, "total_due") : 0;
      return { month: m, totalDue, isFinal: found ? found.is_final : false };
    });
  }, [sortedHistory]);

  const maxChartValue = useMemo(() => {
    const vals = monthlyChartData.map((m) => m.totalDue);
    const max = Math.max(...vals, 0);
    return max > 0 ? max : 0;
  }, [monthlyChartData]);

  const twoPercentCalc = useMemo(() => {
    const base = toNumberSafe(yearlySummary?.taxable_base);
    const tax = base * 0.02;
    return { base, tax };
  }, [yearlySummary]);

  const tabsBase =
    "inline-flex items-center gap-2 rounded-md px-3 py-2 text-xs font-semibold transition-colors";
  const tabsActive = "bg-slate-900 text-white";
  const tabsInactive =
    "bg-white border border-slate-200 text-slate-700 hover:bg-slate-50";

  return (
    <div className="space-y-5">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">Porezi &amp; doprinosi</h2>
          <p className="text-xs text-slate-500 mt-1">
            Demo režim (1 tenant) · API <span className="font-mono">{apiBaseUrl}</span>
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setTab("monthly")}
            className={[tabsBase, tab === "monthly" ? tabsActive : tabsInactive].join(" ")}
          >
            Mjesečno
          </button>
          <button
            type="button"
            onClick={() => setTab("yearly")}
            className={[tabsBase, tab === "yearly" ? tabsActive : tabsInactive].join(" ")}
          >
            Godišnje
          </button>
        </div>
      </div>

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

          {tab === "monthly" && (
            <>
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-600">Mjesec</label>
                <select
                  className="input w-32"
                  value={month}
                  onChange={(e) => setMonth(Number(e.target.value))}
                >
                  {Array.from({ length: 12 }).map((_, idx) => {
                    const m = idx + 1;
                    const label = new Date(2025, idx, 1).toLocaleDateString("sr-Latn-BA", {
                      month: "2-digit",
                    });
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
            </>
          )}

          {tab === "yearly" && (
            <>
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-600">Režim</label>
                <select
                  className="input w-44"
                  value={yearlyMode}
                  onChange={(e) => setYearlyMode(e.target.value as TaxYearlyMode)}
                >
                  <option value="pausal">Paušalac</option>
                  <option value="two_percent">SP 2% (simulacija)</option>
                </select>
              </div>

              <button
                type="button"
                onClick={() => {
                  fetchHistoryForYear().catch(() => {});
                  fetchYearlyPreview().catch(() => {});
                }}
                disabled={historyLoading || yearlyLoading}
                className="text-xs px-4 py-2 rounded border border-slate-300 hover:bg-slate-50 disabled:opacity-60"
              >
                {historyLoading || yearlyLoading ? "Učitavam..." : `Osvježi godišnje (${year}.)`}
              </button>
            </>
          )}
        </div>

        <div className="text-xs text-slate-500 md:text-right space-y-1">
          {tab === "monthly" ? (
            <>
              <p>
                Odabrani period:{" "}
                <span className="font-semibold">
                  {monthName} {year}.
                </span>
              </p>
              <p>
                Izvor podataka:{" "}
                <span className="font-mono">invoices + cash_entries + input_invoices</span>
              </p>
            </>
          ) : (
            <>
              <p>
                Odabrana godina: <span className="font-semibold">{year}.</span>
              </p>
              <p>
                Izvor podataka:{" "}
                <span className="font-mono">
                  /tax/yearly/preview + /tax/monthly/history
                </span>
              </p>
            </>
          )}
        </div>
      </div>

      {tab === "monthly" && errorMsg && (
        <div className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          <p className="font-semibold mb-1">Greška pri učitavanju mjesečnog auto obračuna</p>
          <p className="text-xs">{errorMsg}</p>
        </div>
      )}

      {/* ========================= TAB: MONTHLY ========================= */}
      {tab === "monthly" && (
        <div className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div className="bg-white border rounded-lg p-4 space-y-2">
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
                Status mjeseca
              </p>
              <p className="text-xs text-slate-600">
                {summary
                  ? summary.is_final
                    ? "Zaključan (finalizovan obračun)"
                    : "Još nije finalizovan"
                  : loading
                  ? "Čeka učitavanje..."
                  : "-"}
              </p>
              <p className="text-[11px] text-slate-400">
                Status dolazi iz polja <span className="font-mono">is_final</span>.
              </p>
            </div>

            <div className="bg-white border rounded-lg p-4 space-y-2">
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
                Prihodi (bruto)
              </p>
              <p className="text-lg font-semibold text-slate-800">
                {summary ? `${Number(summary.total_income).toFixed(2)} ${summary.currency}` : "-"}
              </p>
              <p className="text-[11px] text-slate-400">Fakture + kasa prihodi.</p>
            </div>

            <div className="bg-white border rounded-lg p-4 space-y-2">
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
                Rashodi (bruto)
              </p>
              <p className="text-lg font-semibold text-slate-800">
                {summary ? `${Number(summary.total_expense).toFixed(2)} ${summary.currency}` : "-"}
              </p>
              <p className="text-[11px] text-slate-400">Ulazne fakture + kasa rashodi.</p>
            </div>

            <div className="bg-white border rounded-lg p-4 space-y-2">
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
                Poreska osnovica
              </p>
              <p className="text-lg font-semibold text-slate-800">
                {summary ? `${Number(summary.taxable_base).toFixed(2)} ${summary.currency}` : "-"}
              </p>
              <p className="text-[11px] text-slate-400">Računato u backend-u.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="bg-white border rounded-lg p-4 space-y-2">
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
                Porez
              </p>
              <p className="text-lg font-semibold text-slate-800">
                {summary ? `${Number(summary.income_tax).toFixed(2)} ${summary.currency}` : "-"}
              </p>
            </div>

            <div className="bg-white border rounded-lg p-4 space-y-2">
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
                Doprinosi
              </p>
              <p className="text-lg font-semibold text-slate-800">
                {summary
                  ? `${Number(summary.contributions_total).toFixed(2)} ${summary.currency}`
                  : "-"}
              </p>
            </div>

            <div className="bg-white border rounded-lg p-4 space-y-2">
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
                Ukupno za uplatu
              </p>
              <p className="text-lg font-semibold text-slate-800">
                {summary ? `${Number(summary.total_due).toFixed(2)} ${summary.currency}` : "-"}
              </p>
            </div>
          </div>

          <div className="bg-white border rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
                  Zaključavanje (finalizacija) mjeseca
                </p>
                <p className="text-xs text-slate-600">
                  Finalizacija zaključava obračun za mjesec.
                </p>
              </div>
              <button
                type="button"
                onClick={finalizeMonthly}
                disabled={finalizing || loading || (summary ? summary.is_final : false)}
                className="btn-primary h-9 px-4 text-xs disabled:opacity-60"
              >
                {finalizing
                  ? "Finalizujem..."
                  : summary && summary.is_final
                  ? "Mjesec je zaključan"
                  : "Finalizuj ovaj mjesec"}
              </button>
            </div>

            {finalizeError && <p className="text-[11px] text-red-600">{finalizeError}</p>}
          </div>
        </div>
      )}

      {/* ========================= TAB: YEARLY ========================= */}
      {tab === "yearly" && (
        <div className="space-y-5">
          {(historyError || yearlyError) && (
            <div className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
              <p className="font-semibold mb-1">Greška pri učitavanju godišnjih podataka</p>
              <p className="text-xs">{historyError || yearlyError}</p>
            </div>
          )}

          <div className="bg-white border rounded-lg p-4 space-y-3">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
                  Godišnji pregled – {year}. (
                  {yearlyMode === "pausal" ? "paušalac" : "SP 2% (simulacija)"})
                </p>
                <p className="text-xs text-slate-600">
                  Preview: <span className="font-mono">GET /tax/yearly/preview</span>
                </p>
                <p className="text-[11px] text-slate-500 mt-1">
                  Mjeseci uključeni:{" "}
                  <span className="font-semibold">{yearlySummary?.months_included ?? 0}</span>
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() =>
                    exportFile({
                      path: "/tax/yearly/export",
                      params: { year },
                      defaultFilename: `tax-yearly-${year}.csv`,
                      mode: "download",
                    })
                  }
                  className="text-xs px-4 py-2 rounded border border-slate-300 hover:bg-slate-50"
                  title="GET /tax/yearly/export (preko apiClient)"
                >
                  Preuzmi godišnji CSV
                </button>

                <button
                  type="button"
                  onClick={() =>
                    exportFile({
                      path: "/kpr/export",
                      params: { year },
                      defaultFilename: `kpr-${year}.pdf`,
                      mode: "open",
                    })
                  }
                  className="text-xs px-4 py-2 rounded border border-slate-300 hover:bg-slate-50"
                  title="GET /kpr/export (preko apiClient)"
                >
                  Otvori KPR PDF (godina)
                </button>

                <button
                  type="button"
                  onClick={() =>
                    exportFile({
                      path: "/kpr/export-excel",
                      params: { year },
                      defaultFilename: `kpr-${year}.csv`,
                      mode: "download",
                    })
                  }
                  className="text-xs px-4 py-2 rounded border border-slate-300 hover:bg-slate-50"
                  title="GET /kpr/export-excel (preko apiClient)"
                >
                  Preuzmi KPR CSV (godina)
                </button>

                <button
                  type="button"
                  onClick={finalizeYearly}
                  disabled={yearlyLoading}
                  className="btn-primary h-9 px-4 text-xs disabled:opacity-60"
                  title="POST /tax/yearly/finalize"
                >
                  {yearlyLoading ? "Finalizujem..." : "Finalizuj godinu"}
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-[11px]">
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1">
                <p className="font-semibold text-slate-600">Ukupno poreza</p>
                <p className="text-sm font-bold text-slate-900">
                  {formatMoney(toNumberSafe(yearlySummary?.income_tax), currency)}
                </p>
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1">
                <p className="font-semibold text-slate-600">Ukupno doprinosa</p>
                <p className="text-sm font-bold text-slate-900">
                  {formatMoney(toNumberSafe(yearlySummary?.contributions_total), currency)}
                </p>
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1">
                <p className="font-semibold text-slate-600">Ukupno za uplatu</p>
                <p className="text-sm font-bold text-slate-900">
                  {formatMoney(toNumberSafe(yearlySummary?.total_due), currency)}
                </p>
              </div>
            </div>
          </div>

          {yearlyMode === "two_percent" && (
            <div className="bg-white border rounded-lg p-4 space-y-3">
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
                SP 2% – simulacija godišnjeg poreza (frontend)
              </p>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-[11px]">
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1">
                  <p className="font-semibold text-slate-600">Osnovica</p>
                  <p className="text-sm font-bold text-slate-900">
                    {formatMoney(twoPercentCalc.base, currency)}
                  </p>
                </div>

                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-1">
                  <p className="font-semibold text-slate-600">Porez (2%)</p>
                  <p className="text-sm font-bold text-slate-900">
                    {formatMoney(twoPercentCalc.tax, currency)}
                  </p>
                </div>
              </div>

              <p className="text-[11px] text-slate-500">
                Napomena: backend trenutno računa paušalni model. 2% prikaz je simulacija dok
                ne uvedemo režim u settings/onboarding.
              </p>
            </div>
          )}

          <div className="bg-white border rounded-lg p-4 space-y-3">
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
              Istorija finalizovanih mjesečnih obračuna ({year}.)
            </p>

            <div className="mt-2 overflow-x-auto">
              <table className="min-w-full text-[11px] border border-slate-200 rounded-md overflow-hidden">
                <thead className="bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-2 py-1 text-left font-semibold">Mjesec</th>
                    <th className="px-2 py-1 text-left font-semibold">Status</th>
                    <th className="px-2 py-1 text-right font-semibold">Ukupno za uplatu</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedHistory.length === 0 ? (
                    <tr>
                      <td colSpan={3} className="px-2 py-3 text-center text-slate-400">
                        Nema finalizovanih mjeseci za ovu godinu.
                      </td>
                    </tr>
                  ) : (
                    sortedHistory.map((item) => (
                      <tr key={`${item.year}-${item.month}`} className="border-t border-slate-100">
                        <td className="px-2 py-1">
                          {formatMonthShort(item.year, item.month)} ({item.month}) ·{" "}
                          <span className="text-slate-500">
                            {formatMonthLabelSr(item.year, item.month)}
                          </span>
                        </td>
                        <td className="px-2 py-1">
                          {item.is_final ? "Finalizovan (zaključan)" : "Draft"}
                        </td>
                        <td className="px-2 py-1 text-right">
                          {formatMoney(getMonthlyFieldAsNumber(item, "total_due"), item.currency)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <div className="space-y-2 mt-4">
              <p className="text-[11px] font-semibold text-slate-600">
                Trend obaveza po mjesecima (total_due)
              </p>
              <div className="h-40 flex items-end gap-1 border border-slate-200 rounded-lg px-2 py-3 bg-slate-50">
                {monthlyChartData.map((item) => {
                  const heightPercent =
                    maxChartValue > 0 ? Math.max(5, (item.totalDue / maxChartValue) * 100) : 0;

                  return (
                    <div
                      key={item.month}
                      className="flex-1 flex flex-col items-center justify-end gap-1"
                      title={`Mjesec ${item.month} – ${item.totalDue.toFixed(2)} ${currency}${
                        item.isFinal ? " (finalizovan)" : ""
                      }`}
                    >
                      <div
                        className={
                          "w-3 rounded-t-md " +
                          (item.isFinal ? "bg-emerald-500" : "bg-slate-400 opacity-80")
                        }
                        style={{ height: maxChartValue > 0 ? `${heightPercent}%` : "0%" }}
                      />
                      <span className="text-[9px] text-slate-600">
                        {String(item.month).padStart(2, "0")}
                      </span>
                    </div>
                  );
                })}
              </div>
              <p className="text-[10px] text-slate-500">
                Zeleni stubići = finalizovan mjesec.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
