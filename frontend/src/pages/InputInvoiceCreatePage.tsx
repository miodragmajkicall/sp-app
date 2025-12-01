// /home/miso/dev/sp-app/sp-app/frontend/src/pages/InputInvoiceCreatePage.tsx
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { createInputInvoice } from "../services/inputInvoicesApi";

export default function InputInvoiceCreatePage() {
  const navigate = useNavigate();

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

  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  // total_amount = total_base + total_vat
  const parsedBase = parseFloat(totalBase || "0");
  const parsedVat = parseFloat(totalVat || "0");
  const totalAmount =
    Number.isFinite(parsedBase) && Number.isFinite(parsedVat)
      ? parsedBase + parsedVat
      : 0;

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    setErrorMsg("");

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
      setSaving(false);
      setErrorMsg(
        "Obavezna polja: dobavljač, broj fakture, datum izdavanja i iznosi (osnovica i PDV ≥ 0, ukupan iznos > 0).",
      );
      return;
    }

    try {
      await createInputInvoice({
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

        {/* Iznosi */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="space-y-1">
            <label className="text-xs font-medium">Osnovica bez PDV-a *</label>
            <input
              type="number"
              min={0}
              step="0.01"
              value={totalBase}
              onChange={(e) => setTotalBase(e.target.value)}
              className="input"
              placeholder="npr. 100.00"
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
              placeholder="npr. 17.00"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium">Ukupno (osn. + PDV)</label>
            <div className="input flex items-center justify-end bg-slate-50 text-right">
              <span className="text-xs text-slate-700">
                {totalAmount > 0 ? totalAmount.toFixed(2) : "0.00"}{" "}
                {currency || "BAM"}
              </span>
            </div>
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
