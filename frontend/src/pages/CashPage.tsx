// /home/miso/dev/sp-app/sp-app/frontend/src/pages/CashPage.tsx

import React, { FormEvent, useMemo, useState } from "react";
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

function formatMoney(value: number): string {
  return `${value.toFixed(2)} KM`;
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
    return "inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700 ring-1 ring-emerald-100";
  }
  if (kind === "expense") {
    return "inline-flex items-center rounded-full bg-rose-50 px-2.5 py-1 text-[11px] font-semibold text-rose-700 ring-1 ring-rose-100";
  }
  return "inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600 ring-1 ring-slate-200";
}

function accountLabel(account?: string): string {
  if (account === "cash") return "KASA";
  if (account === "bank") return "TEKUĆI RAČUN";
  return "-";
}

function accountBadgeClass(account?: string): string {
  if (account === "cash") {
    return "inline-flex items-center rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-700 ring-1 ring-amber-100";
  }
  if (account === "bank") {
    return "inline-flex items-center rounded-full bg-sky-50 px-2.5 py-1 text-[11px] font-medium text-sky-700 ring-1 ring-sky-100";
  }
  return "inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600 ring-1 ring-slate-200";
}

function linkedInvoiceCell(entry: CashEntry): React.ReactNode {
  if (entry.invoice_id) {
    return (
      <Link
        to={`/invoices/${entry.invoice_id}`}
        className="text-xs font-semibold text-slate-700 underline-offset-2 hover:text-slate-950 hover:underline"
      >
        Izlazna #{entry.invoice_id}
      </Link>
    );
  }

  if (entry.input_invoice_id) {
    return (
      <Link
        to={`/input-invoices/${entry.input_invoice_id}`}
        className="text-xs font-semibold text-slate-700 underline-offset-2 hover:text-slate-950 hover:underline"
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

  const { mutateAsync: createEntry, isPending: isSaving } = useMutation({
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
    };

    try {
      await createEntry(payload);
      setAmount("");
      setDescription("");
      await refetch();
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        "Greška pri snimanju unosa.";
      setFormError(String(msg));
    }
  }

  const stats = useMemo(() => {
    const entries = data ?? [];

    const totalIncome = entries
      .filter((e) => e.kind === "income")
      .reduce((sum, e) => sum + toNumber(e.amount), 0);

    const totalExpense = entries
      .filter((e) => e.kind === "expense")
      .reduce((sum, e) => sum + toNumber(e.amount), 0);

    const cashTotal = entries
      .filter((e) => e.account === "cash")
      .reduce((sum, e) => {
        const amountValue = toNumber(e.amount);
        return e.kind === "expense" ? sum - amountValue : sum + amountValue;
      }, 0);

    const bankTotal = entries
      .filter((e) => e.account === "bank")
      .reduce((sum, e) => {
        const amountValue = toNumber(e.amount);
        return e.kind === "expense" ? sum - amountValue : sum + amountValue;
      }, 0);

    return {
      totalCount: entries.length,
      totalIncome,
      totalExpense,
      net: totalIncome - totalExpense,
      cashTotal,
      bankTotal,
    };
  }, [data]);

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 px-6 py-7 text-white">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <div className="mb-3 inline-flex items-center rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-slate-200 ring-1 ring-white/15">
                Cash / Promet / Tok novca
              </div>

              <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
                Finansijski tokovi kase i banke
              </h1>

              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
                Centralna evidencija priliva i odliva za tenant{" "}
                <span className="rounded-md bg-white/10 px-1.5 py-0.5 font-mono text-white">
                  t-demo
                </span>
                . Ovi podaci se koriste za pregled novca, dashboard metrike,
                KPR i kasnije poreske obračune.
              </p>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => refetch()}
                disabled={isLoading || isRefetching}
                className="inline-flex items-center rounded-xl bg-white px-4 py-2 text-xs font-semibold text-slate-900 shadow-sm hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isRefetching || isLoading ? "Osvježavam..." : "Osvježi podatke"}
              </button>
            </div>
          </div>
        </div>

        <div className="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Neto stanje
            </p>
            <p className="mt-2 text-2xl font-semibold text-slate-950">
              {formatMoney(stats.net)}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Prihodi minus rashodi
            </p>
          </div>

          <div className="rounded-2xl border border-emerald-100 bg-emerald-50 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-emerald-700">
              Ukupni prihodi
            </p>
            <p className="mt-2 text-2xl font-semibold text-emerald-800">
              {formatMoney(stats.totalIncome)}
            </p>
            <p className="mt-1 text-xs text-emerald-700/80">
              Svi evidentirani prilivi
            </p>
          </div>

          <div className="rounded-2xl border border-rose-100 bg-rose-50 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-rose-700">
              Ukupni rashodi
            </p>
            <p className="mt-2 text-2xl font-semibold text-rose-800">
              {formatMoney(stats.totalExpense)}
            </p>
            <p className="mt-1 text-xs text-rose-700/80">
              Svi evidentirani odlivi
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Broj unosa
            </p>
            <p className="mt-2 text-2xl font-semibold text-slate-950">
              {stats.totalCount}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Ručni i povezani zapisi
            </p>
          </div>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-sm font-semibold text-slate-950">
                  Evidencija prometa
                </h2>
                <p className="mt-1 text-xs text-slate-500">
                  Gotovinski i bezgotovinski tokovi kroz kasu i tekući račun.
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                <span className="inline-flex items-center rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700 ring-1 ring-amber-100">
                  Kasa: {formatMoney(stats.cashTotal)}
                </span>
                <span className="inline-flex items-center rounded-full bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700 ring-1 ring-sky-100">
                  Banka: {formatMoney(stats.bankTotal)}
                </span>
              </div>
            </div>
          </div>

          {isLoading && (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">
              Učitavam zapise kase...
            </div>
          )}

          {isError && (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700 shadow-sm">
              Greška pri učitavanju kase: {error.message}
            </div>
          )}

          {!!data && data.length === 0 && !isLoading && !isError && (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center shadow-sm">
              <p className="text-sm font-semibold text-slate-800">
                Trenutno nema unosa u kasi/banci.
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Prvi unos možeš dodati kroz panel sa desne strane.
              </p>
            </div>
          )}

          {!!data && data.length > 0 && (
            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-slate-500">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide whitespace-nowrap">
                        Datum
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide whitespace-nowrap">
                        Račun
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide whitespace-nowrap">
                        Tip
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide">
                        Opis
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide whitespace-nowrap">
                        Iznos
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide whitespace-nowrap">
                        Povezana faktura
                      </th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {data.map((entry) => {
                      const desc = entry.description ?? entry.note;

                      return (
                        <tr
                          key={entry.id}
                          className="transition hover:bg-slate-50/80"
                        >
                          <td className="px-4 py-3 text-xs whitespace-nowrap text-slate-600">
                            {formatDate(pickDate(entry))}
                          </td>

                          <td className="px-4 py-3 text-xs whitespace-nowrap">
                            <span className={accountBadgeClass(entry.account)}>
                              {accountLabel(entry.account)}
                            </span>
                          </td>

                          <td className="px-4 py-3 text-xs whitespace-nowrap">
                            <span className={kindBadgeClass(entry.kind)}>
                              {kindLabel(entry.kind)}
                            </span>
                          </td>

                          <td className="px-4 py-3">
                            {desc ? (
                              <span className="text-xs font-medium text-slate-800">
                                {desc}
                              </span>
                            ) : (
                              <span className="text-xs text-slate-400">—</span>
                            )}
                          </td>

                          <td className="px-4 py-3 text-right text-sm font-semibold whitespace-nowrap text-slate-950">
                            {formatAmount(entry)}
                          </td>

                          <td className="px-4 py-3 whitespace-nowrap">
                            {linkedInvoiceCell(entry)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>

        <aside className="xl:sticky xl:top-6 xl:self-start">
          <form
            onSubmit={handleSubmit}
            className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm"
          >
            <div className="border-b border-slate-100 bg-slate-50 px-5 py-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Quick Entry
              </p>
              <h2 className="mt-1 text-lg font-semibold text-slate-950">
                Novi unos prometa
              </h2>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Ručno evidentiraj prihod ili rashod po kasi ili tekućem računu.
              </p>
            </div>

            <div className="space-y-4 p-5">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-2">
                <label className="space-y-1.5 text-xs font-medium text-slate-600">
                  Datum
                  <input
                    type="date"
                    className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                    value={entryDate}
                    onChange={(e) => setEntryDate(e.target.value)}
                    required
                  />
                </label>

                <label className="space-y-1.5 text-xs font-medium text-slate-600">
                  Tip
                  <select
                    className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
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

              <label className="space-y-1.5 text-xs font-medium text-slate-600">
                Račun
                <select
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                  value={account}
                  onChange={(e) =>
                    setAccount(e.target.value as "cash" | "bank")
                  }
                >
                  <option value="cash">KASA</option>
                  <option value="bank">TEKUĆI RAČUN</option>
                </select>
              </label>

              <label className="space-y-1.5 text-xs font-medium text-slate-600">
                Iznos (KM)
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="0.00"
                  required
                />
              </label>

              <label className="space-y-1.5 text-xs font-medium text-slate-600">
                Opis
                <input
                  type="text"
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="npr. Uplata računa, gorivo, najam..."
                />
              </label>

              {formError && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                  {formError}
                </div>
              )}

              <button
                type="submit"
                disabled={isSaving}
                className="inline-flex w-full items-center justify-center rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSaving ? "Spašavam..." : "Snimi unos"}
              </button>

              <div className="rounded-2xl bg-slate-50 p-4 text-xs leading-5 text-slate-500">
                <p className="font-semibold text-slate-700">Napomena</p>
                <p className="mt-1">
                  Povezivanje sa izlaznim i ulaznim fakturama ostaje kroz
                  postojeće tokove. Ova forma je za brze ručne unose prometa.
                </p>
              </div>
            </div>
          </form>
        </aside>
      </div>
    </div>
  );
}