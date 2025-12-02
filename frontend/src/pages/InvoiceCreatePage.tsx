// frontend/src/pages/InvoiceCreatePage.tsx
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { createInvoice, fetchInvoicesList } from "../services/invoicesApi";
import type { InvoiceListResponse } from "../types/invoice";

type InvoiceItem = {
  description: string;
  // čuvamo kao string radi kontrolisanog input stanja
  quantity: string;
  // cijena BEZ PDV-a po jedinici (BAM)
  unitPrice: string;
};

const VAT_RATE = 0.17; // 17%

export default function InvoiceCreatePage() {
  const navigate = useNavigate();

  // Osnovni podaci o fakturi
  const [number, setNumber] = useState("");
  const [issueDate, setIssueDate] = useState<string>(() =>
    new Date().toISOString().slice(0, 10)
  );
  const [dueDate, setDueDate] = useState("");

  // Podaci o kupcu
  const [buyerName, setBuyerName] = useState("");
  const [buyerAddress, setBuyerAddress] = useState("");
  const [buyerIdNumber, setBuyerIdNumber] = useState(""); // JIB/PIB

  // Stavke
  const [items, setItems] = useState<InvoiceItem[]>([
    {
      description: "",
      quantity: "1",
      unitPrice: "",
    },
  ]);

  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  // Učitamo listu faktura da bi mogli predložiti prvi slobodan broj fakture za tekući mjesec
  const { data: invoicesListData } = useQuery<InvoiceListResponse>({
    queryKey: ["invoices", "list-for-number-suggestion"],
    queryFn: () => fetchInvoicesList(),
  });

  // Automatski prijedlog broja fakture formata GODINA/MJESEC/XXXX
  useEffect(() => {
    if (!invoicesListData) return;
    if (number.trim() !== "") return;
    if (!issueDate) return;

    const [year, month] = issueDate.split("-");
    if (!year || !month) return;

    const prefix = `${year}/${month}/`;

    let maxSuffix = 0;
    for (const inv of invoicesListData.items) {
      if (!inv.number) continue;
      if (!inv.number.startsWith(prefix)) continue;

      const suffixStr = inv.number.slice(prefix.length);
      const suffixNum = parseInt(suffixStr, 10);

      if (Number.isFinite(suffixNum) && suffixNum > maxSuffix) {
        maxSuffix = suffixNum;
      }
    }

    const nextSuffix = maxSuffix + 1;
    const formattedSuffix = String(nextSuffix).padStart(4, "0");

    setNumber(`${prefix}${formattedSuffix}`);
  }, [invoicesListData, issueDate, number]);

  function updateItem(index: number, field: keyof InvoiceItem, value: string) {
    setItems((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], [field]: value };
      return copy;
    });
  }

  function addItemRow() {
    setItems((prev) => [
      ...prev,
      {
        description: "",
        quantity: "1",
        unitPrice: "",
      },
    ]);
  }

  function removeItemRow(index: number) {
    setItems((prev) => {
      if (prev.length === 1) return prev; // barem jedna stavka uvijek
      return prev.filter((_, i) => i !== index);
    });
  }

  // Izračunavanje NETO, PDV i UKUPNO
  const netTotal = items.reduce((sum, item) => {
    const qty = parseFloat(item.quantity || "0");
    const priceNet = parseFloat(item.unitPrice || "0");

    if (!Number.isFinite(qty) || !Number.isFinite(priceNet)) return sum;
    if (qty <= 0 || priceNet < 0) return sum;

    return sum + qty * priceNet;
  }, 0);

  const vatAmount = netTotal * VAT_RATE;
  const grossTotal = netTotal + vatAmount;

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    setErrorMsg("");

    const hasValidItem = items.some((item) => {
      const qty = parseFloat(item.quantity || "0");
      const priceNet = parseFloat(item.unitPrice || "0");

      return (
        item.description.trim().length > 0 &&
        Number.isFinite(qty) &&
        Number.isFinite(priceNet) &&
        qty > 0 &&
        priceNet >= 0
      );
    });

    if (!hasValidItem || grossTotal <= 0) {
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
        // backend prima total_amount = ukupno sa PDV-om
        total_amount: parseFloat(grossTotal.toFixed(2)),
      });

      navigate("/invoices");
    } catch (err: any) {
      setErrorMsg(err?.message ?? "Greška pri snimanju fakture");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header stranice */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">
            Nova izlazna faktura
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Kreiranje nove fakture za tenant{" "}
            <span className="font-mono">t-demo</span>.
          </p>
        </div>
        <div className="text-xs text-slate-500 space-y-0.5 md:text-right">
          <p>
            PDV stopa:{" "}
            <span className="font-mono font-semibold">
              {(VAT_RATE * 100).toFixed(0)}%
            </span>
          </p>
          <p className="text-[11px]">
            Broj fakture se automatski predlaže na osnovu postojećih faktura,
            a po potrebi ga možeš ručno izmijeniti.
          </p>
        </div>
      </div>

      <form
        onSubmit={handleSubmit}
        className="space-y-5"
      >
        {/* Gornji blok: faktura + kupac */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Kartica: Podaci o fakturi */}
          <section className="bg-white rounded-lg border border-slate-200 shadow-sm p-4 space-y-3">
            <h3 className="text-sm font-semibold text-slate-700 border-b border-slate-100 pb-2">
              Podaci o fakturi
            </h3>
            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-700">
                  Broj fakture *
                </label>
                <input
                  type="text"
                  required
                  value={number}
                  onChange={(e) => setNumber(e.target.value)}
                  className="input"
                  placeholder="npr. 2025/12/0001"
                />
                <p className="text-[11px] text-slate-400">
                  Format: GODINA/MJESEC/REDNI (npr. 2025/12/0001).
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-700">
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
                  <label className="text-xs font-medium text-slate-700">
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
            </div>
          </section>

          {/* Kartica: Podaci o kupcu */}
          <section className="bg-white rounded-lg border border-slate-200 shadow-sm p-4 space-y-3">
            <h3 className="text-sm font-semibold text-slate-700 border-b border-slate-100 pb-2">
              Podaci o kupcu
            </h3>
            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-700">
                  Naziv kupca *
                </label>
                <input
                  type="text"
                  required
                  value={buyerName}
                  onChange={(e) => setBuyerName(e.target.value)}
                  className="input"
                  placeholder="npr. SP Primjer d.o.o."
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-700">
                  Adresa kupca (opcionalno)
                </label>
                <input
                  type="text"
                  value={buyerAddress}
                  onChange={(e) => setBuyerAddress(e.target.value)}
                  className="input"
                  placeholder="Ulica i broj, grad"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-700">
                  JIB / PIB kupca (opcionalno)
                </label>
                <input
                  type="text"
                  value={buyerIdNumber}
                  onChange={(e) => setBuyerIdNumber(e.target.value)}
                  className="input"
                  placeholder="npr. 4401234560001"
                />
              </div>

              <p className="text-[11px] text-slate-400">
                U ovoj V1 verziji adresa i JIB/PIB se još ne čuvaju u backendu –
                koriste se kao informativna polja pri kreiranju fakture.
              </p>
            </div>
          </section>
        </div>

        {/* Kartica: Stavke fakture */}
        <section className="bg-white rounded-lg border border-slate-200 shadow-sm p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-700">
              Stavke fakture
            </h3>
            <button
              type="button"
              onClick={addItemRow}
              className="text-xs px-3 py-1 rounded-md border border-slate-300 bg-slate-50 hover:bg-slate-100 transition-colors"
            >
              + Dodaj stavku
            </button>
          </div>

          <div className="space-y-2">
            {items.map((item, index) => {
              const qty = parseFloat(item.quantity || "0");
              const unitPriceNet = parseFloat(item.unitPrice || "0");

              const lineNet =
                Number.isFinite(qty) && Number.isFinite(unitPriceNet)
                  ? qty * unitPriceNet
                  : 0;

              const lineVat = lineNet * VAT_RATE;
              const lineGross = lineNet + lineVat;

              return (
                <div
                  key={index}
                  className="grid grid-cols-1 md:grid-cols-[2fr,0.7fr,0.9fr,1.2fr,auto] gap-2 items-start border border-slate-200 rounded-md p-3 bg-slate-50"
                >
                  <div className="space-y-1">
                    <label className="text-[11px] font-medium text-slate-700">
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
                    <label className="text-[11px] font-medium text-slate-700">
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
                    <label className="text-[11px] font-medium text-slate-700">
                      Cijena bez PDV-a (BAM)
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
                    <label className="text-[11px] font-medium text-slate-700">
                      Iznos sa PDV-om
                    </label>
                    <div className="input bg-slate-100 text-right flex flex-col items-end justify-center">
                      <span className="text-[11px] text-slate-500">
                        Neto:{" "}
                        <span className="font-mono">
                          {lineNet > 0 ? lineNet.toFixed(2) : "0.00"} BAM
                        </span>
                      </span>
                      <span className="text-[11px] text-slate-500">
                        PDV {(VAT_RATE * 100).toFixed(0)}%:{" "}
                        <span className="font-mono">
                          {lineVat > 0 ? lineVat.toFixed(2) : "0.00"} BAM
                        </span>
                      </span>
                      <span className="text-[11px] font-semibold text-slate-800">
                        Ukupno:{" "}
                        <span className="font-mono">
                          {lineGross > 0 ? lineGross.toFixed(2) : "0.00"} BAM
                        </span>
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
        </section>

        {/* Donji blok: rezime + snimanje */}
        <section className="grid grid-cols-1 lg:grid-cols-[2fr,1fr] gap-4 items-start">
          <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-4">
            <h3 className="text-sm font-semibold text-slate-700 border-b border-slate-100 pb-2">
              Napomena / status snimanja
            </h3>
            <div className="pt-2 text-sm text-slate-600 space-y-2">
              {errorMsg ? (
                <p className="text-red-600">{errorMsg}</p>
              ) : (
                <p className="text-xs text-slate-500">
                  Provjeri da li su popunjene sve obavezne kolonice i da je
                  barem jedna stavka validna (opis, količina, cijena).
                </p>
              )}
              <p className="text-[11px] text-slate-400">
                Nakon snimanja, faktura će se pojaviti u listi{" "}
                <span className="font-semibold">Izlazne fakture</span>. Detaljni
                prikaz (V1) trenutno koristi samo osnovne podatke i ukupni iznos
                sa PDV-om.
              </p>
            </div>
          </div>

          <div className="bg-slate-900 text-slate-50 rounded-lg shadow-md p-4 space-y-3">
            <h3 className="text-sm font-semibold text-slate-50 border-b border-slate-700 pb-2">
              Rezime iznosa
            </h3>
            <div className="space-y-1 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-200">Neto osnovica:</span>
                <span className="font-mono">
                  {netTotal > 0 ? netTotal.toFixed(2) : "0.00"} BAM
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-200">
                  PDV {(VAT_RATE * 100).toFixed(0)}%:
                </span>
                <span className="font-mono">
                  {vatAmount > 0 ? vatAmount.toFixed(2) : "0.00"} BAM
                </span>
              </div>
              <div className="flex items-center justify-between pt-2 border-t border-slate-700 mt-1">
                <span className="text-slate-100 font-semibold">
                  Ukupno za naplatu:
                </span>
                <span className="font-mono text-lg font-semibold">
                  {grossTotal > 0 ? grossTotal.toFixed(2) : "0.00"} BAM
                </span>
              </div>
            </div>

            <button
              type="submit"
              disabled={saving}
              className="btn-primary w-full mt-3"
            >
              {saving ? "Spremam..." : "Snimi fakturu"}
            </button>
          </div>
        </section>
      </form>
    </div>
  );
}
