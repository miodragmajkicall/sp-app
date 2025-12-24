// /home/miso/dev/sp-app/sp-app/frontend/src/pages/PrometPage.tsx
import { useEffect, useState } from "react";
import {
  fetchPromet,
  exportPrometCsv,
  PrometRow,
} from "../services/prometApi";

function PrometPage() {
  const [rows, setRows] = useState<PrometRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filteri
  const [year, setYear] = useState<string>("");
  const [month, setMonth] = useState<string>("");
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");
  const [partnerQuery, setPartnerQuery] = useState<string>("");

  const loadData = async () => {
    setLoading(true);
    setError(null);

    try {
      const params: Record<string, any> = {
        limit: 200,
        offset: 0,
      };

      if (year) params.year = year;
      if (month) params.month = month;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      if (partnerQuery) params.partner_query = partnerQuery;

      const data = await fetchPromet(params);
      setRows(data.items ?? []);
      setTotal(data.total ?? 0);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Neočekivana greška");
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      const params: Record<string, any> = {};

      if (year) params.year = year;
      if (month) params.month = month;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      if (partnerQuery) params.partner_query = partnerQuery;

      const blob = await exportPrometCsv(params);
      const url = window.URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = "promet-export.csv";
      a.click();

      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Greška pri eksportovanju");
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const formatAmount = (value: string | number) => {
    const num = typeof value === "number" ? value : parseFloat(value);
    if (Number.isNaN(num)) return value;
    return num.toLocaleString("bs-BA", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">
          Knjiga prometa (KP-1042)
        </h1>
        <p className="text-sm text-slate-500">
          Pregled bezgotovinskog prometa iz keš knjige. Filtriranje po datumu i
          partneru, sa mogućnošću eksportovanja u CSV.
        </p>
      </div>

      {/* FILTERI */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 flex flex-wrap gap-3 items-end">
        <div className="flex flex-col">
          <label className="text-xs font-medium text-slate-600">Godina</label>
          <input
            type="number"
            className="mt-1 w-24 rounded-md border border-slate-300 px-2 py-1 text-sm"
            placeholder="2025"
            value={year}
            onChange={(e) => setYear(e.target.value)}
          />
        </div>

        <div className="flex flex-col">
          <label className="text-xs font-medium text-slate-600">Mjesec</label>
          <input
            type="number"
            className="mt-1 w-20 rounded-md border border-slate-300 px-2 py-1 text-sm"
            placeholder="1-12"
            min={1}
            max={12}
            value={month}
            onChange={(e) => setMonth(e.target.value)}
          />
        </div>

        <div className="flex flex-col">
          <label className="text-xs font-medium text-slate-600">Datum od</label>
          <input
            type="date"
            className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
        </div>

        <div className="flex flex-col">
          <label className="text-xs font-medium text-slate-600">Datum do</label>
          <input
            type="date"
            className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
          />
        </div>

        <div className="flex flex-col min-w-[200px]">
          <label className="text-xs font-medium text-slate-600">
            Partner / opis
          </label>
          <input
            type="text"
            className="mt-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
            placeholder="npr. Frizer, Dobavljač..."
            value={partnerQuery}
            onChange={(e) => setPartnerQuery(e.target.value)}
          />
        </div>

        <div className="flex gap-2 ml-auto">
          <button
            type="button"
            onClick={loadData}
            className="inline-flex items-center rounded-md bg-slate-900 px-3 py-2 text-xs font-medium text-white shadow-sm hover:bg-slate-800"
            disabled={loading}
          >
            Primijeni filtere
          </button>

          <button
            type="button"
            onClick={handleExport}
            className="inline-flex items-center rounded-md bg-white px-3 py-2 text-xs font-medium text-slate-700 shadow-sm border border-slate-300 hover:bg-slate-50"
          >
            Export CSV
          </button>
        </div>
      </div>

      {/* INFO BAR */}
      <div className="flex items-center justify-between text-xs text-slate-500">
        <div>
          Ukupno stavki:{" "}
          <span className="font-medium text-slate-700">{total}</span>
        </div>

        {loading && <div>Učitavanje...</div>}
        {error && <div className="text-red-600">Greška: {error}</div>}
      </div>

      {/* TABELA */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-slate-600">
                Datum
              </th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">
                Broj dokumenta
              </th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">
                Partner / opis
              </th>
              <th className="px-3 py-2 text-right font-medium text-slate-600">
                Iznos
              </th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">
                Napomena
              </th>
            </tr>
          </thead>

          <tbody>
            {rows.length === 0 && !loading && (
              <tr>
                <td
                  colSpan={5}
                  className="px-3 py-6 text-center text-sm text-slate-500"
                >
                  Nema stavki za zadate filtere.
                </td>
              </tr>
            )}

            {rows.map((row, idx) => {
              const val =
                typeof row.amount === "number"
                  ? row.amount
                  : parseFloat(row.amount);

              const isNegative = val < 0;

              return (
                <tr
                  key={`${row.document_number}-${idx}`}
                  className="border-t border-slate-100 hover:bg-slate-50/70"
                >
                  <td className="px-3 py-2">{row.date}</td>
                  <td className="px-3 py-2 font-mono text-xs">
                    {row.document_number}
                  </td>
                  <td className="px-3 py-2">{row.partner_name}</td>
                  <td
                    className={`px-3 py-2 text-right font-medium ${
                      isNegative ? "text-red-600" : "text-emerald-700"
                    }`}
                  >
                    {formatAmount(row.amount)}
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-600">
                    {row.note}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default PrometPage;
