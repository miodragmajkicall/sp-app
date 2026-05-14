// /home/miso/dev/sp-app/sp-app/frontend/src/pages/ReportsPage.tsx

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { apiClient, getApiBaseUrl } from "../services/apiClient";
import { fetchInvoicesList } from "../services/invoicesApi";
import { fetchInputInvoicesList } from "../services/inputInvoicesApi";
import {
  buildReportsCashflowYearCsvUrl,
  fetchReportsCashflowYear,
  fetchReportsYearSummary,
} from "../services/reportsApi";
import type {
  ReportsCashflowYearResponse,
  ReportsYearSummaryResponse,
} from "../types/reports";

interface MonthlyCashSummary {
  year: number;
  month: number;
  income_total?: number | string;
  expense_total?: number | string;
  net_cashflow?: number | string;
}

interface MonthlyInvoicesSummary {
  year: number;
  month: number;
  invoices_count?: number;
  total_amount?: number | string;
}

interface MonthlyTaxSummary {
  year: number;
  month: number;
  has_result: boolean;
  is_final: boolean;
  total_due?: number | string;
}

interface MonthlySamSummary {
  year: number;
  month: number;
  total_due?: number | string;
  has_result: boolean;
  is_final: boolean;
}

interface DashboardMonthlyResponse {
  tenant_code: string;
  year: number;
  month: number;
  cash?: MonthlyCashSummary;
  invoices?: MonthlyInvoicesSummary;
  tax?: MonthlyTaxSummary;
  sam?: MonthlySamSummary;
}

type ReportsTab = "monthly" | "yearly" | "analytics";

