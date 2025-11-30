import { useState } from "react";
import { createInvoice } from "../services/invoicesApi";
import { useNavigate } from "react-router-dom";

export default function InvoiceCreatePage() {
  const navigate = useNavigate();

  const [number, setNumber] = useState("");
  const [buyerName, setBuyerName] = useState("");
  const [issueDate, setIssueDate] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [amount, setAmount] = useState("");
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErrorMsg("");

    try {
      await createInvoice({
        number,
        buyer_name: buyerName,
        issue_date: issueDate,
        due_date: dueDate || null,
        total_amount: parseFloat(amount),
      });

      navigate("/invoices");
    } catch (err: any) {
      setErrorMsg(err?.message ?? "Greška pri snimanju fakture");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-xl space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-slate-800">Nova izlazna faktura</h2>
        <p className="text-xs text-slate-500 mt-1">
          Kreiranje nove fakture za tenant <span className="font-mono">t-demo</span>.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4 bg-white p-5 rounded-lg border">
        
        <div className="space-y-1">
          <label className="text-xs font-medium">Broj fakture *</label>
          <input
            type="text"
            required
            value={number}
            onChange={(e) => setNumber(e.target.value)}
            className="input"
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium">Kupac *</label>
          <input
            type="text"
            required
            value={buyerName}
            onChange={(e) => setBuyerName(e.target.value)}
            className="input"
          />
        </div>

        <div className="flex gap-3">
          <div className="flex-1 space-y-1">
            <label className="text-xs font-medium">Datum izdavanja *</label>
            <input
              type="date"
              required
              value={issueDate}
              onChange={(e) => setIssueDate(e.target.value)}
              className="input"
            />
          </div>
          <div className="flex-1 space-y-1">
            <label className="text-xs font-medium">Rok plaćanja (opcionalno)</label>
            <input
              type="date"
              value={dueDate || ""}
              onChange={(e) => setDueDate(e.target.value)}
              className="input"
            />
          </div>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium">Iznos (BAM) *</label>
          <input
            type="number"
            required
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="input"
          />
        </div>

        {errorMsg && (
          <p className="text-sm text-red-600 mt-2">{errorMsg}</p>
        )}

        <button
          type="submit"
          disabled={saving}
          className="btn-primary w-full"
        >
          {saving ? "Spremam..." : "Snimi fakturu"}
        </button>
      </form>
    </div>
  );
}
