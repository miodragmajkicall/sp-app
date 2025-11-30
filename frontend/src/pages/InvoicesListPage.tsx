import { useQuery } from "@tanstack/react-query";
import { fetchInvoicesList } from "../services/invoicesApi";
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

export default function InvoicesListPage() {
  const { data, isLoading, isError, error, refetch, isRefetching } =
    useQuery({
      queryKey: ["invoices-list"],
      queryFn: fetchInvoicesList,
    });

  return (
    <div className="space-y-4">
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

      {isLoading && <p className="text-sm text-slate-600">Učitavam fakture...</p>}

      {isError && (
        <p className="text-sm text-red-600">
          Greška pri učitavanju faktura: {error instanceof Error ? error.message : "Nepoznata greška"}
        </p>
      )}

      {!!data && data.total === 0 && (
        <p className="text-sm text-slate-500">
          Trenutno nema nijedne izlazne fakture.
        </p>
      )}

      {!!data && data.total > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Broj</th>
                <th className="px-3 py-2 text-left font-medium">Kupac</th>
                <th className="px-3 py-2 text-left font-medium whitespace-nowrap">Datum izdavanja</th>
                <th className="px-3 py-2 text-left font-medium whitespace-nowrap">Rok plaćanja</th>
                <th className="px-3 py-2 text-right font-medium">Iznos</th>
                <th className="px-3 py-2 text-center font-medium">Plaćena</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100 text-slate-700">
              {data.items.map((inv: InvoiceRowItem) => (
                <tr key={inv.id}>
                  <td className="px-3 py-2 font-mono text-xs">{inv.number ?? "-"}</td>
                  <td className="px-3 py-2">{inv.buyer_name ?? <span className="text-slate-400">-</span>}</td>
                  <td className="px-3 py-2 text-xs">{formatDate(inv.issue_date)}</td>
                  <td className="px-3 py-2 text-xs">{formatDate(inv.due_date)}</td>
                  <td className="px-3 py-2 text-right font-medium">{formatAmount(inv.total_amount)}</td>
                  <td className="px-3 py-2 text-center">
                    {inv.is_paid ? (
                      <span className="inline-flex rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">DA</span>
                    ) : (
                      <span className="inline-flex rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700">NE</span>
                    )}
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
