// /home/miso/dev/sp-app/sp-app/frontend/src/pages/DashboardPage.tsx
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { apiClient } from "../services/apiClient";
import { fetchInvoicesList } from "../services/invoicesApi";
import { fetchInputInvoicesList } from "../services/inputInvoicesApi";
import { getTaxProfileSettings } from "../services/settingsApi";
import type { TaxProfileSettingsRead } from "../types/settings";

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

function computePreviousYearMonth(
  year: number,
  month: number,
): { year: number; month: number } {
  if (month === 1) {
    return { year: year - 1, month: 12 };
  }
  return { year, month: month - 1 };
}

function getShortMonthLabel(month: number): string {
  const d = new Date(2025, month - 1, 1);
  return d.toLocaleDateString("sr-Latn-BA", { month: "short" });
}

function buildAiComment(
  current: DashboardMonthlyResponse | undefined,
  previous: DashboardMonthlyResponse | undefined,
): string | null {
  if (!current) {
    return null;
  }

  const curIncome = toNumber(current.cash?.income_total);
  const curExpense = toNumber(current.cash?.expense_total);
  const curNet = toNumber(current.cash?.net_cashflow);

  if (!previous) {
    if (curIncome === 0 && curExpense === 0) {
      return "Nema još dovoljno prometa za analizu ovog mjeseca. Kako se gomilaju prihodi i troškovi, ovdje ćeš dobijati kratak sažetak kretanja.";
    }
    if (curNet >= 0) {
      return `Ovaj mjesec si u plusu ${formatAmount(
        curNet,
      )} KM. Prati da li se ovaj trend zadrži i u narednim mjesecima.`;
    }
    return `Ovaj mjesec si u minusu ${formatAmount(
      Math.abs(curNet),
    )} KM. Provjeri najveće troškove i razmisli šta možeš optimizovati.`;
  }

  const prevIncome = toNumber(previous.cash?.income_total);
  const prevExpense = toNumber(previous.cash?.expense_total);
  const prevNet = toNumber(previous.cash?.net_cashflow);

  const incomeDelta = curIncome - prevIncome;
  const expenseDelta = curExpense - prevExpense;
  const netDelta = curNet - prevNet;

  const incomePct =
    prevIncome !== 0 ? (incomeDelta / Math.abs(prevIncome)) * 100 : null;
  const expensePct =
    prevExpense !== 0 ? (expenseDelta / Math.abs(prevExpense)) * 100 : null;

  const incomePart =
    incomePct === null
      ? null
      : incomePct > 5
        ? `Prihodi su veći za oko ${incomePct.toFixed(
            1,
          )}% u odnosu na prošli mjesec.`
        : incomePct < -5
          ? `Prihodi su manji za oko ${Math.abs(incomePct).toFixed(
              1,
            )}% u odnosu na prošli mjesec.`
          : "Prihodi su na sličnom nivou kao prošli mjesec.";

  const expensePart =
    expensePct === null
      ? null
      : expensePct > 5
        ? `Troškovi su veći za oko ${expensePct.toFixed(
            1,
          )}% u odnosu na prošli mjesec.`
        : expensePct < -5
          ? `Troškovi su manji za oko ${Math.abs(expensePct).toFixed(
              1,
            )}% u odnosu na prošli mjesec.`
          : "Troškovi su na sličnom nivou kao prošli mjesec.";

  let netPart: string;
  if (curNet > 0 && netDelta >= 0) {
    netPart = `Neto rezultat je pozitivan (${formatAmount(
      curNet,
    )} KM) i bolji je nego prošli mjesec.`;
  } else if (curNet > 0 && netDelta < 0) {
    netPart = `Neto rezultat je i dalje pozitivan (${formatAmount(
      curNet,
    )} KM), ali je slabiji nego prošli mjesec.`;
  } else if (curNet <= 0 && netDelta >= 0) {
    netPart = `Ovaj mjesec si blizu nule ili u manjim gubicima (${formatAmount(
      curNet,
    )} KM), ali je bolje nego prošli mjesec.`;
  } else {
    netPart = `Neto rezultat je negativan (${formatAmount(
      curNet,
    )} KM) i lošiji je nego prošli mjesec.`;
  }

  const parts = [incomePart, expensePart, netPart].filter(
    (p): p is string => p !== null,
  );
  if (parts.length === 0) {
    return null;
  }

  return parts.join(" ");
}

