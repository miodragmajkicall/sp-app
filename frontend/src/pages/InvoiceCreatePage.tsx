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
  quantity: string;
  unitPrice: string;
  discountPercent: string;
};

const VAT_RATE = 0.17;

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

function formatMoney(value: number): string {
  return `${value > 0 ? value.toFixed(2) : "0.00"} BAM`;
}

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

  const [issueDate, setIssueDate] = useState<string>(() =>
    getTodayAsDateString(),
  );
  const [dueDate, setDueDate] = useState<string>(() =>
    addDays(getTodayAsDateString(), 7),
  );
  const [number, setNumber] = useState("");

  const [buyerName, setBuyerName] = useState("");
  const [buyerAddress, setBuyerAddress] = useState("");
  const [buyerIdNumber, setBuyerIdNumber] = useState("");

  const [note, setNote] = useState("");

  const [sendEmail, setSendEmail] = useState(false);
  const [buyerEmail, setBuyerEmail] = useState("");

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

  const { data: invoicesListData } = useQuery<InvoiceListResponse>({
    queryKey: ["invoices", "list-for-number-suggestion"],
    queryFn: () => fetchInvoicesList(),
  });

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

    setNote(tpl.note);
  }

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

    return sum + base * discountFactor;
  }, 0);

  const vatAmount = netTotal * VAT_RATE;
  const grossTotal = netTotal + vatAmount;

  const validItemsCount = items.filter((item) => {
    const qty = parseFloat(item.quantity || "0");
    const priceNet = parseFloat(item.unitPrice || "0");
    return (
      item.description.trim().length > 0 &&
      Number.isFinite(qty) &&
      Number.isFinite(priceNet) &&
      qty > 0 &&
      priceNet >= 0
    );
  }).length;

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    setErrorMsg("");

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
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 px-6 py-7 text-white sm:px-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <div className="inline-flex items-center rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs font-medium text-slate-200">
                Izlazne fakture · Nova faktura
              </div>
              <div>
                <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                  Kreiranje nove izlazne fakture
                </h1>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                  Unesi kupca, stavke, popuste i rok plaćanja. Sistem uživo
                  računa neto osnovicu, PDV i ukupan iznos za naplatu.
                </p>
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/10 px-4 py-3 text-sm shadow-sm backdrop-blur">
              <div className="text-xs text-slate-300">Predloženi broj</div>
              <div className="mt-1 font-mono text-lg font-semibold text-white">
                {number || "—"}
              </div>
              <div className="mt-1 text-xs text-slate-300">
                Tenant: <span className="font-mono">t-demo</span>
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-4 border-t border-slate-200 bg-slate-50 px-6 py-5 sm:grid-cols-2 lg:grid-cols-4 sm:px-8">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-medium text-slate-500">Datum izdavanja</p>
            <p className="mt-1 text-lg font-semibold text-slate-900">
              {issueDate || "—"}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-medium text-slate-500">Rok plaćanja</p>
            <p className="mt-1 text-lg font-semibold text-slate-900">
              {dueDate || "—"}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-medium text-slate-500">Validne stavke</p>
            <p className="mt-1 text-lg font-semibold text-slate-900">
              {validItemsCount}/{items.length}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-medium text-slate-500">
              Ukupno za naplatu
            </p>
            <p className="mt-1 font-mono text-lg font-semibold text-slate-900">
              {formatMoney(grossTotal)}
            </p>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="grid gap-6 lg:grid-cols-[1fr,360px]">
        <div className="space-y-6">
          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <div className="mb-5 flex flex-col gap-2 border-b border-slate-100 pb-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-base font-semibold text-slate-900">
                  Osnovni podaci
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Broj fakture, datumi, kupac i opcioni šablon.
                </p>
              </div>
              <span className="inline-flex w-fit rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                PDV {(VAT_RATE * 100).toFixed(0)}%
              </span>
            </div>

            <div className="grid gap-5 lg:grid-cols-2">
              <div className="space-y-4">
                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Broj fakture *
                  </label>
                  <input
                    type="text"
                    required
                    value={number}
                    onChange={(e) => setNumber(e.target.value)}
                    className="input"
                    placeholder="npr. 2026/04/0001"
                  />
                  <p className="mt-1.5 text-xs text-slate-400">
                    Automatski prijedlog po formatu GODINA/MJESEC/REDNI.
                  </p>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
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

                  <div>
                    <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Rok plaćanja
                    </label>
                    <input
                      type="date"
                      value={dueDate || ""}
                      onChange={(e) => setDueDate(e.target.value)}
                      className="input"
                    />
                  </div>
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Šablon fakture
                  </label>
                  <select
                    className="input"
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
                  <p className="mt-1.5 text-xs text-slate-400">
                    Šablon popunjava stavku, napomenu i rok plaćanja.
                  </p>
                </div>
              </div>

              <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Naziv kupca *
                  </label>
                  <input
                    type="text"
                    required
                    value={buyerName}
                    onChange={(e) => setBuyerName(e.target.value)}
                    className="input bg-white"
                    placeholder="npr. Primjer d.o.o."
                  />
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Adresa kupca
                  </label>
                  <input
                    type="text"
                    value={buyerAddress}
                    onChange={(e) => setBuyerAddress(e.target.value)}
                    className="input bg-white"
                    placeholder="Ulica i broj, grad"
                  />
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                    JIB / PIB kupca
                  </label>
                  <input
                    type="text"
                    value={buyerIdNumber}
                    onChange={(e) => setBuyerIdNumber(e.target.value)}
                    className="input bg-white"
                    placeholder="npr. 4401234560001"
                  />
                  <p className="mt-1.5 text-xs text-slate-400">
                    Čuva se u backendu i koristi za prikaz/PDF fakturu.
                  </p>
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <div className="mb-5 flex flex-col gap-3 border-b border-slate-100 pb-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-base font-semibold text-slate-900">
                  Stavke fakture
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Unesi opis, količinu, cijenu bez PDV-a i eventualni popust.
                </p>
              </div>
              <button
                type="button"
                onClick={addItemRow}
                className="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
              >
                + Dodaj stavku
              </button>
            </div>

            <div className="space-y-3">
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
                    className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
                  >
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white">
                          {index + 1}
                        </span>
                        <span className="text-sm font-semibold text-slate-800">
                          Stavka {index + 1}
                        </span>
                      </div>

                      <button
                        type="button"
                        onClick={() => removeItemRow(index)}
                        disabled={items.length === 1}
                        className="text-xs font-semibold text-red-600 transition hover:text-red-700 disabled:text-slate-300"
                      >
                        Ukloni
                      </button>
                    </div>

                    <div className="grid gap-3 lg:grid-cols-[2fr,0.7fr,0.9fr,0.75fr,1.25fr]">
                      <div>
                        <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Opis *
                        </label>
                        <input
                          type="text"
                          value={item.description}
                          onChange={(e) =>
                            updateItem(index, "description", e.target.value)
                          }
                          className="input bg-white"
                          placeholder="npr. Usluge programiranja"
                        />
                      </div>

                      <div>
                        <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
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
                          className="input bg-white"
                        />
                      </div>

                      <div>
                        <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Cijena bez PDV-a
                        </label>
                        <input
                          type="number"
                          min={0}
                          step="0.01"
                          value={item.unitPrice}
                          onChange={(e) =>
                            updateItem(index, "unitPrice", e.target.value)
                          }
                          className="input bg-white"
                        />
                      </div>

                      <div>
                        <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Popust %
                        </label>
                        <input
                          type="number"
                          min={0}
                          max={100}
                          step="0.01"
                          value={item.discountPercent}
                          onChange={(e) =>
                            updateItem(
                              index,
                              "discountPercent",
                              e.target.value,
                            )
                          }
                          className="input bg-white"
                        />
                      </div>

                      <div className="rounded-xl border border-slate-200 bg-white p-3">
                        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Obračun stavke
                        </p>
                        <div className="space-y-1 text-xs">
                          <div className="flex justify-between gap-3">
                            <span className="text-slate-500">Neto:</span>
                            <span className="font-mono font-medium text-slate-800">
                              {formatMoney(lineNet)}
                            </span>
                          </div>
                          <div className="flex justify-between gap-3">
                            <span className="text-slate-500">
                              PDV {(VAT_RATE * 100).toFixed(0)}%:
                            </span>
                            <span className="font-mono font-medium text-slate-800">
                              {formatMoney(lineVat)}
                            </span>
                          </div>
                          <div className="mt-2 flex justify-between gap-3 border-t border-slate-100 pt-2">
                            <span className="font-semibold text-slate-700">
                              Ukupno:
                            </span>
                            <span className="font-mono font-semibold text-slate-950">
                              {formatMoney(lineGross)}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
            <div className="mb-4 border-b border-slate-100 pb-4">
              <h2 className="text-base font-semibold text-slate-900">
                Napomena i email opcije
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Dodatni tekst na fakturi i placeholder za budući email modul.
              </p>
            </div>

            <div className="grid gap-5 lg:grid-cols-2">
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Napomena na fakturi
                </label>
                <textarea
                  rows={5}
                  className="input resize-none"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="npr. Plaćanje po prijemu fakture, rok 7 dana..."
                />
              </div>

              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-start gap-3">
                  <input
                    id="send-email"
                    type="checkbox"
                    className="mt-1"
                    checked={sendEmail}
                    onChange={(e) => setSendEmail(e.target.checked)}
                  />
                  <div className="flex-1 space-y-2">
                    <label
                      htmlFor="send-email"
                      className="block text-sm font-semibold text-slate-800"
                    >
                      Pošalji fakturu kupcu putem emaila
                    </label>
                    <input
                      type="email"
                      className="input bg-white text-sm"
                      placeholder="email kupca"
                      value={buyerEmail}
                      onChange={(e) => setBuyerEmail(e.target.value)}
                      disabled={!sendEmail}
                    />
                    <p className="text-xs leading-5 text-slate-500">
                      Opcija je trenutno samo vizuelna. Kasniji modul može
                      koristiti ovaj podatak za automatsko slanje fakture.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          <div className="rounded-3xl border border-slate-800 bg-slate-950 p-5 text-white shadow-xl">
            <div className="border-b border-white/10 pb-4">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                Live rezime
              </p>
              <h2 className="mt-1 text-lg font-semibold">Iznos za naplatu</h2>
            </div>

            <div className="space-y-3 py-4 text-sm">
              <div className="flex items-center justify-between gap-4">
                <span className="text-slate-300">Neto osnovica</span>
                <span className="font-mono font-semibold">
                  {formatMoney(netTotal)}
                </span>
              </div>
              <div className="flex items-center justify-between gap-4">
                <span className="text-slate-300">
                  PDV {(VAT_RATE * 100).toFixed(0)}%
                </span>
                <span className="font-mono font-semibold">
                  {formatMoney(vatAmount)}
                </span>
              </div>
              <div className="flex items-center justify-between gap-4 border-t border-white/10 pt-4">
                <span className="text-base font-semibold text-white">
                  Ukupno
                </span>
                <span className="font-mono text-xl font-bold text-white">
                  {formatMoney(grossTotal)}
                </span>
              </div>
            </div>

            {errorMsg ? (
              <div className="mb-4 rounded-2xl border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-100">
                {errorMsg}
              </div>
            ) : (
              <div className="mb-4 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-xs leading-5 text-slate-300">
                Provjeri kupca, datume i stavke. Nakon snimanja faktura ide u
                listu izlaznih faktura.
              </div>
            )}

            <button
              type="submit"
              disabled={saving}
              className="w-full rounded-2xl bg-white px-4 py-3 text-sm font-bold text-slate-950 shadow-sm transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? "Spremam fakturu..." : "Snimi fakturu"}
            </button>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-900">
              Kontrola prije snimanja
            </h3>
            <div className="mt-4 space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Kupac</span>
                <span className="font-semibold text-slate-800">
                  {buyerName.trim() ? "Popunjeno" : "Nedostaje"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Broj fakture</span>
                <span className="font-semibold text-slate-800">
                  {number.trim() ? "Popunjeno" : "Nedostaje"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Stavke</span>
                <span className="font-semibold text-slate-800">
                  {validItemsCount > 0 ? `${validItemsCount} validno` : "Nema"}
                </span>
              </div>
            </div>
          </div>
        </aside>
      </form>
    </div>
  );
}