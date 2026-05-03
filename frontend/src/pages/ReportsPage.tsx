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

  const initialYear = clampYear(currentMonthly?.year ?? new Date().getFullYear());
  const initialMonth = Math.min(
    12,
    Math.max(1, currentMonthly?.month ?? new Date().getMonth() + 1),
  );

  const [activeTab, setActiveTab] = useState<"monthly" | "yearly" | "analytics">(
    "monthly",
  );
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

  const monthlyNetClass =
    monthlyProfit > 0
      ? "text-emerald-600"
      : monthlyProfit < 0
        ? "text-rose-600"
        : "text-slate-700";

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

  const maxIncomeValue = Math.max(...incomeSeries.map((i) => Math.abs(i.value)), 0);

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

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold text-slate-900 tracking-tight">
          Izvještaji
        </h2>

        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
          <span>
            API: <span className="font-mono">{apiBaseUrl}</span>
          </span>

          {currentMonthly && (
            <span className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1">
              <span className="text-[10px] uppercase tracking-wide text-slate-500">
                Tenant
              </span>
              <span className="font-semibold text-slate-700">
                <span className="font-mono">{currentMonthly.tenant_code}</span>
              </span>
            </span>
          )}
        </div>
      </div>

      <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div className="flex flex-wrap gap-3 items-end">
            <div>
              <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wide mb-1">
                Godina
              </label>
              <input
                type="number"
                value={year}
                min={2000}
                max={2100}
                onChange={(e) => setYear(clampYear(Number(e.target.value)))}
                className="w-32 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wide mb-1">
                Mjesec
              </label>
              <select
                value={month}
                onChange={(e) => setMonth(Number(e.target.value))}
                className="w-44 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800"
              >
                {Array.from({ length: 12 }, (_, idx) => idx + 1).map((m) => (
                  <option key={m} value={m}>
                    {getMonthName(m)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setActiveTab("monthly")}
              className={
                "rounded-md px-3 py-2 text-sm font-medium border " +
                (activeTab === "monthly"
                  ? "bg-slate-900 text-white border-slate-900"
                  : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50")
              }
            >
              Mjesečni
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("yearly")}
              className={
                "rounded-md px-3 py-2 text-sm font-medium border " +
                (activeTab === "yearly"
                  ? "bg-slate-900 text-white border-slate-900"
                  : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50")
              }
            >
              Godišnji
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("analytics")}
              className={
                "rounded-md px-3 py-2 text-sm font-medium border " +
                (activeTab === "analytics"
                  ? "bg-slate-900 text-white border-slate-900"
                  : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50")
              }
            >
              Analitika (Premium)
            </button>
          </div>
        </div>
      </div>

      {isLoadingAny && (
        <p className="text-sm text-slate-600">
          Učitavam izvještaje za izabrani period...
        </p>
      )}

      {isErrorAny && <p className="text-sm text-red-600">Greška: {errorText}</p>}

      {!isLoadingAny && !isErrorAny && activeTab === "monthly" && (
        <div className="space-y-4">
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div>
                <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
                  Mjesečni izvještaj
                </p>
                <p className="text-sm font-semibold text-slate-900">{monthTitle}</p>
                <p className="text-xs text-slate-500">
                  Prihodi, rashodi, profit i očekivani porez + lista faktura i
                  ulaznih računa.
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => navigate("/dashboard")}
                  className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100"
                >
                  Otvori Kontrolnu tablu
                </button>
                <button
                  type="button"
                  disabled
                  className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-400 cursor-not-allowed"
                  title="PDF export za mjesečni izvještaj još nije implementiran u backendu."
                >
                  PDF (uskoro)
                </button>
              </div>
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-4 text-xs text-slate-700">
              <div>
                <p className="text-[11px] text-slate-500">Prihodi</p>
                <p className="text-sm font-semibold text-emerald-600">
                  {formatAmount(monthlyIncome)} KM
                </p>
              </div>
              <div>
                <p className="text-[11px] text-slate-500">Rashodi</p>
                <p className="text-sm font-semibold text-rose-600">
                  {formatAmount(monthlyExpense)} KM
                </p>
              </div>
              <div>
                <p className="text-[11px] text-slate-500">Profit</p>
                <p className={`text-sm font-semibold ${monthlyNetClass}`}>
                  {formatAmount(monthlyProfit)} KM
                </p>
              </div>
              <div>
                <p className="text-[11px] text-slate-500">Očekivani porez</p>
                <p className="text-sm font-semibold text-slate-900">
                  {formatAmount(monthlyExpectedTax)} KM
                </p>
                <p className="text-[10px] text-slate-500">
                  Prema TAX modulu (mjesečni obračun).
                </p>
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
                  Lista izlaznih faktura (mjesec)
                </p>
                <button
                  type="button"
                  onClick={() => navigate("/invoices")}
                  className="rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-[11px] font-medium text-slate-700 hover:bg-slate-100"
                >
                  Sve izlazne fakture
                </button>
              </div>

              {isLoadingOutgoingForMonth ? (
                <p className="text-[11px] text-slate-500">
                  Učitavam izlazne fakture...
                </p>
              ) : monthlyInvoices.length === 0 ? (
                <p className="text-[11px] text-slate-500">
                  Nema izlaznih faktura u ovom mjesecu.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full text-left text-[11px] text-slate-700">
                    <thead>
                      <tr className="border-b border-slate-100 text-slate-500">
                        <th className="py-1 pr-3">Datum</th>
                        <th className="py-1 pr-3">Broj</th>
                        <th className="py-1 pr-3">Kupac</th>
                        <th className="py-1 text-right">Iznos</th>
                      </tr>
                    </thead>
                    <tbody>
                      {monthlyInvoices.slice(0, 25).map((inv: any) => (
                        <tr key={inv.id} className="border-b border-slate-50 last:border-0">
                          <td className="py-1 pr-3 text-slate-600">
                            {inv.issue_date ?? "-"}
                          </td>
                          <td className="py-1 pr-3 font-mono text-slate-800">
                            {inv.number ?? "-"}
                          </td>
                          <td className="py-1 pr-3 text-slate-700">
                            {inv.buyer_name ?? "-"}
                          </td>
                          <td className="py-1 text-right text-slate-800">
                            {inv.total_amount != null
                              ? `${formatAmount(toNumber(inv.total_amount))} KM`
                              : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {monthlyInvoices.length > 25 && (
                    <p className="mt-2 text-[10px] text-slate-500">
                      Prikazano prvih 25 od ukupno {monthlyInvoices.length}.
                    </p>
                  )}
                </div>
              )}
            </div>

            <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
                  Lista ulaznih računa (mjesec)
                </p>
                <button
                  type="button"
                  onClick={() => navigate("/input-invoices")}
                  className="rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-[11px] font-medium text-slate-700 hover:bg-slate-100"
                >
                  Sve ulazne fakture
                </button>
              </div>

              {isLoadingInputForMonth ? (
                <p className="text-[11px] text-slate-500">
                  Učitavam ulazne račune...
                </p>
              ) : monthlyInputInvoices.length === 0 ? (
                <p className="text-[11px] text-slate-500">
                  Nema ulaznih računa u ovom mjesecu.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full text-left text-[11px] text-slate-700">
                    <thead>
                      <tr className="border-b border-slate-100 text-slate-500">
                        <th className="py-1 pr-3">Datum</th>
                        <th className="py-1 pr-3">Broj</th>
                        <th className="py-1 pr-3">Dobavljač</th>
                        <th className="py-1 text-right">Iznos</th>
                      </tr>
                    </thead>
                    <tbody>
                      {monthlyInputInvoices.slice(0, 25).map((inv: any) => (
                        <tr key={inv.id} className="border-b border-slate-50 last:border-0">
                          <td className="py-1 pr-3 text-slate-600">
                            {inv.issue_date ?? "-"}
                          </td>
                          <td className="py-1 pr-3 font-mono text-slate-800">
                            {inv.number ?? "-"}
                          </td>
                          <td className="py-1 pr-3 text-slate-700">
                            {inv.supplier_name ?? "-"}
                          </td>
                          <td className="py-1 text-right text-slate-800">
                            {inv.total_amount != null
                              ? `${formatAmount(toNumber(inv.total_amount))} KM`
                              : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {monthlyInputInvoices.length > 25 && (
                    <p className="mt-2 text-[10px] text-slate-500">
                      Prikazano prvih 25 od ukupno {monthlyInputInvoices.length}.
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {!isLoadingAny && !isErrorAny && activeTab === "yearly" && (
        <div className="space-y-4">
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div>
                <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
                  Godišnji izvještaj
                </p>
                <p className="text-sm font-semibold text-slate-900">{year}</p>
                <p className="text-xs text-slate-500">
                  Zbir po mjesecima + grafikon prihoda. CSV export cashflow-a je aktivan.
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                <a
                  href={csvUrl}
                  className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100"
                >
                  Preuzmi CSV (cashflow)
                </a>
                <button
                  type="button"
                  disabled
                  className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-400 cursor-not-allowed"
                  title="PDF export godišnjeg izvještaja još nije implementiran u backendu."
                >
                  PDF (uskoro)
                </button>
              </div>
            </div>

            <div className="mt-4 grid gap-4 md:grid-cols-4 text-xs text-slate-700">
              <div>
                <p className="text-[11px] text-slate-500">Ukupni prihodi</p>
                <p className="text-sm font-semibold text-emerald-600">
                  {formatAmount(yearlyTotals.income)} KM
                </p>
              </div>
              <div>
                <p className="text-[11px] text-slate-500">Ukupni rashodi</p>
                <p className="text-sm font-semibold text-rose-600">
                  {formatAmount(yearlyTotals.expense)} KM
                </p>
              </div>
              <div>
                <p className="text-[11px] text-slate-500">Profit</p>
                <p
                  className={
                    "text-sm font-semibold " +
                    (yearlyTotals.profit > 0
                      ? "text-emerald-600"
                      : yearlyTotals.profit < 0
                        ? "text-rose-600"
                        : "text-slate-700")
                  }
                >
                  {formatAmount(yearlyTotals.profit)} KM
                </p>
              </div>
              <div>
                <p className="text-[11px] text-slate-500">Ukupno prema državi</p>
                <p className="text-sm font-semibold text-slate-900">
                  {formatAmount(yearlyTotals.totalDue)} KM
                </p>
                <p className="text-[10px] text-slate-500">
                  Prema TAX modulu (godišnji preview).
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 space-y-3">
            <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
              Grafikoni – prihodi po mjesecima
            </p>
            <p className="text-xs text-slate-500">
              Trend prihoda po mjesecima na osnovu `/reports/cashflow/{year}`.
            </p>

            {isLoadingYearlyCashflow ? (
              <p className="text-[11px] text-slate-500">
                Učitavam godišnji cashflow...
              </p>
            ) : yearlyCashflow?.items?.length ? (
              <div className="mt-2 h-44 flex items-end gap-2 border border-slate-100 rounded-lg bg-slate-50 px-4 py-4 overflow-x-auto">
                {maxIncomeValue === 0 ? (
                  <p className="text-[11px] text-slate-500">
                    Nema dovoljno podataka za graf.
                  </p>
                ) : (
                  incomeSeries.map((item) => {
                    const heightPercent = (Math.abs(item.value) / maxIncomeValue) * 100;
                    return (
                      <div
                        key={item.month}
                        className="flex flex-col items-center justify-end gap-1 h-full min-w-[18px]"
                        title={`${item.label}: ${formatAmount(item.value)} KM`}
                      >
                        <div className="flex flex-col justify-end w-full h-full">
                          <div
                            className="w-3 mx-auto rounded-t-md shadow-sm bg-emerald-500"
                            style={{ height: `${Math.max(6, heightPercent)}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-slate-600">{item.label}</span>
                      </div>
                    );
                  })
                )}
              </div>
            ) : (
              <p className="text-[11px] text-slate-500">
                Nema cashflow podataka za ovu godinu.
              </p>
            )}
          </div>
        </div>
      )}

      {!isLoadingAny && !isErrorAny && activeTab === "analytics" && (
        <div className="space-y-4">
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4">
            <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
              Napredna analitika (Premium)
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Ovdje su “Premium” blokovi (top kupci, top dobavljači, troškovi po
              kategorijama, trend prihoda). AI komentar i savjeti trenutno su “beta”
              koncept (kao na kontrolnoj tabli).
            </p>

            <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-600">
              Napomena: “Troškovi po kategorijama” trenutno koristimo dobavljača kao
              kategoriju. Kasnije možemo uvesti prave kategorije (gorivo, zakup,
              režije...) na ulaznim računima.
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 space-y-3">
              <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
                Top kupci ({year})
              </p>
              {topCustomers.length === 0 ? (
                <p className="text-[11px] text-slate-500">
                  Nema dovoljno izlaznih faktura za analitiku.
                </p>
              ) : (
                <ul className="space-y-1 text-xs text-slate-700">
                  {topCustomers.map((c, idx) => (
                    <li key={c.name} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="w-6 text-[11px] text-slate-500">#{idx + 1}</span>
                        <span>{c.name}</span>
                      </div>
                      <span className="font-semibold">{formatAmount(c.total)} KM</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 space-y-3">
              <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
                Top dobavljači ({year})
              </p>
              {topSuppliers.length === 0 ? (
                <p className="text-[11px] text-slate-500">
                  Nema dovoljno ulaznih računa za analitiku.
                </p>
              ) : (
                <ul className="space-y-1 text-xs text-slate-700">
                  {topSuppliers.map((s, idx) => (
                    <li key={s.name} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="w-6 text-[11px] text-slate-500">#{idx + 1}</span>
                        <span>{s.name}</span>
                      </div>
                      <span className="font-semibold">{formatAmount(s.total)} KM</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 space-y-3">
            <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
              Troškovi po kategorijama (dobavljači) – {year}
            </p>

            <div className="mt-2 h-44 flex items-end gap-4 border border-slate-100 rounded-lg bg-slate-50 px-4 py-4 overflow-x-auto">
              {expenseBySupplier.length === 0 || maxExpenseSupplier === 0 ? (
                <p className="text-[11px] text-slate-500">
                  Nema dovoljno podataka za prikaz troškova po dobavljačima.
                </p>
              ) : (
                expenseBySupplier.map((cat) => {
                  const heightPercent = (Math.abs(cat.total) / maxExpenseSupplier) * 100;
                  return (
                    <div
                      key={cat.name}
                      className="flex flex-col items-center justify-end gap-1 h-full min-w-[52px]"
                      title={`${cat.name}: ${formatAmount(cat.total)} KM`}
                    >
                      <div className="flex flex-col justify-end w-full h-full">
                        <div
                          className="w-7 mx-auto rounded-t-md shadow-sm bg-rose-500"
                          style={{ height: `${Math.max(8, heightPercent)}%` }}
                        />
                      </div>
                      <span className="text-[10px] text-center text-slate-600 line-clamp-2">
                        {cat.name}
                      </span>
                    </div>
                  );
                })
              )}
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => navigate("/input-invoices")}
                className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100"
              >
                Otvori Ulazne fakture
              </button>
              <button
                type="button"
                onClick={() => navigate("/invoices")}
                className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100"
              >
                Otvori Izlazne fakture
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}