export default function DashboardPage() {
  const navigate = useNavigate();

  // TAX PROFILE (Settings) — za “Doprinosi (mjesečno – plan)”
  const taxProfileQuery = useQuery<TaxProfileSettingsRead, Error>({
    queryKey: ["settings", "tax"],
    queryFn: getTaxProfileSettings,
    staleTime: 60_000,
  });

  const manualPension = taxProfileQuery.data?.monthly_pension ?? null;
  const manualHealth = taxProfileQuery.data?.monthly_health ?? null;
  const manualUnemployment = taxProfileQuery.data?.monthly_unemployment ?? null;

  const hasAnyManualContrib =
    manualPension != null || manualHealth != null || manualUnemployment != null;

  const contributionsPlan =
    hasAnyManualContrib
      ? toNumber(manualPension) + toNumber(manualHealth) + toNumber(manualUnemployment)
      : null;

  // 1) Trenutni mjesečni dashboard
  const {
    data,
    isLoading,
    isError,
    error,
  } = useQuery<DashboardMonthlyResponse, Error>({
    queryKey: ["dashboard", "monthly", "current"],
    queryFn: async () => {
      const res = await apiClient.get<DashboardMonthlyResponse>(
        "/dashboard/monthly/current",
      );
      return res.data;
    },
  });

  // 2) Prethodni mjesec – za AI komentar
  const { data: previousMonthlyData } = useQuery<
    DashboardMonthlyResponse,
    Error
  >({
    queryKey: ["dashboard", "monthly", "previous", data?.year, data?.month],
    enabled: !!data,
    queryFn: async () => {
      if (!data) {
        throw new Error("Missing current month data");
      }
      const { year, month } = computePreviousYearMonth(data.year, data.month);
      const res = await apiClient.get<DashboardMonthlyResponse>(
        `/dashboard/monthly/${year}/${month}`,
      );
      return res.data;
    },
    staleTime: 60_000,
  });

  // 3) Lista izlaznih faktura (za zadnjih 5 + overdue + top kupce)
  const { data: invoicesListData } = useQuery({
    queryKey: ["dashboard", "invoices", "recent"],
    queryFn: () => fetchInvoicesList(),
    staleTime: 60_000,
  });

  // 4) Lista ulaznih faktura za TEKUĆI mjesec (za kategorije + top dobavljače + zadnjih 5)
  const { data: inputInvoicesListData } = useQuery({
    queryKey: [
      "dashboard",
      "input-invoices",
      "current-month",
      data?.year,
      data?.month,
    ],
    enabled: !!data,
    queryFn: async () => {
      if (!data) {
        throw new Error("Missing dashboard data");
      }
      return fetchInputInvoicesList({
        year: data.year,
        month: data.month,
        limit: 200,
        offset: 0,
      });
    },
    staleTime: 60_000,
  });

  // 5) Yearly cash by month – za graf prihoda po mjesecima
  const { data: yearlyCashByMonth } = useQuery<(DashboardMonthlyResponse | null)[]>(
    {
      queryKey: ["dashboard", "cash", "yearly-by-month", data?.year],
      enabled: !!data,
      queryFn: async () => {
        if (!data) {
          throw new Error("Missing dashboard data");
        }
        const year = data.year;
        const months = Array.from({ length: 12 }, (_, idx) => idx + 1);
        const results = await Promise.all(
          months.map((m) =>
            apiClient
              .get<DashboardMonthlyResponse>(`/dashboard/monthly/${year}/${m}`)
              .then((res) => res.data)
              .catch(() => null),
          ),
        );
        return results;
      },
      staleTime: 60_000,
    },
  );

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

  const inputInvoicesCount = inputInvoicesListData?.items?.length ?? 0;
  const inputInvoicesTotal =
    inputInvoicesListData?.items?.reduce((acc: number, inv: any) => {
      const amount = inv?.total_amount ?? 0;
      return acc + (Number.isFinite(amount) ? amount : 0);
    }, 0) ?? 0;

  const netClass =
    cashNet > 0
      ? "text-emerald-600"
      : cashNet < 0
        ? "text-rose-600"
        : "text-slate-700";

  // Zadnjih 5 izlaznih i ulaznih faktura
  const lastOutgoingInvoices = invoicesListData?.items.slice(0, 5) ?? [];
  const lastInputInvoices = inputInvoicesListData?.items.slice(0, 5) ?? [];

  // Neplaćene fakture starije od 30 dana
  const overdueUnpaidCount =
    invoicesListData?.items.filter((inv: any) => {
      if (!inv.due_date) return false;
      if (inv.is_paid) return false;
      const due = new Date(inv.due_date);
      if (Number.isNaN(due.getTime())) return false;
      const today = new Date();
      const diffDays = (today.getTime() - due.getTime()) / (1000 * 60 * 60 * 24);
      return diffDays > 30;
    }).length ?? 0;

  // Graf prihoda po mjesecima (stubičasti)
  const incomeSeries =
    yearlyCashByMonth?.map((m, idx) => {
      const month = idx + 1;
      const income = m ? toNumber(m.cash?.income_total) : 0;
      return {
        month,
        label: getShortMonthLabel(month),
        value: income,
      };
    }) ?? [];

  const maxIncomeValue = Math.max(...incomeSeries.map((i) => Math.abs(i.value)), 0);

  // Graf rashoda po dobavljačima (privremeno “kategorije”)
  const expenseBySupplierMap = new Map<string, number>();
  if (inputInvoicesListData) {
    for (const inv of inputInvoicesListData.items) {
      const name = inv.supplier_name || "Ostalo";
      const amount = inv.total_amount ?? 0;
      expenseBySupplierMap.set(name, (expenseBySupplierMap.get(name) ?? 0) + amount);
    }
  }

  const expenseSuppliers = Array.from(expenseBySupplierMap.entries())
    .map(([name, total]) => ({ name, total }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 6);

  const maxExpenseSupplier = Math.max(
    ...expenseSuppliers.map((c) => Math.abs(c.total)),
    0,
  );

  // Top kupci (po ukupnom prometu)
  const topCustomers = (() => {
    const map = new Map<string, number>();
    if (invoicesListData) {
      for (const inv of invoicesListData.items) {
        const name = inv.buyer_name || "Nepoznat kupac";
        const amount = inv.total_amount ?? 0;
        map.set(name, (map.get(name) ?? 0) + amount);
      }
    }
    return Array.from(map.entries())
      .map(([name, total]) => ({ name, total }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 5);
  })();

  // Top dobavljači (po ukupnom prometu u tekućem mjesecu)
  const topSuppliers = (() => {
    const map = new Map<string, number>();
    if (inputInvoicesListData) {
      for (const inv of inputInvoicesListData.items) {
        const name = inv.supplier_name || "Nepoznat dobavljač";
        const amount = inv.total_amount ?? 0;
        map.set(name, (map.get(name) ?? 0) + amount);
      }
    }
    return Array.from(map.entries())
      .map(([name, total]) => ({ name, total }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 5);
  })();

  // Poruke asistenta (bez TAX/SAM “dev” koncepta u UI)
  const messages: { type: "warning" | "info"; text: string }[] = [];

  if (cashNet < 0) {
    messages.push({
      type: "warning",
      text: "Neto kretanje gotovine za trenutni mjesec je negativno – rashodi su veći od prihoda.",
    });
  }

  if (overdueUnpaidCount > 0) {
    messages.push({
      type: "warning",
      text: `Imaš ${overdueUnpaidCount} neplaćenih izlaznih faktura sa rokom dospijeća starijim od 30 dana.`,
    });
  }

  const aiComment = buildAiComment(data, previousMonthlyData);

  // Podaci za mini graf kase (3 stubića: prihodi, rashodi, neto)
  const cashChartItems = [
    {
      key: "Prihodi",
      value: cashIncome,
      colorClass: "bg-emerald-500",
    },
    {
      key: "Rashodi",
      value: cashExpense,
      colorClass: "bg-rose-500",
    },
    {
      key: "Neto",
      value: cashNet,
      colorClass: cashNet >= 0 ? "bg-sky-500" : "bg-slate-700",
    },
  ];

  const maxCashAbs = Math.max(...cashChartItems.map((i) => Math.abs(i.value)), 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900 tracking-tight">
            Kontrolna tabla – mjesečni pregled
          </h2>
        </div>

        {/* QUICK ACTIONS */}
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => navigate("/export/inspection")}
            className="inline-flex items-center justify-center rounded-md bg-rose-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-rose-700 focus:outline-none focus:ring-2 focus:ring-rose-500/40"
            title="Kreiraj paket dokumenata za inspekciju"
          >
            Izvoz za inspekciju
          </button>
        </div>
      </div>

      {isLoading && (
        <p className="text-sm text-slate-600">
          Učitavam mjesečne podatke za kontrolnu tablu...
        </p>
      )}

      {isError && (
        <p className="text-sm text-red-600">
          Greška pri učitavanju kontrolne table: {error.message}
        </p>
      )}

      {/* Sumarni pregled tekućeg mjeseca */}
      {!isLoading && !isError && data && (
        <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4">
          <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide mb-2">
            Sumarni pregled za tekući mjesec
          </p>

          <div className="grid gap-4 md:grid-cols-4 text-xs text-slate-700">
            <div>
              <p className="text-[11px] text-slate-500">Ukupni prihodi</p>
              <p className="text-sm font-semibold text-emerald-600">
                {formatAmount(cashIncome)} KM
              </p>
            </div>

            <div>
              <p className="text-[11px] text-slate-500">Ukupni rashodi</p>
              <p className="text-sm font-semibold text-rose-600">
                {formatAmount(cashExpense)} KM
              </p>
            </div>

            <div>
              <p className="text-[11px] text-slate-500">
                Rezultat (profit / gubitak)
              </p>
              <p className={`text-sm font-semibold ${netClass}`}>
                {formatAmount(cashNet)} KM
              </p>
            </div>

            <div>
              <p className="text-[11px] text-slate-500">
                Doprinosi (mjesečno – plan)
              </p>

              {contributionsPlan != null ? (
                <>
                  <p className="text-sm font-semibold text-slate-900">
                    {formatAmount(contributionsPlan)} KM
                  </p>
                  <p className="text-[10px] text-slate-500">
                    Prema unosu u Postavkama (Poreski profil).
                  </p>
                </>
              ) : (
                <>
                  <p className="text-sm font-semibold text-slate-900">—</p>
                  <div className="mt-1 rounded-md border border-rose-200 bg-rose-50 px-2 py-1.5">
                    <p className="text-[11px] font-medium text-rose-700">
                      Nije podešeno.
                    </p>
                    <p className="text-[11px] text-rose-700/90">
                      U Postavkama izaberi entitet/režim i unesi potrebne podatke
                      o načinu poslovanja (mjesečne doprinose).
                    </p>
                    <button
                      type="button"
                      onClick={() => navigate("/settings")}
                      className="mt-2 inline-flex items-center justify-center rounded-md bg-rose-600 px-2.5 py-1.5 text-[11px] font-semibold text-white hover:bg-rose-700"
                    >
                      Otvori Postavke
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Asistent – status mjeseca (spojeno: upozorenja + komentar) */}
      {!isLoading && !isError && data && (
        <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 space-y-3">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
                Asistent – status mjeseca
              </p>
              <p className="text-xs text-slate-500 mt-1">
                {monthLabel || `${data.year}-${data.month}`}
              </p>
            </div>
          </div>

          {messages.length > 0 && (
            <ul className="space-y-2">
              {messages.map((m, idx) => (
                <li
                  key={idx}
                  className="flex items-start gap-2 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2"
                >
                  <span
                    className={
                      "mt-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-bold " +
                      (m.type === "warning"
                        ? "bg-amber-500 text-white"
                        : "bg-slate-400 text-white")
                    }
                    aria-hidden="true"
                  >
                    {m.type === "warning" ? "!" : "i"}
                  </span>
                  <span className="text-[12px] text-slate-800">{m.text}</span>
                </li>
              ))}
            </ul>
          )}

          <div className="pt-1">
            <p className="text-sm text-slate-700">
              {aiComment ??
                "Nema dovoljno podataka za detaljniji komentar. Kako se gomilaju mjeseci i promet, ovdje ćeš imati kratak sažetak kretanja prihoda, troškova i neto rezultata."}
            </p>
          </div>
        </div>
      )}

      {/* Mini graf – kretanje gotovine za trenutni mjesec */}
      {!isLoading && !isError && data && (
        <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
                Kretanje gotovine – {monthLabel || `${data.year}-${data.month}`}
              </p>
            </div>
          </div>

          <div className="mt-2 h-40 flex items-end justify-around gap-6 border border-slate-100 rounded-lg bg-slate-50 px-6 py-4">
            {maxCashAbs === 0 ? (
              <p className="text-[11px] text-slate-500">
                Nema dovoljno podataka za prikaz grafa.
              </p>
            ) : (
              cashChartItems.map((item) => {
                const heightPercent =
                  maxCashAbs > 0
                    ? Math.max(10, (Math.abs(item.value) / maxCashAbs) * 100)
                    : 0;

                return (
                  <div
                    key={item.key}
                    className="flex flex-col items-center justify-end gap-1 h-full"
                    title={`${item.key}: ${formatAmount(item.value)} KM`}
                  >
                    <div className="flex flex-col justify-end w-full h-full">
                      <div
                        className={
                          "w-8 mx-auto rounded-t-md shadow-sm transition-all " +
                          item.colorClass
                        }
                        style={{
                          height: maxCashAbs > 0 ? `${heightPercent}%` : "0%",
                        }}
                      />
                    </div>
                    <span className="text-[11px] font-medium text-slate-700">
                      {item.key}
                    </span>
                    <span className="text-[11px] font-semibold text-slate-800">
                      {formatAmount(item.value)} KM
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* Glavne kartice (Kasa, Izlazne, Ulazne) */}
      {data && (
        <div className="grid gap-4 md:grid-cols-3">
          {/* Kasa kartica */}
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 flex flex-col gap-2">
            <p className="text-xs font-medium text-slate-500">
              Kasa – {monthLabel || `${data.year}-${data.month}`}
            </p>
            <p className={`text-2xl font-semibold ${netClass}`}>
              {formatAmount(cashNet)} KM
            </p>
            <p className="text-xs text-slate-500">
              Prihodi:{" "}
              <span className="font-medium text-emerald-600">
                {formatAmount(cashIncome)} KM
              </span>{" "}
              • Rashodi:{" "}
              <span className="font-medium text-rose-600">
                {formatAmount(cashExpense)} KM
              </span>
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
                {formatAmount(invoicesTotal)} KM
              </span>
            </p>
            <button
              type="button"
              onClick={() => navigate("/invoices")}
              className="mt-2 inline-flex items-center justify-center rounded-md bg-slate-900 px-3 py-2 text-[12px] font-semibold text-white hover:bg-slate-800"
            >
              Otvori izlazne fakture
            </button>
          </div>

          {/* Ulazne fakture kartica */}
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 flex flex-col gap-2">
            <p className="text-xs font-medium text-slate-500">
              Ulazne fakture – {monthLabel || `${data.year}-${data.month}`}
            </p>
            <p className="text-2xl font-semibold text-slate-900">
              {inputInvoicesCount}
            </p>
            <p className="text-xs text-slate-500">
              Ukupan iznos:{" "}
              <span className="font-semibold">
                {formatAmount(inputInvoicesTotal)} KM
              </span>
            </p>
            <button
              type="button"
              onClick={() => navigate("/input-invoices")}
              className="mt-2 inline-flex items-center justify-center rounded-md bg-slate-900 px-3 py-2 text-[12px] font-semibold text-white hover:bg-slate-800"
            >
              Otvori ulazne fakture
            </button>
          </div>
        </div>
      )}

      {/* Grafovi – prihodi po mjesecima + rashodi po dobavljačima */}
      {!isLoading && !isError && data && (
        <div className="grid gap-4 md:grid-cols-2">
          {/* Graf prihoda po mjesecima */}
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 space-y-3">
            <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
              Prihodi po mjesecima – {data.year}
            </p>

            <div className="mt-2 h-44 flex items-end gap-2 border border-slate-100 rounded-lg bg-slate-50 px-4 py-4 overflow-x-auto">
              {incomeSeries.length === 0 || maxIncomeValue === 0 ? (
                <p className="text-[11px] text-slate-500">
                  Nema dovoljno podataka za prikaz ovog grafa.
                </p>
              ) : (
                incomeSeries.map((item) => {
                  const heightPercent =
                    (Math.abs(item.value) / maxIncomeValue) * 100;
                  const isActiveMonth = item.month === data.month;

                  return (
                    <div
                      key={item.month}
                      className="flex flex-col items-center justify-end gap-1 h-full min-w-[26px]"
                      title={`${item.label}: ${formatAmount(item.value)} KM`}
                    >
                      <span
                        className={
                          "text-[11px] font-semibold " +
                          (isActiveMonth ? "text-slate-800" : "text-slate-400")
                        }
                      >
                        {isActiveMonth ? `${formatAmount(item.value)} KM` : ""}
                      </span>

                      <div className="flex flex-col justify-end w-full h-full">
                        <div
                          className={
                            "mx-auto rounded-t-md shadow-sm " +
                            (isActiveMonth
                              ? "bg-emerald-600 w-4"
                              : "bg-emerald-400 w-3")
                          }
                          style={{
                            height: `${Math.max(8, heightPercent)}%`,
                          }}
                        />
                      </div>

                      <span
                        className={
                          "text-[10px] " +
                          (isActiveMonth ? "text-slate-700" : "text-slate-500")
                        }
                      >
                        {item.label}
                      </span>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Graf rashoda po dobavljačima */}
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 space-y-3">
            <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
              Rashodi po dobavljačima – {monthLabel}
            </p>

            <div className="mt-2 h-44 flex items-end gap-4 border border-slate-100 rounded-lg bg-slate-50 px-4 py-4 overflow-x-auto">
              {expenseSuppliers.length === 0 || maxExpenseSupplier === 0 ? (
                <p className="text-[11px] text-slate-500">
                  Nema dovoljno podataka za prikaz ovog grafa.
                </p>
              ) : (
                expenseSuppliers.map((cat) => {
                  const heightPercent =
                    (Math.abs(cat.total) / maxExpenseSupplier) * 100;
                  return (
                    <div
                      key={cat.name}
                      className="flex flex-col items-center justify-end gap-1 h-full min-w-[56px]"
                      title={`${cat.name}: ${formatAmount(cat.total)} KM`}
                    >
                      <span className="text-[11px] font-semibold text-slate-800">
                        {formatAmount(cat.total)} KM
                      </span>

                      <div className="flex flex-col justify-end w-full h-full">
                        <div
                          className="w-8 mx-auto rounded-t-md shadow-sm bg-rose-500"
                          style={{
                            height: `${Math.max(10, heightPercent)}%`,
                          }}
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
          </div>
        </div>
      )}

      {/* Zadnjih 5 faktura – izlazne i ulazne */}
      {!isLoading && !isError && (
        <div className="grid gap-4 md:grid-cols-2">
          {/* Zadnjih 5 izlaznih faktura */}
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
                  Zadnjih 5 izlaznih faktura
                </p>
              </div>
              <button
                type="button"
                onClick={() => navigate("/invoices")}
                className="inline-flex items-center justify-center rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-[11px] font-medium text-slate-700 hover:bg-slate-100"
              >
                Sve fakture
              </button>
            </div>

            {lastOutgoingInvoices.length === 0 ? (
              <p className="text-[11px] text-slate-500">
                Nema izlaznih faktura za prikaz. Kreiraj prvu fakturu u modulu izlaznih faktura.
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
                    {lastOutgoingInvoices.map((inv: any) => (
                      <tr
                        key={inv.id}
                        className="border-b border-slate-50 last:border-0"
                      >
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
                            ? `${formatAmount(inv.total_amount)} KM`
                            : "-"}
                          {!inv.is_paid && (
                            <span className="ml-1 inline-flex rounded-full bg-rose-50 px-2 py-[1px] text-[10px] font-medium text-rose-700">
                              neplaćena
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Zadnjih 5 ulaznih računa */}
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
                  Zadnjih 5 ulaznih računa
                </p>
              </div>
              <button
                type="button"
                onClick={() => navigate("/input-invoices")}
                className="inline-flex items-center justify-center rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-[11px] font-medium text-slate-700 hover:bg-slate-100"
              >
                Sve ulazne fakture
              </button>
            </div>

            {lastInputInvoices.length === 0 ? (
              <p className="text-[11px] text-slate-500">
                Nema ulaznih računa za prikaz. Dodaj prvi račun u modulu ulaznih faktura.
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
                    {lastInputInvoices.map((inv: any) => (
                      <tr
                        key={inv.id}
                        className="border-b border-slate-50 last:border-0"
                      >
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
                            ? `${formatAmount(inv.total_amount)} KM`
                            : "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Top kupci / Top dobavljači */}
      {!isLoading && !isError && (
        <div className="grid gap-4 md:grid-cols-2">
          {/* Top kupci */}
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
                Top kupci
              </p>
            </div>
            {topCustomers.length === 0 ? (
              <p className="text-[11px] text-slate-500">
                Nema dovoljno izlaznih faktura za prikaz top kupaca.
              </p>
            ) : (
              <ul className="space-y-1 text-xs text-slate-700">
                {topCustomers.map((c, idx) => (
                  <li key={c.name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-5 text-[11px] text-slate-500">
                        #{idx + 1}
                      </span>
                      <span>{c.name}</span>
                    </div>
                    <span className="font-semibold">
                      {formatAmount(c.total)} KM
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Top dobavljači */}
          <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
                Top dobavljači (tekući mjesec)
              </p>
            </div>
            {topSuppliers.length === 0 ? (
              <p className="text-[11px] text-slate-500">
                Nema dovoljno ulaznih računa za prikaz top dobavljača.
              </p>
            ) : (
              <ul className="space-y-1 text-xs text-slate-700">
                {topSuppliers.map((s, idx) => (
                  <li key={s.name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="w-5 text-[11px] text-slate-500">
                        #{idx + 1}
                      </span>
                      <span>{s.name}</span>
                    </div>
                    <span className="font-semibold">
                      {formatAmount(s.total)} KM
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {/* Ako nema podataka */}
      {!isLoading && !isError && !data && (
        <p className="text-sm text-slate-500">
          Nema dostupnih podataka za kontrolnu tablu.
        </p>
      )}
    </div>
  );
}
