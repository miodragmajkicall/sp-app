import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
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
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

export default function DashboardPage() {
  const apiUrl = getApiBaseUrl();
  const navigate = useNavigate();

  const { data, isLoading, isError, error } = useQuery<
    DashboardMonthlyResponse,
    Error
  >({
    queryKey: ["dashboard", "monthly", "current"],
    queryFn: async () => {
      const res = await apiClient.get<DashboardMonthlyResponse>(
        "/dashboard/monthly/current",
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

  const samTotal = toNumber(data?.sam?.total_due);
  const hasSamResult = data?.sam?.has_result ?? false;
  const isSamFinal = data?.sam?.is_final ?? false;

  const netClass =
    cashNet > 0
      ? "text-emerald-600"
      : cashNet < 0
      ? "text-rose-600"
      : "text-slate-700";

  // Brza upozorenja / info badge-ovi
  const alerts: { type: "warning" | "info"; text: string }[] = [];

  if (hasTaxResult && !isTaxFinal) {
    alerts.push({
      type: "warning",
      text: "Porezi za trenutni mjesec nisu finalizovani – otvori TAX ekran i izvrši finalizaciju.",
    });
  } else if (!hasTaxResult) {
    alerts.push({
      type: "info",
      text: "Nema obračuna poreza za trenutni mjesec – pokreni auto obračun u TAX modulu.",
    });
  }

  if (hasSamResult && !isSamFinal) {
    alerts.push({
      type: "warning",
      text: "SAM doprinosi za trenutni mjesec nisu finalizovani.",
    });
  } else if (!hasSamResult) {
    alerts.push({
      type: "info",
      text: "Nema SAM obračuna za trenutni mjesec – podaci će se pojaviti nakon obračuna u TAX / SAM modulu.",
    });
  }

  if (cashNet < 0) {
    alerts.push({
      type: "warning",
      text: "Neto kretanje gotovine za trenutni mjesec je NEGATIVNO – rashodi su veći od prihoda.",
    });
  }

  // Podaci za mini graf kase (3 stubića: prihodi, rashodi, neto)
  const cashChartItems = [
    {
      key: "Prihodi",
      value: cashIncome,
      colorClass: "bg-emerald-500",
      hint: "Ukupan priliv gotovine za mjesec",
    },
    {
      key: "Rashodi",
      value: cashExpense,
      colorClass: "bg-rose-500",
      hint: "Ukupan odliv gotovine za mjesec",
    },
    {
      key: "Neto",
      value: cashNet,
      colorClass:
        cashNet >= 0 ? "bg-sky-500" : "bg-slate-700", // neto može biti +/-
      hint: "Prihodi - rashodi za mjesec",
    },
  ];

  const maxCashAbs = Math.max(
    ...cashChartItems.map((i) => Math.abs(i.value)),
    0,
  );

  return (
    <div className="space-y-6">
      {/* Header */}
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

      {/* Upozorenja / brzi info badge-ovi */}
      {!isLoading && !isError && data && alerts.length > 0 && (
        <div className="rounded-xl border border-amber-100 bg-amber-50 px-4 py-3 space-y-2">
          <p className="text-[11px] font-semibold text-amber-800 uppercase tracking-wide">
            Brza upozorenja za trenutni mjesec
          </p>
          <ul className="space-y-1">
            {alerts.map((a, idx) => (
              <li
                key={idx}
                className="text-[11px] flex items-start gap-2 text-slate-800"
              >
                <span
                  className={
                    "mt-0.5 inline-flex h-4 w-4 items-center justify-center rounded-full text-[10px] " +
                    (a.type === "warning"
                      ? "bg-amber-500 text-white"
                      : "bg-slate-400 text-white")
                  }
                >
                  {a.type === "warning" ? "!" : "i"}
                </span>
                <span>{a.text}</span>
              </li>
            ))}
          </ul>
          <p className="text-[10px] text-amber-900/80 mt-1">
            Ova lista se generiše automatski na osnovu stanja kase i TAX / SAM
            modula za aktivni mjesec.
          </p>
        </div>
      )}

      {/* Mini graf – kretanje kase za trenutni mjesec */}
      {!isLoading && !isError && data && (
        <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
                Kretanje gotovine – {monthLabel || `${data.year}-${data.month}`}
              </p>
              <p className="text-xs text-slate-600">
                Poređenje ukupnih{" "}
                <span className="font-semibold">prihoda, rashoda i neta</span>{" "}
                za aktivni mjesec.
              </p>
            </div>
          </div>

          <div className="mt-2 h-40 flex items-end justify-around gap-4 border border-slate-100 rounded-lg bg-slate-50 px-4 py-3">
            {maxCashAbs === 0 ? (
              <p className="text-[11px] text-slate-500">
                Nema dovoljno podataka za prikaz grafa – provjeri da li postoje
                zapisi u kasi za ovaj mjesec.
              </p>
            ) : (
              cashChartItems.map((item) => {
                const heightPercent =
                  maxCashAbs > 0
                    ? Math.max(
                        5,
                        (Math.abs(item.value) / maxCashAbs) * 100,
                      )
                    : 0;

                return (
                  <div
                    key={item.key}
                    className="flex flex-col items-center justify-end gap-1"
                    title={`${item.key}: ${item.value.toFixed(
                      2,
                    )} KM – ${item.hint}`}
                  >
                    <div className="flex flex-col justify-end h-full">
                      <div
                        className={
                          "w-6 rounded-t-md transition-all " +
                          item.colorClass
                        }
                        style={{
                          height:
                            maxCashAbs > 0 ? `${heightPercent}%` : "0%",
                        }}
                      ></div>
                    </div>
                    <span className="text-[11px] font-medium text-slate-700">
                      {item.key}
                    </span>
                    <span className="text-[10px] text-slate-600">
                      {item.value.toFixed(2)} KM
                    </span>
                  </div>
                );
              })
            )}
          </div>

          <p className="text-[10px] text-slate-500 mt-1">
            Visina stubića je proporcionalna apsolutnoj vrijednosti (|iznos|).
            Neto može biti pozitivan ili negativan; boja označava vrstu
            vrijednosti.
          </p>
        </div>
      )}

      {/* Glavne kartice */}
      {data && (
        <div className="grid gap-4 md:grid-cols-4">
          {/* Kasa kartica */}
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 flex flex-col gap-2">
            <p className="text-xs font-medium text-slate-500">
              Kasa – {monthLabel || `${data.year}-${data.month}`}
            </p>
            <p className={`text-2xl font-semibold ${netClass}`}>
              {cashNet.toFixed(2)} KM
            </p>
            <p className="text-xs text-slate-500">
              Prihodi:{" "}
              <span className="font-medium text-emerald-600">
                {cashIncome.toFixed(2)} KM
              </span>{" "}
              • Rashodi:{" "}
              <span className="font-medium text-rose-600">
                {cashExpense.toFixed(2)} KM
              </span>
            </p>
            <p className="text-[11px] text-slate-400 pt-1">
              Pozitivan neto iznos znači višak u kasi za ovaj mjesec.
            </p>
          </div>

          {/* Izlazne fakture kartica */}
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 flex flex-col gap-2">
            <p className="text-xs font-medium text-slate-500">
              Izlazne fakture – {monthLabel || `${data.year}-${data.month}`}
            </p>
            <p className="text-2xl font-semibold text-slate-900">
              {invoicesCount}
            </p>
            <p className="text-xs text-slate-500">
              Ukupan iznos:{" "}
              <span className="font-semibold">
                {invoicesTotal.toFixed(2)} KM
              </span>
            </p>
            <button
              type="button"
              onClick={() => navigate("/invoices")}
              className="mt-2 inline-flex items-center justify-center rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-[11px] font-medium text-slate-700 hover:bg-slate-100"
            >
              Otvori izlazne fakture
            </button>
          </div>

          {/* Porezi kartica */}
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 flex flex-col gap-2">
            <p className="text-xs font-medium text-slate-500">
              Porezi – {monthLabel || `${data.year}-${data.month}`}
            </p>
            <p className="text-lg font-semibold text-slate-900">
              {taxTotal.toFixed(2)} KM
            </p>
            <p className="text-xs text-slate-500">
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
            <button
              type="button"
              onClick={() => navigate("/tax")}
              className="mt-2 inline-flex items-center justify-center rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-[11px] font-medium text-slate-700 hover:bg-slate-100"
            >
              Otvori Porezi / SAM
            </button>
          </div>

          {/* SAM kartica */}
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 flex flex-col gap-2">
            <p className="text-xs font-medium text-slate-500">
              SAM doprinosi – {monthLabel || `${data.year}-${data.month}`}
            </p>
            <p className="text-lg font-semibold text-slate-900">
              {samTotal.toFixed(2)} KM
            </p>
            <p className="text-xs text-slate-500">
              Status:{" "}
              {hasSamResult ? (
                <span
                  className={
                    "inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold " +
                    (isSamFinal
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-amber-50 text-amber-700")
                  }
                >
                  {isSamFinal ? "FINALIZOVAN" : "NACRT"}
                </span>
              ) : (
                <span className="inline-flex rounded-full bg-slate-50 px-2 py-0.5 text-[11px] font-semibold text-slate-500">
                  NEMA OBRAČUNA
                </span>
              )}
            </p>
            <p className="text-[11px] text-slate-400">
              Vrijednosti dolaze iz TAX / SAM modula za aktivni mjesec.
            </p>
          </div>
        </div>
      )}

      {/* Ako nema podataka */}
      {!isLoading && !isError && !data && (
        <p className="text-sm text-slate-500">
          Nema dostupnih podataka za dashboard.
        </p>
      )}
    </div>
  );
}
