// /home/miso/dev/sp-app/sp-app/frontend/src/pages/CashPage.tsx

import React, { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchCashEntries,
  createCashEntry,
  type CashEntryCreatePayload,
} from "../services/cashApi";
import type { CashEntry } from "../types/cash";

function toNumber(value: number | string | undefined | null): number {
  if (value === undefined || value === null) return 0;
  if (typeof value === "number") return value;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function pickDate(entry: CashEntry): string | undefined {
  // backend može slati entry_date ili occurred_at – koristimo šta god postoji
  return entry.entry_date ?? entry.occurred_at;
}

function formatDate(value?: string): string {
  if (!value) return "-";
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleDateString("sr-Latn-BA");
  } catch {
    return value;
  }
}

function formatAmount(entry: CashEntry): string {
  const raw = toNumber(entry.amount);
  const sign = entry.kind === "expense" ? "-" : "";
  return `${sign}${raw.toFixed(2)} KM`;
}

function kindLabel(kind?: string) {
  if (kind === "income") return "PRIHOD";
  if (kind === "expense") return "RASHOD";
  return kind ?? "-";
}

function kindBadgeClass(kind?: string): string {
  if (kind === "income") {
    return "inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700";
  }
  if (kind === "expense") {
    return "inline-flex items-center rounded-full bg-rose-50 px-2 py-0.5 text-[11px] font-semibold text-rose-700";
  }
  return "inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600";
}

function accountLabel(account?: string): string {
  if (account === "cash") return "KASA";
  if (account === "bank") return "TEKUĆI RAČUN";
  return "-";
}

function accountBadgeClass(account?: string): string {
  if (account === "cash") {
    return "inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700";
  }
  if (account === "bank") {
    return "inline-flex items-center rounded-full bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-700";
  }
  return "inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600";
}

