// /home/miso/dev/sp-app/sp-app/frontend/src/pages/InvoicesListPage.tsx
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Download,
  FilePlus2,
  Filter,
  Receipt,
  RotateCcw,
  Search,
  Wallet,
} from "lucide-react";

import {
  fetchInvoicesList,
  markInvoicePaid,
  exportInvoicesExcel,
  type InvoicesListParams,
} from "../services/invoicesApi";
import type { InvoiceListResponse, InvoiceRowItem } from "../types/invoice";

const CURRENT_YEAR = new Date().getFullYear();

function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleDateString("sr-Latn-BA");
  } catch {
    return value;
  }
}

function formatAmount(value?: number | null): string {
  if (value == null) return "—";
  return `${value.toLocaleString("sr-Latn-BA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} KM`;
}

function isOverdue(invoice: InvoiceRowItem): boolean {
  if (invoice.is_paid || !invoice.due_date) return false;

  const due = new Date(invoice.due_date);
  if (Number.isNaN(due.getTime())) return false;

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  due.setHours(0, 0, 0, 0);

  return due.getTime() < today.getTime();
}

function Card({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "rounded-2xl border border-slate-200 bg-white shadow-sm",
        className,
      )}
    >
      {children}
    </div>
  );
}

function KpiCard({
  title,
  value,
  subtitle,
  icon,
  tone,
}: {
  title: string;
  value: string;
  subtitle: string;
  icon: ReactNode;
  tone: "emerald" | "rose" | "sky" | "slate" | "amber";
}) {
  const toneClasses = {
    emerald: "bg-emerald-50 text-emerald-700 ring-emerald-100",
    rose: "bg-rose-50 text-rose-700 ring-rose-100",
    sky: "bg-sky-50 text-sky-700 ring-sky-100",
    slate: "bg-slate-100 text-slate-700 ring-slate-200",
    amber: "bg-amber-50 text-amber-700 ring-amber-100",
  };

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-500">{title}</p>
          <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
            {value}
          </p>
          <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
        </div>

        <div
          className={cx(
            "grid h-10 w-10 shrink-0 place-items-center rounded-xl ring-1",
            toneClasses[tone],
          )}
        >
          {icon}
        </div>
      </div>
    </Card>
  );
}

function StatusBadge({ invoice }: { invoice: InvoiceRowItem }) {
  if (invoice.is_paid) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700 ring-1 ring-emerald-100">
        <CheckCircle2 className="h-3.5 w-3.5" />
        PLAĆENA
      </span>
    );
  }

  if (isOverdue(invoice)) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-2.5 py-1 text-[11px] font-semibold text-rose-700 ring-1 ring-rose-100">
        <AlertTriangle className="h-3.5 w-3.5" />
        DOSPJELA
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-semibold text-amber-700 ring-1 ring-amber-100">
      <Wallet className="h-3.5 w-3.5" />
      NEPLAĆENA
    </span>
  );
}

