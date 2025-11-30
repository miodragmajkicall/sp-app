import { useQuery } from "@tanstack/react-query";
import { fetchCashEntries } from "../services/cashApi";
import type { CashEntry } from "../types/cash";

function formatDate(value?: string): string {
  if (!value) return "-";
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleDateString("sr-Latn-BA");
  } catch {
    return value;
  }
}

function formatAmount(entry: CashEntry): string {
  if (entry.amount == null) return "-";
  const sign = entry.kind === "expense" ? "-" : "";
  return `${sign}${entry.amount.toFixed(2)} KM`;
}

function kindLabel(kind?: string) {
  if (kind === "income") return "PRIHOD";
  if (kind === "expense") return "RASHOD";
  return kind ?? "-";
}

export default function CashPage() {
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    isRefetching,
  } = useQuery<CashEntry[], Error>({
    queryKey: ["cash"],
    queryFn: fetchCashEntries,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">Kasa</h2>
          <p className="text-xs text-slate-500 mt-1">
            Lista svih unosa u kasi za tenant{" "}
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

      {isLoading && (
        <p className="text-sm text-slate-600">Učitavam zapise kase...</p>
      )}

      {isError && (
        <p className="text-sm text-red-600">
          Greška pri učitavanju kase: {error.message}
        </p>
      )}

      {!!data && data.length === 0 && !isLoading && !isError && (
        <p className="text-sm text-slate-500">
          Trenutno nema unosa u kasi.
        </p>
      )}

      {!!data && data.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left font-medium whitespace-nowrap">
                  Datum
                </th>
                <th className="px-3 py-2 text-left font-medium">Tip</th>
                <th className="px-3 py-2 text-left font-medium">
                  Opis
                </th>
                <th className="px-3 py-2 text-right font-medium">
                  Iznos
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {data.map((entry) => (
                <tr key={entry.id}>
                  <td className="px-3 py-2 text-xs">
                    {formatDate(entry.occurred_at)}
                  </td>
                  <td className="px-3 py-2 text-xs">
                    {kindLabel(entry.kind)}
                  </td>
                  <td className="px-3 py-2">
                    {entry.description ?? (
                      <span className="text-slate-400">-</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right font-medium">
                    {formatAmount(entry)}
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