function toNumber(value: number | string | undefined | null): number {
  if (value === undefined || value === null) return 0;
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function formatAmount(value: number): string {
  return value.toLocaleString("sr-Latn-BA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function getMonthName(month: number): string {
  const d = new Date(2025, month - 1, 1);
  return d.toLocaleDateString("sr-Latn-BA", { month: "long" });
}

function getShortMonthLabel(month: number): string {
  const d = new Date(2025, month - 1, 1);
  return d.toLocaleDateString("sr-Latn-BA", { month: "short" });
}

function clampYear(y: number): number {
  if (!Number.isFinite(y)) return new Date().getFullYear();
  if (y < 2000) return 2000;
  if (y > 2100) return 2100;
  return y;
}

function netClass(value: number): string {
  if (value > 0) return "text-emerald-600";
  if (value < 0) return "text-rose-600";
  return "text-slate-700";
}

function HeroMetric({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: string;
  hint: string;
  tone?: "neutral" | "income" | "expense";
}) {
  const valueClass =
    tone === "income"
      ? "text-emerald-300"
      : tone === "expense"
        ? "text-amber-300"
        : "text-white";

  return (
    <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
      <p className="text-xs text-slate-300">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${valueClass}`}>{value}</p>
      <p className="mt-1 text-[11px] text-slate-400">{hint}</p>
    </div>
  );
}

function MiniMetric({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "income" | "expense" | "dark";
}) {
  const valueClass =
    tone === "income"
      ? "text-emerald-600"
      : tone === "expense"
        ? "text-rose-600"
        : tone === "dark"
          ? "text-slate-950"
          : "text-slate-800";

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
        {label}
      </p>
      <p className={`mt-2 text-xl font-semibold ${valueClass}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export default function ReportsPage() {
  const navigate = useNavigate();
  const apiBaseUrl = getApiBaseUrl();

  const {
    data: currentMonthly,
    isLoading: isLoadingCurrent,
    isError: isErrorCurrent,
    error: errorCurrent,
  } = useQuery<DashboardMonthlyResponse, Error>({
    queryKey: ["reports", "bootstrap", "dashboard-monthly-current"],
    queryFn: async () => {
      const res = await apiClient.get<DashboardMonthlyResponse>(
        "/dashboard/monthly/current",
      );
      return res.data;
    },
    staleTime: 60_000,
  });

  const initialYear = clampYear(
    currentMonthly?.year ?? new Date().getFullYear(),
  );
  const initialMonth = Math.min(
    12,
    Math.max(1, currentMonthly?.month ?? new Date().getMonth() + 1),
  );

  const [activeTab, setActiveTab] = useState<ReportsTab>("monthly");
  const [year, setYear] = useState<number>(initialYear);
  const [month, setMonth] = useState<number>(initialMonth);

  const {
    data: monthlySummary,
    isLoading: isLoadingMonthlySummary,
    isError: isErrorMonthlySummary,
    error: errorMonthlySummary,
  } = useQuery<DashboardMonthlyResponse, Error>({
    queryKey: ["reports", "monthly", "summary", year, month],
    enabled: !!year && !!month,
    queryFn: async () => {
      const res = await apiClient.get<DashboardMonthlyResponse>(
        `/dashboard/monthly/${year}/${month}`,
      );
      return res.data;
    },
    staleTime: 60_000,
  });

  const { data: outgoingForMonth, isLoading: isLoadingOutgoingForMonth } =
    useQuery({
      queryKey: ["reports", "monthly", "outgoing", year, month],
      enabled: !!year && !!month,
      queryFn: () =>
        fetchInvoicesList({
          year,
          month,
        }),
      staleTime: 60_000,
    });

  const { data: inputForMonth, isLoading: isLoadingInputForMonth } = useQuery({
    queryKey: ["reports", "monthly", "input", year, month],
    enabled: !!year && !!month,
    queryFn: () =>
      fetchInputInvoicesList({
        year,
        month,
        limit: 200,
        offset: 0,
      }),
    staleTime: 60_000,
  });

  const {
    data: yearlyCashflow,
    isLoading: isLoadingYearlyCashflow,
    isError: isErrorYearlyCashflow,
    error: errorYearlyCashflow,
  } = useQuery<ReportsCashflowYearResponse, Error>({
    queryKey: ["reports", "yearly", "cashflow", year],
    enabled: !!year,
    queryFn: () => fetchReportsCashflowYear(year),
    staleTime: 60_000,
  });

  const {
    data: yearlySummary,
    isLoading: isLoadingYearlySummary,
    isError: isErrorYearlySummary,
    error: errorYearlySummary,
  } = useQuery<ReportsYearSummaryResponse, Error>({
    queryKey: ["reports", "yearly", "summary", year],
    enabled: !!year,
    queryFn: () => fetchReportsYearSummary(year),
    staleTime: 60_000,
  });

  const { data: outgoingForYear } = useQuery({
    queryKey: ["reports", "analytics", "outgoing-year", year],
    enabled: !!year,
    queryFn: () =>
      fetchInvoicesList({
        year,
      }),
    staleTime: 60_000,
  });

  const { data: inputForYear } = useQuery({
    queryKey: ["reports", "analytics", "input-year", year],
    enabled: !!year,
    queryFn: () =>
      fetchInputInvoicesList({
        year,
        limit: 1000,
        offset: 0,
      }),
    staleTime: 60_000,
  });

  const monthTitle = useMemo(() => {
    return `${getMonthName(month)} ${year}`;
  }, [month, year]);

  const monthlyIncome = toNumber(monthlySummary?.cash?.income_total);
  const monthlyExpense = toNumber(monthlySummary?.cash?.expense_total);
  const monthlyProfit = monthlyIncome - monthlyExpense;
  const monthlyExpectedTax = toNumber(monthlySummary?.tax?.total_due);

  const monthlyInvoices = outgoingForMonth?.items ?? [];
  const monthlyInputInvoices = inputForMonth?.items ?? [];

  const incomeSeries = useMemo(() => {
    const items = yearlyCashflow?.items ?? [];
    const byMonth = new Map<number, number>();

    for (const it of items) {
      byMonth.set(it.month, toNumber(it.income));
    }

    return Array.from({ length: 12 }, (_, idx) => {
      const m = idx + 1;
      return {
        month: m,
        label: getShortMonthLabel(m),
        value: byMonth.get(m) ?? 0,
      };
    });
  }, [yearlyCashflow]);

  const maxIncomeValue = Math.max(
    ...incomeSeries.map((i) => Math.abs(i.value)),
    0,
  );

  const yearlyTotals = useMemo(() => {
    return {
      income: toNumber(yearlySummary?.total_income),
      expense: toNumber(yearlySummary?.total_expense),
      profit: toNumber(yearlySummary?.profit),
      totalDue: toNumber(yearlySummary?.total_due),
      currency: yearlySummary?.currency ?? "BAM",
    };
  }, [yearlySummary]);

  const topCustomers = useMemo(() => {
    const map = new Map<string, number>();

    for (const inv of outgoingForYear?.items ?? []) {
      const name = inv.buyer_name || "Nepoznat kupac";
      const amount = toNumber(inv.total_amount);
      map.set(name, (map.get(name) ?? 0) + amount);
    }

    return Array.from(map.entries())
      .map(([name, total]) => ({ name, total }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 10);
  }, [outgoingForYear]);

  const topSuppliers = useMemo(() => {
    const map = new Map<string, number>();

    for (const inv of inputForYear?.items ?? []) {
      const name = inv.supplier_name || "Nepoznat dobavljač";
      const amount = toNumber(inv.total_amount);
      map.set(name, (map.get(name) ?? 0) + amount);
    }

    return Array.from(map.entries())
      .map(([name, total]) => ({ name, total }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 10);
  }, [inputForYear]);

  const expenseBySupplier = useMemo(() => {
    const map = new Map<string, number>();

    for (const inv of inputForYear?.items ?? []) {
      const name = inv.supplier_name || "Ostalo";
      const amount = toNumber(inv.total_amount);
      map.set(name, (map.get(name) ?? 0) + amount);
    }

    return Array.from(map.entries())
      .map(([name, total]) => ({ name, total }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 12);
  }, [inputForYear]);

  const maxExpenseSupplier = Math.max(
    ...expenseBySupplier.map((c) => Math.abs(c.total)),
    0,
  );

  const csvUrl = buildReportsCashflowYearCsvUrl(apiBaseUrl, year);

  const isLoadingAny =
    isLoadingCurrent ||
    isLoadingMonthlySummary ||
    isLoadingYearlyCashflow ||
    isLoadingYearlySummary;

  const isErrorAny =
    isErrorCurrent ||
    isErrorMonthlySummary ||
    isErrorYearlyCashflow ||
    isErrorYearlySummary;

  const errorText =
    errorCurrent?.message ||
    errorMonthlySummary?.message ||
    errorYearlyCashflow?.message ||
    errorYearlySummary?.message ||
    "Nepoznata greška pri učitavanju izvještaja.";

  const tenantCode = currentMonthly?.tenant_code ?? "t-demo";

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 px-5 py-6 text-white sm:px-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-300">
                Evident · poslovna analitika
              </p>

              <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
                Izvještaji
              </h1>

              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
                Mjesečni i godišnji pregled prihoda, rashoda, poreza, faktura i
                napredne analitike za tenant{" "}
                <span className="font-mono text-white">{tenantCode}</span>.
              </p>

              <div className="mt-4 flex flex-wrap items-center gap-2 text-[11px] text-slate-300">
                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1">
                  Period:{" "}
                  <span className="font-semibold text-white">{monthTitle}</span>
                </span>

                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1">
                  Godina:{" "}
                  <span className="font-semibold text-white">{year}</span>
                </span>

                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1">
                  API: <span className="font-mono text-white">{apiBaseUrl}</span>
                </span>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => navigate("/dashboard")}
                className="rounded-2xl border border-white/10 bg-white/10 px-4 py-2 text-xs font-semibold text-white backdrop-blur transition hover:bg-white/15"
              >
                Kontrolna tabla
              </button>

              <button
                type="button"
                onClick={() => navigate("/invoices")}
                className="rounded-2xl border border-white/10 bg-white/10 px-4 py-2 text-xs font-semibold text-white backdrop-blur transition hover:bg-white/15"
              >
                Izlazne fakture
              </button>

              <a
                href={csvUrl}
                className="rounded-2xl bg-emerald-500 px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-emerald-400"
              >
                CSV cashflow
              </a>
            </div>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <HeroMetric
              label="Godišnji prihodi"
              value={`${formatAmount(yearlyTotals.income)} KM`}
              hint="Ukupan prihod za izabranu godinu."
              tone="income"
            />

            <HeroMetric
              label="Godišnji rashodi"
              value={`${formatAmount(yearlyTotals.expense)} KM`}
              hint="Ukupni rashodi za izabranu godinu."
              tone="expense"
            />

            <HeroMetric
              label="Godišnji profit"
              value={`${formatAmount(yearlyTotals.profit)} KM`}
              hint="Razlika prihoda i rashoda."
            />

            <HeroMetric
              label="Prema državi"
              value={`${formatAmount(yearlyTotals.totalDue)} KM`}
              hint="TAX/SAM godišnji preview."
            />
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              Kontrole izvještaja
            </p>
            <h2 className="mt-1 text-lg font-semibold text-slate-900">
              Period i vrsta pregleda
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Odaberi godinu, mjesec i tip izvještaja. Backend logika i endpointi
              ostaju nepromijenjeni.
            </p>
          </div>

          <div className="grid gap-3 md:grid-cols-[140px_180px_auto]">
            <label className="space-y-1 text-xs font-medium text-slate-600">
              Godina
              <input
                type="number"
                value={year}
                min={2000}
                max={2100}
                onChange={(e) => setYear(clampYear(Number(e.target.value)))}
                className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
              />
            </label>

            <label className="space-y-1 text-xs font-medium text-slate-600">
              Mjesec
              <select
                value={month}
                onChange={(e) => setMonth(Number(e.target.value))}
                className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
              >
                {Array.from({ length: 12 }, (_, idx) => idx + 1).map((m) => (
                  <option key={m} value={m}>
                    {getMonthName(m)}
                  </option>
                ))}
              </select>
            </label>

            <div className="space-y-1">
              <p className="text-xs font-medium text-slate-600">Prikaz</p>
              <div className="grid grid-cols-3 gap-1 rounded-2xl border border-slate-200 bg-slate-50 p-1">
                {[
                  ["monthly", "Mjesečni"],
                  ["yearly", "Godišnji"],
                  ["analytics", "Analitika"],
                ].map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setActiveTab(key as ReportsTab)}
                    className={
                      "rounded-xl px-3 py-2 text-xs font-semibold transition " +
                      (activeTab === key
                        ? "bg-white text-slate-950 shadow-sm"
                        : "text-slate-500 hover:text-slate-800")
                    }
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {isLoadingAny && (
        <section className="rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <p className="text-sm font-medium text-slate-700">
            Učitavam izvještaje za izabrani period...
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Prikupljam podatke iz dashboard, reports, invoices i input invoices
            modula.
          </p>
        </section>
      )}

      {isErrorAny && (
        <section className="rounded-3xl border border-red-200 bg-red-50 p-5 text-sm text-red-700 shadow-sm">
          Greška pri učitavanju izvještaja: {errorText}
        </section>
      )}

      {!isLoadingAny && !isErrorAny && activeTab === "monthly" && (
        <div className="space-y-5">
          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Mjesečni izvještaj
                </p>
                <h2 className="mt-1 text-lg font-semibold text-slate-900">
                  {monthTitle}
                </h2>
                <p className="mt-1 text-xs text-slate-500">
                  Prihodi, rashodi, profit, očekivani porez i pregled mjesečnih
                  faktura.
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => navigate("/dashboard")}
                  className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                >
                  Kontrolna tabla
                </button>

                <button
                  type="button"
                  disabled
                  className="cursor-not-allowed rounded-2xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-400"
                  title="PDF export za mjesečni izvještaj još nije implementiran u backendu."
                >
                  PDF uskoro
                </button>
              </div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-4">
              <MiniMetric
                label="Prihodi"
                value={`${formatAmount(monthlyIncome)} KM`}
                hint="Cashflow prihod za mjesec."
                tone="income"
              />

              <MiniMetric
                label="Rashodi"
                value={`${formatAmount(monthlyExpense)} KM`}
                hint="Cashflow rashod za mjesec."
                tone="expense"
              />

              <MiniMetric
                label="Profit"
                value={`${formatAmount(monthlyProfit)} KM`}
                hint="Mjesečni neto rezultat."
                tone={monthlyProfit >= 0 ? "income" : "expense"}
              />

              <MiniMetric
                label="Očekivani porez"
                value={`${formatAmount(monthlyExpectedTax)} KM`}
                hint="Prema TAX/SAM modulu."
                tone="dark"
              />
            </div>
          </section>

          <section className="grid gap-5 lg:grid-cols-2">
            <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
              <div className="flex items-center justify-between gap-3 border-b border-slate-100 bg-slate-50 px-5 py-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                    Izlazne fakture
                  </p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">
                    Fakturisani prihodi za mjesec
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => navigate("/invoices")}
                  className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold text-slate-700 hover:bg-slate-100"
                >
                  Otvori
                </button>
              </div>

              {isLoadingOutgoingForMonth ? (
                <p className="p-5 text-xs text-slate-500">
                  Učitavam izlazne fakture...
                </p>
              ) : monthlyInvoices.length === 0 ? (
                <p className="p-5 text-xs text-slate-500">
                  Nema izlaznih faktura u ovom mjesecu.
                </p>
              ) : (
                <div className="max-h-[420px] overflow-auto">
                  <table className="min-w-full text-left text-[11px] text-slate-700">
                    <thead className="sticky top-0 bg-white text-slate-500 shadow-sm">
                      <tr>
                        <th className="px-4 py-3 font-semibold">Datum</th>
                        <th className="px-4 py-3 font-semibold">Broj</th>
                        <th className="px-4 py-3 font-semibold">Kupac</th>
                        <th className="px-4 py-3 text-right font-semibold">
                          Iznos
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {monthlyInvoices.slice(0, 25).map((inv: any) => (
                        <tr key={inv.id} className="hover:bg-slate-50">
                          <td className="whitespace-nowrap px-4 py-3">
                            {inv.issue_date ?? "-"}
                          </td>
                          <td className="whitespace-nowrap px-4 py-3 font-mono text-slate-900">
                            {inv.number ?? "-"}
                          </td>
                          <td className="px-4 py-3">{inv.buyer_name ?? "-"}</td>
                          <td className="whitespace-nowrap px-4 py-3 text-right font-semibold text-slate-900">
                            {inv.total_amount != null
                              ? `${formatAmount(toNumber(inv.total_amount))} KM`
                              : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  {monthlyInvoices.length > 25 && (
                    <p className="border-t border-slate-100 px-4 py-3 text-[10px] text-slate-500">
                      Prikazano prvih 25 od ukupno {monthlyInvoices.length}.
                    </p>
                  )}
                </div>
              )}
            </div>

            <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
              <div className="flex items-center justify-between gap-3 border-b border-slate-100 bg-slate-50 px-5 py-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                    Ulazni računi
                  </p>
                  <p className="mt-1 text-sm font-semibold text-slate-900">
                    Rashodi i dobavljači za mjesec
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => navigate("/input-invoices")}
                  className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-[11px] font-semibold text-slate-700 hover:bg-slate-100"
                >
                  Otvori
                </button>
              </div>

              {isLoadingInputForMonth ? (
                <p className="p-5 text-xs text-slate-500">
                  Učitavam ulazne račune...
                </p>
              ) : monthlyInputInvoices.length === 0 ? (
                <p className="p-5 text-xs text-slate-500">
                  Nema ulaznih računa u ovom mjesecu.
                </p>
              ) : (
                <div className="max-h-[420px] overflow-auto">
                  <table className="min-w-full text-left text-[11px] text-slate-700">
                    <thead className="sticky top-0 bg-white text-slate-500 shadow-sm">
                      <tr>
                        <th className="px-4 py-3 font-semibold">Datum</th>
                        <th className="px-4 py-3 font-semibold">Broj</th>
                        <th className="px-4 py-3 font-semibold">Dobavljač</th>
                        <th className="px-4 py-3 text-right font-semibold">
                          Iznos
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {monthlyInputInvoices.slice(0, 25).map((inv: any) => (
                        <tr key={inv.id} className="hover:bg-slate-50">
                          <td className="whitespace-nowrap px-4 py-3">
                            {inv.issue_date ?? "-"}
                          </td>
                          <td className="whitespace-nowrap px-4 py-3 font-mono text-slate-900">
                            {inv.number ?? "-"}
                          </td>
                          <td className="px-4 py-3">
                            {inv.supplier_name ?? "-"}
                          </td>
                          <td className="whitespace-nowrap px-4 py-3 text-right font-semibold text-slate-900">
                            {inv.total_amount != null
                              ? `${formatAmount(toNumber(inv.total_amount))} KM`
                              : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  {monthlyInputInvoices.length > 25 && (
                    <p className="border-t border-slate-100 px-4 py-3 text-[10px] text-slate-500">
                      Prikazano prvih 25 od ukupno{" "}
                      {monthlyInputInvoices.length}.
                    </p>
                  )}
                </div>
              )}
            </div>
          </section>
        </div>
      )}

      {!isLoadingAny && !isErrorAny && activeTab === "yearly" && (
        <div className="space-y-5">
          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                  Godišnji izvještaj
                </p>
                <h2 className="mt-1 text-lg font-semibold text-slate-900">
                  {year}
                </h2>
                <p className="mt-1 text-xs text-slate-500">
                  Zbirni godišnji pregled prihoda, rashoda, profita i obaveza
                  prema državi.
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                <a
                  href={csvUrl}
                  className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                >
                  Preuzmi CSV
                </a>

                <button
                  type="button"
                  disabled
                  className="cursor-not-allowed rounded-2xl border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-400"
                  title="PDF export godišnjeg izvještaja još nije implementiran u backendu."
                >
                  PDF uskoro
                </button>
              </div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-4">
              <MiniMetric
                label="Ukupni prihodi"
                value={`${formatAmount(yearlyTotals.income)} KM`}
                tone="income"
              />

              <MiniMetric
                label="Ukupni rashodi"
                value={`${formatAmount(yearlyTotals.expense)} KM`}
                tone="expense"
              />

              <MiniMetric
                label="Profit"
                value={`${formatAmount(yearlyTotals.profit)} KM`}
                tone={yearlyTotals.profit >= 0 ? "income" : "expense"}
              />

              <MiniMetric
                label="Ukupno prema državi"
                value={`${formatAmount(yearlyTotals.totalDue)} KM`}
                hint="Prema TAX/SAM modulu."
                tone="dark"
              />
            </div>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                Prihodi po mjesecima
              </p>
              <h2 className="text-lg font-semibold text-slate-900">
                Cashflow trend
              </h2>
              <p className="text-xs text-slate-500">
                Trend prihoda po mjesecima na osnovu godišnjeg cashflow
                izvještaja.
              </p>
            </div>

            {isLoadingYearlyCashflow ? (
              <p className="mt-5 text-xs text-slate-500">
                Učitavam godišnji cashflow...
              </p>
            ) : yearlyCashflow?.items?.length ? (
              <div className="mt-5 flex h-56 items-end gap-3 overflow-x-auto rounded-2xl border border-slate-100 bg-slate-50 px-4 py-5">
                {maxIncomeValue === 0 ? (
                  <p className="text-xs text-slate-500">
                    Nema dovoljno podataka za graf.
                  </p>
                ) : (
                  incomeSeries.map((item) => {
                    const heightPercent =
                      (Math.abs(item.value) / maxIncomeValue) * 100;

                    return (
                      <div
                        key={item.month}
                        className="flex h-full min-w-[34px] flex-col items-center justify-end gap-2"
                        title={`${item.label}: ${formatAmount(item.value)} KM`}
                      >
                        <div className="flex h-full w-full flex-col justify-end">
                          <div
                            className="mx-auto w-5 rounded-t-xl bg-emerald-500 shadow-sm"
                            style={{
                              height: `${Math.max(8, heightPercent)}%`,
                            }}
                          />
                        </div>
                        <span className="text-[10px] text-slate-600">
                          {item.label}
                        </span>
                      </div>
                    );
                  })
                )}
              </div>
            ) : (
              <p className="mt-5 text-xs text-slate-500">
                Nema cashflow podataka za ovu godinu.
              </p>
            )}
          </section>
        </div>
      )}

      {!isLoadingAny && !isErrorAny && activeTab === "analytics" && (
        <div className="space-y-5">
          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              Napredna analitika
            </p>
            <h2 className="mt-1 text-lg font-semibold text-slate-900">
              Premium pregled poslovanja
            </h2>
            <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-500">
              Top kupci, top dobavljači i troškovi po dobavljačima za izabranu
              godinu. Kategorije troškova trenutno se aproksimiraju preko
              dobavljača, dok kasnije možemo dodati prave kategorije na ulaznim
              računima.
            </p>
          </section>

          <section className="grid gap-5 lg:grid-cols-2">
            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                Top kupci ({year})
              </p>

              {topCustomers.length === 0 ? (
                <p className="mt-4 text-xs text-slate-500">
                  Nema dovoljno izlaznih faktura za analitiku.
                </p>
              ) : (
                <ul className="mt-4 space-y-2 text-xs text-slate-700">
                  {topCustomers.map((c, idx) => (
                    <li
                      key={c.name}
                      className="flex items-center justify-between gap-3 rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2"
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        <span className="w-7 shrink-0 text-[11px] font-semibold text-slate-400">
                          #{idx + 1}
                        </span>
                        <span className="truncate font-medium text-slate-800">
                          {c.name}
                        </span>
                      </div>

                      <span className="shrink-0 font-semibold text-slate-950">
                        {formatAmount(c.total)} KM
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                Top dobavljači ({year})
              </p>

              {topSuppliers.length === 0 ? (
                <p className="mt-4 text-xs text-slate-500">
                  Nema dovoljno ulaznih računa za analitiku.
                </p>
              ) : (
                <ul className="mt-4 space-y-2 text-xs text-slate-700">
                  {topSuppliers.map((s, idx) => (
                    <li
                      key={s.name}
                      className="flex items-center justify-between gap-3 rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2"
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        <span className="w-7 shrink-0 text-[11px] font-semibold text-slate-400">
                          #{idx + 1}
                        </span>
                        <span className="truncate font-medium text-slate-800">
                          {s.name}
                        </span>
                      </div>

                      <span className="shrink-0 font-semibold text-slate-950">
                        {formatAmount(s.total)} KM
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                Troškovi po dobavljačima
              </p>
              <h2 className="text-lg font-semibold text-slate-900">
                Struktura rashoda za {year}
              </h2>
              <p className="text-xs text-slate-500">
                Vizuelni pregled najvećih rashodovnih dobavljača.
              </p>
            </div>

            <div className="mt-5 flex h-56 items-end gap-4 overflow-x-auto rounded-2xl border border-slate-100 bg-slate-50 px-4 py-5">
              {expenseBySupplier.length === 0 || maxExpenseSupplier === 0 ? (
                <p className="text-xs text-slate-500">
                  Nema dovoljno podataka za prikaz troškova po dobavljačima.
                </p>
              ) : (
                expenseBySupplier.map((cat) => {
                  const heightPercent =
                    (Math.abs(cat.total) / maxExpenseSupplier) * 100;

                  return (
                    <div
                      key={cat.name}
                      className="flex h-full min-w-[72px] flex-col items-center justify-end gap-2"
                      title={`${cat.name}: ${formatAmount(cat.total)} KM`}
                    >
                      <div className="flex h-full w-full flex-col justify-end">
                        <div
                          className="mx-auto w-8 rounded-t-xl bg-rose-500 shadow-sm"
                          style={{ height: `${Math.max(8, heightPercent)}%` }}
                        />
                      </div>

                      <span className="line-clamp-2 text-center text-[10px] text-slate-600">
                        {cat.name}
                      </span>
                    </div>
                  );
                })
              )}
            </div>

            <div className="mt-5 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => navigate("/input-invoices")}
                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
              >
                Otvori Ulazne fakture
              </button>

              <button
                type="button"
                onClick={() => navigate("/invoices")}
                className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
              >
                Otvori Izlazne fakture
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}