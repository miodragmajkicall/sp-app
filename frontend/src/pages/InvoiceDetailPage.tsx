// frontend/src/pages/InvoiceDetailPage.tsx
import { useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import type { InvoiceRowItem } from "../types/invoice";
import { apiClient } from "../services/apiClient";

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

  const invoice =
    (location.state as { invoice?: InvoiceRowItem } | null)?.invoice ?? null;

  const numericId = id ? Number(id) : null;

  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState("");

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

  // Ako je ekran otvoren direktno (bez state-a iz liste) nemamo pune podatke.
  if (!invoice) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-slate-800">
              Detalj fakture
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              ID fakture: <span className="font-mono">{id ?? "?"}</span>
            </p>
          </div>
          <button
            type="button"
            onClick={() => navigate("/invoices")}
            className="text-xs px-3 py-1.5 rounded-md border border-slate-300 bg-white hover:bg-slate-50"
          >
            ← Nazad na listu
          </button>
        </div>

        <div className="bg-amber-50 border border-amber-200 text-amber-800 text-sm rounded-lg p-4">
          <p className="font-semibold mb-1">Nedostupni detalji fakture</p>
          <p>
            Ovaj ekran je otvoren direktno bez podataka iz liste. U sljedećoj
            iteraciji možemo dodati poseban API za{" "}
            <code className="font-mono">GET /invoices/{":id"}</code> i ovdje
            fetchati podatke.
          </p>
        </div>

        {numericId != null && Number.isFinite(numericId) && (
          <div className="space-y-2">
            <button
              type="button"
              onClick={handleOpenPdf}
              disabled={pdfLoading}
              className="btn-primary text-xs disabled:opacity-60"
            >
              {pdfLoading ? "Pripremam PDF..." : "Preuzmi PDF fakture"}
            </button>
            {pdfError && (
              <p className="text-xs text-red-600 mt-1">{pdfError}</p>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header + back link */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">
            Faktura {invoice.number ?? `#${invoice.id}`}
          </h2>
        <p className="text-xs text-slate-500 mt-1">
            Detalji izlazne fakture za tenant{" "}
            <span className="font-mono">t-demo</span>.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {numericId != null && Number.isFinite(numericId) && (
            <button
              type="button"
              onClick={handleOpenPdf}
              disabled={pdfLoading}
              className="inline-flex items-center rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:bg-slate-800 disabled:opacity-60"
            >
              {pdfLoading ? "Pripremam PDF..." : "PDF fakture"}
            </button>
          )}

          <button
            type="button"
            onClick={() => navigate("/invoices")}
            className="inline-flex items-center rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50"
          >
            ← Nazad na listu
          </button>
        </div>
      </div>

      {/* Info kartica */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-white border rounded-lg p-4 text-sm text-slate-700">
        <div className="space-y-2">
          <div>
            <p className="text-[11px] uppercase tracking-wide text-slate-400">
              Broj fakture
            </p>
            <p className="font-medium">
              {invoice.number ?? <span className="text-slate-400">N/A</span>}
            </p>
          </div>

          <div>
            <p className="text-[11px] uppercase tracking-wide text-slate-400">
              Kupac
            </p>
            <p className="font-medium">
              {invoice.buyer_name ?? (
                <span className="text-slate-400">Nepoznat kupac</span>
              )}
            </p>
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
              Ukupni iznos
            </p>
            <p className="text-lg font-semibold">
              {formatAmount(invoice.total_amount)}
            </p>
          </div>

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

          <div className="text-xs text-slate-400 pt-2">
            <p>
              ID fakture:{" "}
              <span className="font-mono text-slate-500">{invoice.id}</span>
            </p>
            <p>
              Ruta:{" "}
              <span className="font-mono text-slate-500">
                /invoices/{invoice.id}
              </span>
            </p>
          </div>
        </div>
      </div>

      {/* PDF error ako postoji */}
      {pdfError && (
        <p className="text-xs text-red-600 mt-1">{pdfError}</p>
      )}

      {/* Brza navigacija */}
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
