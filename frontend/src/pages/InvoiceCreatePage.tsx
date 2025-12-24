// /home/miso/dev/sp-app/sp-app/frontend/src/pages/InvoiceCreatePage.tsx
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { createInvoice, fetchInvoicesList } from "../services/invoicesApi";
import type {
  InvoiceListResponse,
  InvoiceCreatePayload,
} from "../types/invoice";

type InvoiceItem = {
  description: string;
  quantity: string;        // string radi kontrolisanog inputa
  unitPrice: string;       // cijena BEZ PDV-a
  discountPercent: string; // popust u %
};

const VAT_RATE = 0.17; // 17%

function getTodayAsDateString(): string {
  return new Date().toISOString().slice(0, 10);
}

function addDays(dateStr: string, days: number): string {
  if (!dateStr) return "";
  const parts = dateStr.split("-").map((part) => parseInt(part, 10));
  if (parts.length !== 3) return "";
  const [year, month, day] = parts;
  if (!year || !month || !day) return "";

  const d = new Date(year, month - 1, day);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

// Jednostavni šabloni – vrijednosti možeš kasnije prilagoditi svojim realnim cijenama
const INVOICE_TEMPLATES = [
  {
    id: "standard-service",
    label: "Standardna usluga",
    description: "Standardna usluga / usluge programiranja",
    quantity: "1",
    unitPrice: "100.00",
    discountPercent: "0",
    paymentDaysOffset: 7,
    note: "Standardna usluga prema ugovoru.",
  },
  {
    id: "monthly-flat",
    label: "Mjesečni paušal",
    description: "Mjesečni paušal za usluge",
    quantity: "1",
    unitPrice: "500.00",
    discountPercent: "0",
    paymentDaysOffset: 7,
    note: "Mjesečni paušal za pružene usluge u toku mjeseca.",
  },
] as const;

export default function InvoiceCreatePage() {
  const navigate = useNavigate();

  // Osnovni podaci o fakturi
  const [issueDate, setIssueDate] = useState<string>(() =>
    getTodayAsDateString(),
  );
  const [dueDate, setDueDate] = useState<string>(() =>
    addDays(getTodayAsDateString(), 7),
  );
  const [number, setNumber] = useState("");

  // Podaci o kupcu
  const [buyerName, setBuyerName] = useState("");
  const [buyerAddress, setBuyerAddress] = useState("");
  const [buyerIdNumber, setBuyerIdNumber] = useState(""); // JIB/PIB kupca – ide ka backendu

  // Napomena fakture
  const [note, setNote] = useState("");

  // Email opcije (samo UI, bez pozadinske logike)
  const [sendEmail, setSendEmail] = useState(false);
  const [buyerEmail, setBuyerEmail] = useState("");

  // Stavke
  const [items, setItems] = useState<InvoiceItem[]>([
    {
      description: "",
      quantity: "1",
      unitPrice: "",
      discountPercent: "0",
    },
  ]);

  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  // Lista faktura radi prijedloga broja
  const { data: invoicesListData } = useQuery<InvoiceListResponse>({
    queryKey: ["invoices", "list-for-number-suggestion"],
    queryFn: () => fetchInvoicesList(),
  });

  // Automatski prijedlog broja fakture GODINA/MJESEC/XXXX
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

  function handleIssueDateChange(value: string) {
    setIssueDate(value);
    if (value) {
      setDueDate(addDays(value, 7));
    } else {
      setDueDate("");
    }
  }

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
        discountPercent: "0",
      },
    ]);
  }

  function removeItemRow(index: number) {
    setItems((prev) => {
      if (prev.length === 1) return prev;
      return prev.filter((_, i) => i !== index);
    });
  }

  function applyTemplate(templateId: string) {
    if (!templateId) return;
    const tpl = INVOICE_TEMPLATES.find((t) => t.id === templateId);
    if (!tpl) return;

    setItems([
      {
        description: tpl.description,
        quantity: tpl.quantity,
        unitPrice: tpl.unitPrice,
        discountPercent: tpl.discountPercent,
      },
    ]);

    if (issueDate) {
      setDueDate(addDays(issueDate, tpl.paymentDaysOffset));
    }

    // Napomena šablona, možeš je ručno mijenjati
    setNote(tpl.note);
  }

  // Izračun NETO, PDV, UKUPNO za prikaz – uz uračunat popust
  const netTotal = items.reduce((sum, item) => {
    const qty = parseFloat(item.quantity || "0");
    const priceNet = parseFloat(item.unitPrice || "0");
    const discountPercent = parseFloat(item.discountPercent || "0");

    if (!Number.isFinite(qty) || !Number.isFinite(priceNet)) return sum;
    if (qty <= 0 || priceNet < 0) return sum;

    const base = qty * priceNet;
    const discountFactor =
      Number.isFinite(discountPercent) && discountPercent > 0
        ? Math.max(0, 1 - discountPercent / 100)
        : 1;

    const netAfterDiscount = base * discountFactor;
    return sum + netAfterDiscount;
  }, 0);

  const vatAmount = netTotal * VAT_RATE;
  const grossTotal = netTotal + vatAmount;

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    setErrorMsg("");

    // Pripremi stavke za backend – samo validne
    const preparedItems = items
      .map((item) => {
        const qty = parseFloat(item.quantity || "0");
        const priceNet = parseFloat(item.unitPrice || "0");
        const discountPercent = parseFloat(item.discountPercent || "0");

        if (
          item.description.trim().length === 0 ||
          !Number.isFinite(qty) ||
          !Number.isFinite(priceNet) ||
          qty <= 0 ||
          priceNet < 0
        ) {
          return null;
        }

        return {
          description: item.description.trim(),
          quantity: qty,
          unit_price: priceNet,
          vat_rate: VAT_RATE,
          discount_percent:
            Number.isFinite(discountPercent) && discountPercent > 0
              ? discountPercent
              : 0,
        };
      })
      .filter(
        (
          x,
        ): x is {
          description: string;
          quantity: number;
          unit_price: number;
          vat_rate: number;
          discount_percent: number;
        } => x !== null,
      );

    if (!preparedItems.length || grossTotal <= 0) {
      setSaving(false);
      setErrorMsg(
        "Dodaj barem jednu validnu stavku (opis, količina > 0, cijena ≥ 0).",
      );
      return;
    }

    if (!buyerName.trim()) {
      setSaving(false);
      setErrorMsg("Unesi naziv kupca (obavezno polje).");
      return;
    }

    try {
      const payload: InvoiceCreatePayload = {
        number,
        buyer_name: buyerName.trim(),
        buyer_address: buyerAddress || null,
        buyer_tax_id: buyerIdNumber || null,
        issue_date: issueDate,
        due_date: dueDate || null,
        note: note.trim() || null,
        items: preparedItems,
      };

      await createInvoice(payload);
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

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Gornji blok: faktura + kupac */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Podaci o fakturi */}
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
                    onChange={(e) => handleIssueDateChange(e.target.value)}
                    className="input"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-slate-700">
                    Rok plaćanja (default +7 dana)
                  </label>
                  <input
                    type="date"
                    value={dueDate || ""}
                    onChange={(e) => setDueDate(e.target.value)}
                    className="input"
                  />
                  <p className="text-[11px] text-slate-400">
                    Po difoltu je postavljeno 7 dana nakon datuma izdavanja,
                    ali možeš ručno promijeniti.
                  </p>
                </div>
              </div>

              {/* Šabloni fakture */}
              <div className="space-y-1 pt-1">
                <label className="text-xs font-medium text-slate-700">
                  Primijeni šablon fakture (opcionalno)
                </label>
                <div className="flex flex-col sm:flex-row gap-2">
                  <select
                    className="input sm:max-w-xs"
                    defaultValue=""
                    onChange={(e) => applyTemplate(e.target.value)}
                  >
                    <option value="">— Odaberi šablon —</option>
                    {INVOICE_TEMPLATES.map((tpl) => (
                      <option key={tpl.id} value={tpl.id}>
                        {tpl.label}
                      </option>
                    ))}
                  </select>
                  <p className="text-[11px] text-slate-400 sm:self-center">
                    Šablon popunjava jednu stavku, rok plaćanja i napomenu.
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Podaci o kupcu */}
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
                JIB/PIB se čuva u backendu i prikazuje na PDF fakturi.
              </p>
            </div>
          </section>
        </div>

        {/* Stavke fakture */}
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
              const discountPercent = parseFloat(item.discountPercent || "0");

              const base =
                Number.isFinite(qty) && Number.isFinite(unitPriceNet)
                  ? qty * unitPriceNet
                  : 0;

              const discountFactor =
                Number.isFinite(discountPercent) && discountPercent > 0
                  ? Math.max(0, 1 - discountPercent / 100)
                  : 1;

              const lineNet = base * discountFactor;
              const lineVat = lineNet * VAT_RATE;
              const lineGross = lineNet + lineVat;

              return (
                <div
                  key={index}
                  className="grid grid-cols-1 md:grid-cols-[2fr,0.7fr,0.9fr,0.8fr,1.3fr,auto] gap-2 items-start border border-slate-200 rounded-md p-3 bg-slate-50"
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
                      Popust %
                    </label>
                    <input
                      type="number"
                      min={0}
                      max={100}
                      step="0.01"
                      value={item.discountPercent}
                      onChange={(e) =>
                        updateItem(index, "discountPercent", e.target.value)
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
                        Neto (poslije popusta):{" "}
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

        {/* Donji blok: napomena + rezime + email */}
        <section className="grid grid-cols-1 lg:grid-cols-[2fr,1fr] gap-4 items-start">
          <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-4 space-y-3">
            <h3 className="text-sm font-semibold text-slate-700 border-b border-slate-100 pb-2">
              Napomena & status snimanja
            </h3>

            <div className="space-y-2 pt-1">
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-700">
                  Napomena na fakturi (opcionalno)
                </label>
                <textarea
                  rows={3}
                  className="input resize-none"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="npr. Plaćanje po prijemu fakture, rok 7 dana..."
                />
              </div>

              <div className="pt-1 text-sm text-slate-600 space-y-2">
                {errorMsg ? (
                  <p className="text-red-600 text-xs">{errorMsg}</p>
                ) : (
                  <p className="text-xs text-slate-500">
                    Provjeri da li su popunjene sve obavezne kolonice i da je
                    barem jedna stavka validna (opis, količina, cijena).
                  </p>
                )}
                <p className="text-[11px] text-slate-400">
                  Nakon snimanja, faktura će se pojaviti u listi{" "}
                  <span className="font-semibold">Izlazne fakture</span>. Detaljni
                  prikaz sada koristi sve stavke, popuste i ukupne iznose sa
                  PDV-om.
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-3">
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

            {/* Email sekcija – samo UI, bez pozadinske akcije */}
            <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-4 space-y-2">
              <h3 className="text-sm font-semibold text-slate-700 border-b border-slate-100 pb-2">
                Slanje fakture emailom (placeholder)
              </h3>
              <div className="flex items-start gap-2">
                <input
                  id="send-email"
                  type="checkbox"
                  className="mt-1"
                  checked={sendEmail}
                  onChange={(e) => setSendEmail(e.target.checked)}
                />
                <div className="flex-1 space-y-1">
                  <label
                    htmlFor="send-email"
                    className="text-xs font-medium text-slate-700"
                  >
                    Pošalji fakturu kupcu putem emaila
                  </label>
                  <input
                    type="email"
                    className="input text-xs"
                    placeholder="email kupca (opcionalno)"
                    value={buyerEmail}
                    onChange={(e) => setBuyerEmail(e.target.value)}
                    disabled={!sendEmail}
                  />
                  <p className="text-[11px] text-slate-400">
                    U ovoj verziji opcija je samo vizuelna – budući modul će
                    koristiti ove podatke za automatsko slanje fakture.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>
      </form>
    </div>
  );
}
