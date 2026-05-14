// /home/miso/dev/sp-app/sp-app/frontend/src/pages/TaxPage.tsx
import { useEffect, useMemo, useState } from "react";
import { apiClient, getApiBaseUrl } from "../services/apiClient";
import { getTaxProfileUiSchema } from "../services/settingsApi";
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
import type { TaxProfileUiSchemaResponse } from "../types/settings";

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
  return new Date(y, m - 1, 1).toLocaleDateString("sr-Latn-BA", {
    month: "2-digit",
  });
}

function getMonthlyFieldAsNumber(
  item: MonthlyTaxSummaryRead,
  field: keyof MonthlyTaxSummaryRead,
): number {
  return toNumberSafe(item[field]);
}

function parseFilenameFromContentDisposition(cd?: string | null): string | null {
  if (!cd) return null;

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
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

function formatEntityLabel(entity?: string | null): string {
  if (!entity) return "-";
  if (entity === "Brcko") return "Brčko";
  return entity;
}

function formatScenarioLabel(scenarioKey?: string | null): string {
  if (!scenarioKey) return "-";

  const labels: Record<string, string> = {
    rs_primary: "RS – Osnovna djelatnost",
    rs_supplementary: "RS – Dopunska djelatnost",
    fbih_obrt: "FBiH – Obrt",
    fbih_slobodna: "FBiH – Slobodna djelatnost",
    bd_samostalna: "Brčko – Samostalna djelatnost",
  };

  return labels[scenarioKey] ?? scenarioKey;
}

function formatDateLocal(value?: string | null): string {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("sr-Latn-BA");
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
  const [yearlySummary, setYearlySummary] =
    useState<YearlyTaxSummaryRead | null>(null);

  const [taxUiSchema, setTaxUiSchema] =
    useState<TaxProfileUiSchemaResponse | null>(null);
  const [taxUiSchemaLoading, setTaxUiSchemaLoading] = useState(false);
  const [taxUiSchemaError, setTaxUiSchemaError] = useState<string | null>(null);

  const [yearlyMode, setYearlyMode] = useState<TaxYearlyMode>(() => {
    const raw = window.localStorage.getItem("spapp.tax.yearlyMode");
    return raw === "two_percent" ? "two_percent" : "pausal";
  });

  useEffect(() => {
    window.localStorage.setItem("spapp.tax.yearlyMode", yearlyMode);
  }, [yearlyMode]);

  const currency =
    taxUiSchema?.constants_currency ??
    yearlySummary?.currency ??
    history[0]?.currency ??
    summary?.currency ??
    "BAM";

  const monthName = useMemo(() => {
    return new Date(year, month - 1, 1).toLocaleDateString("sr-Latn-BA", {
      month: "long",
    });
  }, [year, month]);

  const selectedMonthHistoryItem = useMemo(() => {
    return history.find((h) => h.year === year && h.month === month) ?? null;
  }, [history, year, month]);

  const monthlyStatusLabel = useMemo(() => {
    const source = selectedMonthHistoryItem ?? summary;
    if (!source) return loading ? "Čeka učitavanje..." : "-";
    return source.is_final
      ? "Zaključan (finalizovan obračun)"
      : "Još nije finalizovan";
  }, [selectedMonthHistoryItem, summary, loading]);

  const taxProfileBadgeTone = useMemo(() => {
    if (taxUiSchema?.constants_set_id) {
      return "border-emerald-200 bg-emerald-50 text-emerald-800";
    }
    return "border-amber-200 bg-amber-50 text-amber-800";
  }, [taxUiSchema?.constants_set_id]);

  async function fetchAutoMonthly() {
    setLoading(true);
    setErrorMsg(null);

    try {
      const data = await fetchTaxMonthlyAuto({ year, month });
      setSummary(data);
    } catch (err: any) {
      console.error("Failed to load monthly tax auto:", err);
      setSummary(null);
      setErrorMsg(
        err?.message ?? "Greška pri učitavanju mjesečnog auto obračuna.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function fetchTaxProfileContext() {
    setTaxUiSchemaLoading(true);
    setTaxUiSchemaError(null);

    try {
      const data = await getTaxProfileUiSchema();
      setTaxUiSchema(data);
    } catch (err: any) {
      console.error("Failed to load tax profile UI schema:", err);
      setTaxUiSchema(null);
      setTaxUiSchemaError(err?.message ?? "Greška pri učitavanju poreskog profila.");
    } finally {
      setTaxUiSchemaLoading(false);
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

      const cd =
        (res.headers?.["content-disposition"] as string | undefined) ?? null;
      const filename =
        parseFilenameFromContentDisposition(cd) ?? opts.defaultFilename;

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
    fetchTaxProfileContext().catch(() => {});
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

  const monthlyIncome = summary ? toNumberSafe(summary.total_income) : 0;
  const monthlyExpense = summary ? toNumberSafe(summary.total_expense) : 0;
  const monthlyTaxableBase = summary ? toNumberSafe(summary.taxable_base) : 0;
  const monthlyIncomeTax = summary ? toNumberSafe(summary.income_tax) : 0;
  const monthlyContributions = summary
    ? toNumberSafe(summary.contributions_total)
    : 0;
  const monthlyTotalDue = summary ? toNumberSafe(summary.total_due) : 0;

  const yearlyIncomeTax = toNumberSafe(yearlySummary?.income_tax);
  const yearlyContributions = toNumberSafe(yearlySummary?.contributions_total);
  const yearlyTotalDue = toNumberSafe(yearlySummary?.total_due);

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 px-5 py-6 text-white sm:px-6">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div className="max-w-3xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-300">
                Evident · poreski obračuni
              </p>

              <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
                Porezi i doprinosi
              </h1>

              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
                Mjesečni i godišnji obračuni, finalizacija perioda, pregled
                obaveza i export dokumenata za aktivni poreski profil.
              </p>

              <div className="mt-4 flex flex-wrap items-center gap-2 text-[11px] text-slate-300">
                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1">
                  API: <span className="font-mono text-white">{apiBaseUrl}</span>
                </span>

                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1">
                  Period:{" "}
                  <span className="font-semibold text-white">
                    {tab === "monthly" ? `${monthName} ${year}.` : `${year}.`}
                  </span>
                </span>

                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1">
                  Valuta:{" "}
                  <span className="font-semibold text-white">{currency}</span>
                </span>
              </div>
            </div>

            <div className="grid gap-2 sm:grid-cols-2 xl:min-w-[420px]">
              <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
                <p className="text-xs text-slate-300">Aktivni profil</p>
                <p className="mt-1 truncate text-lg font-semibold text-white">
                  {taxUiSchemaLoading
                    ? "Učitavam..."
                    : `${formatEntityLabel(taxUiSchema?.entity)} / ${
                        taxUiSchema?.scenario_key ?? "-"
                      }`}
                </p>
                <p className="mt-1 truncate text-[11px] text-slate-400">
                  {formatScenarioLabel(taxUiSchema?.scenario_key)}
                </p>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
                <p className="text-xs text-slate-300">Izvor obračuna</p>
                <p className="mt-1 truncate text-lg font-semibold text-white">
                  {taxUiSchemaLoading
                    ? "Provjera..."
                    : taxUiSchema?.constants_set_id
                    ? `Admin Constants #${taxUiSchema.constants_set_id}`
                    : "Fallback"}
                </p>
                <p className="mt-1 truncate text-[11px] text-slate-400">
                  {taxUiSchema?.constants_set_id
                    ? "Aktivni effective-dated set"
                    : "Nema aktivnog seta konstanti"}
                </p>
              </div>
            </div>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
              <p className="text-xs text-slate-300">
                {tab === "monthly" ? "Mjesečna obaveza" : "Godišnja obaveza"}
              </p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {formatMoney(
                  tab === "monthly" ? monthlyTotalDue : yearlyTotalDue,
                  currency,
                )}
              </p>
              <p className="mt-1 text-[11px] text-slate-400">
                Ukupno za uplatu.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
              <p className="text-xs text-slate-300">Porez</p>
              <p className="mt-2 text-2xl font-semibold text-amber-300">
                {formatMoney(
                  tab === "monthly" ? monthlyIncomeTax : yearlyIncomeTax,
                  currency,
                )}
              </p>
              <p className="mt-1 text-[11px] text-slate-400">
                Obračunati porez.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
              <p className="text-xs text-slate-300">Doprinosi</p>
              <p className="mt-2 text-2xl font-semibold text-emerald-300">
                {formatMoney(
                  tab === "monthly" ? monthlyContributions : yearlyContributions,
                  currency,
                )}
              </p>
              <p className="mt-1 text-[11px] text-slate-400">
                Ukupni doprinosi.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
              <p className="text-xs text-slate-300">Status</p>
              <p className="mt-2 text-lg font-semibold text-white">
                {tab === "monthly"
                  ? monthlyStatusLabel
                  : yearlyLoading
                  ? "Učitavanje..."
                  : `${yearlySummary?.months_included ?? 0} mj. uključeno`}
              </p>
              <p className="mt-1 text-[11px] text-slate-400">
                Zaključavanje i istorija.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              Kontrole obračuna
            </p>
            <h2 className="mt-1 text-lg font-semibold text-slate-900">
              Period, režim i prikaz
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Promjena perioda ne mijenja backend logiku. Obračun i dalje dolazi
              iz postojećih TAX endpointa.
            </p>
          </div>

          <div className="grid gap-3 md:grid-cols-[140px_160px_auto]">
            <label className="space-y-1 text-xs font-medium text-slate-600">
              Godina
              <select
                className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
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
            </label>

            {tab === "monthly" ? (
              <label className="space-y-1 text-xs font-medium text-slate-600">
                Mjesec
                <select
                  className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                  value={month}
                  onChange={(e) => setMonth(Number(e.target.value))}
                >
                  {Array.from({ length: 12 }).map((_, idx) => {
                    const m = idx + 1;
                    const label = new Date(2025, idx, 1).toLocaleDateString(
                      "sr-Latn-BA",
                      {
                        month: "2-digit",
                      },
                    );
                    return (
                      <option key={m} value={m}>
                        {label} ({m})
                      </option>
                    );
                  })}
                </select>
              </label>
            ) : (
              <label className="space-y-1 text-xs font-medium text-slate-600">
                Režim
                <select
                  className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                  value={yearlyMode}
                  onChange={(e) => setYearlyMode(e.target.value as TaxYearlyMode)}
                >
                  <option value="pausal">Paušalac</option>
                  <option value="two_percent">SP 2% (simulacija)</option>
                </select>
              </label>
            )}

            <div className="space-y-1">
              <p className="text-xs font-medium text-slate-600">Prikaz</p>
              <div className="grid grid-cols-2 gap-1 rounded-2xl border border-slate-200 bg-slate-50 p-1">
                <button
                  type="button"
                  onClick={() => setTab("monthly")}
                  className={
                    "rounded-xl px-3 py-2 text-xs font-semibold transition " +
                    (tab === "monthly"
                      ? "bg-white text-slate-950 shadow-sm"
                      : "text-slate-500 hover:text-slate-800")
                  }
                >
                  Mjesečno
                </button>

                <button
                  type="button"
                  onClick={() => setTab("yearly")}
                  className={
                    "rounded-xl px-3 py-2 text-xs font-semibold transition " +
                    (tab === "yearly"
                      ? "bg-white text-slate-950 shadow-sm"
                      : "text-slate-500 hover:text-slate-800")
                  }
                >
                  Godišnje
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="text-xs text-slate-500">
            {tab === "monthly" ? (
              <>
                Odabrani period:{" "}
                <span className="font-semibold text-slate-800">
                  {monthName} {year}.
                </span>{" "}
                · Izvor:{" "}
                <span className="font-mono">
                  invoices + cash_entries + input_invoices
                </span>
              </>
            ) : (
              <>
                Odabrana godina:{" "}
                <span className="font-semibold text-slate-800">{year}.</span>{" "}
                · Izvor:{" "}
                <span className="font-mono">
                  /tax/yearly/preview + /tax/monthly/history
                </span>
              </>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            {tab === "monthly" ? (
              <button
                type="button"
                onClick={fetchAutoMonthly}
                disabled={loading}
                className="rounded-2xl bg-slate-950 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-slate-800 disabled:opacity-60"
              >
                {loading ? "Učitavam..." : "Osvježi preview"}
              </button>
            ) : (
              <button
                type="button"
                onClick={() => {
                  fetchHistoryForYear().catch(() => {});
                  fetchYearlyPreview().catch(() => {});
                  fetchTaxProfileContext().catch(() => {});
                }}
                disabled={historyLoading || yearlyLoading || taxUiSchemaLoading}
                className="rounded-2xl bg-slate-950 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-slate-800 disabled:opacity-60"
              >
                {historyLoading || yearlyLoading || taxUiSchemaLoading
                  ? "Učitavam..."
                  : `Osvježi godišnje (${year}.)`}
              </button>
            )}
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              Aktivni poreski profil
            </p>
            <h2 className="mt-1 text-lg font-semibold text-slate-900">
              {taxUiSchemaLoading
                ? "Učitavam poreski profil..."
                : `${formatEntityLabel(taxUiSchema?.entity)} / ${formatScenarioLabel(
                    taxUiSchema?.scenario_key,
                  )}`}
            </h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Obračun se prikazuje na osnovu aktivnog poreskog profila i važećih
              Admin konstanti za tenant.
            </p>
          </div>

          <div
            className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${taxProfileBadgeTone}`}
          >
            {taxUiSchemaLoading
              ? "Provjera izvora obračuna..."
              : taxUiSchema?.constants_set_id
              ? `Admin Constants #${taxUiSchema.constants_set_id}`
              : "Fallback konfiguracija"}
          </div>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              Entitet / scenario
            </p>
            <p className="mt-2 text-sm font-semibold text-slate-900">
              {taxUiSchemaLoading
                ? "Učitavam..."
                : `${formatEntityLabel(taxUiSchema?.entity)} / ${
                    taxUiSchema?.scenario_key ?? "-"
                  }`}
            </p>
            <p className="mt-1 text-[11px] text-slate-500">
              {taxUiSchemaLoading
                ? "—"
                : formatScenarioLabel(taxUiSchema?.scenario_key)}
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              Aktivni set
            </p>
            <p className="mt-2 text-sm font-semibold text-slate-900">
              {taxUiSchemaLoading
                ? "Učitavam..."
                : taxUiSchema?.constants_set_id
                ? `#${taxUiSchema.constants_set_id}`
                : "Nije pronađen"}
            </p>
            <p className="mt-1 text-[11px] text-slate-500">
              {taxUiSchema?.constants_set_id
                ? "Effective-dated set"
                : "Fallback / default"}
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              Važenje
            </p>
            <p className="mt-2 text-sm font-semibold text-slate-900">
              {taxUiSchemaLoading
                ? "Učitavam..."
                : formatDateLocal(taxUiSchema?.constants_effective_from)}
            </p>
            <p className="mt-1 text-[11px] text-slate-500">
              do{" "}
              {taxUiSchemaLoading
                ? "—"
                : taxUiSchema?.constants_effective_to
                ? formatDateLocal(taxUiSchema.constants_effective_to)
                : "daljnjeg"}
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              Valuta
            </p>
            <p className="mt-2 text-sm font-semibold text-slate-900">
              {taxUiSchemaLoading
                ? "Učitavam..."
                : taxUiSchema?.constants_currency ?? currency}
            </p>
            <p className="mt-1 text-[11px] text-slate-500">
              Prikaz i obračun.
            </p>
          </div>
        </div>

        {taxUiSchemaError && (
          <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">
            {taxUiSchemaError}
          </div>
        )}
      </section>

      {tab === "monthly" && errorMsg && (
        <div className="rounded-3xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700 shadow-sm">
          <p className="font-semibold">
            Greška pri učitavanju mjesečnog auto obračuna
          </p>
          <p className="mt-1 text-xs">{errorMsg}</p>
        </div>
      )}

      {tab === "monthly" && (
        <div className="space-y-5">
          <section className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                Status mjeseca
              </p>
              <p className="mt-2 text-sm font-semibold text-slate-900">
                {monthlyStatusLabel}
              </p>
              <p className="mt-1 text-[11px] text-slate-500">
                Status dolazi iz polja <span className="font-mono">is_final</span>.
              </p>
            </div>

            <div className="rounded-3xl border border-emerald-100 bg-emerald-50 p-5 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-emerald-700">
                Prihodi
              </p>
              <p className="mt-2 text-xl font-semibold text-emerald-900">
                {summary ? formatMoney(monthlyIncome, summary.currency) : "-"}
              </p>
              <p className="mt-1 text-[11px] text-emerald-700">
                Fakture + kasa prihodi.
              </p>
            </div>

            <div className="rounded-3xl border border-rose-100 bg-rose-50 p-5 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-rose-700">
                Rashodi
              </p>
              <p className="mt-2 text-xl font-semibold text-rose-900">
                {summary ? formatMoney(monthlyExpense, summary.currency) : "-"}
              </p>
              <p className="mt-1 text-[11px] text-rose-700">
                Ulazne fakture + kasa rashodi.
              </p>
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                Poreska osnovica
              </p>
              <p className="mt-2 text-xl font-semibold text-slate-900">
                {summary ? formatMoney(monthlyTaxableBase, summary.currency) : "-"}
              </p>
              <p className="mt-1 text-[11px] text-slate-500">
                Računato u backendu.
              </p>
            </div>
          </section>

          <section className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                Porez
              </p>
              <p className="mt-2 text-2xl font-semibold text-slate-900">
                {summary ? formatMoney(monthlyIncomeTax, summary.currency) : "-"}
              </p>
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                Doprinosi
              </p>
              <p className="mt-2 text-2xl font-semibold text-slate-900">
                {summary
                  ? formatMoney(monthlyContributions, summary.currency)
                  : "-"}
              </p>
            </div>

            <div className="rounded-3xl border border-slate-900 bg-slate-950 p-5 text-white shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300">
                Ukupno za uplatu
              </p>
              <p className="mt-2 text-2xl font-semibold">
                {summary ? formatMoney(monthlyTotalDue, summary.currency) : "-"}
              </p>
            </div>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Zaključavanje mjeseca
                </p>
                <h2 className="mt-1 text-lg font-semibold text-slate-900">
                  Finalizacija obračuna
                </h2>
                <p className="mt-1 text-xs text-slate-500">
                  Finalizacija zaključava obračun za mjesec i backend blokira
                  izmjene povezanih dokumenata.
                </p>
              </div>

              <button
                type="button"
                onClick={finalizeMonthly}
                disabled={finalizing || loading || (summary ? summary.is_final : false)}
                className="rounded-2xl bg-slate-950 px-5 py-2.5 text-xs font-semibold text-white shadow-sm hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {finalizing
                  ? "Finalizujem..."
                  : summary && summary.is_final
                  ? "Mjesec je zaključan"
                  : "Finalizuj ovaj mjesec"}
              </button>
            </div>

            {finalizeError && (
              <p className="mt-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-700">
                {finalizeError}
              </p>
            )}
          </section>
        </div>
      )}

      {tab === "yearly" && (
        <div className="space-y-5">
          {(historyError || yearlyError) && (
            <div className="rounded-3xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700 shadow-sm">
              <p className="font-semibold">
                Greška pri učitavanju godišnjih podataka
              </p>
              <p className="mt-1 text-xs">{historyError || yearlyError}</p>
            </div>
          )}

          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Godišnji pregled
                </p>
                <h2 className="mt-1 text-lg font-semibold text-slate-900">
                  {year}. godina ·{" "}
                  {yearlyMode === "pausal" ? "paušalac" : "SP 2% simulacija"}
                </h2>
                <p className="mt-1 text-xs text-slate-500">
                  Preview: <span className="font-mono">GET /tax/yearly/preview</span>{" "}
                  · Mjeseci uključeni:{" "}
                  <span className="font-semibold">
                    {yearlySummary?.months_included ?? 0}
                  </span>
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
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
                  className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                  title="GET /tax/yearly/export (preko apiClient)"
                >
                  Godišnji CSV
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
                  className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                  title="GET /kpr/export (preko apiClient)"
                >
                  KPR PDF
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
                  className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                  title="GET /kpr/export-excel (preko apiClient)"
                >
                  KPR CSV
                </button>

                <button
                  type="button"
                  onClick={finalizeYearly}
                  disabled={yearlyLoading}
                  className="rounded-2xl bg-slate-950 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-slate-800 disabled:opacity-60"
                  title="POST /tax/yearly/finalize"
                >
                  {yearlyLoading ? "Finalizujem..." : "Finalizuj godinu"}
                </button>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                  Ukupno poreza
                </p>
                <p className="mt-2 text-2xl font-semibold text-slate-900">
                  {formatMoney(yearlyIncomeTax, currency)}
                </p>
              </div>

              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                  Ukupno doprinosa
                </p>
                <p className="mt-2 text-2xl font-semibold text-slate-900">
                  {formatMoney(yearlyContributions, currency)}
                </p>
              </div>

              <div className="rounded-3xl border border-slate-900 bg-slate-950 p-5 text-white">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300">
                  Ukupno za uplatu
                </p>
                <p className="mt-2 text-2xl font-semibold">
                  {formatMoney(yearlyTotalDue, currency)}
                </p>
              </div>
            </div>
          </section>

          {yearlyMode === "two_percent" && (
            <section className="rounded-3xl border border-amber-200 bg-amber-50 p-5 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-700">
                SP 2% simulacija
              </p>
              <h2 className="mt-1 text-lg font-semibold text-amber-950">
                Godišnji porez po stopi 2%
              </h2>

              <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-4">
                <div className="rounded-2xl border border-amber-200 bg-white/70 p-4">
                  <p className="text-xs font-semibold text-amber-800">Osnovica</p>
                  <p className="mt-1 text-lg font-semibold text-amber-950">
                    {formatMoney(twoPercentCalc.base, currency)}
                  </p>
                </div>

                <div className="rounded-2xl border border-amber-200 bg-white/70 p-4">
                  <p className="text-xs font-semibold text-amber-800">Porez 2%</p>
                  <p className="mt-1 text-lg font-semibold text-amber-950">
                    {formatMoney(twoPercentCalc.tax, currency)}
                  </p>
                </div>
              </div>

              <p className="mt-4 text-xs text-amber-800">
                Napomena: backend trenutno računa paušalni model. 2% prikaz je
                frontend simulacija dok ne uvedemo režim u settings/onboarding.
              </p>
            </section>
          )}

          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              Istorija mjesečnih obračuna
            </p>
            <h2 className="mt-1 text-lg font-semibold text-slate-900">
              Finalizovani mjeseci za {year}.
            </h2>

            <div className="mt-5 overflow-x-auto rounded-2xl border border-slate-200">
              <table className="min-w-full text-xs">
                <thead className="bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-4 py-3 text-left font-semibold">Mjesec</th>
                    <th className="px-4 py-3 text-left font-semibold">Status</th>
                    <th className="px-4 py-3 text-right font-semibold">
                      Ukupno za uplatu
                    </th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100">
                  {sortedHistory.length === 0 ? (
                    <tr>
                      <td
                        colSpan={3}
                        className="px-4 py-8 text-center text-slate-400"
                      >
                        Nema finalizovanih mjeseci za ovu godinu.
                      </td>
                    </tr>
                  ) : (
                    sortedHistory.map((item) => (
                      <tr key={`${item.year}-${item.month}`} className="hover:bg-slate-50">
                        <td className="px-4 py-3">
                          {formatMonthShort(item.year, item.month)} ({item.month}) ·{" "}
                          <span className="text-slate-500">
                            {formatMonthLabelSr(item.year, item.month)}
                          </span>
                        </td>

                        <td className="px-4 py-3">
                          {item.is_final ? (
                            <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[10px] font-semibold text-emerald-700">
                              Finalizovan
                            </span>
                          ) : (
                            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-semibold text-slate-500">
                              Draft
                            </span>
                          )}
                        </td>

                        <td className="px-4 py-3 text-right font-semibold text-slate-900">
                          {formatMoney(
                            getMonthlyFieldAsNumber(item, "total_due"),
                            item.currency,
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <div className="mt-6 space-y-2">
              <p className="text-xs font-semibold text-slate-700">
                Trend obaveza po mjesecima
              </p>

              <div className="flex h-48 items-end gap-2 overflow-x-auto rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                {monthlyChartData.map((item) => {
                  const heightPercent =
                    maxChartValue > 0
                      ? Math.max(5, (item.totalDue / maxChartValue) * 100)
                      : 0;

                  return (
                    <div
                      key={item.month}
                      className="flex h-full min-w-[28px] flex-1 flex-col items-center justify-end gap-1"
                      title={`Mjesec ${item.month} – ${item.totalDue.toFixed(
                        2,
                      )} ${currency}${item.isFinal ? " (finalizovan)" : ""}`}
                    >
                      <div
                        className={
                          "w-4 rounded-t-xl " +
                          (item.isFinal
                            ? "bg-emerald-500"
                            : "bg-slate-400 opacity-80")
                        }
                        style={{
                          height: maxChartValue > 0 ? `${heightPercent}%` : "0%",
                        }}
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
          </section>
        </div>
      )}
    </div>
  );
}