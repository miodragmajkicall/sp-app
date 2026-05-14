// /home/miso/dev/sp-app/sp-app/frontend/src/pages/PrometPage.tsx

import { useEffect, useMemo, useState } from "react";
import {
  ArrowDownLeft,
  ArrowUpRight,
  CalendarRange,
  Download,
  FileSpreadsheet,
  Filter,
  RefreshCw,
} from "lucide-react";

import {
  exportPrometCsv,
  fetchPromet,
  PrometRow,
} from "../services/prometApi";

function PrometPage() {
  const [rows, setRows] = useState<PrometRow[]>([]);
  const [total, setTotal] = useState(0);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

    if (Number.isNaN(num)) {
      return value;
    }

    return num.toLocaleString("bs-BA", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  const totalPositive = useMemo(() => {
    return rows.reduce((sum, row) => {
      const amount =
        typeof row.amount === "number"
          ? row.amount
          : parseFloat(row.amount);

      return amount > 0 ? sum + amount : sum;
    }, 0);
  }, [rows]);

  const totalNegative = useMemo(() => {
    return rows.reduce((sum, row) => {
      const amount =
        typeof row.amount === "number"
          ? row.amount
          : parseFloat(row.amount);

      return amount < 0 ? sum + Math.abs(amount) : sum;
    }, 0);
  }, [rows]);

  const netResult = totalPositive - totalNegative;

  return (
    <div className="space-y-6">
      {/* HERO */}
      <section className="overflow-hidden rounded-[32px] border border-slate-800 bg-gradient-to-br from-[#020817] via-[#071132] to-[#111c44] text-white shadow-2xl">
        <div className="flex flex-col gap-10 px-6 py-7 lg:px-8 lg:py-8">
          <div className="flex flex-col gap-8 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-4 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-200">
                <FileSpreadsheet className="h-3.5 w-3.5" />
                KP-1042 • KNJIGA PROMETA
              </div>

              <h1 className="text-3xl font-bold tracking-tight lg:text-5xl">
                Pregled bezgotovinskog prometa
              </h1>

              <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-300 lg:text-base">
                Centralizovan pregled svih stavki knjige prometa,
                filtriranje po periodu i partnerima, uz CSV eksport za
                računovodstvo i inspekcijske evidencije.
              </p>

              <div className="mt-6 flex flex-wrap items-center gap-3 text-sm">
                <div className="rounded-full border border-white/10 bg-white/10 px-4 py-2 text-slate-100">
                  Stavki: {total}
                </div>

                {year && (
                  <div className="rounded-full border border-white/10 bg-white/10 px-4 py-2 text-slate-100">
                    Godina: {year}
                  </div>
                )}

                {month && (
                  <div className="rounded-full border border-white/10 bg-white/10 px-4 py-2 text-slate-100">
                    Mjesec: {month}
                  </div>
                )}
              </div>
            </div>

            <div className="flex w-full max-w-md flex-col gap-3 rounded-3xl border border-white/10 bg-white/10 p-5 backdrop-blur">
              <div className="flex items-center justify-between rounded-2xl bg-white/10 px-4 py-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-300">
                    Ukupan priliv
                  </p>

                  <p className="mt-1 text-xl font-bold text-emerald-300">
                    {formatAmount(totalPositive)} KM
                  </p>
                </div>

                <ArrowUpRight className="h-5 w-5 text-emerald-300" />
              </div>

              <div className="flex items-center justify-between rounded-2xl bg-white/10 px-4 py-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-300">
                    Ukupan odliv
                  </p>

                  <p className="mt-1 text-xl font-bold text-rose-300">
                    {formatAmount(totalNegative)} KM
                  </p>
                </div>

                <ArrowDownLeft className="h-5 w-5 text-rose-300" />
              </div>

              <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-[#0f172a]/70 px-4 py-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-400">
                    Neto rezultat
                  </p>

                  <p className="mt-1 text-2xl font-bold text-white">
                    {formatAmount(netResult)} KM
                  </p>
                </div>

                <CalendarRange className="h-5 w-5 text-slate-300" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* FILTERS */}
      <section className="rounded-[28px] border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-6 p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                <Filter className="h-4 w-4" />
                Filteri pregleda
              </div>

              <h2 className="mt-2 text-2xl font-semibold text-slate-900">
                Period i partneri
              </h2>

              <p className="mt-1 text-sm text-slate-500">
                Kontrola prikaza knjige prometa po datumu i partnerima.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={loadData}
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-2xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-60"
              >
                <RefreshCw className="h-4 w-4" />
                Osvježi podatke
              </button>

              <button
                type="button"
                onClick={handleExport}
                className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
              >
                <Download className="h-4 w-4" />
                Export CSV
              </button>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            <div>
              <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                Godina
              </label>

              <input
                type="number"
                placeholder="2026"
                value={year}
                onChange={(e) => setYear(e.target.value)}
                className="h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm outline-none transition focus:border-slate-400"
              />
            </div>

            <div>
              <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                Mjesec
              </label>

              <input
                type="number"
                placeholder="1-12"
                min={1}
                max={12}
                value={month}
                onChange={(e) => setMonth(e.target.value)}
                className="h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm outline-none transition focus:border-slate-400"
              />
            </div>

            <div>
              <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                Datum od
              </label>

              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm outline-none transition focus:border-slate-400"
              />
            </div>

            <div>
              <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                Datum do
              </label>

              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm outline-none transition focus:border-slate-400"
              />
            </div>

            <div>
              <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                Partner / opis
              </label>

              <input
                type="text"
                placeholder="Pretraga partnera..."
                value={partnerQuery}
                onChange={(e) => setPartnerQuery(e.target.value)}
                className="h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm outline-none transition focus:border-slate-400"
              />
            </div>
          </div>

          {(loading || error) && (
            <div className="flex flex-wrap items-center gap-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm">
              {loading && (
                <span className="font-medium text-slate-600">
                  Učitavanje podataka...
                </span>
              )}

              {error && (
                <span className="font-medium text-red-600">
                  Greška: {error}
                </span>
              )}
            </div>
          )}
        </div>
      </section>

      {/* TABLE */}
      <section className="overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-5">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
              Knjiga prometa
            </div>

            <h2 className="mt-1 text-2xl font-semibold text-slate-900">
              Evidencija stavki
            </h2>
          </div>

          <div className="rounded-full bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700">
            Ukupno: {total}
          </div>
        </div>

        {rows.length === 0 && !loading ? (
          <div className="flex flex-col items-center justify-center px-6 py-20 text-center">
            <div className="flex h-20 w-20 items-center justify-center rounded-3xl bg-slate-100">
              <FileSpreadsheet className="h-10 w-10 text-slate-400" />
            </div>

            <h3 className="mt-6 text-xl font-semibold text-slate-900">
              Nema stavki za prikaz
            </h3>

            <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">
              Trenutno nema pronađenih stavki za odabrane filtere
              knjige prometa.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Datum
                  </th>

                  <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Dokument
                  </th>

                  <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Partner / opis
                  </th>

                  <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Iznos
                  </th>

                  <th className="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Napomena
                  </th>
                </tr>
              </thead>

              <tbody>
                {rows.map((row, idx) => {
                  const amount =
                    typeof row.amount === "number"
                      ? row.amount
                      : parseFloat(row.amount);

                  const isNegative = amount < 0;

                  return (
                    <tr
                      key={`${row.document_number}-${idx}`}
                      className="border-b border-slate-100 transition hover:bg-slate-50/80"
                    >
                      <td className="px-6 py-4 font-medium text-slate-700">
                        {row.date}
                      </td>

                      <td className="px-6 py-4">
                        <div className="font-mono text-xs text-slate-700">
                          {row.document_number}
                        </div>
                      </td>

                      <td className="px-6 py-4 text-slate-700">
                        {row.partner_name}
                      </td>

                      <td className="px-6 py-4 text-right">
                        <span
                          className={`inline-flex rounded-full px-3 py-1 text-sm font-semibold ${
                            isNegative
                              ? "bg-rose-50 text-rose-700"
                              : "bg-emerald-50 text-emerald-700"
                          }`}
                        >
                          {isNegative ? "-" : "+"}
                          {formatAmount(Math.abs(amount))} KM
                        </span>
                      </td>

                      <td className="px-6 py-4 text-sm text-slate-500">
                        {row.note || "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export default PrometPage;