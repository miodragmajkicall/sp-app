import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  fetchInvoicesList,
  markInvoicePaid,
} from "../services/invoicesApi";
import type { InvoiceRowItem } from "../types/invoice";

function formatDate(value?: string | null): string {
  if (!value) return "-";
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleDateString("sr-Latn-BA");
  } catch {
    return value;
  }
}

function formatAmount(value?: number | null): string {
  if (value == null) return "-";
  return `${value.toFixed(2)} KM`;
}

type StatusFilter = "ALL" | "PAID" | "UNPAID";

export default function InvoicesListPage() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("ALL");
  const [actionError, setActionError] = useState("");
  const [markingId, setMarkingId] = useState<number | null>(null);

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    isRefetching,
  } = useQuery({
    queryKey: ["invoices-list", { statusFilter }],
    queryFn: () =>
      fetchInvoicesList({
        unpaidOnly: statusFilter === "UNPAID",
      }),
  });

  const visibleItems: InvoiceRowItem[] = useMemo(() => {
    if (!data) return [];
    if (statusFilter === "ALL") return data.items;
    if (statusFilter === "UNPAID") {
      // već filtrirano na backu, ali za svaki slučaj filter i ovdje
      return data.items.filter((i) => !i.is_paid);
    }
    // PAID – filtriramo samo u UI-u
    return data.items.filter((i) => i.is_paid);
  }, [data, statusFilter]);

  async function handleMarkPaid(inv: InvoiceRowItem) {
    if (inv.is_paid) return;
    if (markingId !== null) return;

    setActionError("");
    setMarkingId(inv.id);
    try {
      await markInvoicePaid(inv.id);
      await refetch();
    } catch (err) {
      console.error(err);
      setActionError(
        "Greška pri označavanju fakture kao plaćene. Pokušaj ponovo.",
      );
    } finally {
      setMarkingId(null);
    }
  }

  return (
    <div className="space-y-4">
      {/* Header + refresh */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">
            Izlazne fakture
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Pregled svih izlaznih faktura za tenant{" "}
            <span className="font-mono">t-demo</span>.
          </p>
        </div>

        <button
          type="button"
          onClick={() => refetch()}
          className="inline-flex items-center rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-60"
          disabled={isLoading || isRefetching}
        >
          {isRefetching || isLoading ? "Osvježavam..." : "Osvježi listu"}
        </button>
      </div>

      {/* Filter statusa */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-slate-500">Filter status:</span>
        <button
          type="button"
          onClick={() => setStatusFilter("ALL")}
          className={[
            "rounded-full px-3 py-1 border text-xs",
            statusFilter === "ALL"
              ? "bg-slate-900 text-white border-slate-900"
              : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50",
          ].join(" ")}
        >
          Sve
        </button>
        <button
          type="button"
          onClick={() => setStatusFilter("UNPAID")}
          className={[
            "rounded-full px-3 py-1 border text-xs",
            statusFilter === "UNPAID"
              ? "bg-amber-500 text-white border-amber-500"
              : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50",
          ].join(" ")}
        >
          Neplaćene
        </button>
        <button
          type="button"
          onClick={() => setStatusFilter("PAID")}
          className={[
            "rounded-full px-3 py-1 border text-xs",
            statusFilter === "PAID"
              ? "bg-emerald-600 text-white border-emerald-600"
              : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50",
          ].join(" ")}
        >
          Plaćene
        </button>
      </div>

      {isLoading && (
        <p className="text-sm text-slate-600">Učitavam fakture...</p>
      )}

      {isError && (
        <p className="text-sm text-red-600">
          Greška pri učitavanju faktura:{" "}
          {error instanceof Error ? error.message : "Nepoznata greška"}
        </p>
      )}

      {actionError && (
        <p className="text-xs text-red-600">{actionError}</p>
      )}

      {!!data && data.total === 0 && (
        <p className="text-sm text-slate-500">
          Trenutno nema nijedne izlazne fakture.
        </p>
      )}

      {!!data && data.total > 0 && visibleItems.length === 0 && (
        <p className="text-sm text-slate-500">
          Nema faktura za odabrani filter.
        </p>
      )}

      {!!data && visibleItems.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Broj</th>
                <th className="px-3 py-2 text-left font-medium">Kupac</th>
                <th className="px-3 py-2 text-left font-medium whitespace-nowrap">
                  Datum izdavanja
                </th>
                <th className="px-3 py-2 text-left font-medium whitespace-nowrap">
                  Rok plaćanja
                </th>
                <th className="px-3 py-2 text-right font-medium">Iznos</th>
                <th className="px-3 py-2 text-center font-medium">
                  Plaćena
                </th>
                <th className="px-3 py-2 text-center font-medium">
                  Akcije
                </th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100 text-slate-700">
              {visibleItems.map((inv: InvoiceRowItem) => (
                <tr key={inv.id}>
                  <td className="px-3 py-2 font-mono text-xs">
                    <Link
                      to={`/invoices/${inv.id}`}
                      state={{ invoice: inv }}
                      className="text-slate-800 hover:text-slate-900 hover:underline underline-offset-2"
                    >
                      {inv.number ?? "-"}
                    </Link>
                  </td>
                  <td className="px-3 py-2">
                    {inv.buyer_name ?? (
                      <span className="text-slate-400">-</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs">
                    {formatDate(inv.issue_date)}
                  </td>
                  <td className="px-3 py-2 text-xs">
                    {formatDate(inv.due_date)}
                  </td>
                  <td className="px-3 py-2 text-right font-medium">
                    {formatAmount(inv.total_amount)}
                  </td>
                  <td className="px-3 py-2 text-center">
                    {inv.is_paid ? (
                      <span className="inline-flex rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                        DA
                      </span>
                    ) : (
                      <span className="inline-flex rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700">
                        NE
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <div className="flex items-center justify-center gap-2">
                      <Link
                        to={`/invoices/${inv.id}`}
                        state={{ invoice: inv }}
                        className="inline-flex items-center rounded-md border border-slate-300 bg-white px-2 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-50"
                      >
                        Detalji
                      </Link>

                      {!inv.is_paid && (
                        <button
                          type="button"
                          onClick={() => handleMarkPaid(inv)}
                          disabled={markingId === inv.id}
                          className="inline-flex items-center rounded-md bg-emerald-600 px-2 py-1 text-[11px] font-medium text-white hover:bg-emerald-700 disabled:opacity-60"
                        >
                          {markingId === inv.id
                            ? "Označavam..."
                            : "Označi kao plaćenu"}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
