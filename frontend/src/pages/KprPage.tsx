// /home/miso/dev/sp-app/sp-app/frontend/src/pages/KprPage.tsx
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchKprList, exportKprPdf } from "../services/kprApi";
import type { KprListResponse, KprRowItem } from "../types/kpr";

const CURRENT_YEAR = new Date().getFullYear();
const CURRENT_MONTH = new Date().getMonth() + 1;

type KindFilter = "ALL" | "INCOME" | "EXPENSE";

function formatDate(value?: string | null): string {
  if (!value) return "-";
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleDateString("sr-Latn-BA");
  } catch {
    return value ?? "-";
  }
}

function formatAmount(value?: number | null): string {
  if (value == null) return "-";
  return `${value.toFixed(2)} KM`;
}

function formatKind(kind: string): string {
  if (kind === "income") return "Prihod";
  if (kind === "expense") return "Rashod";
  return kind;
}

function formatCategory(category: string): string {
  switch (category) {
    case "invoice":
      return "Izlazna faktura";
    case "input_invoice":
      return "Ulazna faktura";
    case "cash":
      return "Novac / cash";
    default:
      return category || "-";
  }
}

export default function KprPage() {
  const [year, setYear] = useState<number | undefined>(CURRENT_YEAR);
  const [month, setMonth] = useState<number | undefined>(CURRENT_MONTH);
  const [kindFilter, setKindFilter] = useState<KindFilter>("ALL");

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    isRefetching,
  } = useQuery<KprListResponse, Error>({
    queryKey: ["kpr", { year, month }],
    queryFn: () =>
      fetchKprList({
        year,
        month,
      }),
  });

  const allItems: KprRowItem[] = data?.items ?? [];

  const filteredItems = useMemo(() => {
    if (kindFilter === "ALL") return allItems;
    if (kindFilter === "INCOME") {
      return allItems.filter((r) => r.kind === "income");
    }
    // EXPENSE
    return allItems.filter((r) => r.kind === "expense");
  }, [allItems, kindFilter]);

  const total = data?.total ?? 0;

  const totals = useMemo(() => {
    let income = 0;
    let expense = 0;
    for (const row of allItems) {
      if (row.kind === "income") {
        income += row.amount ?? 0;
      } else if (row.kind === "expense") {
        expense += row.amount ?? 0;
      }
    }
    return {
      income,
      expense,
      net: income - expense,
    };
  }, [allItems]);

  const handleExportPdf = async () => {
    if (!year || !month) {
      window.alert(
        "Za PDF export trenutno zahtijevamo odabranu godinu i mjesec.",
      );
      return;
    }
    try {
      await exportKprPdf(year, month);
    } catch (err) {
      console.error("Greška pri exportKprPdf:", err);
      const anyErr = err as any;
      const msg =
        anyErr?.response?.data?.detail ||
        anyErr?.message ||
        "Nepoznata greška pri exportu PDF-a.";
      window.alert(msg);
    }
  };

  return (
    <div className="space-y-6">
      {/* HEADER */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">
            Knjiga prihoda i rashoda (KPR)
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Pregled svih prihoda i rashoda za tenant{" "}
            <span className="font-mono">t-demo</span> prema izlaznim
            fakturama, ulaznim fakturama i cash unosima.
          </p>
          <p className="mt-0.5 text-[11px] text-slate-400">
            Ukupno stavki (prema filterima):{" "}
            <span className="font-semibold text-slate-600">
              {total}
            </span>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => refetch()}
            className="inline-flex items-center rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-60"
            disabled={isLoading || isRefetching}
          >
            {isLoading || isRefetching ? "Osvježavam..." : "Osvježi podatke"}
          </button>

          <button
            type="button"
            onClick={handleExportPdf}
            className="inline-flex items-center rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:bg-slate-800"
          >
            📄 Export KPR (PDF)
          </button>
        </div>
      </div>

      {/* FILTER BAR */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div className="flex flex-wrap items-end gap-3">
            {/* YEAR */}
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Godina
              </label>
              <select
                value={year ?? ""}
                onChange={(e) => {
                  const v = e.target.value;
                  setYear(v === "" ? undefined : Number(v));
                }}
                className="mt-1 w-24 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              >
                <option value="">Sve</option>
                <option value={CURRENT_YEAR}>{CURRENT_YEAR}</option>
                <option value={CURRENT_YEAR - 1}>{CURRENT_YEAR - 1}</option>
                <option value={CURRENT_YEAR - 2}>{CURRENT_YEAR - 2}</option>
              </select>
            </div>

            {/* MONTH */}
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Mjesec
              </label>
              <select
                value={month ?? ""}
                onChange={(e) => {
                  const v = e.target.value;
                  setMonth(v === "" ? undefined : Number(v));
                }}
                className="mt-1 w-28 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              >
                <option value="">Svi</option>
                <option value={1}>Januar</option>
                <option value={2}>Februar</option>
                <option value={3}>Mart</option>
                <option value={4}>April</option>
                <option value={5}>Maj</option>
                <option value={6}>Jun</option>
                <option value={7}>Jul</option>
                <option value={8}>Avgust</option>
                <option value={9}>Septembar</option>
                <option value={10}>Oktobar</option>
                <option value={11}>Novembar</option>
                <option value={12}>Decembar</option>
              </select>
            </div>

            {/* KIND FILTER */}
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Vrsta
              </label>
              <div className="mt-1 flex flex-wrap gap-1">
                <button
                  type="button"
                  onClick={() => setKindFilter("ALL")}
                  className={[
                    "rounded-full px-3 py-1 text-[11px] border",
                    kindFilter === "ALL"
                      ? "bg-slate-900 text-white border-slate-900"
                      : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50",
                  ].join(" ")}
                >
                  Sve
                </button>
                <button
                  type="button"
                  onClick={() => setKindFilter("INCOME")}
                  className={[
                    "rounded-full px-3 py-1 text-[11px] border",
                    kindFilter === "INCOME"
                      ? "bg-emerald-600 text-white border-emerald-600"
                      : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50",
                  ].join(" ")}
                >
                  Prihodi
                </button>
                <button
                  type="button"
                  onClick={() => setKindFilter("EXPENSE")}
                  className={[
                    "rounded-full px-3 py-1 text-[11px] border",
                    kindFilter === "EXPENSE"
                      ? "bg-amber-500 text-white border-amber-500"
                      : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50",
                  ].join(" ")}
                >
                  Rashodi
                </button>
              </div>
            </div>
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => {
                setYear(CURRENT_YEAR);
                setMonth(CURRENT_MONTH);
                setKindFilter("ALL");
              }}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
            >
              Reset filtera
            </button>
          </div>
        </div>
      </div>

      {/* SUMARNA TRAKA */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
          <div className="font-semibold text-[11px] uppercase tracking-wide">
            Ukupni prihodi
          </div>
          <div className="mt-1 text-sm font-semibold">
            {formatAmount(totals.income)}
          </div>
        </div>
        <div className="rounded-xl border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          <div className="font-semibold text-[11px] uppercase tracking-wide">
            Ukupni rashodi
          </div>
          <div className="mt-1 text-sm font-semibold">
            {formatAmount(totals.expense)}
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-800">
          <div className="font-semibold text-[11px] uppercase tracking-wide">
            Rezultat (prihodi - rashodi)
          </div>
          <div className="mt-1 text-sm font-semibold">
            {formatAmount(totals.net)}
          </div>
        </div>
      </div>

      {/* TABELA KPR */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-3 py-2 border-b border-slate-100 text-[11px] text-slate-500">
          <span>
            Ukupno stavki:{" "}
            <span className="font-mono font-semibold text-slate-700">
              {total}
            </span>{" "}
            • Prikazano:{" "}
            <span className="font-mono font-semibold text-slate-700">
              {filteredItems.length}
            </span>
          </span>
          <span className="hidden sm:inline">
            Lista se puni iz izlaznih/ulaznih faktura i cash unosa po principu
            blagajne.
          </span>
        </div>

        {isLoading && (
          <p className="px-3 py-3 text-sm text-slate-600">
            Učitavam KPR stavke...
          </p>
        )}

        {isError && (
          <p className="px-3 py-3 text-sm text-red-600">
            Greška pri učitavanju KPR podataka:{" "}
            {error?.message ?? "Nepoznata greška"}
          </p>
        )}

        {!isLoading && !isError && total === 0 && (
          <p className="px-3 py-3 text-sm text-slate-500">
            Trenutno nema stavki za zadane filtere.
          </p>
        )}

        {!isLoading && !isError && total > 0 && filteredItems.length === 0 && (
          <p className="px-3 py-3 text-sm text-slate-500">
            Nema stavki za odabrani filter vrste (prihod/rashod).
          </p>
        )}

        {!isLoading && !isError && filteredItems.length > 0 && (
          <div className="overflow-x-auto max-h-[520px] overflow-y-auto">
            <table className="min-w-full text-xs">
              <thead className="bg-slate-50 text-slate-500 sticky top-0 z-10">
                <tr>
                  <th className="px-3 py-2 text-left font-medium whitespace-nowrap">
                    Datum
                  </th>
                  <th className="px-3 py-2 text-left font-medium">
                    Vrsta
                  </th>
                  <th className="px-3 py-2 text-left font-medium">
                    Kategorija
                  </th>
                  <th className="px-3 py-2 text-left font-medium">
                    Kupac / Dobavljač
                  </th>
                  <th className="px-3 py-2 text-left font-medium">
                    Dok. broj
                  </th>
                  <th className="px-3 py-2 text-left font-medium">
                    Opis
                  </th>
                  <th className="px-3 py-2 text-right font-medium">
                    Iznos
                  </th>
                  <th className="px-3 py-2 text-center font-medium whitespace-nowrap">
                    Poreski priznat
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {filteredItems.map((row) => (
                  <tr key={`${row.source}-${row.source_id}-${row.date}`}>
                    <td className="px-3 py-1.5 whitespace-nowrap">
                      {formatDate(row.date)}
                    </td>
                    <td className="px-3 py-1.5 whitespace-nowrap">
                      <span
                        className={[
                          "inline-flex rounded-full px-2 py-0.5 text-[10px] font-semibold",
                          row.kind === "income"
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-amber-50 text-amber-700",
                        ].join(" ")}
                      >
                        {formatKind(row.kind)}
                      </span>
                    </td>
                    <td className="px-3 py-1.5 whitespace-nowrap text-[11px]">
                      {formatCategory(row.category)}
                    </td>
                    <td className="px-3 py-1.5 text-[11px]">
                      {row.counterparty ?? (
                        <span className="text-slate-400">-</span>
                      )}
                    </td>
                    <td className="px-3 py-1.5 text-[11px] font-mono">
                      {row.document_number ?? (
                        <span className="text-slate-400">-</span>
                      )}
                    </td>
                    <td className="px-3 py-1.5 text-[11px] max-w-[260px]">
                      {row.description ?? (
                        <span className="text-slate-400">-</span>
                      )}
                    </td>
                    <td className="px-3 py-1.5 text-right font-medium">
                      {formatAmount(row.amount)}
                    </td>
                    <td className="px-3 py-1.5 text-center">
                      {row.tax_deductible ? (
                        <span className="inline-flex rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                          DA
                        </span>
                      ) : (
                        <span className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500">
                          NE
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
    </div>
  );
}
