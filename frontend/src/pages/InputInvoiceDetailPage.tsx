// /home/miso/dev/sp-app/sp-app/frontend/src/pages/InputInvoiceDetailPage.tsx
import {
  useEffect,
  useState,
  type FormEvent,
} from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  getInputInvoice,
  updateInputInvoice,
  fetchInvoiceAttachments,
  downloadInvoiceAttachment,
  linkAttachmentToInputInvoice,
  type InvoiceAttachmentItem,
} from "../services/inputInvoicesApi";
import type { InputInvoiceDetail } from "../types/inputInvoice";

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
  const queryClient = useQueryClient();

  const numericId = id ? Number(id) : NaN;

  // ==========================
  //  QUERY: detalj ulazne fakture
  // ==========================
  const {
    data: invoice,
    isLoading,
    isError,
    error,
  } = useQuery<InputInvoiceDetail, Error>({
    queryKey: ["input-invoice", numericId],
    enabled: Number.isFinite(numericId),
    queryFn: () => getInputInvoice(numericId),
  });

  // ==========================
  //  QUERY: attachment-i (tenant-wide)
  // ==========================
  const {
    data: attachments,
    isLoading: attachmentsLoading,
    isError: attachmentsError,
    error: attachmentsErrorObj,
  } = useQuery<InvoiceAttachmentItem[], Error>({
    queryKey: ["invoice-attachments"],
    queryFn: fetchInvoiceAttachments,
  });

  // ==========================
  //  LOCAL STATE za edit formu
  // ==========================
  const [supplierName, setSupplierName] = useState("");
  const [supplierTaxId, setSupplierTaxId] = useState("");
  const [supplierAddress, setSupplierAddress] = useState("");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [issueDate, setIssueDate] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [totalBase, setTotalBase] = useState("");
  const [totalVat, setTotalVat] = useState("");
  const [currency, setCurrency] = useState("BAM");
  const [note, setNote] = useState("");

  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (!invoice) return;

    setSupplierName(invoice.supplier_name ?? "");
    setSupplierTaxId(invoice.supplier_tax_id ?? "");
    setSupplierAddress(invoice.supplier_address ?? "");
    setInvoiceNumber(invoice.invoice_number ?? "");
    setIssueDate(invoice.issue_date ?? "");
    setDueDate(invoice.due_date ?? "");
    setTotalBase(
      invoice.total_base != null ? invoice.total_base.toString() : "",
    );
    setTotalVat(
      invoice.total_vat != null ? invoice.total_vat.toString() : "",
    );
    setCurrency(invoice.currency ?? "BAM");
    setNote(invoice.note ?? "");
  }, [invoice]);

  const parsedBase = parseFloat(totalBase || "0");
  const parsedVat = parseFloat(totalVat || "0");
  const totalAmount =
    Number.isFinite(parsedBase) && Number.isFinite(parsedVat)
      ? parsedBase + parsedVat
      : 0;

  // ==========================
  //  MUTATION: update fakture
  // ==========================
  const updateMutation = useMutation({
    mutationFn: async () => {
      if (!invoice) return;

      const base = parseFloat(totalBase || "0");
      const vat = parseFloat(totalVat || "0");

      if (
        !supplierName.trim() ||
        !invoiceNumber.trim() ||
        !issueDate ||
        !Number.isFinite(base) ||
        !Number.isFinite(vat) ||
        base < 0 ||
        vat < 0 ||
        base + vat <= 0
      ) {
        throw new Error(
          "Obavezna polja: dobavljač, broj fakture, datum izdavanja i iznosi (osnovica i PDV ≥ 0, ukupan iznos > 0).",
        );
      }

      await updateInputInvoice(invoice.id, {
        supplier_name: supplierName.trim(),
        supplier_tax_id: supplierTaxId.trim() || null,
        supplier_address: supplierAddress.trim() || null,
        invoice_number: invoiceNumber.trim(),
        issue_date: issueDate,
        due_date: dueDate || null,
        total_base: parseFloat(base.toFixed(2)),
        total_vat: parseFloat(vat.toFixed(2)),
        total_amount: parseFloat((base + vat).toFixed(2)),
        currency: currency.trim() || "BAM",
        note: note.trim() || null,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["input-invoices"] });
      queryClient.invalidateQueries({
        queryKey: ["input-invoice", numericId],
      });
    },
  });

  const isSaving = updateMutation.isPending;

  useEffect(() => {
    if (updateMutation.error) {
      const err = updateMutation.error as Error;
      setErrorMsg(
        err.message ||
          "Greška pri snimanju ulazne fakture (moguće je da je mjesec finalizovan ili postoji dupli broj).",
      );
    } else {
      setErrorMsg("");
    }
  }, [updateMutation.error]);

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErrorMsg("");
    updateMutation.mutate();
  };

  const handleDownloadAttachment = (id: number) => {
    void downloadInvoiceAttachment(id);
  };

  // ==========================
  //  MUTATION: link attachment → input invoice
  // ==========================
  const linkMutation = useMutation({
    mutationFn: async (attachmentId: number) => {
      if (!invoice) {
        throw new Error("Faktura nije učitana.");
      }
      return linkAttachmentToInputInvoice(attachmentId, invoice.id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoice-attachments"] });
    },
  });

  const isLinking = linkMutation.isPending;

  if (!Number.isFinite(numericId)) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-red-600">
          Neispravan ID ulazne fakture.
        </p>
        <button
          type="button"
          onClick={() => navigate("/input-invoices")}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
        >
          ← Nazad na listu ulaznih faktura
        </button>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-slate-600">
          Učitavam ulaznu fakturu...
        </p>
      </div>
    );
  }

  if (isError || !invoice) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-red-600">
          Greška pri učitavanju ulazne fakture: {error?.message ?? "Nije pronađena."}
        </p>
        <button
          type="button"
          onClick={() => navigate("/input-invoices")}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
        >
          ← Nazad na listu ulaznih faktura
        </button>
      </div>
    );
  }

  // filtriramo attachment-e
  const linkedAttachments: InvoiceAttachmentItem[] =
    attachments?.filter((att) => att.input_invoice_id === invoice.id) ?? [];

  const availableAttachments: InvoiceAttachmentItem[] =
    attachments?.filter((att) => att.input_invoice_id == null) ?? [];

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
      {/* FORM / DETALJ FAKTURE */}
      <div className="space-y-5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-slate-800">
              Ulazna faktura {invoice.invoice_number}
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Dobavljač:{" "}
              <span className="font-semibold">
                {invoice.supplier_name}
              </span>
              {" · "}Tenant:{" "}
              <span className="font-mono text-slate-600">
                {invoice.tenant_code}
              </span>
            </p>
            <p className="mt-0.5 text-[11px] text-slate-400">
              Kreirana: {formatDate(invoice.created_at)} · ID:{" "}
              <span className="font-mono">{invoice.id}</span>
            </p>
          </div>

          <button
            type="button"
            onClick={() => navigate("/input-invoices")}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50"
          >
            ← Nazad na listu
          </button>
        </div>

        <form
          onSubmit={handleSubmit}
          className="space-y-6 rounded-lg border bg-white p-5"
        >
          {/* DOBAVLJAČ */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <label className="text-xs font-medium">
                Dobavljač *
              </label>
              <input
                type="text"
                required
                value={supplierName}
                onChange={(e) => setSupplierName(e.target.value)}
                className="input"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium">
                PIB / JIB dobavljača
              </label>
              <input
                type="text"
                value={supplierTaxId}
                onChange={(e) => setSupplierTaxId(e.target.value)}
                className="input"
              />
            </div>

            <div className="space-y-1 md:col-span-2">
              <label className="text-xs font-medium">
                Adresa dobavljača
              </label>
              <input
                type="text"
                value={supplierAddress}
                onChange={(e) => setSupplierAddress(e.target.value)}
                className="input"
              />
            </div>
          </div>

          {/* OSNOVNI PODACI */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-1">
              <label className="text-xs font-medium">
                Broj fakture *
              </label>
              <input
                type="text"
                required
                value={invoiceNumber}
                onChange={(e) => setInvoiceNumber(e.target.value)}
                className="input"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium">Valuta</label>
              <input
                type="text"
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="input"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium">
                Datum izdavanja *
              </label>
              <input
                type="date"
                required
                value={issueDate}
                onChange={(e) => setIssueDate(e.target.value)}
                className="input"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium">
                Rok dospijeća
              </label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="input"
              />
            </div>
          </div>

          {/* IZNOSI */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="space-y-1">
              <label className="text-xs font-medium">
                Osnovica bez PDV-a *
              </label>
              <input
                type="number"
                min={0}
                step="0.01"
                value={totalBase}
                onChange={(e) => setTotalBase(e.target.value)}
                className="input"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium">PDV *</label>
              <input
                type="number"
                min={0}
                step="0.01"
                value={totalVat}
                onChange={(e) => setTotalVat(e.target.value)}
                className="input"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium">
                Ukupno (osn. + PDV)
              </label>
              <div className="input flex items-center justify-end bg-slate-50 text-right">
                <span className="text-xs text-slate-700">
                  {totalAmount > 0 ? totalAmount.toFixed(2) : "0.00"}{" "}
                  {currency || "BAM"}
                </span>
              </div>
            </div>
          </div>

          {/* NAPOMENA */}
          <div className="space-y-1">
            <label className="text-xs font-medium">
              Interna napomena
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="input min-h-[80px]"
            />
          </div>

          {/* ERROR + SUBMIT */}
          <div className="flex flex-col gap-3 border-t pt-3 md:flex-row md:items-center md:justify-between">
            <div>
              {errorMsg && (
                <p className="mt-1 text-sm text-red-600">{errorMsg}</p>
              )}
            </div>

            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => navigate("/input-invoices")}
                className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
              >
                Otkaži
              </button>
              <button
                type="submit"
                disabled={isSaving}
                className="btn-primary w-full text-xs md:w-auto"
              >
                {isSaving ? "Spremam..." : "Snimi izmjene"}
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* ATTACHMENTS ZA OVU FAKTURU + LINKOVANJE */}
      <div className="space-y-3">
        <div className="rounded-lg border bg-white p-4">
          <h3 className="text-sm font-semibold text-slate-800">
            Attachment-i ove ulazne fakture
          </h3>
          <p className="mt-1 text-[11px] text-slate-500">
            Fajlovi koji su već povezani sa ovom ulaznom fakturom.
          </p>

          <div className="mt-3 max-h-64 space-y-1 overflow-y-auto rounded-md border border-slate-100 bg-slate-50 p-2">
            {attachmentsLoading && (
              <p className="text-xs text-slate-600">
                Učitavam attachment-e...
              </p>
            )}

            {attachmentsError && (
              <p className="text-xs text-red-600">
                Greška pri učitavanju attachment-a:{" "}
                {attachmentsErrorObj?.message}
              </p>
            )}

            {!attachmentsLoading &&
              !attachmentsError &&
              linkedAttachments.length === 0 && (
                <p className="text-xs text-slate-500">
                  Trenutno nema attachment-a povezanih sa ovom ulaznom
                  fakturom.
                </p>
              )}

            {linkedAttachments.map((att) => (
              <div
                key={att.id}
                className="flex items-start justify-between gap-2 rounded-md bg-white px-2 py-1.5 text-xs text-slate-700 shadow-sm"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">
                    {att.filename ?? `attachment-${att.id}`}
                  </p>
                  <p className="mt-0.5 text-[11px] text-slate-400">
                    {formatBytes(att.size_bytes)} · status:{" "}
                    <span className="font-semibold">
                      {att.status ?? "unknown"}
                    </span>
                  </p>
                </div>
                <div className="flex flex-shrink-0 items-center gap-1">
                  <button
                    type="button"
                    onClick={() => handleDownloadAttachment(att.id)}
                    className="rounded-md border border-slate-200 px-2 py-0.5 text-[11px] text-slate-700 hover:bg-slate-50"
                  >
                    Preuzmi
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* SEKCIJA: dostupni attachment-i koji još nisu povezani */}
        <div className="rounded-lg border bg-white p-4">
          <h3 className="text-sm font-semibold text-slate-800">
            Dostupni attachment-i (nepovezani)
          </h3>
          <p className="mt-1 text-[11px] text-slate-500">
            Attachment-i koji su uploadovani za tenant{" "}
            <span className="font-mono">t-demo</span>, ali još nisu
            povezani ni sa jednom ulaznom fakturom. Ovdje ih možeš
            direktno povezati sa ovom fakturom.
          </p>

          <div className="mt-3 max-h-64 space-y-1 overflow-y-auto rounded-md border border-slate-100 bg-slate-50 p-2">
            {attachmentsLoading && (
              <p className="text-xs text-slate-600">
                Učitavam attachment-e...
              </p>
            )}

            {attachmentsError && (
              <p className="text-xs text-red-600">
                Greška pri učitavanju attachment-a:{" "}
                {attachmentsErrorObj?.message}
              </p>
            )}

            {!attachmentsLoading &&
              !attachmentsError &&
              availableAttachments.length === 0 && (
                <p className="text-xs text-slate-500">
                  Trenutno nema nepovezanih attachment-a.
                </p>
              )}

            {availableAttachments.map((att) => (
              <div
                key={att.id}
                className="flex items-start justify-between gap-2 rounded-md bg-white px-2 py-1.5 text-xs text-slate-700 shadow-sm"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">
                    {att.filename ?? `attachment-${att.id}`}
                  </p>
                  <p className="mt-0.5 text-[11px] text-slate-400">
                    {formatBytes(att.size_bytes)} · status:{" "}
                    <span className="font-semibold">
                      {att.status ?? "unknown"}
                    </span>
                  </p>
                </div>
                <div className="flex flex-shrink-0 items-center gap-1">
                  <button
                    type="button"
                    onClick={() => handleDownloadAttachment(att.id)}
                    className="rounded-md border border-slate-200 px-2 py-0.5 text-[11px] text-slate-700 hover:bg-slate-50"
                  >
                    Pregled
                  </button>
                  <button
                    type="button"
                    disabled={isLinking}
                    onClick={() => linkMutation.mutate(att.id)}
                    className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 hover:bg-emerald-100 disabled:opacity-60"
                  >
                    {isLinking ? "Povezujem..." : "Poveži sa ovom fakturom"}
                  </button>
                </div>
              </div>
            ))}
          </div>

          {linkMutation.error && (
            <p className="mt-2 text-[11px] text-red-600">
              Greška pri povezivanju attachment-a:{" "}
              {(linkMutation.error as Error).message}
            </p>
          )}
        </div>

        <div className="rounded-lg border border-dashed border-amber-200 bg-amber-50 p-3 text-[11px] text-amber-800">
          <p className="font-semibold">Napomena</p>
          <p className="mt-1">
            Upload attachment-a radiš i dalje u ekranu{" "}
            <strong>Ulazne fakture</strong> (desni panel). Ovdje na
            detalju fakture sada možeš nepovezane fajlove direktno
            vezati za ovu ulaznu fakturu, koristeći backend endpoint{" "}
            <span className="font-mono">
              POST /invoice-attachments/{"{id}"}/link-to-input-invoice
            </span>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
