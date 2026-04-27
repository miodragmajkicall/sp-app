// /home/miso/dev/sp-app/sp-app/frontend/src/pages/InputInvoiceCreatePage.tsx
import { useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import {
  createInputInvoice,
  deleteInvoiceAttachment,
  linkAttachmentToInputInvoice,
  uploadInvoiceAttachment,
  type InvoiceAttachmentItem,
} from "../services/inputInvoicesApi";

const VAT_RATE = 0.17;

const EXPENSE_CATEGORY_OPTIONS = [
  "",
  "Gorivo",
  "Kancelarijski materijal",
  "Komunalije",
  "Telekom usluge",
  "Usluge trećih lica",
  "Ostali troškovi",
];

function formatAmount(value: number, currency = "BAM"): string {
  return `${value > 0 ? value.toFixed(2) : "0.00"} ${currency || "BAM"}`;
}

export default function InputInvoiceCreatePage() {
  const navigate = useNavigate();

  const [supplierName, setSupplierName] = useState("");
  const [supplierTaxId, setSupplierTaxId] = useState("");
  const [supplierAddress, setSupplierAddress] = useState("");

  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [issueDate, setIssueDate] = useState("");
  const [postingDate, setPostingDate] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [currency, setCurrency] = useState("BAM");

  const [expenseCategory, setExpenseCategory] = useState("");
  const [isTaxDeductible, setIsTaxDeductible] = useState(true);
  const [isPaid, setIsPaid] = useState(false);

  const [includeVat, setIncludeVat] = useState(true);
  const [baseStr, setBaseStr] = useState("");
  const [totalStr, setTotalStr] = useState("");

  const [note, setNote] = useState("");

  const [attachments, setAttachments] = useState<InvoiceAttachmentItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const numericBase = parseFloat(baseStr.replace(",", ".") || "0") || 0;
  const numericTotal = parseFloat(totalStr.replace(",", ".") || "0") || 0;

  let totalBase = numericBase;
  let totalAmount = numericTotal;
  let totalVat = 0;

  if (includeVat) {
    if (baseStr !== "" && (totalStr === "" || !Number.isFinite(numericTotal))) {
      totalBase = numericBase;
      totalVat = totalBase * VAT_RATE;
      totalAmount = totalBase + totalVat;
    } else if (
      totalStr !== "" &&
      (baseStr === "" || !Number.isFinite(numericBase))
    ) {
      totalAmount = numericTotal;
      totalBase = totalAmount / (1 + VAT_RATE);
      totalVat = totalAmount - totalBase;
    } else {
      totalBase = numericBase;
      totalVat = totalBase * VAT_RATE;
      totalAmount = totalBase + totalVat;
    }
  } else {
    if (baseStr !== "" && (totalStr === "" || !Number.isFinite(numericTotal))) {
      totalBase = numericBase;
      totalAmount = totalBase;
    } else if (
      totalStr !== "" &&
      (baseStr === "" || !Number.isFinite(numericBase))
    ) {
      totalAmount = numericTotal;
      totalBase = totalAmount;
    } else {
      totalBase = numericBase;
      totalAmount = totalBase;
    }
    totalVat = 0;
  }

  const displayVat = includeVat ? totalVat : 0;

  function handleBaseChange(e: ChangeEvent<HTMLInputElement>) {
    const value = e.target.value;
    setBaseStr(value);

    const v = parseFloat(value.replace(",", "."));
    if (!Number.isFinite(v)) return;

    if (includeVat) {
      setTotalStr((v + v * VAT_RATE).toFixed(2));
    } else {
      setTotalStr(v.toFixed(2));
    }
  }

  function handleTotalChange(e: ChangeEvent<HTMLInputElement>) {
    const value = e.target.value;
    setTotalStr(value);

    const v = parseFloat(value.replace(",", "."));
    if (!Number.isFinite(v)) return;

    if (includeVat) {
      setBaseStr((v / (1 + VAT_RATE)).toFixed(2));
    } else {
      setBaseStr(v.toFixed(2));
    }
  }

  function handleToggleVat(e: ChangeEvent<HTMLInputElement>) {
    const checked = e.target.checked;
    setIncludeVat(checked);

    const base = parseFloat(baseStr.replace(",", ".") || "0");
    if (!Number.isFinite(base)) return;

    if (checked) {
      const total = base + base * VAT_RATE;
      setTotalStr(total > 0 ? total.toFixed(2) : totalStr);
    } else {
      setTotalStr(base.toFixed(2));
    }
  }

  async function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadError(null);
    setIsUploading(true);

    try {
      const uploaded = await uploadInvoiceAttachment(file);
      setAttachments((prev) => [...prev, uploaded]);
    } catch (err: any) {
      setUploadError(
        err?.message ?? "Greška pri uploadu fajla. Pokušaj ponovo.",
      );
    } finally {
      setIsUploading(false);
      e.target.value = "";
    }
  }

  async function handleRemoveAttachment(att: InvoiceAttachmentItem) {
    if (!window.confirm("Da li sigurno želiš obrisati ovaj prilog?")) return;

    try {
      await deleteInvoiceAttachment(att.id);
      setAttachments((prev) => prev.filter((a) => a.id !== att.id));
    } catch (err: any) {
      alert(err?.message ?? "Greška pri brisanju priloga. Pokušaj ponovo.");
    }
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    setErrorMsg("");

    if (!supplierName.trim() || !invoiceNumber.trim() || !issueDate) {
      setSaving(false);
      setErrorMsg("Obavezna polja: dobavljač, broj fakture i datum izdavanja.");
      return;
    }

    if (totalBase < 0 || totalAmount <= 0 || totalVat < 0) {
      setSaving(false);
      setErrorMsg(
        "Iznosi moraju biti ≥ 0, a ukupno mora biti veće od 0.",
      );
      return;
    }

    const effectivePostingDate = postingDate || issueDate || null;

    try {
      const created = await createInputInvoice({
        supplier_name: supplierName.trim(),
        supplier_tax_id: supplierTaxId.trim() || null,
        supplier_address: supplierAddress.trim() || null,
        invoice_number: invoiceNumber.trim(),
        issue_date: issueDate,
        posting_date: effectivePostingDate,
        due_date: dueDate || null,
        expense_category: expenseCategory || null,
        is_tax_deductible: isTaxDeductible,
        is_paid: isPaid,
        total_base: parseFloat(totalBase.toFixed(2)),
        total_vat: parseFloat(displayVat.toFixed(2)),
        total_amount: parseFloat(totalAmount.toFixed(2)),
        currency: currency.trim() || "BAM",
        note: note.trim() || null,
      });

      if (attachments.length > 0) {
        await Promise.all(
          attachments.map((att) =>
            linkAttachmentToInputInvoice(att.id, created.id),
          ),
        );
      }

      navigate("/input-invoices");
    } catch (err: any) {
      setErrorMsg(
        err?.message ??
          "Greška pri snimanju ulazne fakture. Provjeri da li kombinacija dobavljač + broj već postoji.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 px-6 py-7 text-white sm:px-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <div className="inline-flex items-center rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs font-medium text-slate-200">
                Ulazne fakture · Nova faktura
              </div>
              <div>
                <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                  Kreiranje nove ulazne fakture
                </h1>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                  Unesi račun dobavljača, obračunaj PDV, označi poreski status i
                  priloži PDF ili sliku računa.
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

        <div className="grid gap-4 border-t border-slate-200 bg-slate-50 px-6 py-5 sm:grid-cols-2 lg:grid-cols-4 sm:px-8">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-medium text-slate-500">Dobavljač</p>
            <p className="mt-1 truncate text-lg font-semibold text-slate-900">
              {supplierName.trim() || "Nije unesen"}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-medium text-slate-500">Osnovica</p>
            <p className="mt-1 font-mono text-lg font-semibold text-slate-900">
              {formatAmount(totalBase, currency)}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-medium text-slate-500">PDV</p>
            <p className="mt-1 font-mono text-lg font-semibold text-slate-900">
              {formatAmount(displayVat, currency)}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-medium text-slate-500">Ukupno</p>
            <p className="mt-1 font-mono text-lg font-semibold text-slate-900">
              {formatAmount(totalAmount, currency)}
            </p>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="grid gap-6 lg:grid-cols-[1fr,380px]">
        <div className="space-y-6">
          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <div className="mb-5 border-b border-slate-100 pb-4">
              <h2 className="text-base font-semibold text-slate-900">
                Dobavljač
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Osnovni podaci o firmi ili licu koje je izdalo račun.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Dobavljač *
                </label>
                <input
                  type="text"
                  required
                  value={supplierName}
                  onChange={(e) => setSupplierName(e.target.value)}
                  className="input"
                  placeholder="npr. Elektrodistribucija Banja Luka"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                  PIB / JIB dobavljača
                </label>
                <input
                  type="text"
                  value={supplierTaxId}
                  onChange={(e) => setSupplierTaxId(e.target.value)}
                  className="input"
                  placeholder="npr. 1234567890000"
                />
              </div>

              <div className="md:col-span-2">
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Adresa dobavljača
                </label>
                <input
                  type="text"
                  value={supplierAddress}
                  onChange={(e) => setSupplierAddress(e.target.value)}
                  className="input"
                  placeholder="npr. Kralja Petra I Karađorđevića 15, Banja Luka"
                />
              </div>
            </div>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <div className="mb-5 border-b border-slate-100 pb-4">
              <h2 className="text-base font-semibold text-slate-900">
                Podaci o fakturi
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Broj dokumenta, datumi, valuta, kategorija i statusi.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Broj fakture *
                </label>
                <input
                  type="text"
                  required
                  value={invoiceNumber}
                  onChange={(e) => setInvoiceNumber(e.target.value)}
                  className="input"
                  placeholder="npr. 2026-INV-001"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Valuta
                </label>
                <input
                  type="text"
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                  className="input"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Datum izdavanja *
                </label>
                <input
                  type="date"
                  required
                  value={issueDate}
                  onChange={(e) => {
                    const val = e.target.value;
                    setIssueDate(val);
                    setPostingDate((prev) => (prev ? prev : val));
                  }}
                  className="input"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Datum knjiženja
                </label>
                <input
                  type="date"
                  value={postingDate}
                  onChange={(e) => setPostingDate(e.target.value)}
                  className="input"
                />
                <p className="mt-1.5 text-xs text-slate-400">
                  Ako ostane prazno, koristi se datum izdavanja.
                </p>
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Rok dospijeća
                </label>
                <input
                  type="date"
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                  className="input"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Kategorija troška
                </label>
                <select
                  value={expenseCategory}
                  onChange={(e) => setExpenseCategory(e.target.value)}
                  className="input"
                >
                  {EXPENSE_CATEGORY_OPTIONS.map((opt) => (
                    <option key={opt || "all"} value={opt}>
                      {opt === "" ? "— Bez kategorije —" : opt}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 transition hover:bg-slate-100">
                <input
                  id="is-tax-deductible"
                  type="checkbox"
                  className="mt-1 h-4 w-4 rounded border-slate-300 text-slate-900"
                  checked={isTaxDeductible}
                  onChange={(e) => setIsTaxDeductible(e.target.checked)}
                />
                <span>
                  <span className="block text-sm font-semibold text-slate-900">
                    Priznat rashod
                  </span>
                  <span className="mt-1 block text-xs leading-5 text-slate-500">
                    Trošak ulazi u KPR / poresku osnovicu.
                  </span>
                </span>
              </label>

              <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 transition hover:bg-slate-100">
                <input
                  id="is-paid"
                  type="checkbox"
                  className="mt-1 h-4 w-4 rounded border-slate-300 text-slate-900"
                  checked={isPaid}
                  onChange={(e) => setIsPaid(e.target.checked)}
                />
                <span>
                  <span className="block text-sm font-semibold text-slate-900">
                    Plaćeno
                  </span>
                  <span className="mt-1 block text-xs leading-5 text-slate-500">
                    Označi ako je račun već plaćen kroz kasu/banku.
                  </span>
                </span>
              </label>
            </div>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <div className="mb-5 border-b border-slate-100 pb-4">
              <h2 className="text-base font-semibold text-slate-900">
                Obračun iznosa
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Unesi osnovicu ili ukupno — drugo polje se računa automatski.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Osnovica bez PDV-a *
                </label>
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={baseStr}
                  onChange={handleBaseChange}
                  className="input"
                  placeholder="npr. 100.00"
                />
              </div>

              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    PDV 17%
                  </span>
                  <span className="font-mono text-sm font-bold text-slate-900">
                    {formatAmount(displayVat, currency)}
                  </span>
                </div>
                <label className="mt-4 flex cursor-pointer items-start gap-2">
                  <input
                    id="include-vat"
                    type="checkbox"
                    className="mt-1 h-4 w-4 rounded border-slate-300 text-slate-900"
                    checked={includeVat}
                    onChange={handleToggleVat}
                  />
                  <span className="text-xs leading-5 text-slate-600">
                    Uključi PDV u obračun. Stopa je fiksna 17%.
                  </span>
                </label>
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Ukupno
                </label>
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={totalStr}
                  onChange={handleTotalChange}
                  className="input text-right"
                  placeholder="npr. 117.00"
                />
              </div>
            </div>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <div className="mb-5 border-b border-slate-100 pb-4">
              <h2 className="text-base font-semibold text-slate-900">
                Napomena i prilozi
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Interna napomena i upload PDF/slike računa.
              </p>
            </div>

            <div className="grid gap-5 lg:grid-cols-2">
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Interna napomena
                </label>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  className="input min-h-[150px] resize-none"
                  placeholder="npr. Račun za struju za oktobar."
                />
              </div>

              <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4">
                <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Prilaganje računa
                </label>
                <input
                  type="file"
                  accept="application/pdf,image/*"
                  onChange={handleFileChange}
                  disabled={isUploading}
                  className="block w-full text-xs text-slate-700 file:mr-3 file:rounded-xl file:border-0 file:bg-slate-950 file:px-4 file:py-2 file:text-xs file:font-bold file:text-white hover:file:bg-slate-800"
                />

                {isUploading && (
                  <p className="mt-2 text-xs text-slate-500">
                    Uploadujem fajl...
                  </p>
                )}
                {uploadError && (
                  <p className="mt-2 text-xs text-red-600">{uploadError}</p>
                )}

                {attachments.length > 0 && (
                  <div className="mt-4 space-y-2">
                    {attachments.map((att) => (
                      <div
                        key={att.id}
                        className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 shadow-sm"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-semibold">
                            {att.filename ?? `attachment-${att.id}`}
                          </p>
                          <p className="mt-0.5 text-[11px] text-slate-400">
                            ID: {att.id} · status:{" "}
                            <span className="font-semibold">
                              {att.status ?? "n/a"}
                            </span>
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => void handleRemoveAttachment(att)}
                          className="rounded-xl border border-red-100 px-3 py-1.5 text-[11px] font-semibold text-red-600 hover:bg-red-50"
                        >
                          Ukloni
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                <p className="mt-3 text-xs leading-5 text-slate-500">
                  Fajl će biti automatski povezan sa ovom ulaznom fakturom nakon
                  snimanja.
                </p>
              </div>
            </div>
          </section>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          <section className="rounded-3xl border border-slate-800 bg-slate-950 p-5 text-white shadow-xl">
            <div className="border-b border-white/10 pb-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                Live rezime
              </p>
              <h2 className="mt-1 text-lg font-semibold">Ukupni trošak</h2>
            </div>

            <div className="space-y-3 py-4 text-sm">
              <div className="flex items-center justify-between gap-4">
                <span className="text-slate-300">Osnovica</span>
                <span className="font-mono font-semibold">
                  {formatAmount(totalBase, currency)}
                </span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-slate-300">PDV</span>
                <span className="font-mono font-semibold">
                  {formatAmount(displayVat, currency)}
                </span>
              </div>
              <div className="flex items-center justify-between gap-4 border-t border-white/10 pt-4">
                <span className="text-base font-semibold text-white">
                  Ukupno
                </span>
                <span className="font-mono text-xl font-bold">
                  {formatAmount(totalAmount, currency)}
                </span>
              </div>
            </div>

            {errorMsg ? (
              <div className="mb-4 rounded-2xl border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-100">
                {errorMsg}
              </div>
            ) : (
              <div className="mb-4 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-xs leading-5 text-slate-300">
                Obavezno: dobavljač, broj fakture, datum izdavanja i pozitivan
                iznos.
              </div>
            )}

            <button
              type="submit"
              disabled={saving}
              className="w-full rounded-2xl bg-white px-4 py-3 text-sm font-bold text-slate-950 shadow-sm transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? "Spremam fakturu..." : "Snimi ulaznu fakturu"}
            </button>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900">
              Kontrola prije snimanja
            </h3>

            <div className="mt-4 space-y-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-500">Dobavljač</span>
                <span className="font-semibold text-slate-900">
                  {supplierName.trim() ? "Popunjeno" : "Nedostaje"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-500">Broj fakture</span>
                <span className="font-semibold text-slate-900">
                  {invoiceNumber.trim() ? "Popunjeno" : "Nedostaje"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-500">Datum izdavanja</span>
                <span className="font-semibold text-slate-900">
                  {issueDate ? "Popunjeno" : "Nedostaje"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-500">Prilozi</span>
                <span className="font-semibold text-slate-900">
                  {attachments.length}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-500">Poreski status</span>
                <span className="font-semibold text-slate-900">
                  {isTaxDeductible ? "Priznat rashod" : "Nepriznat"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-500">Plaćanje</span>
                <span className="font-semibold text-slate-900">
                  {isPaid ? "Plaćeno" : "Nije plaćeno"}
                </span>
              </div>
            </div>
          </section>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => navigate("/input-invoices")}
              className="w-full rounded-2xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
            >
              Otkaži
            </button>
          </div>
        </aside>
      </form>
    </div>
  );
}