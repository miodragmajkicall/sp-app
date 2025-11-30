import { useQuery } from "@tanstack/react-query";
import { apiClient, getApiBaseUrl } from "../services/apiClient";

interface CashSummary {
  balance?: number;
  income?: number;
  expense?: number;
}

interface InvoicesSummary {
  total_count?: number;
  unpaid_count?: number;
}

interface TaxSummary {
  current_month_tax?: number;
  current_year_tax?: number;
}

interface DashboardData {
  cash_summary?: CashSummary;
  invoices_summary?: InvoicesSummary;
  tax_summary?: TaxSummary;
}

export default function DashboardPage() {
  const apiUrl = getApiBaseUrl();

  const { data, isLoading, isError, error } = useQuery<DashboardData, Error>({
    queryKey: ["dashboard"],
    queryFn: async () => {
      const res = await apiClient.get("/dashboard");
      return res.data;
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-slate-800">Dashboard</h2>
        <p className="text-xs text-slate-500 mt-1">
          API: <span className="font-mono">{apiUrl}</span>
        </p>
      </div>

      {isLoading && (
        <p className="text-sm text-slate-600">Učitavam dashboard podatke...</p>
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
            <p className="text-xs font-medium text-slate-500 mb-1">Kasa</p>
            <p className="text-2xl font-semibold text-slate-900">
              {(data.cash_summary?.balance ?? 0).toFixed(2)} KM
            </p>
            <p className="text-xs text-slate-500 mt-2">
              Prihodi:{" "}
              <span className="font-medium text-emerald-600">
                {(data.cash_summary?.income ?? 0).toFixed(2)} KM
              </span>{" "}
              • Rashodi:{" "}
              <span className="font-medium text-rose-600">
                {(data.cash_summary?.expense ?? 0).toFixed(2)} KM
              </span>
            </p>
          </div>

          {/* Fakture kartica */}
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4">
            <p className="text-xs font-medium text-slate-500 mb-1">
              Izlazne fakture
            </p>
            <p className="text-2xl font-semibold text-slate-900">
              {data.invoices_summary?.total_count ?? 0}
            </p>
            <p className="text-xs text-slate-500 mt-2">
              Neplaćene:{" "}
              <span className="font-medium text-amber-600">
                {data.invoices_summary?.unpaid_count ?? 0}
              </span>
            </p>
          </div>

          {/* Porezi / SAM kartica */}
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4">
            <p className="text-xs font-medium text-slate-500 mb-1">
              Porezi / SAM (trenutno)
            </p>
            <p className="text-sm text-slate-700">
              Mjesečni porez:{" "}
              <span className="font-semibold">
                {(data.tax_summary?.current_month_tax ?? 0).toFixed(2)} KM
              </span>
            </p>
            <p className="text-sm text-slate-700">
              Godišnji porez:{" "}
              <span className="font-semibold">
                {(data.tax_summary?.current_year_tax ?? 0).toFixed(2)} KM
              </span>
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
