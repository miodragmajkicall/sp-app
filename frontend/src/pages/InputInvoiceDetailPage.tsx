// /home/miso/dev/sp-app/sp-app/frontend/src/pages/InputInvoiceDetailPage.tsx
import React from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import type { InputInvoiceDetail } from "../types/inputInvoice";
import {
  fetchInvoiceAttachments,
  type InvoiceAttachmentItem,
  downloadInvoiceAttachment,
} from "../services/inputInvoicesApi";
import { getInputInvoice } from "../services/inputInvoicesApi";

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
      <div className="space-y-4">
        <p className="text-sm text-red-600">
          Nevalidan ID ulazne fakture u URL-u.
        </p>
        <button
          type="button"
          onClick={() => navigate("/input-invoices")}
          className="text-xs px-3 py-1.5 rounded-md border border-slate-300 bg-white hover:bg-slate-50"
        >
          ← Nazad na listu ulaznih faktura
        </button>
      </div>
    );
  }

  const linkedAttachments =
    attachments?.filter((att) => att.input_invoice_id === numericId) ?? [];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">
            {invoice
              ? `Ulazna faktura ${invoice.invoice_number}`
              : "Detalj ulazne fakture"}
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Detalji ulazne fakture (troškovi dobavljača) za tenant{" "}
            <span className="font-mono">t-demo</span>.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => navigate("/input-invoices")}
            className="inline-flex items-center rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50"
          >
            ← Nazad na listu
          </button>
        </div>
      </div>

      {/* Loading / error */}
      {isLoading && (
        <p className="text-sm text-slate-600">
          Učitavam detalje ulazne fakture...
        </p>
      )}

      {isError && (
        <p className="text-sm text-red-600">
          Greška pri učitavanju ulazne fakture:{" "}
          {error instanceof Error ? error.message : "Nepoznata greška"}
        </p>
      )}

      {invoice && (
        <>
          {/* Osnovne informacije */}
          <div className="grid grid-cols-1 gap-4 rounded-lg border bg-white p-4 text-sm text-slate-700 md:grid-cols-2">
            <div className="space-y-2">
              <div>
                <p className="text-[11px] uppercase tracking-wide text-slate-400">
                  Dobavljač
                </p>
                <p className="font-medium">{invoice.supplier_name}</p>
                {invoice.supplier_address && (
                  <p className="text-xs text-slate-500">
                    {invoice.supplier_address}
                  </p>
                )}
                {invoice.supplier_tax_id && (
                  <p className="text-xs text-slate-500">
                    PIB/JIB: {invoice.supplier_tax_id}
                  </p>
                )}
              </div>

              <div>
                <p className="text-[11px] uppercase tracking-wide text-slate-400">
                  Broj fakture
                </p>
                <p className="font-mono text-sm">
                  {invoice.invoice_number}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-slate-400">
                    Datum izdavanja
                  </p>
                  <p>{formatDate(invoice.issue_date)}</p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-slate-400">
                    Rok dospijeća
                  </p>
                  <p>{formatDate(invoice.due_date)}</p>
                </div>
              </div>

              {invoice.note && (
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-slate-400">
                    Interna napomena
                  </p>
                  <p className="text-xs text-slate-600 whitespace-pre-line">
                    {invoice.note}
                  </p>
                </div>
              )}
            </div>

            {/* Iznosi + tehnički info */}
            <div className="space-y-2">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-slate-400">
                    Osnovica bez PDV-a
                  </p>
                  <p className="font-mono">
                    {formatAmount(invoice.total_base)}
                  </p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-slate-400">
                    PDV iznos
                  </p>
                  <p className="font-mono">
                    {formatAmount(invoice.total_vat)}
                  </p>
                </div>
              </div>

              <div>
                <p className="text-[11px] uppercase tracking-wide text-slate-400">
                  Ukupno (osnovica + PDV)
                </p>
                <p className="text-lg font-semibold">
                  {formatAmount(invoice.total_amount)}{" "}
                  <span className="text-xs font-normal text-slate-400">
                    {invoice.currency}
                  </span>
                </p>
              </div>

              <div className="pt-2 text-xs text-slate-400 space-y-1">
                <p>
                  ID ulazne fakture:{" "}
                  <span className="font-mono text-slate-500">
                    {invoice.id}
                  </span>
                </p>
                <p>
                  Tenant:{" "}
                  <span className="font-mono text-slate-500">
                    {invoice.tenant_code}
                  </span>
                </p>
                <p>
                  Kreirano:{" "}
                  <span className="font-mono text-slate-500">
                    {formatDateTime(invoice.created_at)}
                  </span>
                </p>
              </div>
            </div>
          </div>

          {/* Povezani dokumenti (attachments) */}
          <div className="rounded-lg border bg-white p-4">
            <h3 className="mb-2 text-sm font-semibold text-slate-700">
              Priloženi dokumenti (računi / slike)
            </h3>

            {isAttachmentsLoading && (
              <p className="text-xs text-slate-600">
                Učitavam priložene dokumente...
              </p>
            )}

            {isAttachmentsError && (
              <p className="text-xs text-red-600">
                Greška pri učitavanju priloženih dokumenata:{" "}
                {attachmentsError?.message}
              </p>
            )}

            {!isAttachmentsLoading &&
              !isAttachmentsError &&
              linkedAttachments.length === 0 && (
                <p className="text-xs text-slate-500">
                  Nema dokumenata povezanih sa ovom ulaznom fakturom.
                  Dokument možeš prvo uploadovati kroz modul{" "}
                  <span className="font-semibold">
                    Uploadovani računi (attachments)
                  </span>{" "}
                  i zatim ga povezati sa konkretnom ulaznom fakturom.
                </p>
              )}

            {linkedAttachments.length > 0 && (
              <div className="mt-2 space-y-1">
                {linkedAttachments.map((att) => (
                  <div
                    key={att.id}
                    className="flex items-start justify-between gap-2 rounded-md border border-slate-100 bg-slate-50 px-3 py-2 text-xs text-slate-700"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">
                        {att.filename ?? `attachment-${att.id}`}
                      </p>
                      <p className="mt-0.5 text-[11px] text-slate-500">
                        {formatBytes(att.size_bytes)} · status:{" "}
                        <span className="font-semibold">
                          {att.status ?? "unknown"}
                        </span>
                      </p>
                    </div>
                    <div className="flex flex-shrink-0 items-center gap-1">
                      <button
                        type="button"
                        onClick={() => downloadInvoiceAttachment(att.id)}
                        className="rounded-md border border-slate-200 px-2 py-0.5 text-[11px] text-slate-700 hover:bg-slate-100"
                      >
                        Otvori / preuzmi
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      <div className="text-xs text-slate-500">
        <Link
          to="/input-invoices"
          className="underline underline-offset-2 hover:text-slate-700"
        >
          ← Nazad na listu ulaznih faktura
        </Link>
      </div>
    </div>
  );
}
