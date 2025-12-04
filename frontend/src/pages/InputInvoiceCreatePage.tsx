// /home/miso/dev/sp-app/sp-app/frontend/src/pages/InputInvoiceCreatePage.tsx
import { useState, type FormEvent, type ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  createInputInvoice,
  uploadInvoiceAttachment,
  deleteInvoiceAttachment,
  linkAttachmentToInputInvoice,
  type InvoiceAttachmentItem,
} from "../services/inputInvoicesApi";

const VAT_RATE = 0.17; // 17% PDV u BiH

export default function InputInvoiceCreatePage() {
  const navigate = useNavigate();

  // Dobavljač
  const [supplierName, setSupplierName] = useState("");
  const [supplierTaxId, setSupplierTaxId] = useState("");
  const [supplierAddress, setSupplierAddress] = useState("");

  // Osnovni podaci
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [issueDate, setIssueDate] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [currency, setCurrency] = useState("BAM");

  // Iznosi – osnovica / ukupno (osnovica + PDV)
  const [includeVat, setIncludeVat] = useState(true);
  const [baseStr, setBaseStr] = useState("");
  const [totalStr, setTotalStr] = useState("");

  // Napomena
  const [note, setNote] = useState("");

  // Attachment-i za ovu fakturu (uploadovani na server, ali još nisu linkovani)
  const [attachments, setAttachments] = useState<InvoiceAttachmentItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  // Izračun iz stringova
  const numericBase = parseFloat(baseStr.replace(",", ".") || "0") || 0;
  const numericTotal = parseFloat(totalStr.replace(",", ".") || "0") || 0;

  let totalBase = numericBase;
  let totalAmount = numericTotal;
  let totalVat = 0;

  if (includeVat) {
    if (baseStr !== "" && (totalStr === "" || !Number.isFinite(numericTotal))) {
      // iz osnovice računamo sve
      totalBase = numericBase;
      totalVat = totalBase * VAT_RATE;
      totalAmount = totalBase + totalVat;
    } else if (totalStr !== "" && (baseStr === "" || !Number.isFinite(numericBase))) {
      // iz ukupnog računamo nazad
      totalAmount = numericTotal;
      totalBase = totalAmount / (1 + VAT_RATE);
      totalVat = totalAmount - totalBase;
    } else {
      // ako su oba polja popunjena i validna, koristimo osnovicu kao izvor istine
      totalBase = numericBase;
      totalVat = totalBase * VAT_RATE;
      totalAmount = totalBase + totalVat;
    }
  } else {
    // bez PDV-a: ukupno == osnovica
    if (baseStr !== "" && (totalStr === "" || !Number.isFinite(numericTotal))) {
      totalBase = numericBase;
      totalAmount = totalBase;
    } else if (totalStr !== "" && (baseStr === "" || !Number.isFinite(numericBase))) {
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
    if (!Number.isFinite(v)) {
      return;
    }

    if (includeVat) {
      const vat = v * VAT_RATE;
      const total = v + vat;
      setTotalStr(total.toFixed(2));
    } else {
      setTotalStr(v.toFixed(2));
    }
  }

  function handleTotalChange(e: ChangeEvent<HTMLInputElement>) {
    const value = e.target.value;
    setTotalStr(value);

    const v = parseFloat(value.replace(",", "."));
    if (!Number.isFinite(v)) {
      return;
    }

    if (includeVat) {
      const base = v / (1 + VAT_RATE);
      setBaseStr(base.toFixed(2));
    } else {
      setBaseStr(v.toFixed(2));
    }
  }

  function handleToggleVat(e: ChangeEvent<HTMLInputElement>) {
    const checked = e.target.checked;
    setIncludeVat(checked);

    if (checked) {
      // prelazimo na "sa PDV-om": iz osnovice računamo ukupno
      const base = parseFloat(baseStr.replace(",", ".") || "0");
      if (Number.isFinite(base)) {
        const vat = base * VAT_RATE;
        const total = base + vat;
        setTotalStr(total > 0 ? total.toFixed(2) : totalStr);
      }
    } else {
      // bez PDV-a: ukupno == osnovica
      const base = parseFloat(baseStr.replace(",", ".") || "0");
      if (Number.isFinite(base)) {
        setTotalStr(base.toFixed(2));
      }
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
    if (!window.confirm("Da li sigurno želiš obrisati ovaj prilog?")) {
      return;
    }

    try {
      await deleteInvoiceAttachment(att.id);
      setAttachments((prev) => prev.filter((a) => a.id !== att.id));
    } catch (err: any) {
      alert(
        err?.message ?? "Greška pri brisanju priloga. Pokušaj ponovo.",
      );
    }
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    setErrorMsg("");

    if (
      !supplierName.trim() ||
      !invoiceNumber.trim() ||
      !issueDate
    ) {
      setSaving(false);
      setErrorMsg(
        "Obavezna polja: dobavljač, broj fakture i datum izdavanja.",
      );
      return;
    }

    if (totalBase < 0 || totalAmount <= 0 || totalVat < 0) {
      setSaving(false);
      setErrorMsg(
        "Iznosi moraju biti ≥ 0, a ukupno (osnovica + PDV) mora biti veće od 0.",
      );
      return;
    }

    try {
      // 1) Kreiramo ulaznu fakturu
      const created = await createInputInvoice({
        supplier_name: supplierName.trim(),
        supplier_tax_id: supplierTaxId.trim() || null,
        supplier_address: supplierAddress.trim() || null,
        invoice_number: invoiceNumber.trim(),
        issue_date: issueDate,
        due_date: dueDate || null,
        total_base: parseFloat(totalBase.toFixed(2)),
        total_vat: parseFloat(displayVat.toFixed(2)),
        total_amount: parseFloat(totalAmount.toFixed(2)),
        currency: currency.trim() || "BAM",
        note: note.trim() || null,
      });

      // 2) Linkujemo sve uploadovane priloge na ovu fakturu
      if (attachments.length > 0) {
        await Promise.all(
          attachments.map((att) =>
            linkAttachmentToInputInvoice(att.id, created.id),
          ),
        );
      }

      // 3) Redirect na listu ulaznih faktura
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
    <div className="max-w-4xl space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-slate-800">
          Nova ulazna faktura
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Kreiranje novog računa dobavljača za tenant{" "}
          <span className="font-mono">t-demo</span>.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="space-y-6 rounded-lg border bg-white p-5"
      >
        {/* Dobavljač */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="space-y-1">
            <label className="text-xs font-medium">Dobavljač *</label>
            <input
              type="text"
              required
              value={supplierName}
              onChange={(e) => setSupplierName(e.target.value)}
              className="input"
              placeholder="npr. Elektrodistribucija Banja Luka"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium">
              PIB / JIB dobavljača (opcionalno)
            </label>
            <input
              type="text"
              value={supplierTaxId}
              onChange={(e) => setSupplierTaxId(e.target.value)}
              className="input"
              placeholder="npr. 1234567890000"
            />
          </div>

          <div className="space-y-1 md:col-span-2">
            <label className="text-xs font-medium">
              Adresa dobavljača (opcionalno)
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

        {/* Osnovni podaci o fakturi */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="space-y-1">
            <label className="text-xs font-medium">Broj fakture *</label>
            <input
              type="text"
              required
              value={invoiceNumber}
              onChange={(e) => setInvoiceNumber(e.target.value)}
              className="input"
              placeholder="npr. 2025-INV-001"
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
            <label className="text-xs font-medium">Datum izdavanja *</label>
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
              Rok dospijeća (opcionalno)
            </label>
            <input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="input"
            />
          </div>
        </div>

        {/* Iznosi + PDV 17% */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="space-y-1">
            <label className="text-xs font-medium">
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

          <div className="space-y-1">
            <label className="text-xs font-medium">
              PDV 17% (dodatak na osnovicu)
            </label>
            <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
              <div className="flex items-center justify-between gap-2">
                <span>Iznos PDV-a:</span>
                <span className="font-mono">
                  {displayVat > 0 ? displayVat.toFixed(2) : "0.00"}{" "}
                  {currency || "BAM"}
                </span>
              </div>
              <div className="mt-2 flex items-center gap-2">
                <input
                  id="include-vat"
                  type="checkbox"
                  className="h-3 w-3 rounded border-slate-300 text-slate-900"
                  checked={includeVat}
                  onChange={handleToggleVat}
                />
                <label
                  htmlFor="include-vat"
                  className="text-[11px] text-slate-600"
                >
                  Uključi PDV (stopa je fiksnih 17%. Možeš ga samo uključiti ili
                  isključiti iz obračuna.)
                </label>
              </div>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium">
              Ukupno (osnovica + PDV)
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

        {/* Napomena */}
        <div className="space-y-1">
          <label className="text-xs font-medium">
            Interna napomena (opcionalno)
          </label>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="input min-h-[80px]"
            placeholder="npr. Račun za struju za oktobar."
          />
        </div>

        {/* Upload računa */}
        <div className="space-y-2 border-t pt-3">
          <label className="text-xs font-medium">
            Prilaganje računa (PDF/slika, opcionalno)
          </label>
          <input
            type="file"
            accept="application/pdf,image/*"
            onChange={handleFileChange}
            disabled={isUploading}
            className="block w-full text-xs text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-white hover:file:bg-slate-800"
          />
          {isUploading && (
            <p className="text-[11px] text-slate-500">
              Uploadujem fajl...
            </p>
          )}
          {uploadError && (
            <p className="text-[11px] text-red-600">
              {uploadError}
            </p>
          )}

          {attachments.length > 0 && (
            <div className="mt-2 space-y-1 rounded-md border border-slate-200 bg-slate-50 p-2">
              {attachments.map((att) => (
                <div
                  key={att.id}
                  className="flex items-center justify-between rounded-md bg-white px-2 py-1.5 text-xs text-slate-700 shadow-sm"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">
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
                    className="rounded-md border border-red-100 px-2 py-0.5 text-[11px] text-red-600 hover:bg-red-50"
                  >
                    Ukloni
                  </button>
                </div>
              ))}
            </div>
          )}

          <p className="mt-1 text-[11px] text-slate-400">
            Fajl će biti sačuvan među &quot;Uploadovanim računima
            (attachments)&quot; za ovaj tenant i biće automatski povezan sa
            ovom ulaznom fakturom nakon snimanja.
          </p>
        </div>

        {/* Error + submit */}
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
              className="rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
            >
              Otkaži
            </button>
            <button
              type="submit"
              disabled={saving}
              className="btn-primary w-full text-xs md:w-auto"
            >
              {saving ? "Spremam..." : "Snimi ulaznu fakturu"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
