// frontend/src/pages/InvoiceCreatePage.tsx
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { createInvoice } from "../services/invoicesApi";

type InvoiceItem = {
  description: string;
  quantity: string;   // čuvamo kao string radi input kontrolisanog stanja
  unitPrice: string;  // isto, kasnije preračunavamo u broj
};

export default function InvoiceCreatePage() {
  const navigate = useNavigate();

  const [number, setNumber] = useState("");
  const [buyerName, setBuyerName] = useState("");
  const [issueDate, setIssueDate] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [items, setItems] = useState<InvoiceItem[]>([
    {
      description: "",
      quantity: "1",
      unitPrice: "",
    },
  ]);

  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  function updateItem(
    index: number,
    field: keyof InvoiceItem,
    value: string
  ) {
    setItems((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], [field]: value };
      return copy;
    });
  }

  function addItemRow() {
    setItems((prev) => [
      ...prev,
      { description: "", quantity: "1", unitPrice: "" },
    ]);
  }

  function removeItemRow(index: number) {
    setItems((prev) => {
      if (prev.length === 1) return prev; // barem jedna stavka uvijek
      return prev.filter((_, i) => i !== index);
    });
  }

  // Izračunavanje total-a na osnovu stavki
  const totalAmount = items.reduce((sum, item) => {
    const qty = parseFloat(item.quantity || "0");
    const price = parseFloat(item.unitPrice || "0");
    if (!Number.isFinite(qty) || !Number.isFinite(price)) return sum;
    if (qty <= 0 || price < 0) return sum;
    return sum + qty * price;
  }, 0);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    setErrorMsg("");

    // minimalna validacija stavki
    const hasValidItem = items.some((item) => {
      const qty = parseFloat(item.quantity || "0");
      const price = parseFloat(item.unitPrice || "0");
      return (
        item.description.trim().length > 0 &&
        Number.isFinite(qty) &&
        Number.isFinite(price) &&
        qty > 0 &&
        price >= 0
      );
    });

    if (!hasValidItem || totalAmount <= 0) {
      setSaving(false);
      setErrorMsg(
        "Dodaj barem jednu stavku sa opisom, količinom > 0 i cijenom ≥ 0."
      );
      return;
    }

    try {
      await createInvoice({
        number,
        buyer_name: buyerName,
        issue_date: issueDate,
        due_date: dueDate || null,
        // backend za sada prima samo total_amount → zbir svih stavki
        total_amount: parseFloat(totalAmount.toFixed(2)),
      });

      navigate("/invoices");
    } catch (err: any) {
      setErrorMsg(err?.message ?? "Greška pri snimanju fakture");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-slate-800">
          Nova izlazna faktura
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          Kreiranje nove fakture za tenant{" "}
          <span className="font-mono">t-demo</span>.
        </p>
      </div>

      <form
        onSubmit={handleSubmit}
        className="space-y-6 bg-white p-5 rounded-lg border"
      >
        {/* Osnovni podaci o fakturi */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
              Rok plaćanja (opcionalno)
            </label>
            <input
              type="date"
              value={dueDate || ""}
              onChange={(e) => setDueDate(e.target.value)}
              className="input"
            />
          </div>
        </div>

        {/* Stavke fakture */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-700">
              Stavke fakture
            </h3>
            <button
              type="button"
              onClick={addItemRow}
              className="text-xs px-3 py-1 rounded border border-slate-300 hover:bg-slate-50"
            >
              + Dodaj stavku
            </button>
          </div>

          <div className="space-y-2">
            {items.map((item, index) => {
              const qty = parseFloat(item.quantity || "0");
              const price = parseFloat(item.unitPrice || "0");
              const lineTotal =
                Number.isFinite(qty) && Number.isFinite(price)
                  ? qty * price
                  : 0;

              return (
                <div
                  key={index}
                  className="grid grid-cols-1 md:grid-cols-[2fr,0.8fr,0.8fr,0.9fr,auto] gap-2 items-start border rounded-md p-3"
                >
                  <div className="space-y-1">
                    <label className="text-[11px] font-medium text-slate-600">
                      Opis stavke *
                    </label>
                    <input
                      type="text"
                      value={item.description}
                      onChange={(e) =>
                        updateItem(index, "description", e.target.value)
                      }
                      className="input"
                      placeholder="npr. Usluge programiranja"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-[11px] font-medium text-slate-600">
                      Količina
                    </label>
                    <input
                      type="number"
                      min={0}
                      step="1"
                      value={item.quantity}
                      onChange={(e) =>
                        updateItem(index, "quantity", e.target.value)
                      }
                      className="input"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-[11px] font-medium text-slate-600">
                      Cijena (BAM)
                    </label>
                    <input
                      type="number"
                      min={0}
                      step="0.01"
                      value={item.unitPrice}
                      onChange={(e) =>
                        updateItem(index, "unitPrice", e.target.value)
                      }
                      className="input"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-[11px] font-medium text-slate-600">
                      Iznos
                    </label>
                    <div className="input bg-slate-50 text-right flex items-center justify-end">
                      <span className="text-xs text-slate-700">
                        {lineTotal > 0 ? lineTotal.toFixed(2) : "0.00"} BAM
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-end pt-5">
                    <button
                      type="button"
                      onClick={() => removeItemRow(index)}
                      disabled={items.length === 1}
                      className="text-[11px] text-red-600 disabled:text-slate-300"
                    >
                      Ukloni
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Total i error */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 pt-2 border-t">
          <div>
            {errorMsg && (
              <p className="text-sm text-red-600 mt-1">{errorMsg}</p>
            )}
          </div>

          <div className="flex flex-col items-end space-y-1">
            <span className="text-xs uppercase tracking-wide text-slate-500">
              Ukupno (BAM)
            </span>
            <div className="text-lg font-semibold text-slate-800">
              {totalAmount > 0 ? totalAmount.toFixed(2) : "0.00"} BAM
            </div>
          </div>
        </div>

        <button
          type="submit"
          disabled={saving}
          className="btn-primary w-full md:w-auto md:self-end"
        >
          {saving ? "Spremam..." : "Snimi fakturu"}
        </button>
      </form>
    </div>
  );
}
