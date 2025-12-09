// /home/miso/dev/sp-app/sp-app/frontend/src/pages/InvoiceDetailPage.tsx
import React, { useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import type { InvoiceRowItem, InvoiceDetail } from "../types/invoice";
import { apiClient } from "../services/apiClient";
import { fetchInvoiceById, markInvoicePaid } from "../services/invoicesApi";

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

export default function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  const numericId = id ? Number(id) : null;

  // Ako dolazimo iz liste, u state-u imamo osnovne podatke o fakturi
  const listInvoice =
    (location.state as { invoice?: InvoiceRowItem } | null)?.invoice ?? null;

  const {
    data: invoice,
    isLoading,
    isError,
    error,
  } = useQuery<InvoiceDetail>({
    queryKey: ["invoice-detail", numericId],
    enabled: numericId != null && Number.isFinite(numericId),
    queryFn: () => fetchInvoiceById(numericId as number),
  });

  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState("");
  const [statusSaving, setStatusSaving] = useState(false);
  const [statusError, setStatusError] = useState("");

  const handleOpenPdf = async () => {
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
  };

  const handleStatusChange = async (
    e: React.ChangeEvent<HTMLSelectElement>,
  ) => {
    if (!invoice || numericId == null || !Number.isFinite(numericId)) return;

    const value = e.target.value;
    setStatusError("");

    // Dozvoljavamo samo prelaz NIJE PLAĆENA -> PLAĆENA, jer backend ima samo /mark-paid
    if (value === "PAID" && !invoice.is_paid) {
      try {
        setStatusSaving(true);
        await markInvoicePaid(numericId);
        await queryClient.invalidateQueries({
          queryKey: ["invoice-detail", numericId],
        });
      } catch (err) {
        console.error(err);
        setStatusError("Greška pri ažuriranju statusa plaćanja.");
      } finally {
        setStatusSaving(false);
      }
    }
  };

  if (numericId == null || !Number.isFinite(numericId)) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-red-600">
          Nevalidan ID fakture u URL-u.
        </p>
        <button
          type="button"
          onClick={() => navigate("/invoices")}
          className="text-xs px-3 py-1.5 rounded-md border border-slate-300 bg-white hover:bg-slate-50"
        >
          ← Nazad na listu
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">
            {invoice
              ? `Faktura ${invoice.invoice_number}`
              : listInvoice
              ? `Faktura ${listInvoice.number ?? `#${listInvoice.id}`}`
              : "Detalj fakture"}
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Detalji izlazne fakture za tenant{" "}
            <span className="font-mono">t-demo</span>.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleOpenPdf}
            disabled={pdfLoading}
            className="inline-flex items-center rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:bg-slate-800 disabled:opacity-60"
          >
            {pdfLoading ? "Pripremam PDF..." : "PDF fakture"}
          </button>

          <button
            type="button"
            onClick={() => navigate("/invoices")}
            className="inline-flex items-center rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50"
          >
            ← Nazad na listu
          </button>
        </div>
      </div>

      {/* Loading / error */}
      {isLoading && (
        <p className="text-sm text-slate-600">Učitavam detalje fakture...</p>
      )}

      {isError && (
        <p className="text-sm text-red-600">
          Greška pri učitavanju fakture:{" "}
          {error instanceof Error ? error.message : "Nepoznata greška"}
        </p>
      )}

      {invoice && (
        <>
          {/* Info kartica */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-white border rounded-lg p-4 text-sm text-slate-700">
            <div className="space-y-2">
              <div>
                <p className="text-[11px] uppercase tracking-wide text-slate-400">
                  Broj fakture
                </p>
                <p className="font-medium">{invoice.invoice_number}</p>
              </div>

              <div>
                <p className="text-[11px] uppercase tracking-wide text-slate-400">
                  Kupac
                </p>
                <p className="font-medium">
                  {invoice.buyer_name || (
                    <span className="text-slate-400">Nepoznat kupac</span>
                  )}
                </p>
                {invoice.buyer_address && (
                  <p className="text-xs text-slate-500">
                    {invoice.buyer_address}
                  </p>
                )}
                {invoice.buyer_tax_id && (
                  <p className="text-xs text-slate-500">
                    JIB/PIB:{" "}
                    <span className="font-mono">
                      {invoice.buyer_tax_id}
                    </span>
                  </p>
                )}
              </div>

              <div>
                <p className="text-[11px] uppercase tracking-wide text-slate-400">
                  Datum izdavanja
                </p>
                <p>{formatDate(invoice.issue_date)}</p>
              </div>

              <div>
                <p className="text-[11px] uppercase tracking-wide text-slate-400">
                  Rok plaćanja
                </p>
                <p>{formatDate(invoice.due_date)}</p>
              </div>
            </div>

            <div className="space-y-2">
              <div>
                <p className="text-[11px] uppercase tracking-wide text-slate-400">
                  Neto osnovica
                </p>
                <p className="font-mono">
                  {formatAmount(invoice.total_base)}
                </p>
              </div>

              <div>
                <p className="text-[11px] uppercase tracking-wide text-slate-400">
                  PDV
                </p>
                <p className="font-mono">
                  {formatAmount(invoice.total_vat)}
                </p>
              </div>

              <div>
                <p className="text-[11px] uppercase tracking-wide text-slate-400">
                  Ukupni iznos (sa PDV-om)
                </p>
                <p className="text-lg font-semibold">
                  {formatAmount(invoice.total_amount)}
                </p>
              </div>

              <div>
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-[11px] uppercase tracking-wide text-slate-400">
                      Status plaćanja
                    </p>
                    {invoice.is_paid ? (
                      <span className="inline-flex rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                        PLAĆENA
                      </span>
                    ) : (
                      <span className="inline-flex rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700">
                        NIJE PLAĆENA
                      </span>
                    )}
                  </div>

                  <div className="text-right">
                    <label className="text-[11px] uppercase tracking-wide text-slate-400 block mb-1">
                      Promijeni status
                    </label>
                    <select
                      className="input text-xs py-1 px-2"
                      value={invoice.is_paid ? "PAID" : "UNPAID"}
                      onChange={handleStatusChange}
                      disabled={statusSaving}
                    >
                      <option value="UNPAID">NIJE PLAĆENA</option>
                      <option value="PAID">PLAĆENA</option>
                    </select>
                    {statusError && (
                      <p className="text-[11px] text-red-600 mt-1">
                        {statusError}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              <div className="text-xs text-slate-400 pt-2">
                <p>
                  ID fakture:{" "}
                  <span className="font-mono text-slate-500">
                    {invoice.id}
                  </span>
                </p>
                <p>
                  Ruta:{" "}
                  <span className="font-mono text-slate-500">
                    /invoices/{invoice.id}
                  </span>
                </p>
                <p>
                  Tenant:{" "}
                  <span className="font-mono text-slate-500">
                    {invoice.tenant_code}
                  </span>
                </p>
              </div>
            </div>
          </div>

          {/* Napomena fakture, ako postoji */}
          {invoice.note && (
            <div className="bg-white border rounded-lg p-4 text-sm text-slate-700">
              <h3 className="text-sm font-semibold text-slate-700 mb-2">
                Napomena fakture
              </h3>
              <p className="text-xs whitespace-pre-line text-slate-600">
                {invoice.note}
              </p>
            </div>
          )}

          {/* Stavke fakture */}
          <div className="bg-white border rounded-lg p-4">
            <h3 className="text-sm font-semibold text-slate-700 mb-3">
              Stavke fakture
            </h3>

            {invoice.items.length === 0 ? (
              <p className="text-xs text-slate-500">
                Nema stavki evidentiranih za ovu fakturu.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-slate-500">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium">
                        Opis stavke
                      </th>
                      <th className="px-3 py-2 text-right font-medium">
                        Količina
                      </th>
                      <th className="px-3 py-2 text-right font-medium">
                        Jed. cijena (bez PDV)
                      </th>
                      <th className="px-3 py-2 text-right font-medium">
                        Popust %
                      </th>
                      <th className="px-3 py-2 text-right font-medium">
                        PDV %
                      </th>
                      <th className="px-3 py-2 text-right font-medium">
                        Osnovica
                      </th>
                      <th className="px-3 py-2 text-right font-medium">
                        PDV
                      </th>
                      <th className="px-3 py-2 text-right font-medium">
                        Ukupno (sa PDV)
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {invoice.items.map((item) => (
                      <tr key={item.id}>
                        <td className="px-3 py-2">
                          {item.description}
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {item.quantity.toFixed(2)}
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {item.unit_price.toFixed(2)} KM
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {item.discount_percent.toFixed(2)}%
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {(item.vat_rate * 100).toFixed(0)}%
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {item.base_amount.toFixed(2)} KM
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {item.vat_amount.toFixed(2)} KM
                        </td>
                        <td className="px-3 py-2 text-right font-mono">
                          {item.total_amount.toFixed(2)} KM
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {pdfError && (
        <p className="text-xs text-red-600 mt-1">{pdfError}</p>
      )}

      <div className="text-xs text-slate-500">
        <Link
          to="/invoices"
          className="underline underline-offset-2 hover:text-slate-700"
        >
          ← Nazad na listu izlaznih faktura
        </Link>
      </div>
    </div>
  );
}
