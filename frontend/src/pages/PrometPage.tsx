// /home/miso/dev/sp-app/sp-app/frontend/src/pages/PrometPage.tsx

import { useEffect, useState } from "react";
import axios from "axios";
import {
  Banknote,
  CircleDollarSign,
  Landmark,
  Download,
  FileSpreadsheet,
  Filter,
  RefreshCw,
} from "lucide-react";

import {
  exportPrometCsv,
  exportPrometPdf,
  fetchPromet,
  type ExportPrometParams,
  type FetchPrometParams,
  type PrometRow,
  type PrometSummary,
} from "../services/prometApi";

const PAGE_SIZE = 25;

const EMPTY_SUMMARY: PrometSummary = {
  total_amount: 0,
  cash_amount: 0,
  bank_amount: 0,
};

function getPrometErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) {
    return error instanceof Error
      ? error.message
      : "Neočekivana greška";
  }

  const detail = error.response?.data?.detail;

  if (detail?.code === "promet_needs_configuration") {
    return "Knjiga prometa nije dostupna dok se ne dopune potrebni poslovni i poreski podaci.";
  }

  if (detail?.code === "promet_not_applicable") {
    return "Knjiga prometa nije primjenjiva na trenutno podešeni poslovni scenario.";
  }

  if (detail?.code === "promet_dataset_not_implemented") {
    return "Knjiga prometa za ovaj poslovni scenario još nije implementirana.";
  }

  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  return error.message || "Neočekivana greška";
}

