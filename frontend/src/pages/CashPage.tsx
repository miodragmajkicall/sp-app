// /home/miso/dev/sp-app/sp-app/frontend/src/pages/CashPage.tsx

import React, { FormEvent, useState } from "react";
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

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function CashPage() {
  const queryClient = useQueryClient();

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    isRefetching,
  } = useQuery<CashEntry[], Error>({
    queryKey: ["cash"],
    queryFn: fetchCashEntries,
  });

  const [entryDate, setEntryDate] = useState<string>(todayIso());
  const [kind, setKind] = useState<"income" | "expense">("income");
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

  return (
    <div className="space-y-6">
      {/* Header + forma */}
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">Kasa</h2>
          <p className="text-xs text-slate-500 mt-1">
            Lista svih unosa u kasi za tenant{" "}
            <span className="font-mono">t-demo</span>.
          </p>
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
          Ukupno unosa:{" "}
          <span className="font-semibold text-slate-700">
            {data?.length ?? 0}
          </span>
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
          Trenutno nema unosa u kasi.
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
                <th className="px-3 py-2 text-left font-medium">Tip</th>
                <th className="px-3 py-2 text-left font-medium">Opis</th>
                <th className="px-3 py-2 text-right font-medium">Iznos</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {data.map((entry) => {
                const desc = entry.description ?? entry.note;

                return (
                  <tr key={entry.id}>
                    <td className="px-3 py-2 text-xs">
                      {formatDate(pickDate(entry))}
                    </td>
                    <td className="px-3 py-2 text-xs">
                      {kindLabel(entry.kind)}
                    </td>
                    <td className="px-3 py-2">
                      {desc ?? <span className="text-slate-400">-</span>}
                    </td>
                    <td className="px-3 py-2 text-right font-medium">
                      {formatAmount(entry)}
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