function linkedInvoiceCell(entry: CashEntry): React.ReactNode {
  if (entry.invoice_id) {
    return (
      <Link
        to={`/invoices/${entry.invoice_id}`}
        className="text-xs font-medium text-slate-700 underline-offset-2 hover:underline"
      >
        Izlazna #{entry.invoice_id}
      </Link>
    );
  }
  if (entry.input_invoice_id) {
    return (
      <Link
        to={`/input-invoices/${entry.input_invoice_id}`}
        className="text-xs font-medium text-slate-700 underline-offset-2 hover:underline"
      >
        Ulazna #{entry.input_invoice_id}
      </Link>
    );
  }
  return <span className="text-xs text-slate-400">—</span>;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function CashPage() {
  const queryClient = useQueryClient();

  const { data, isLoading, isError, error, refetch, isRefetching } = useQuery<
    CashEntry[],
    Error
  >({
    queryKey: ["cash"],
    queryFn: fetchCashEntries,
  });

  const [entryDate, setEntryDate] = useState<string>(todayIso());
  const [kind, setKind] = useState<"income" | "expense">("income");
  const [account, setAccount] = useState<"cash" | "bank">("cash");
  const [amount, setAmount] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [formError, setFormError] = useState<string>("");

  const {
    mutateAsync: createEntry,
    isLoading: isSaving,
  } = useMutation({
    mutationFn: async (payload: CashEntryCreatePayload) =>
      createCashEntry(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cash"] });
      queryClient.invalidateQueries({
        queryKey: ["dashboard", "monthly", "current"],
      });
    },
  });

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError("");

    const parsed = Number(amount);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setFormError("Iznos mora biti veći od nule.");
      return;
    }

    const payload: CashEntryCreatePayload = {
      entry_date: entryDate,
      kind,
      amount: parsed,
      note: description.trim() || null,
      account,
      // invoice_id / input_invoice_id za sada ne unosimo ručno u formi;
      // backend ih može popuniti iz drugih tokova (npr. iz faktura).
    };

    try {
      await createEntry(payload);
      setAmount("");
      setDescription("");
      // po defaultu ostavljamo isti datum, tip i račun (kasa/banka)
      await refetch();
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        "Greška pri snimanju unosa.";
      setFormError(String(msg));
    }
  }

  const totalCount = data?.length ?? 0;
  const totalIncome = (data ?? [])
    .filter((e) => e.kind === "income")
    .reduce((sum, e) => sum + toNumber(e.amount), 0);
  const totalExpense = (data ?? [])
    .filter((e) => e.kind === "expense")
    .reduce((sum, e) => sum + toNumber(e.amount), 0);
  const net = totalIncome - totalExpense;

  return (
    <div className="space-y-6">
      {/* Header + forma */}
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">Kasa</h2>
          <p className="text-xs text-slate-500 mt-1">
            Evidencija svih priliva i odliva po kasi i bankovnom računu za
            tenant{" "}
            <span className="font-mono text-slate-700 bg-slate-100 px-1 py-0.5 rounded">
              t-demo
            </span>
            . Ovi podaci ulaze u KPR i poreske obračune.
          </p>

          <div className="mt-3 inline-flex flex-wrap gap-2 text-xs">
            <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-700">
              Ukupno unosa:{" "}
              <span className="ml-1 font-semibold">{totalCount}</span>
            </span>
            <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700">
              Prihodi:{" "}
              <span className="ml-1 font-semibold">
                {totalIncome.toFixed(2)} KM
              </span>
            </span>
            <span className="inline-flex items-center rounded-full bg-rose-50 px-2 py-0.5 text-[11px] text-rose-700">
              Rashodi:{" "}
              <span className="ml-1 font-semibold">
                {totalExpense.toFixed(2)} KM
              </span>
            </span>
            <span className="inline-flex items-center rounded-full bg-slate-900 px-2 py-0.5 text-[11px] text-white">
              Neto:{" "}
              <span className="ml-1 font-semibold">{net.toFixed(2)} KM</span>
            </span>
          </div>
        </div>

        {/* Forma za novi unos */}
        <form
          onSubmit={handleSubmit}
          className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-4 shadow-sm space-y-3"
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Novi unos
          </p>

          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-xs text-slate-600 space-y-1">
              Datum
              <input
                type="date"
                className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                value={entryDate}
                onChange={(e) => setEntryDate(e.target.value)}
                required
              />
            </label>

            <label className="text-xs text-slate-600 space-y-1">
              Tip
              <select
                className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
                value={kind}
                onChange={(e) =>
                  setKind(e.target.value as "income" | "expense")
                }
              >
                <option value="income">PRIHOD</option>
                <option value="expense">RASHOD</option>
              </select>
            </label>
          </div>

          <label className="text-xs text-slate-600 space-y-1">
            Račun
            <select
              className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              value={account}
              onChange={(e) => setAccount(e.target.value as "cash" | "bank")}
            >
              <option value="cash">KASA</option>
              <option value="bank">TEKUĆI RAČUN</option>
            </select>
          </label>

          <label className="text-xs text-slate-600 space-y-1">
            Iznos (KM)
            <input
              type="number"
              min="0"
              step="0.01"
              className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              required
            />
          </label>

          <label className="text-xs text-slate-600 space-y-1">
            Opis (opciono)
            <input
              type="text"
              className="w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="npr. Uplata računa, gorivo, najam..."
            />
          </label>

          {formError && (
            <p className="text-xs text-red-600">{formError}</p>
          )}

          <div className="flex items-center justify-end gap-2">
            <button
              type="submit"
              disabled={isSaving}
              className="inline-flex items-center rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:bg-slate-800 disabled:opacity-60"
            >
              {isSaving ? "Spašavam..." : "Snimi unos"}
            </button>
          </div>
        </form>
      </div>

      {/* Kontrole liste */}
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-slate-500">
          Evidencija gotovinskih i bezgotovinskih tokova (kasa / tekući račun).
        </p>

        <button
          type="button"
          onClick={() => refetch()}
          className="inline-flex items-center rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-60"
          disabled={isLoading || isRefetching}
        >
          {isRefetching || isLoading ? "Osvježavam..." : "Osvježi listu"}
        </button>
      </div>

      {/* Stanja učitavanja / greške */}
      {isLoading && (
        <p className="text-sm text-slate-600">Učitavam zapise kase...</p>
      )}

      {isError && (
        <p className="text-sm text-red-600">
          Greška pri učitavanju kase: {error.message}
        </p>
      )}

      {/* Lista zapisa */}
      {!!data && data.length === 0 && !isLoading && !isError && (
        <p className="text-sm text-slate-500">
          Trenutno nema unosa u kasi/banci.
        </p>
      )}

      {!!data && data.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left font-medium whitespace-nowrap">
                  Datum
                </th>
                <th className="px-3 py-2 text-left font-medium whitespace-nowrap">
                  Račun
                </th>
                <th className="px-3 py-2 text-left font-medium whitespace-nowrap">
                  Tip
                </th>
                <th className="px-3 py-2 text-left font-medium">Opis</th>
                <th className="px-3 py-2 text-right font-medium whitespace-nowrap">
                  Iznos
                </th>
                <th className="px-3 py-2 text-left font-medium whitespace-nowrap">
                  Povezana faktura
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {data.map((entry) => {
                const desc = entry.description ?? entry.note;
                return (
                  <tr key={entry.id}>
                    <td className="px-3 py-2 text-xs whitespace-nowrap">
                      {formatDate(pickDate(entry))}
                    </td>
                    <td className="px-3 py-2 text-xs whitespace-nowrap">
                      <span className={accountBadgeClass(entry.account)}>
                        {accountLabel(entry.account)}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-xs whitespace-nowrap">
                      <span className={kindBadgeClass(entry.kind)}>
                        {kindLabel(entry.kind)}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      {desc ? (
                        <span className="text-xs text-slate-800">
                          {desc}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right font-medium whitespace-nowrap">
                      {formatAmount(entry)}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      {linkedInvoiceCell(entry)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