function PrometPage() {
  const [rows, setRows] = useState<PrometRow[]>([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState<PrometSummary>(EMPTY_SUMMARY);
  const [page, setPage] = useState(1);

  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [year, setYear] = useState<string>("");
  const [month, setMonth] = useState<string>("");
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");
  const [partnerQuery, setPartnerQuery] = useState<string>("");

  const [appliedFilters, setAppliedFilters] =
    useState<ExportPrometParams>({});

  const buildDraftFilters = (): ExportPrometParams => {
    const params: ExportPrometParams = {};

    if (year) params.year = Number(year);
    if (month) params.month = Number(month);
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;

    const trimmedPartnerQuery = partnerQuery.trim();
    if (trimmedPartnerQuery) {
      params.partner_query = trimmedPartnerQuery;
    }

    return params;
  };

  const loadData = async (
    requestedPage = page,
    filters: ExportPrometParams = appliedFilters,
  ) => {
    setLoading(true);
    setError(null);

    try {
      const params: FetchPrometParams = {
        ...filters,
        limit: PAGE_SIZE,
        offset: (requestedPage - 1) * PAGE_SIZE,
      };

      const data = await fetchPromet(params);

      setRows(data.items ?? []);
      setTotal(data.total ?? 0);
      setSummary(data.summary ?? EMPTY_SUMMARY);
    } catch (err: unknown) {
      console.error(err);
      setRows([]);
      setTotal(0);
      setSummary(EMPTY_SUMMARY);
      setError(getPrometErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };


  const handleRefresh = () => {
    const nextFilters = buildDraftFilters();

    setAppliedFilters(nextFilters);
    setPage(1);
    void loadData(1, nextFilters);
  };

  const handlePageChange = (nextPage: number) => {
    setPage(nextPage);
    void loadData(nextPage, appliedFilters);
  };

  const handleExport = async () => {
    setExporting(true);
    setError(null);

    try {
      const blob = await exportPrometCsv(appliedFilters);
      const url = URL.createObjectURL(blob);

      try {
        const link = document.createElement("a");
        link.href = url;
        link.download = "promet-export.csv";
        document.body.appendChild(link);
        link.click();
        link.remove();
      } finally {
        URL.revokeObjectURL(url);
      }
    } catch (err: unknown) {
      console.error(err);
      setError(getPrometErrorMessage(err));
    } finally {
      setExporting(false);
    }
  };

  const handleExportPdf = async () => {
    setExportingPdf(true);
    setError(null);

    try {
      const blob = await exportPrometPdf(appliedFilters);
      const url = URL.createObjectURL(blob);

      try {
        const link = document.createElement("a");
        link.href = url;
        link.download = "promet-export.pdf";
        document.body.appendChild(link);
        link.click();
        link.remove();
      } finally {
        URL.revokeObjectURL(url);
      }
    } catch (err: unknown) {
      console.error(err);
      setError(getPrometErrorMessage(err));
    } finally {
      setExportingPdf(false);
    }
  };

  useEffect(() => {
    void loadData(1, {});
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

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const offset = (page - 1) * PAGE_SIZE;
  const pageStart = rows.length > 0 ? offset + 1 : 0;
  const pageEnd =
    rows.length > 0
      ? Math.min(offset + rows.length, total)
      : 0;

  return (
    <div className="space-y-6">
      {/* HERO */}
      <section className="overflow-hidden rounded-[32px] border border-slate-800 bg-gradient-to-br from-[#020817] via-[#071132] to-[#111c44] text-white shadow-2xl">
        <div className="flex flex-col gap-10 px-6 py-7 lg:px-8 lg:py-8">
          <div className="flex flex-col gap-8 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-4 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-200">
                <FileSpreadsheet className="h-3.5 w-3.5" />
                KNJIGA PROMETA
              </div>

              <h1 className="text-3xl font-bold tracking-tight lg:text-5xl">
                Pregled prometa
              </h1>

              <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-300 lg:text-base">
                Pregled stavki Knjige prometa prema poslovnom scenariju,
                sa filtriranjem po periodu i partneru te zbirnim pregledom
                gotovinskog i bankovnog prometa.
              </p>

              <div className="mt-6 flex flex-wrap items-center gap-3 text-sm">
                <div className="rounded-full border border-white/10 bg-white/10 px-4 py-2 text-slate-100">
                  Stavki: {total}
                </div>

                {appliedFilters.year !== undefined && (
                  <div className="rounded-full border border-white/10 bg-white/10 px-4 py-2 text-slate-100">
                    Godina: {appliedFilters.year}
                  </div>
                )}

                {appliedFilters.month !== undefined && (
                  <div className="rounded-full border border-white/10 bg-white/10 px-4 py-2 text-slate-100">
                    Mjesec: {appliedFilters.month}
                  </div>
                )}
              </div>
            </div>

            <div className="flex w-full max-w-md flex-col gap-3 rounded-3xl border border-white/10 bg-white/10 p-5 backdrop-blur">
              <div className="flex items-center justify-between rounded-2xl bg-white/10 px-4 py-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-300">
                    Ukupan promet
                  </p>

                  <p className="mt-1 text-xl font-bold text-white">
                    {formatAmount(summary.total_amount)} KM
                  </p>
                </div>

                <CircleDollarSign className="h-5 w-5 text-slate-200" />
              </div>

              <div className="flex items-center justify-between rounded-2xl bg-white/10 px-4 py-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-300">
                    Gotovina
                  </p>

                  <p className="mt-1 text-xl font-bold text-emerald-300">
                    {formatAmount(summary.cash_amount)} KM
                  </p>
                </div>

                <Banknote className="h-5 w-5 text-emerald-300" />
              </div>

              <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-[#0f172a]/70 px-4 py-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-400">
                    Banka
                  </p>

                  <p className="mt-1 text-2xl font-bold text-white">
                    {formatAmount(summary.bank_amount)} KM
                  </p>
                </div>

                <Landmark className="h-5 w-5 text-slate-300" />
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
                onClick={() => void handleExport()}
                disabled={loading || exporting || exportingPdf}
                className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Download className="h-4 w-4" />
                {exporting ? "Priprema CSV..." : "Preuzmi CSV"}
              </button>

              <button
                type="button"
                onClick={() => void handleExportPdf()}
                disabled={loading || exporting || exportingPdf}
                className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Download className="h-4 w-4" />
                {exportingPdf ? "Priprema PDF..." : "Preuzmi PDF"}
              </button>

              <button
                type="button"
                onClick={handleRefresh}
                disabled={loading || exporting || exportingPdf}
                className="inline-flex items-center gap-2 rounded-2xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <RefreshCw className="h-4 w-4" />
                Osvježi podatke
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


                  return (
                    <tr
                      key={`${row.date}-${row.document_number ?? "no-document"}-${idx}`}
                      className="border-b border-slate-100 transition hover:bg-slate-50/80"
                    >
                      <td className="px-6 py-4 font-medium text-slate-700">
                        {row.date}
                      </td>

                      <td className="px-6 py-4">
                        <div className="font-mono text-xs text-slate-700">
                          {row.document_number ?? "—"}
                        </div>
                      </td>

                      <td className="px-6 py-4 text-slate-700">
                        {row.partner_name ?? "—"}
                      </td>

                      <td className="px-6 py-4 text-right">
                        <span className="inline-flex rounded-full bg-emerald-50 px-3 py-1 text-sm font-semibold text-emerald-700">
                          {formatAmount(amount)} KM
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

          {!loading && !error && (
            <nav
              aria-label="Paginacija Knjige prometa"
              className="flex flex-col gap-3 border-t border-slate-100 px-6 py-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <p className="text-xs text-slate-500">
                {rows.length > 0
                  ? `Prikazano ${pageStart}–${pageEnd} od ${total} stavki`
                  : `Prikazano 0 od ${total} stavki`}
              </p>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() =>
                    handlePageChange(Math.max(1, page - 1))
                  }
                  disabled={loading || page <= 1}
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Prethodna
                </button>

                <span className="whitespace-nowrap text-xs font-medium text-slate-600">
                  Stranica {page} od {totalPages}
                </span>

                <button
                  type="button"
                  onClick={() =>
                    handlePageChange(Math.min(totalPages, page + 1))
                  }
                  disabled={loading || page >= totalPages}
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Sljedeća
                </button>
              </div>
            </nav>
          )}
      </section>
    </div>
  );
}

export default PrometPage;
