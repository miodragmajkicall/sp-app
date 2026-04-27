// /home/miso/dev/sp-app/sp-app/frontend/src/pages/InvoiceDetailPage.tsx
import { useState } from "react";
import type { ChangeEvent, ReactNode } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Download,
  FileText,
  Landmark,
  Receipt,
  UserRound,
  Wallet,
} from "lucide-react";

import type { InvoiceRowItem, InvoiceDetail } from "../types/invoice";
import { apiClient } from "../services/apiClient";
import { fetchInvoiceById, markInvoicePaid } from "../services/invoicesApi";

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

function isOverdue(invoice: InvoiceDetail): boolean {
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

function StatusBadge({ invoice }: { invoice: InvoiceDetail }) {
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
      NIJE PLAĆENA
    </span>
  );
}

function InfoLine({
  label,
  value,
  mono,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="rounded-xl bg-slate-50 px-3 py-2">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
        {label}
      </p>
      <div
        className={cx(
          "mt-1 text-sm font-semibold text-slate-900",
          mono && "font-mono",
        )}
      >
        {value}
      </div>
    </div>
  );
}

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  const numericId = id ? Number(id) : null;

  const listInvoice =
    (location.state as { invoice?: InvoiceRowItem } | null)?.invoice ?? null;

  const {
    data: invoice,
    isLoading,
    isError,
    error,
  } = useQuery<InvoiceDetail, Error>({
    queryKey: ["invoice-detail", numericId],
    enabled: numericId != null && Number.isFinite(numericId),
    queryFn: () => fetchInvoiceById(numericId as number),
  });

  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState("");
  const [statusSaving, setStatusSaving] = useState(false);
  const [statusError, setStatusError] = useState("");

  async function handleOpenPdf() {
    if (numericId == null || !Number.isFinite(numericId)) return;

    setPdfError("");
    setPdfLoading(true);

    try {
      const response = await apiClient.get(`/invoices/${numericId}/pdf`, {
        responseType: "blob",
      });

      const blob = new Blob([response.data], { type: "application/pdf" });
      const url = URL.createObjectURL(blob);

      window.open(url, "_blank", "noopener,noreferrer");
    } catch (err) {
      console.error(err);
      setPdfError("Greška pri preuzimanju PDF fakture.");
    } finally {
      setPdfLoading(false);
    }
  }

  async function handleStatusChange(e: ChangeEvent<HTMLSelectElement>) {
    if (!invoice || numericId == null || !Number.isFinite(numericId)) return;

    const value = e.target.value;
    setStatusError("");

    if (value === "PAID" && !invoice.is_paid) {
      try {
        setStatusSaving(true);
        await markInvoicePaid(numericId);
        await queryClient.invalidateQueries({
          queryKey: ["invoice-detail", numericId],
        });
        await queryClient.invalidateQueries({
          queryKey: ["invoices"],
        });
        await queryClient.invalidateQueries({
          queryKey: ["dashboard"],
        });
      } catch (err) {
        console.error(err);
        setStatusError("Greška pri ažuriranju statusa plaćanja.");
      } finally {
        setStatusSaving(false);
      }
    }
  }

  if (numericId == null || !Number.isFinite(numericId)) {
    return (
      <div className="space-y-4">
        <Card className="border-red-200 bg-red-50 p-5">
          <p className="text-sm font-medium text-red-700">
            Nevalidan ID fakture u URL-u.
          </p>
        </Card>

        <button
          type="button"
          onClick={() => navigate("/invoices")}
          className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
        >
          <ArrowLeft className="h-4 w-4" />
          Nazad na listu
        </button>
      </div>
    );
  }

  const title = invoice
    ? `Faktura ${invoice.invoice_number}`
    : listInvoice
      ? `Faktura ${listInvoice.number ?? `#${listInvoice.id}`}`
      : "Detalj fakture";

  return (
    <div className="space-y-6">
      <div className="overflow-hidden rounded-3xl border border-slate-200 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 shadow-sm">
        <div className="grid gap-6 p-6 lg:grid-cols-[1.35fr_0.85fr]">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-slate-200 ring-1 ring-white/10">
              <Receipt className="h-4 w-4" />
              Detalj izlazne fakture
            </div>

            <h2 className="mt-4 text-3xl font-semibold tracking-tight text-white">
              {title}
            </h2>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
              Pregled kupca, stavki, PDV-a, ukupnog iznosa i statusa naplate za
              izabranu izlaznu fakturu.
            </p>

            {invoice && (
              <div className="mt-5 flex flex-wrap gap-2">
                <span className="inline-flex items-center rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-slate-200 ring-1 ring-white/10">
                  Kupac: {invoice.buyer_name || "Nepoznat kupac"}
                </span>
                <span className="inline-flex items-center rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-slate-200 ring-1 ring-white/10">
                  Iznos: {formatAmount(invoice.total_amount)}
                </span>
                <span className="inline-flex items-center rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-slate-200 ring-1 ring-white/10">
                  Rok: {formatDate(invoice.due_date)}
                </span>
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-300">
              Akcije
            </p>

            <div className="mt-4 grid gap-3">
              <button
                type="button"
                onClick={handleOpenPdf}
                disabled={pdfLoading}
                className="group flex items-center justify-between gap-3 rounded-xl bg-white px-4 py-3 text-left text-slate-950 shadow-sm hover:bg-slate-100 disabled:opacity-60"
              >
                <span className="flex items-center gap-3">
                  <span className="grid h-9 w-9 place-items-center rounded-xl bg-slate-950 text-white">
                    <Download className="h-4 w-4" />
                  </span>
                  <span>
                    <span className="block text-sm font-semibold">
                      {pdfLoading ? "Pripremam PDF..." : "PDF fakture"}
                    </span>
                    <span className="block text-xs text-slate-500">
                      Otvori fakturu za štampu ili slanje
                    </span>
                  </span>
                </span>
              </button>

              <button
                type="button"
                onClick={() => navigate("/invoices")}
                className="group flex items-center justify-between gap-3 rounded-xl bg-white/10 px-4 py-3 text-left text-white ring-1 ring-white/10 hover:bg-white/15"
              >
                <span className="flex items-center gap-3">
                  <span className="grid h-9 w-9 place-items-center rounded-xl bg-white/10 text-white">
                    <ArrowLeft className="h-4 w-4" />
                  </span>
                  <span>
                    <span className="block text-sm font-semibold">
                      Nazad na listu
                    </span>
                    <span className="block text-xs text-slate-300">
                      Povratak na izlazne fakture
                    </span>
                  </span>
                </span>
              </button>
            </div>

            {pdfError && (
              <p className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                {pdfError}
              </p>
            )}
          </div>
        </div>
      </div>

      {isLoading && (
        <Card className="p-5">
          <p className="text-sm text-slate-600">
            Učitavam detalje fakture...
          </p>
        </Card>
      )}

      {isError && (
        <Card className="border-red-200 bg-red-50 p-5">
          <p className="text-sm text-red-700">
            Greška pri učitavanju fakture: {error.message}
          </p>
        </Card>
      )}

      {invoice && (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              title="Ukupno za naplatu"
              value={formatAmount(invoice.total_amount)}
              subtitle={invoice.is_paid ? "Faktura je plaćena" : "Otvoreno za naplatu"}
              icon={<Wallet className="h-5 w-5" />}
              tone={invoice.is_paid ? "emerald" : "amber"}
            />

            <KpiCard
              title="Neto osnovica"
              value={formatAmount(invoice.total_base)}
              subtitle="Iznos bez PDV-a"
              icon={<FileText className="h-5 w-5" />}
              tone="slate"
            />

            <KpiCard
              title="PDV"
              value={formatAmount(invoice.total_vat)}
              subtitle="Obračunati porez"
              icon={<Landmark className="h-5 w-5" />}
              tone="sky"
            />

            <KpiCard
              title="Status"
              value={invoice.is_paid ? "Plaćena" : isOverdue(invoice) ? "Dospjela" : "Neplaćena"}
              subtitle={`Rok: ${formatDate(invoice.due_date)}`}
              icon={
                invoice.is_paid ? (
                  <CheckCircle2 className="h-5 w-5" />
                ) : (
                  <AlertTriangle className="h-5 w-5" />
                )
              }
              tone={invoice.is_paid ? "emerald" : isOverdue(invoice) ? "rose" : "amber"}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-[1fr_0.8fr]">
            <Card className="p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                    <UserRound className="h-3.5 w-3.5" />
                    Kupac i dokument
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Osnovni podaci o kupcu i fakturi.
                  </p>
                </div>
                <StatusBadge invoice={invoice} />
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <InfoLine label="Broj fakture" value={invoice.invoice_number} mono />
                <InfoLine label="ID fakture" value={invoice.id} mono />
                <InfoLine
                  label="Kupac"
                  value={invoice.buyer_name || "Nepoznat kupac"}
                />
                <InfoLine
                  label="JIB / PIB"
                  value={invoice.buyer_tax_id || "Nije uneseno"}
                  mono
                />
                <InfoLine label="Datum izdavanja" value={formatDate(invoice.issue_date)} />
                <InfoLine label="Rok plaćanja" value={formatDate(invoice.due_date)} />
              </div>

              {invoice.buyer_address && (
                <div className="mt-3 rounded-xl bg-slate-50 px-3 py-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                    Adresa kupca
                  </p>
                  <p className="mt-1 text-sm text-slate-700">
                    {invoice.buyer_address}
                  </p>
                </div>
              )}
            </Card>

            <Card className="p-4">
              <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                <Wallet className="h-3.5 w-3.5" />
                Naplata
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Trenutni status i brzo označavanje plaćanja.
              </p>

              <div className="mt-4 rounded-2xl border border-slate-100 bg-slate-50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs text-slate-500">Status plaćanja</p>
                    <div className="mt-2">
                      <StatusBadge invoice={invoice} />
                    </div>
                  </div>

                  <div className="text-right">
                    <label className="mb-1 block text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                      Promijeni status
                    </label>
                    <select
                      className="input py-2 text-xs"
                      value={invoice.is_paid ? "PAID" : "UNPAID"}
                      onChange={handleStatusChange}
                      disabled={statusSaving || invoice.is_paid}
                    >
                      <option value="UNPAID">NIJE PLAĆENA</option>
                      <option value="PAID">PLAĆENA</option>
                    </select>
                  </div>
                </div>

                {invoice.is_paid ? (
                  <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
                    Faktura je označena kao plaćena.
                  </p>
                ) : (
                  <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                    Backend trenutno podržava promjenu samo iz neplaćena u
                    plaćena.
                  </p>
                )}

                {statusError && (
                  <p className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                    {statusError}
                  </p>
                )}
              </div>

              <div className="mt-4 space-y-2 text-xs text-slate-500">
                <p>
                  Ruta:{" "}
                  <span className="font-mono text-slate-700">
                    /invoices/{invoice.id}
                  </span>
                </p>
                <p>
                  Tenant:{" "}
                  <span className="font-mono text-slate-700">
                    {invoice.tenant_code}
                  </span>
                </p>
              </div>
            </Card>
          </div>

          {invoice.note && (
            <Card className="p-4">
              <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                <FileText className="h-3.5 w-3.5" />
                Napomena fakture
              </p>
              <p className="mt-3 whitespace-pre-line rounded-xl bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700">
                {invoice.note}
              </p>
            </Card>
          )}

          <Card className="overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-4">
              <div>
                <p className="text-sm font-semibold text-slate-950">
                  Stavke fakture
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Detaljan pregled usluga/proizvoda, osnovice, PDV-a i ukupnog
                  iznosa.
                </p>
              </div>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                {invoice.items.length} stavki
              </span>
            </div>

            {invoice.items.length === 0 ? (
              <div className="p-6 text-sm text-slate-500">
                Nema stavki evidentiranih za ovu fakturu.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-slate-500">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide">
                        Opis stavke
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide">
                        Količina
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide">
                        Jed. cijena
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide">
                        Popust
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide">
                        PDV %
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide">
                        Osnovica
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide">
                        PDV
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide">
                        Ukupno
                      </th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {invoice.items.map((item) => (
                      <tr key={item.id} className="hover:bg-slate-50">
                        <td className="px-4 py-3 font-medium text-slate-900">
                          {item.description}
                        </td>
                        <td className="px-4 py-3 text-right font-mono">
                          {item.quantity.toFixed(2)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono">
                          {formatAmount(item.unit_price)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono">
                          {item.discount_percent.toFixed(2)}%
                        </td>
                        <td className="px-4 py-3 text-right font-mono">
                          {(item.vat_rate * 100).toFixed(0)}%
                        </td>
                        <td className="px-4 py-3 text-right font-mono">
                          {formatAmount(item.base_amount)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono">
                          {formatAmount(item.vat_amount)}
                        </td>
                        <td className="px-4 py-3 text-right font-mono font-semibold text-slate-950">
                          {formatAmount(item.total_amount)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <Link
              to="/invoices"
              className="inline-flex items-center gap-2 text-xs font-semibold text-slate-600 underline underline-offset-2 hover:text-slate-900"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Nazad na listu izlaznih faktura
            </Link>

            <button
              type="button"
              onClick={handleOpenPdf}
              disabled={pdfLoading}
              className="inline-flex items-center gap-2 rounded-xl bg-slate-950 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
            >
              <Download className="h-4 w-4" />
              {pdfLoading ? "Pripremam PDF..." : "PDF fakture"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}