export default function InvoicesListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [year, setYear] = useState<number | undefined>(CURRENT_YEAR);
  const [month, setMonth] = useState<number | undefined>(undefined);
  const [buyerQuery, setBuyerQuery] = useState("");
  const [unpaidOnly, setUnpaidOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  const queryParams: InvoicesListParams = useMemo(
    () => ({
      year,
      month,
      buyer_query: buyerQuery.trim() || undefined,
      unpaid_only: unpaidOnly || undefined,
      page,
      page_size: pageSize,
    }),
    [year, month, buyerQuery, unpaidOnly, page, pageSize],
  );

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery<
    InvoiceListResponse,
    Error
  >({
    queryKey: ["invoices", "ui-list", queryParams],
    queryFn: () => fetchInvoicesList(queryParams),
    placeholderData: (previousData) => previousData,
  });

  const total: number = data?.total ?? 0;
  const items: InvoiceRowItem[] = data?.items ?? [];

  const totalPages = useMemo(() => {
    if (!total) return 1;
    return Math.max(1, Math.ceil(total / pageSize));
  }, [total, pageSize]);

  const stats = useMemo(() => {
    const totalAmount = items.reduce(
      (acc: number, invoice: InvoiceRowItem) =>
        acc + (invoice.total_amount ?? 0),
      0,
    );

    const unpaid = items.filter(
      (invoice: InvoiceRowItem) => !invoice.is_paid,
    );

    const unpaidAmount = unpaid.reduce(
      (acc: number, invoice: InvoiceRowItem) =>
        acc + (invoice.total_amount ?? 0),
      0,
    );

    const overdueCount = items.filter(
      (invoice: InvoiceRowItem) => isOverdue(invoice),
    ).length;

    return {
      totalAmount,
      unpaidCount: unpaid.length,
      unpaidAmount,
      overdueCount,
      paidCount: items.filter(
        (invoice: InvoiceRowItem) => invoice.is_paid,
      ).length,
    };
  }, [items]);

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  function handleClearFilters() {
    setYear(CURRENT_YEAR);
    setMonth(undefined);
    setBuyerQuery("");
    setUnpaidOnly(false);
    setPage(1);
  }

  async function handleMarkPaid(invoice: InvoiceRowItem) {
    if (
      !window.confirm(
        `Označiti fakturu ${invoice.number ?? `#${invoice.id}`} kao plaćenu?`,
      )
    ) {
      return;
    }

    try {
      await markInvoicePaid(invoice.id);
      await refetch();
      queryClient.invalidateQueries({
        queryKey: ["invoice-detail", invoice.id],
      });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    } catch (err) {
      console.error(err);
      alert("Greška pri označavanju fakture kao plaćene.");
    }
  }

  async function handleExport() {
    try {
      const blob = await exportInvoicesExcel(queryParams);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");

      a.href = url;
      a.download = "izlazne-fakture-export.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();

      URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
      alert("Greška pri eksportu faktura.");
    }
  }

  return (
    <div className="space-y-6">
      <div className="overflow-hidden rounded-3xl border border-slate-200 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 shadow-sm">
        <div className="grid gap-6 p-6 lg:grid-cols-[1.35fr_0.85fr]">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-slate-200 ring-1 ring-white/10">
              <Receipt className="h-4 w-4" />
              Modul izlaznih faktura
            </div>

            <h2 className="mt-4 text-3xl font-semibold tracking-tight text-white">
              Izlazne fakture
            </h2>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
              Profesionalan pregled faktura, naplate, dospjelih obaveza kupaca i
              exporta za poslovne evidencije.
            </p>

            <div className="mt-5 flex flex-wrap gap-2">
              <span className="inline-flex items-center rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-slate-200 ring-1 ring-white/10">
                Ukupno: {total}
              </span>
              <span className="inline-flex items-center rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-slate-200 ring-1 ring-white/10">
                Neplaćene: {stats.unpaidCount}
              </span>
              <span className="inline-flex items-center rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-slate-200 ring-1 ring-white/10">
                Dospjele: {stats.overdueCount}
              </span>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-300">
              Brze akcije
            </p>

            <div className="mt-4 grid gap-3">
              <button
                type="button"
                onClick={() => navigate("/invoices/new")}
                className="group flex items-center justify-between gap-3 rounded-xl bg-white px-4 py-3 text-left text-slate-950 shadow-sm hover:bg-slate-100"
              >
                <span className="flex items-center gap-3">
                  <span className="grid h-9 w-9 place-items-center rounded-xl bg-slate-950 text-white">
                    <FilePlus2 className="h-4 w-4" />
                  </span>
                  <span>
                    <span className="block text-sm font-semibold">
                      Nova faktura
                    </span>
                    <span className="block text-xs text-slate-500">
                      Kreiraj novu izlaznu fakturu
                    </span>
                  </span>
                </span>
                <ArrowRight className="h-4 w-4 text-slate-400 transition group-hover:translate-x-0.5" />
              </button>

              <button
                type="button"
                onClick={handleExport}
                className="group flex items-center justify-between gap-3 rounded-xl bg-white/10 px-4 py-3 text-left text-white ring-1 ring-white/10 hover:bg-white/15"
              >
                <span className="flex items-center gap-3">
                  <span className="grid h-9 w-9 place-items-center rounded-xl bg-white/10 text-white">
                    <Download className="h-4 w-4" />
                  </span>
                  <span>
                    <span className="block text-sm font-semibold">
                      Export liste
                    </span>
                    <span className="block text-xs text-slate-300">
                      CSV format za Excel
                    </span>
                  </span>
                </span>
                <ArrowRight className="h-4 w-4 text-slate-300 transition group-hover:translate-x-0.5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          title="Fakture u prikazu"
          value={String(total)}
          subtitle={isFetching ? "Osvježavanje u toku" : "Prema aktivnim filterima"}
          icon={<Receipt className="h-5 w-5" />}
          tone="slate"
        />

        <KpiCard
          title="Ukupan iznos"
          value={formatAmount(stats.totalAmount)}
          subtitle="Suma trenutno učitanih faktura"
          icon={<Wallet className="h-5 w-5" />}
          tone="sky"
        />

        <KpiCard
          title="Neplaćeno"
          value={formatAmount(stats.unpaidAmount)}
          subtitle={`${stats.unpaidCount} faktura čeka naplatu`}
          icon={<AlertTriangle className="h-5 w-5" />}
          tone={stats.unpaidCount > 0 ? "amber" : "emerald"}
        />

        <KpiCard
          title="Dospjelo"
          value={String(stats.overdueCount)}
          subtitle={
            stats.overdueCount > 0
              ? "Potrebna provjera naplate"
              : "Nema dospjelih faktura"
          }
          icon={<CheckCircle2 className="h-5 w-5" />}
          tone={stats.overdueCount > 0 ? "rose" : "emerald"}
        />
      </div>

      <Card className="p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              <Filter className="h-3.5 w-3.5" />
              Filteri i pretraga
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Suzi prikaz po periodu, kupcu i statusu naplate.
            </p>
          </div>

          <button
            type="button"
            onClick={handleClearFilters}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Reset filtera
          </button>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-[0.7fr_0.7fr_1.4fr_auto] md:items-end">
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-700">Godina</label>
            <select
              value={year ?? ""}
              onChange={(e) => {
                setYear(
                  e.target.value === "" ? undefined : Number(e.target.value),
                );
                setPage(1);
              }}
              className="input"
            >
              <option value="">Sve godine</option>
              <option value={CURRENT_YEAR}>{CURRENT_YEAR}</option>
              <option value={CURRENT_YEAR - 1}>{CURRENT_YEAR - 1}</option>
              <option value={CURRENT_YEAR - 2}>{CURRENT_YEAR - 2}</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-700">Mjesec</label>
            <select
              value={month ?? ""}
              onChange={(e) => {
                setMonth(
                  e.target.value === "" ? undefined : Number(e.target.value),
                );
                setPage(1);
              }}
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
            <label className="text-xs font-medium text-slate-700">Kupac</label>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={buyerQuery}
                onChange={(e) => {
                  setBuyerQuery(e.target.value);
                  setPage(1);
                }}
                className="input pl-9"
                placeholder="Pretraga po nazivu kupca..."
              />
            </div>
          </div>

          <label className="flex min-h-[42px] items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 text-xs font-semibold text-slate-700">
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
            Samo neplaćene
          </label>
        </div>
      </Card>

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-4">
          <div>
            <p className="text-sm font-semibold text-slate-950">
              Lista faktura
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {isFetching
                ? "Osvježavam podatke..."
                : `Prikazano ${items.length} od ukupno ${total} faktura.`}
            </p>
          </div>

          <button
            type="button"
            onClick={handleExport}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          >
            <Download className="h-3.5 w-3.5" />
            Export
          </button>
        </div>

        {isLoading && (
          <div className="p-6 text-sm text-slate-600">
            Učitavam izlazne fakture...
          </div>
        )}

        {isError && (
          <div className="m-4 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Greška pri učitavanju faktura:{" "}
            {error instanceof Error ? error.message : "Nepoznata greška"}
          </div>
        )}

        {!isLoading && !isError && items.length === 0 && (
          <div className="px-4 py-10">
            <div className="mx-auto max-w-md rounded-3xl border border-dashed border-slate-200 bg-slate-50 px-6 py-8 text-center">
              <Receipt className="mx-auto h-10 w-10 text-slate-400" />
              <p className="mt-4 text-sm font-semibold text-slate-900">
                Nema faktura za zadate filtere.
              </p>
              <p className="mt-2 text-xs leading-5 text-slate-500">
                Promijeni filtere ili kreiraj novu izlaznu fakturu ako počinješ
                unos poslovnih dokumenata.
              </p>
              <button
                type="button"
                onClick={() => navigate("/invoices/new")}
                className="mt-5 inline-flex items-center justify-center gap-2 rounded-xl bg-slate-950 px-4 py-2.5 text-xs font-semibold text-white hover:bg-slate-800"
              >
                <FilePlus2 className="h-4 w-4" />
                Nova faktura
              </button>
            </div>
          </div>
        )}

        {!isLoading && !isError && items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide">
                    Faktura
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide">
                    Kupac
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide">
                    Datum
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide">
                    Rok
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide">
                    Iznos
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wide">
                    Status
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide">
                    Akcije
                  </th>
                </tr>
              </thead>

              <tbody className="divide-y divide-slate-100 text-slate-700">
                {items.map((invoice: InvoiceRowItem) => (
                  <tr
                    key={invoice.id}
                    onDoubleClick={() =>
                      navigate(`/invoices/${invoice.id}`, {
                        state: { invoice },
                      })
                    }
                    className="group hover:bg-slate-50"
                  >
                    <td className="px-4 py-3">
                      <Link
                        to={`/invoices/${invoice.id}`}
                        state={{ invoice }}
                        className="font-semibold text-slate-950 hover:underline"
                      >
                        {invoice.number ?? `#${invoice.id}`}
                      </Link>
                      <p className="mt-0.5 text-[11px] text-slate-500">
                        ID: {invoice.id}
                      </p>
                    </td>

                    <td className="px-4 py-3">
                      <p className="max-w-[260px] truncate font-medium text-slate-800">
                        {invoice.buyer_name || "Nepoznat kupac"}
                      </p>
                    </td>

                    <td className="px-4 py-3 text-slate-600">
                      {formatDate(invoice.issue_date)}
                    </td>

                    <td className="px-4 py-3">
                      <span
                        className={cx(
                          "text-slate-600",
                          isOverdue(invoice) && "font-semibold text-rose-700",
                        )}
                      >
                        {formatDate(invoice.due_date)}
                      </span>
                    </td>

                    <td className="px-4 py-3 text-right font-mono font-semibold text-slate-950">
                      {formatAmount(invoice.total_amount)}
                    </td>

                    <td className="px-4 py-3 text-center">
                      <StatusBadge invoice={invoice} />
                    </td>

                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Link
                          to={`/invoices/${invoice.id}`}
                          state={{ invoice }}
                          className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-slate-700 hover:bg-slate-50"
                        >
                          Detalji
                        </Link>

                        {!invoice.is_paid && (
                          <button
                            type="button"
                            onClick={() => handleMarkPaid(invoice)}
                            className="rounded-lg bg-emerald-50 px-2.5 py-1.5 text-[11px] font-semibold text-emerald-700 ring-1 ring-emerald-100 hover:bg-emerald-100"
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

        {!isLoading && !isError && totalPages > 1 && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-4 py-3 text-xs text-slate-600">
            <div>
              Stranica{" "}
              <span className="font-semibold text-slate-900">{page}</span> od{" "}
              <span className="font-semibold text-slate-900">
                {totalPages}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="rounded-xl border border-slate-300 bg-white px-3 py-2 font-semibold hover:bg-slate-50 disabled:opacity-40"
              >
                ← Nazad
              </button>

              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="rounded-xl border border-slate-300 bg-white px-3 py-2 font-semibold hover:bg-slate-50 disabled:opacity-40"
              >
                Naprijed →
              </button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}