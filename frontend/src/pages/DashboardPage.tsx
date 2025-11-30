import { useQuery } from "@tanstack/react-query";
import { apiClient, getApiBaseUrl } from "../services/apiClient";

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
  if (typeof value === "number") return value;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

export default function DashboardPage() {
  const apiUrl = getApiBaseUrl();

  const { data, isLoading, isError, error } = useQuery<
    DashboardMonthlyResponse,
    Error
  >({
    queryKey: ["dashboard", "monthly", "current"],
    queryFn: async () => {
      const res = await apiClient.get<DashboardMonthlyResponse>(
        "/dashboard/monthly/current"
      );
      return res.data;
    },
  });

  const monthLabel = (() => {
    if (!data) return "";
    const d = new Date(data.year, data.month - 1, 1);
    if (Number.isNaN(d.getTime())) return `${data.year}-${data.month}`;
    return d.toLocaleDateString("sr-Latn-BA", {
      month: "long",
      year: "numeric",
    });
  })();

  const cashIncome = toNumber(data?.cash?.income_total);
  const cashExpense = toNumber(data?.cash?.expense_total);
  const cashNet = toNumber(data?.cash?.net_cashflow);

  const invoicesCount = data?.invoices?.invoices_count ?? 0;
  const invoicesTotal = toNumber(data?.invoices?.total_amount);

  const taxTotal = toNumber(data?.tax?.total_due);
  const hasTaxResult = data?.tax?.has_result ?? false;
  const isTaxFinal = data?.tax?.is_final ?? false;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-slate-800">
          Dashboard – mjesečni pregled
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          API: <span className="font-mono">{apiUrl}</span>
        </p>
        {data && (
          <p className="text-xs text-slate-500 mt-1">
            Period:{" "}
            <span className="font-semibold text-slate-700">
              {monthLabel} (tenant{" "}
              <span className="font-mono">{data.tenant_code}</span>)
            </span>
          </p>
        )}
      </div>

      {isLoading && (
        <p className="text-sm text-slate-600">
          Učitavam mjesečni dashboard...
        </p>
      )}

      {isError && (
        <p className="text-sm text-red-600">
          Greška pri učitavanju dashboarda: {error.message}
        </p>
      )}

      {data && (
        <div className="grid gap-4 md:grid-cols-3">
          {/* Kasa kartica */}
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4">
            <p className="text-xs font-medium text-slate-500 mb-1">
              Kasa – {monthLabel || `${data.year}-${data.month}`}
            </p>
            <p className="text-2xl font-semibold text-slate-900">
              {cashNet.toFixed(2)} KM
            </p>
            <p className="text-xs text-slate-500 mt-2">
              Prihodi:{" "}
              <span className="font-medium text-emerald-600">
                {cashIncome.toFixed(2)} KM
              </span>{" "}
              • Rashodi:{" "}
              <span className="font-medium text-rose-600">
                {cashExpense.toFixed(2)} KM
              </span>
            </p>
          </div>

          {/* Izlazne fakture kartica */}
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4">
            <p className="text-xs font-medium text-slate-500 mb-1">
              Izlazne fakture – {monthLabel || `${data.year}-${data.month}`}
            </p>
            <p className="text-2xl font-semibold text-slate-900">
              {invoicesCount}
            </p>
            <p className="text-xs text-slate-500 mt-2">
              Ukupan iznos:{" "}
              <span className="font-semibold">
                {invoicesTotal.toFixed(2)} KM
              </span>
            </p>
          </div>

          {/* Porezi / SAM kartica */}
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4">
            <p className="text-xs font-medium text-slate-500 mb-1">
              Porezi / SAM – {monthLabel || `${data.year}-${data.month}`}
            </p>
            <p className="text-sm text-slate-700">
              Mjesečna obaveza:{" "}
              <span className="font-semibold">
                {taxTotal.toFixed(2)} KM
              </span>
            </p>
            <p className="text-xs text-slate-500 mt-2">
              Status obračuna:{" "}
              {hasTaxResult ? (
                <span
                  className={
                    "inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold " +
                    (isTaxFinal
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-amber-50 text-amber-700")
                  }
                >
                  {isTaxFinal ? "FINALIZOVAN" : "NACRT"}
                </span>
              ) : (
                <span className="inline-flex rounded-full bg-slate-50 px-2 py-0.5 text-[11px] font-semibold text-slate-500">
                  NEMA OBRAČUNA
                </span>
              )}
            </p>
          </div>
        </div>
      )}

      {!isLoading && !isError && !data && (
        <p className="text-sm text-slate-500">
          Nema dostupnih podataka za dashboard.
        </p>
      )}
    </div>
  );
}
