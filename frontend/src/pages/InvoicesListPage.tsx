// /home/miso/dev/sp-app/sp-app/frontend/src/pages/InvoicesListPage.tsx
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchInvoicesList,
  markInvoicePaid,
  exportInvoicesExcel,
  type InvoicesListParams,
} from "../services/invoicesApi";
import type { InvoiceListResponse, InvoiceRowItem } from "../types/invoice";

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

const CURRENT_YEAR = new Date().getFullYear();

export default function InvoicesListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Filteri i paginacija
  const [year, setYear] = useState<number | undefined>(CURRENT_YEAR);
  const [month, setMonth] = useState<number | undefined>(undefined);
  const [buyerQuery, setBuyerQuery] = useState("");
  const [unpaidOnly, setUnpaidOnly] = useState(false);

  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  // Derivirani parametri za query
  const queryParams: InvoicesListParams = useMemo(
    () => ({
      year,
      month,
      buyer_query: buyerQuery || undefined,
      unpaid_only: unpaidOnly || undefined,
      page,
      page_size: pageSize,
    }),
    [year, month, buyerQuery, unpaidOnly, page, pageSize],
  );

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery<InvoiceListResponse>({
    queryKey: ["invoices", "ui-list", queryParams],
    queryFn: () => fetchInvoicesList(queryParams),
    keepPreviousData: true,
  });

  const total = data?.total ?? 0;
  const items = data?.items ?? [];

  const totalPages = useMemo(() => {
    if (!total) return 1;
    return Math.max(1, Math.ceil(total / pageSize));
  }, [total, pageSize]);

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  const handleClearFilters = () => {
    setYear(CURRENT_YEAR);
    setMonth(undefined);
    setBuyerQuery("");
    setUnpaidOnly(false);
    setPage(1);
  };

  const handleMarkPaid = async (invoice: InvoiceRowItem) => {
    if (!window.confirm(`Označiti fakturu ${invoice.number ?? `#${invoice.id}`} kao plaćenu?`)) {
      return;
    }

    try {
      await markInvoicePaid(invoice.id);
      // Osvježimo listu i eventualne keširane detalje
      await refetch();
      queryClient.invalidateQueries({ queryKey: ["invoice-detail", invoice.id] });
    } catch (err) {
      console.error(err);
      alert("Greška pri označavanju fakture kao plaćene.");
    }
  };

  const handleExport = async () => {
    try {
      const blob = await exportInvoicesExcel(queryParams);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "invoices-export.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
      alert("Greška pri eksportu faktura.");
    }
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">
            Izlazne fakture
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Pregled, filtriranje, označavanje plaćenih faktura i export u Excel.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleExport}
            className="inline-flex items-center rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50"
          >
            Export (Excel)
          </button>

          <button
            type="button"
            onClick={() => navigate("/invoices/new")}
            className="btn-primary text-xs px-4 py-1.5"
          >
            + Nova faktura
          </button>
        </div>
      </div>

      {/* Filteri */}
      <section className="bg-white border border-slate-200 rounded-lg shadow-sm p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-slate-700">
            Filteri
          </h3>
          <div className="flex items-center gap-2 text-[11px] text-slate-500">
            {isFetching ? (
              <span>Osvježavam listu…</span>
            ) : (
              <span>
                Pronađeno:{" "}
                <span className="font-semibold text-slate-700">
                  {total}
                </span>{" "}
                faktura
              </span>
            )}
            <button
              type="button"
              onClick={handleClearFilters}
              className="underline underline-offset-2 hover:text-slate-700"
            >
              Reset filtera
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-[0.7fr,0.7fr,1.2fr,auto] gap-3 items-end">
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-700">
              Godina
            </label>
            <select
              value={year ?? ""}
              onChange={(e) =>
                setYear(
                  e.target.value === ""
                    ? undefined
                    : Number(e.target.value),
                )
              }
              className="input"
            >
              <option value="">Sve godine</option>
              {/* Možeš po potrebi proširiti listu godina */}
              <option value={CURRENT_YEAR}>{CURRENT_YEAR}</option>
              <option value={CURRENT_YEAR - 1}>{CURRENT_YEAR - 1}</option>
              <option value={CURRENT_YEAR - 2}>{CURRENT_YEAR - 2}</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-700">
              Mjesec
            </label>
            <select
              value={month ?? ""}
              onChange={(e) =>
                setMonth(
                  e.target.value === ""
                    ? undefined
                    : Number(e.target.value),
                )
              }
              className="input"
            >
              <option value="">Svi mjeseci</option>
              <option value="1">Januar</option>
              <option value="2">Februar</option>
              <option value="3">Mart</option>
              <option value="4">April</option>
              <option value="5">Maj</option>
              <option value="6">Juni</option>
              <option value="7">Juli</option>
              <option value="8">Avgust</option>
              <option value="9">Septembar</option>
              <option value="10">Oktobar</option>
              <option value="11">Novembar</option>
              <option value="12">Decembar</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-700">
              Kupac (pretraga po nazivu)
            </label>
            <input
              type="text"
              value={buyerQuery}
              onChange={(e) => {
                setBuyerQuery(e.target.value);
                setPage(1);
              }}
              className="input"
              placeholder="npr. 'Frizer', 'Kafic', 'SP Primjer'"
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              id="unpaid-only"
              type="checkbox"
              checked={unpaidOnly}
              onChange={(e) => {
                setUnpaidOnly(e.target.checked);
                setPage(1);
              }}
              className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900"
            />
            <label
              htmlFor="unpaid-only"
              className="text-xs font-medium text-slate-700"
            >
              Samo neplaćene
            </label>
          </div>
        </div>
      </section>

      {/* Tabela */}
      <section className="bg-white border border-slate-200 rounded-lg shadow-sm">
        {isLoading && (
          <div className="p-4 text-sm text-slate-600">
            Učitavam fakture...
          </div>
        )}

        {isError && (
          <div className="p-4 text-sm text-red-600">
            Greška pri učitavanju faktura:{" "}
            {error instanceof Error ? error.message : "Nepoznata greška"}
          </div>
        )}

        {!isLoading && !isError && items.length === 0 && (
          <div className="p-4 text-sm text-slate-500">
            Nema faktura za zadate filtere.
          </div>
        )}

        {!isLoading && !isError && items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">
                    Broj
                  </th>
                  <th className="px-3 py-2 text-left font-medium">
                    Kupac
                  </th>
                  <th className="px-3 py-2 text-left font-medium">
                    Datum
                  </th>
                  <th className="px-3 py-2 text-left font-medium">
                    Rok plaćanja
                  </th>
                  <th className="px-3 py-2 text-right font-medium">
                    Iznos (sa PDV)
                  </th>
                  <th className="px-3 py-2 text-center font-medium">
                    Status
                  </th>
                  <th className="px-3 py-2 text-right font-medium">
                    Akcije
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {items.map((invoice) => (
                  <tr key={invoice.id} className="hover:bg-slate-50">
                    <td className="px-3 py-2">
                      <Link
                        to={`/invoices/${invoice.id}`}
                        state={{ invoice }}
                        className="text-slate-800 hover:underline"
                      >
                        {invoice.number ?? `#${invoice.id}`}
                      </Link>
                    </td>
                    <td className="px-3 py-2">
                      {invoice.buyer_name || (
                        <span className="text-slate-400">
                          Nepoznat kupac
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      {formatDate(invoice.issue_date)}
                    </td>
                    <td className="px-3 py-2">
                      {formatDate(invoice.due_date)}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {formatAmount(invoice.total_amount)}
                    </td>
                    <td className="px-3 py-2 text-center">
                      {invoice.is_paid ? (
                        <span className="inline-flex rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                          PLAĆENA
                        </span>
                      ) : (
                        <span className="inline-flex rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700">
                          NIJE PLAĆENA
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Link
                          to={`/invoices/${invoice.id}`}
                          state={{ invoice }}
                          className="text-[11px] text-slate-700 underline underline-offset-2 hover:text-slate-900"
                        >
                          Detalji
                        </Link>
                        {!invoice.is_paid && (
                          <button
                            type="button"
                            onClick={() => handleMarkPaid(invoice)}
                            className="text-[11px] text-emerald-700 underline underline-offset-2 hover:text-emerald-900"
                          >
                            Označi plaćenu
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

        {/* Paginacija */}
        {!isLoading && !isError && totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-2 border-t border-slate-100 text-xs text-slate-600">
            <div>
              Stranica{" "}
              <span className="font-semibold">
                {page}
              </span>{" "}
              od{" "}
              <span className="font-semibold">
                {totalPages}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-2 py-1 rounded-md border border-slate-300 bg-white disabled:opacity-40 hover:bg-slate-50"
              >
                ← Nazad
              </button>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() =>
                  setPage((p) => Math.min(totalPages, p + 1))
                }
                className="px-2 py-1 rounded-md border border-slate-300 bg-white disabled:opacity-40 hover:bg-slate-50"
              >
                Naprijed →
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
