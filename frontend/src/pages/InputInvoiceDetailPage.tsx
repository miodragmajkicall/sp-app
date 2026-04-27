// /home/miso/dev/sp-app/sp-app/frontend/src/pages/InputInvoiceDetailPage.tsx
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import type { InputInvoiceDetail } from "../types/inputInvoice";
import {
  downloadInvoiceAttachment,
  fetchInvoiceAttachments,
  getInputInvoice,
  type InvoiceAttachmentItem,
} from "../services/inputInvoicesApi";

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

function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleString("sr-Latn-BA");
  } catch {
    return value ?? "-";
  }
}

function formatAmount(value?: number | null): string {
  if (value == null) return "-";
  return `${value.toFixed(2)} KM`;
}

function formatBytes(size?: number | null): string {
  if (size == null || Number.isNaN(size)) return "-";
  if (size < 1024) return `${size} B`;
  const kb = size / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  return `${mb.toFixed(1)} MB`;
}

function StatusBadge({
  children,
  tone = "slate",
}: {
  children: string;
  tone?: "slate" | "emerald" | "amber" | "blue";
}) {
  const classes =
    tone === "emerald"
      ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
      : tone === "amber"
        ? "bg-amber-50 text-amber-700 ring-amber-200"
        : tone === "blue"
          ? "bg-blue-50 text-blue-700 ring-blue-200"
          : "bg-slate-100 text-slate-600 ring-slate-200";

  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ${classes}`}
    >
      {children}
    </span>
  );
}

export default function InputInvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const numericId = id ? Number(id) : null;

  const {
    data: invoice,
    isLoading,
    isError,
    error,
  } = useQuery<InputInvoiceDetail>({
    queryKey: ["input-invoice-detail", numericId],
    enabled: numericId != null && Number.isFinite(numericId),
    queryFn: () => getInputInvoice(numericId as number),
  });

  const {
    data: attachments,
    isLoading: isAttachmentsLoading,
    isError: isAttachmentsError,
    error: attachmentsError,
  } = useQuery<InvoiceAttachmentItem[], Error>({
    queryKey: ["invoice-attachments"],
    queryFn: fetchInvoiceAttachments,
  });

  if (numericId == null || !Number.isFinite(numericId)) {
    return (
      <div className="mx-auto max-w-4xl rounded-3xl border border-red-200 bg-red-50 p-6 shadow-sm">
        <h1 className="text-lg font-semibold text-red-800">
          Nevalidan ID ulazne fakture
        </h1>
        <p className="mt-2 text-sm text-red-700">
          URL ne sadrži ispravan identifikator ulazne fakture.
        </p>
        <button
          type="button"
          onClick={() => navigate("/input-invoices")}
          className="mt-4 rounded-xl border border-red-200 bg-white px-4 py-2 text-sm font-semibold text-red-700 shadow-sm hover:bg-red-50"
        >
          ← Nazad na listu ulaznih faktura
        </button>
      </div>
    );
  }

  const linkedAttachments =
    attachments?.filter((att) => att.input_invoice_id === numericId) ?? [];

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 px-6 py-7 text-white sm:px-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <div className="inline-flex items-center rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs font-medium text-slate-200">
                Ulazne fakture · Detalji
              </div>
              <div>
                <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                  {invoice
                    ? `Ulazna faktura ${invoice.invoice_number}`
                    : "Detalj ulazne fakture"}
                </h1>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                  Pregled dobavljača, datuma, finansijskih iznosa, tehničkih
                  podataka i povezanih dokumenata za tenant{" "}
                  <span className="font-mono text-white">t-demo</span>.
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => navigate("/input-invoices")}
              className="inline-flex items-center justify-center rounded-2xl bg-white px-4 py-2.5 text-sm font-bold text-slate-950 shadow-sm transition hover:bg-slate-100"
            >
              ← Nazad na listu
            </button>
          </div>
        </div>

        {invoice && (
          <div className="grid gap-4 border-t border-slate-200 bg-slate-50 px-6 py-5 sm:grid-cols-2 lg:grid-cols-4 sm:px-8">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs font-medium text-slate-500">
                Dobavljač
              </p>
              <p className="mt-1 truncate text-lg font-semibold text-slate-900">
                {invoice.supplier_name || "-"}
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs font-medium text-slate-500">
                Osnovica
              </p>
              <p className="mt-1 font-mono text-lg font-semibold text-slate-900">
                {formatAmount(invoice.total_base)}
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs font-medium text-slate-500">PDV</p>
              <p className="mt-1 font-mono text-lg font-semibold text-slate-900">
                {formatAmount(invoice.total_vat)}
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs font-medium text-slate-500">
                Ukupno
              </p>
              <p className="mt-1 font-mono text-lg font-semibold text-slate-900">
                {formatAmount(invoice.total_amount)}
              </p>
            </div>
          </div>
        )}
      </div>

      {isLoading && (
        <div className="rounded-3xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">
          Učitavam detalje ulazne fakture...
        </div>
      )}

      {isError && (
        <div className="rounded-3xl border border-red-200 bg-red-50 p-6 text-sm text-red-700 shadow-sm">
          Greška pri učitavanju ulazne fakture:{" "}
          {error instanceof Error ? error.message : "Nepoznata greška"}
        </div>
      )}

      {invoice && (
        <div className="grid gap-6 lg:grid-cols-[1fr,380px]">
          <div className="space-y-6">
            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
              <div className="mb-5 border-b border-slate-100 pb-4">
                <h2 className="text-base font-semibold text-slate-900">
                  Dobavljač i dokument
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Osnovni podaci o ulaznoj fakturi i dobavljaču.
                </p>
              </div>

              <div className="grid gap-5 md:grid-cols-2">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Dobavljač
                  </p>
                  <p className="mt-2 text-lg font-semibold text-slate-900">
                    {invoice.supplier_name || "-"}
                  </p>
                  {invoice.supplier_address && (
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      {invoice.supplier_address}
                    </p>
                  )}
                  {invoice.supplier_tax_id && (
                    <p className="mt-2 text-sm text-slate-500">
                      PIB/JIB:{" "}
                      <span className="font-mono font-semibold text-slate-700">
                        {invoice.supplier_tax_id}
                      </span>
                    </p>
                  )}
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Dokument
                  </p>
                  <p className="mt-2 font-mono text-lg font-semibold text-slate-900">
                    {invoice.invoice_number || "-"}
                  </p>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <div>
                      <p className="text-xs text-slate-400">Datum izdavanja</p>
                      <p className="mt-1 text-sm font-semibold text-slate-800">
                        {formatDate(invoice.issue_date)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400">Rok dospijeća</p>
                      <p className="mt-1 text-sm font-semibold text-slate-800">
                        {formatDate(invoice.due_date)}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {invoice.note && (
                <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Interna napomena
                  </p>
                  <p className="mt-2 whitespace-pre-line text-sm leading-6 text-slate-700">
                    {invoice.note}
                  </p>
                </div>
              )}
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
              <div className="mb-5 border-b border-slate-100 pb-4">
                <h2 className="text-base font-semibold text-slate-900">
                  Obračun i metapodaci
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Finansijski pregled i tehnički trag zapisa u sistemu.
                </p>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Osnovica bez PDV-a
                  </p>
                  <p className="mt-2 font-mono text-lg font-semibold text-slate-900">
                    {formatAmount(invoice.total_base)}
                  </p>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    PDV iznos
                  </p>
                  <p className="mt-2 font-mono text-lg font-semibold text-slate-900">
                    {formatAmount(invoice.total_vat)}
                  </p>
                </div>

                <div className="rounded-2xl border border-slate-900 bg-slate-950 p-4 text-white">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    Ukupno
                  </p>
                  <p className="mt-2 font-mono text-xl font-bold">
                    {formatAmount(invoice.total_amount)}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    Valuta: {invoice.currency || "KM"}
                  </p>
                </div>
              </div>

              <div className="mt-5 grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 text-sm sm:grid-cols-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    ID fakture
                  </p>
                  <p className="mt-1 font-mono font-semibold text-slate-700">
                    {invoice.id}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    Tenant
                  </p>
                  <p className="mt-1 font-mono font-semibold text-slate-700">
                    {invoice.tenant_code}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    Kreirano
                  </p>
                  <p className="mt-1 font-mono text-xs font-semibold text-slate-700">
                    {formatDateTime(invoice.created_at)}
                  </p>
                </div>
              </div>
            </section>
          </div>

          <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="border-b border-slate-100 pb-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Dokumentacija
                </p>
                <h2 className="mt-1 text-base font-semibold text-slate-900">
                  Priloženi dokumenti
                </h2>
                <p className="mt-1 text-sm leading-5 text-slate-500">
                  Računi, slike ili PDF dokumenti povezani sa ovom ulaznom
                  fakturom.
                </p>
              </div>

              <div className="mt-4">
                {isAttachmentsLoading && (
                  <p className="text-sm text-slate-600">
                    Učitavam priložene dokumente...
                  </p>
                )}

                {isAttachmentsError && (
                  <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    Greška pri učitavanju priloženih dokumenata:{" "}
                    {attachmentsError?.message}
                  </div>
                )}

                {!isAttachmentsLoading &&
                  !isAttachmentsError &&
                  linkedAttachments.length === 0 && (
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-5 text-center">
                      <p className="text-sm font-semibold text-slate-800">
                        Nema povezanih dokumenata
                      </p>
                      <p className="mt-1 text-xs leading-5 text-slate-500">
                        Dokument prvo uploaduj kroz listu ulaznih faktura, pa ga
                        poveži sa ovom fakturom.
                      </p>
                    </div>
                  )}

                {linkedAttachments.length > 0 && (
                  <div className="space-y-3">
                    {linkedAttachments.map((att) => (
                      <div
                        key={att.id}
                        className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-slate-900">
                              {att.filename ?? `attachment-${att.id}`}
                            </p>
                            <p className="mt-1 text-xs text-slate-500">
                              {formatBytes(att.size_bytes)}
                            </p>
                          </div>

                          <StatusBadge tone="blue">
                            {att.status ?? "unknown"}
                          </StatusBadge>
                        </div>

                        <button
                          type="button"
                          onClick={() => downloadInvoiceAttachment(att.id)}
                          className="mt-4 w-full rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-bold text-slate-700 shadow-sm transition hover:bg-slate-50"
                        >
                          Otvori / preuzmi
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-900">
                Brze informacije
              </h3>

              <div className="mt-4 space-y-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-slate-500">Broj dokumenata</span>
                  <span className="font-semibold text-slate-900">
                    {linkedAttachments.length}
                  </span>
                </div>

                <div className="flex items-center justify-between gap-3">
                  <span className="text-slate-500">Broj fakture</span>
                  <span className="font-mono text-xs font-semibold text-slate-900">
                    {invoice.invoice_number || "-"}
                  </span>
                </div>

                <div className="flex items-center justify-between gap-3">
                  <span className="text-slate-500">Dobavljač</span>
                  <span className="max-w-[160px] truncate font-semibold text-slate-900">
                    {invoice.supplier_name || "-"}
                  </span>
                </div>
              </div>
            </section>

            <div className="text-xs text-slate-500">
              <Link
                to="/input-invoices"
                className="underline underline-offset-2 hover:text-slate-700"
              >
                ← Nazad na listu ulaznih faktura
              </Link>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}