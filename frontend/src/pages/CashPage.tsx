// /home/miso/dev/sp-app/sp-app/frontend/src/pages/CashPage.tsx

import React, { FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchCashEntries,
  fetchCashSummary,
  createCashEntry,
  updateCashEntry,
  deleteCashEntry,
  type CashEntryCreatePayload,
  type CashEntryUpdatePayload,
  type CashListParams,
  type CashSummaryParams,
} from "../services/cashApi";
import type {
  CashAccount,
  CashEntry,
  CashKind,
  CashListItem,
  CashListResponse,
  CashRecognitionClass,
  CashSourceType,
  CashSummary,
  CashTaxTreatment,
} from "../types/cash";

const PAGE_SIZE = 20;

function toNumber(value: number | string | undefined | null): number {
  if (value === undefined || value === null) return 0;
  if (typeof value === "number") return value;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? 0 : parsed;
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

function sourceLabel(source: CashSourceType): string {
  if (source === "manual") return "RUČNI";
  if (source === "output_invoice_payment") return "NAPLATA";
  return "PLAĆANJE";
}

function sourceBadgeClass(source: CashSourceType): string {
  if (source === "manual") {
    return "inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600 ring-1 ring-slate-200";
  }

  if (source === "output_invoice_payment") {
    return "inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700 ring-1 ring-emerald-100";
  }

  return "inline-flex items-center rounded-full bg-rose-50 px-2.5 py-1 text-[11px] font-semibold text-rose-700 ring-1 ring-rose-100";
}

function recognitionLabel(value: CashRecognitionClass): string {
  if (value === "business_activity") return "POSLOVNI";
  return "SAMO TOK";
}

function recognitionBadgeClass(value: CashRecognitionClass): string {
  if (value === "business_activity") {
    return "inline-flex items-center rounded-full bg-sky-50 px-2 py-0.5 text-[10px] font-semibold text-sky-700 ring-1 ring-sky-100";
  }

  return "inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600 ring-1 ring-slate-200";
}

function taxTreatmentLabel(value: CashTaxTreatment): string {
  if (value === "deductible") return "ODBITNO";
  if (value === "nondeductible") return "NEODBITNO";
  return "NERAZRIJEŠENO";
}

function taxTreatmentBadgeClass(value: CashTaxTreatment): string {
  if (value === "deductible") {
    return "inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 ring-1 ring-emerald-100";
  }

  if (value === "nondeductible") {
    return "inline-flex items-center rounded-full bg-rose-50 px-2 py-0.5 text-[10px] font-semibold text-rose-700 ring-1 ring-rose-100";
  }

  return "inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-800 ring-1 ring-amber-100";
}

function treatmentCell(entry: CashListItem): React.ReactNode {
  if (entry.source_type !== "manual") {
    return <span className="text-xs text-slate-400">—</span>;
  }

  if (!entry.recognition_class) {
    return (
      <span className="inline-flex items-center rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-semibold text-red-700 ring-1 ring-red-100">
        NEMA KLASIFIKACIJE
      </span>
    );
  }

  const showTaxTreatment =
    entry.kind === "expense" &&
    entry.recognition_class === "business_activity";

  return (
    <div className="flex min-w-[120px] flex-col items-start gap-1">
      <span className={recognitionBadgeClass(entry.recognition_class)}>
        {recognitionLabel(entry.recognition_class)}
      </span>

      {showTaxTreatment &&
        (entry.tax_treatment ? (
          <span className={taxTreatmentBadgeClass(entry.tax_treatment)}>
            {taxTreatmentLabel(entry.tax_treatment)}
          </span>
        ) : (
          <span className="inline-flex items-center rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-semibold text-red-700 ring-1 ring-red-100">
            NEMA TRETMANA
          </span>
        ))}
    </div>
  );
}

function sourceDocumentCell(entry: CashListItem): React.ReactNode {
  if (
    entry.source_type === "output_invoice_payment" &&
    entry.source_document_id
  ) {
    return (
      <div className="min-w-[150px]">
        <Link
          to={`/invoices/${entry.source_document_id}`}
          className="text-xs font-semibold text-slate-800 underline-offset-2 hover:text-slate-950 hover:underline"
        >
          {entry.source_document_number ?? `#${entry.source_document_id}`}
        </Link>
        {entry.source_party_name && (
          <p className="mt-0.5 text-[11px] text-slate-500">
            {entry.source_party_name}
          </p>
        )}
      </div>
    );
  }

  if (
    entry.source_type === "input_invoice_payment" &&
    entry.source_document_id
  ) {
    return (
      <div className="min-w-[150px]">
        <Link
          to={`/input-invoices/${entry.source_document_id}`}
          className="text-xs font-semibold text-slate-800 underline-offset-2 hover:text-slate-950 hover:underline"
        >
          {entry.source_document_number ?? `#${entry.source_document_id}`}
        </Link>
        {entry.source_party_name && (
          <p className="mt-0.5 text-[11px] text-slate-500">
            {entry.source_party_name}
          </p>
        )}
      </div>
    );
  }

  return <span className="text-xs text-slate-400">—</span>;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function CashPage() {
  const queryClient = useQueryClient();

    const [dateFrom, setDateFrom] = useState("");
    const [dateTo, setDateTo] = useState("");
    const [kindFilter, setKindFilter] = useState<"" | CashKind>("");
    const [accountFilter, setAccountFilter] = useState<"" | CashAccount>("");
    const [sourceFilter, setSourceFilter] = useState<"" | CashSourceType>("");
    const [page, setPage] = useState(0);

    const listParams = useMemo<CashListParams>(
      () => ({
        ...(dateFrom ? { date_from: dateFrom } : {}),
        ...(dateTo ? { date_to: dateTo } : {}),
        ...(kindFilter ? { kind: kindFilter } : {}),
        ...(accountFilter ? { account: accountFilter } : {}),
        ...(sourceFilter ? { source_type: sourceFilter } : {}),
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
      [dateFrom, dateTo, kindFilter, accountFilter, sourceFilter, page]
    );

    const summaryParams = useMemo<CashSummaryParams>(
      () => ({
        ...(dateFrom ? { date_from: dateFrom } : {}),
        ...(dateTo ? { date_to: dateTo } : {}),
      }),
      [dateFrom, dateTo]
    );

    const {
      data,
      isLoading,
      isError,
      error,
      refetch: refetchList,
      isRefetching,
    } = useQuery<CashListResponse, Error>({
      queryKey: ["cash", "list", listParams],
      queryFn: () => fetchCashEntries(listParams),
    });

    const {
      data: summaryData,
      isLoading: isSummaryLoading,
      refetch: refetchSummary,
      isRefetching: isSummaryRefetching,
    } = useQuery<CashSummary, Error>({
      queryKey: ["cash", "summary", summaryParams],
      queryFn: () => fetchCashSummary(summaryParams),
    });

    const [entryDate, setEntryDate] = useState<string>(todayIso());
    const [kind, setKind] = useState<CashKind>("income");
    const [account, setAccount] = useState<CashAccount>("cash");
    const [recognitionClass, setRecognitionClass] =
      useState<CashRecognitionClass>("business_activity");
    const [taxTreatment, setTaxTreatment] =
      useState<CashTaxTreatment>("unresolved");
    const [amount, setAmount] = useState<string>("");
    const [description, setDescription] = useState<string>("");
    const [formError, setFormError] = useState<string>("");

    const [editingEntryId, setEditingEntryId] = useState<number | null>(null);
    const [deletingEntryId, setDeletingEntryId] = useState<number | null>(null);
    const [rowActionError, setRowActionError] = useState("");

    function invalidateCashConsumers() {
      queryClient.invalidateQueries({ queryKey: ["cash"] });
      queryClient.invalidateQueries({ queryKey: ["kpr"] });
      queryClient.invalidateQueries({
        queryKey: ["dashboard", "monthly", "current"],
      });
      queryClient.invalidateQueries({ queryKey: ["reports"] });
    }

    function resetEntryForm() {
      setEntryDate(todayIso());
      setKind("income");
      setAccount("cash");
      setRecognitionClass("business_activity");
      setTaxTreatment("unresolved");
      setAmount("");
      setDescription("");
      setFormError("");
    }

    function cancelEdit() {
      setEditingEntryId(null);
      resetEntryForm();
    }

    function startEdit(entry: CashListItem) {
      if (entry.source_type !== "manual") return;

      setEditingEntryId(entry.id);
      setEntryDate(entry.entry_date);
      setKind(entry.kind);
      setAccount(entry.account);
      setRecognitionClass(entry.recognition_class ?? "business_activity");
      setTaxTreatment(entry.tax_treatment ?? "unresolved");
      setAmount(String(entry.amount));
      setDescription(entry.note ?? "");
      setFormError("");
      setRowActionError("");
    }

    const { mutateAsync: createEntry, isPending: isSaving } = useMutation({
      mutationFn: (payload: CashEntryCreatePayload) =>
        createCashEntry(payload),
      onSuccess: invalidateCashConsumers,
    });

    const { mutateAsync: updateEntry, isPending: isUpdating } = useMutation({
      mutationFn: ({
        cashId,
        payload,
      }: {
        cashId: number;
        payload: CashEntryUpdatePayload;
      }) => updateCashEntry(cashId, payload),
      onSuccess: invalidateCashConsumers,
    });

    const { mutateAsync: removeEntry } = useMutation({
      mutationFn: (cashId: number) => deleteCashEntry(cashId),
      onSuccess: invalidateCashConsumers,
    });

    const isFormSaving = isSaving || isUpdating;

    async function handleDelete(entry: CashListItem) {
      if (entry.source_type !== "manual") return;

      const confirmed = window.confirm(
        "Da li sigurno želiš obrisati ovaj ručni zapis?"
      );
      if (!confirmed) return;

      setRowActionError("");
      setDeletingEntryId(entry.id);

      try {
        await removeEntry(entry.id);

        if (editingEntryId === entry.id) {
          cancelEdit();
        }

        if (data?.items.length === 1 && page > 0) {
          setPage((current) => Math.max(0, current - 1));
        }
      } catch (err: any) {
        const detail = err?.response?.data?.detail;

        setRowActionError(
          typeof detail === "string"
            ? detail
            : err?.message || "Greška pri brisanju unosa."
        );
      } finally {
        setDeletingEntryId(null);
      }
    }

    async function handleSubmit(e: FormEvent) {
      e.preventDefault();
      setFormError("");

      const parsed = Number(amount);
      if (!Number.isFinite(parsed) || parsed <= 0) {
        setFormError("Iznos mora biti veći od nule.");
        return;
      }

      const taxTreatmentForPayload =
        kind === "expense" && recognitionClass === "business_activity"
          ? taxTreatment
          : null;

      try {
        if (editingEntryId !== null) {
          const payload: CashEntryUpdatePayload = {
            entry_date: entryDate,
            kind,
            amount: parsed,
            account,
            recognition_class: recognitionClass,
            tax_treatment: taxTreatmentForPayload,
            note: description.trim() || null,
          };

          await updateEntry({
            cashId: editingEntryId,
            payload,
          });

          setEditingEntryId(null);
          resetEntryForm();
          return;
        }

        const payload: CashEntryCreatePayload = {
          entry_date: entryDate,
          kind,
          amount: parsed,
          account,
          recognition_class: recognitionClass,
          tax_treatment: taxTreatmentForPayload,
          note: description.trim() || null,
        };

        await createEntry(payload);
        resetEntryForm();
      } catch (err: any) {
        const detail = err?.response?.data?.detail;

        setFormError(
          typeof detail === "string"
            ? detail
            : err?.message || "Greška pri snimanju unosa."
        );
      }
    }

    const currentPage = Math.floor((data?.offset ?? 0) / PAGE_SIZE) + 1;
    const hasPrevious = page > 0;
    const hasNext = data
      ? data.offset + data.items.length < data.total
      : false;

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
                onClick={() => {
                  void refetchList();
                  void refetchSummary();
                }}
                disabled={
                  isLoading ||
                  isRefetching ||
                  isSummaryLoading ||
                  isSummaryRefetching
                }
                className="inline-flex items-center rounded-xl bg-white px-4 py-2 text-xs font-semibold text-slate-900 shadow-sm hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isRefetching ||
                isLoading ||
                isSummaryLoading ||
                isSummaryRefetching
                  ? "Osvježavam..."
                  : "Osvježi podatke"}
              </button>
            </div>
          </div>
        </div>

        <div className="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Neto tok
            </p>
            <p className="mt-2 text-2xl font-semibold text-slate-950">
              {formatMoney(toNumber(summaryData?.net))}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Ukupni priliv minus odliv u aktivnom periodu
            </p>
          </div>

          <div className="rounded-2xl border border-emerald-100 bg-emerald-50 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-emerald-700">
              Prilivi
            </p>
            <p className="mt-2 text-2xl font-semibold text-emerald-800">
              {formatMoney(toNumber(summaryData?.income))}
            </p>
            <p className="mt-1 text-xs text-emerald-700/80">
              Ukupni prilivi u aktivnom periodu
            </p>
          </div>

          <div className="rounded-2xl border border-rose-100 bg-rose-50 p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-rose-700">
              Odlivi
            </p>
            <p className="mt-2 text-2xl font-semibold text-rose-800">
              {formatMoney(toNumber(summaryData?.expense))}
            </p>
            <p className="mt-1 text-xs text-rose-700/80">
              Ukupni odlivi u aktivnom periodu
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Zapisi
            </p>
            <p className="mt-2 text-2xl font-semibold text-slate-950">
              {summaryData?.total_count ?? 0}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Cash/Bank zapisi u aktivnom periodu
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
                    Neto tok kase:{" "}
                    {formatMoney(toNumber(summaryData?.cash_net))}
                  </span>
                  <span className="inline-flex items-center rounded-full bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700 ring-1 ring-sky-100">
                    Neto tok banke:{" "}
                    {formatMoney(toNumber(summaryData?.bank_net))}
                  </span>
                </div>
            </div>
          </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <label className="space-y-1 text-xs font-medium text-slate-600">
                  Od datuma
                  <input
                    type="date"
                    value={dateFrom}
                    onChange={(e) => {
                      setDateFrom(e.target.value);
                      setPage(0);
                    }}
                    className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
                  />
                </label>

                <label className="space-y-1 text-xs font-medium text-slate-600">
                  Do datuma
                  <input
                    type="date"
                    value={dateTo}
                    onChange={(e) => {
                      setDateTo(e.target.value);
                      setPage(0);
                    }}
                    className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
                  />
                </label>

                <label className="space-y-1 text-xs font-medium text-slate-600">
                  Tip
                  <select
                    value={kindFilter}
                    onChange={(e) => {
                      setKindFilter(e.target.value as "" | CashKind);
                      setPage(0);
                    }}
                    className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
                  >
                    <option value="">Svi</option>
                    <option value="income">Prihodi</option>
                    <option value="expense">Rashodi</option>
                  </select>
                </label>

                <label className="space-y-1 text-xs font-medium text-slate-600">
                  Račun
                  <select
                    value={accountFilter}
                    onChange={(e) => {
                      setAccountFilter(e.target.value as "" | CashAccount);
                      setPage(0);
                    }}
                    className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
                  >
                    <option value="">Svi</option>
                    <option value="cash">Kasa</option>
                    <option value="bank">Tekući račun</option>
                  </select>
                </label>

                <label className="space-y-1 text-xs font-medium text-slate-600">
                  Izvor
                  <select
                    value={sourceFilter}
                    onChange={(e) => {
                      setSourceFilter(e.target.value as "" | CashSourceType);
                      setPage(0);
                    }}
                    className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900"
                  >
                    <option value="">Svi</option>
                    <option value="manual">Ručni unos</option>
                    <option value="output_invoice_payment">Izlazna faktura</option>
                    <option value="input_invoice_payment">Ulazna faktura</option>
                  </select>
                </label>
              </div>

              <div className="mt-3 flex justify-end">
                <button
                  type="button"
                  onClick={() => {
                    setDateFrom("");
                    setDateTo("");
                    setKindFilter("");
                    setAccountFilter("");
                    setSourceFilter("");
                    setPage(0);
                  }}
                  className="text-xs font-semibold text-slate-600 hover:text-slate-950"
                >
                  Poništi filtere
                </button>
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

            {rowActionError && (
              <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-700 shadow-sm">
                {rowActionError}
              </div>
            )}

{!!data && data.items.length === 0 && !isLoading && !isError && (
  <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center shadow-sm">
    <p className="text-sm font-semibold text-slate-800">
      Nema zapisa za aktivne filtere.
    </p>
    <p className="mt-1 text-xs text-slate-500">
      Promijeni filtere ili dodaj novi ručni unos.
    </p>
  </div>
)}

{!!data && data.items.length > 0 && (
  <>
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
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide whitespace-nowrap">
                Izvor
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide whitespace-nowrap">
                Tretman
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide">
                Opis
              </th>
              <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide whitespace-nowrap">
                Iznos
              </th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide">
                  Dokument
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide whitespace-nowrap">
                  Akcije
                </th>
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-100 text-slate-700">
            {data.items.map((entry) => (
              <tr
                key={entry.id}
                className="transition hover:bg-slate-50/80"
              >
                <td className="px-4 py-3 text-xs whitespace-nowrap text-slate-600">
                  {formatDate(entry.entry_date)}
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

                <td className="px-4 py-3 text-xs whitespace-nowrap">
                  <span className={sourceBadgeClass(entry.source_type)}>
                    {sourceLabel(entry.source_type)}
                  </span>
                </td>

                <td className="px-4 py-3">
                  {treatmentCell(entry)}
                </td>

                <td className="px-4 py-3">
                  {entry.note ? (
                    <span className="text-xs font-medium text-slate-800">
                      {entry.note}
                    </span>
                  ) : (
                    <span className="text-xs text-slate-400">—</span>
                  )}
                </td>

                <td className="px-4 py-3 text-right text-sm font-semibold whitespace-nowrap text-slate-950">
                  {formatAmount(entry)}
                </td>

                  <td className="px-4 py-3">
                    {sourceDocumentCell(entry)}
                  </td>

                  <td className="px-4 py-3 text-right whitespace-nowrap">
                    {entry.source_type === "manual" ? (
                      <div className="inline-flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => startEdit(entry)}
                          disabled={isFormSaving || deletingEntryId === entry.id}
                          className="text-xs font-semibold text-slate-600 hover:text-slate-950 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Izmijeni
                        </button>

                        <button
                          type="button"
                          onClick={() => handleDelete(entry)}
                          disabled={isFormSaving || deletingEntryId === entry.id}
                          className="text-xs font-semibold text-rose-600 hover:text-rose-800 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {deletingEntryId === entry.id ? "Brišem..." : "Obriši"}
                        </button>
                      </div>
                    ) : (
                      <span className="text-xs text-slate-400">—</span>
                    )}
                  </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>

    <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
      <p className="text-xs text-slate-500">
        Prikazano {data.items.length} od {data.total} zapisa
      </p>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setPage((current) => Math.max(0, current - 1))}
          disabled={!hasPrevious || isRefetching}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Prethodna
        </button>

        <span className="px-2 text-xs font-medium text-slate-600">
          Stranica {currentPage}
        </span>

        <button
          type="button"
          onClick={() => setPage((current) => current + 1)}
          disabled={!hasNext || isRefetching}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Sljedeća
        </button>
      </div>
    </div>
  </>
)}
        </section>

        <aside className="xl:sticky xl:top-6 xl:self-start">
          <form
            onSubmit={handleSubmit}
            className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm"
          >
              <div className="border-b border-slate-100 bg-slate-50 px-5 py-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {editingEntryId === null ? "Quick Entry" : "Izmjena"}
                </p>
                <h2 className="mt-1 text-lg font-semibold text-slate-950">
                  {editingEntryId === null
                    ? "Novi unos prometa"
                    : "Izmjena ručnog unosa"}
                </h2>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  {editingEntryId === null
                    ? "Ručno evidentiraj prihod ili rashod po kasi ili tekućem računu."
                    : "Izmijeni datum, tip, račun, iznos ili napomenu ručnog zapisa."}
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
                Namjena unosa
                <select
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                  value={recognitionClass}
                  onChange={(e) =>
                    setRecognitionClass(
                      e.target.value as CashRecognitionClass
                    )
                  }
                >
                  <option value="business_activity">
                    POSLOVNI DOGAĐAJ
                  </option>
                  <option value="cash_only">
                    SAMO NOVČANI TOK
                  </option>
                </select>
                <span className="block text-[11px] font-normal leading-4 text-slate-500">
                  Poslovni događaj može učestvovati u poslovnim i poreskim
                  evidencijama. Samo novčani tok utiče samo na kretanje novca.
                </span>
              </label>

              {kind === "expense" &&
                recognitionClass === "business_activity" && (
                  <label className="space-y-1.5 text-xs font-medium text-slate-600">
                    Poreski tretman rashoda
                    <select
                      className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-slate-500 focus:ring-2 focus:ring-slate-200"
                      value={taxTreatment}
                      onChange={(e) =>
                        setTaxTreatment(
                          e.target.value as CashTaxTreatment
                        )
                      }
                    >
                      <option value="unresolved">NERAZRIJEŠENO</option>
                      <option value="deductible">PORESKI ODBITNO</option>
                      <option value="nondeductible">
                        PORESKI NEODBITNO
                      </option>
                    </select>

                    {taxTreatment === "unresolved" && (
                      <span className="block rounded-lg bg-amber-50 px-2.5 py-2 text-[11px] font-normal leading-4 text-amber-800 ring-1 ring-amber-100">
                        Nerazriješen poreski tretman neće biti automatski
                        smatran odbitnim i može blokirati završni automatski
                        poreski obračun dok se ne razriješi.
                      </span>
                    )}
                  </label>
                )}

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

                <div className="flex gap-2">
                  {editingEntryId !== null && (
                    <button
                      type="button"
                      onClick={cancelEdit}
                      disabled={isFormSaving}
                      className="inline-flex flex-1 items-center justify-center rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      Odustani
                    </button>
                  )}

                  <button
                    type="submit"
                    disabled={isFormSaving}
                    className="inline-flex flex-1 items-center justify-center rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isFormSaving
                      ? "Spašavam..."
                      : editingEntryId === null
                        ? "Snimi unos"
                        : "Sačuvaj izmjene"}
                  </button>
                </div>

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
