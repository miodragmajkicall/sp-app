// /home/miso/dev/sp-app/sp-app/frontend/src/pages/InputInvoicesPage.tsx
import { useState, type ChangeEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import {
  deleteInvoiceAttachment,
  downloadInvoiceAttachment,
  fetchInputInvoicesList,
  fetchInvoiceAttachments,
  linkAttachmentToInputInvoice,
  uploadInvoiceAttachment,
  type InvoiceAttachmentItem,
} from "../services/inputInvoicesApi";
import type {
  InputInvoiceListItem,
  InputInvoiceListResponse,
} from "../types/inputInvoice";

function formatDate(value?: string | null): string {
  if (!value) return "-";
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleDateString("sr-Latn-BA");
  } catch {
    return value ?? "-";
  }
}

function formatAmount(value?: number | null): string {
  if (value == null) return "-";
  return `${value.toFixed(2)} KM`;
}

function formatBytes(size?: number | null): string {
  if (size == null || Number.isNaN(size)) return "-";
  if (size < 1024) return `${size} B`;
  const kb = size / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  return `${mb.toFixed(1)} MB`;
}

const CURRENT_YEAR = new Date().getFullYear();
const CURRENT_MONTH = new Date().getMonth() + 1;

const EXPENSE_CATEGORY_OPTIONS = [
  "",
  "Gorivo",
  "Kancelarijski materijal",
  "Komunalije",
  "Telekom usluge",
  "Usluge trećih lica",
  "Ostali troškovi",
];

const MONTH_LABELS: Record<number, string> = {
  1: "Januar",
  2: "Februar",
  3: "Mart",
  4: "April",
  5: "Maj",
  6: "Jun",
  7: "Jul",
  8: "Avgust",
  9: "Septembar",
  10: "Oktobar",
  11: "Novembar",
  12: "Decembar",
};

function PaidBadge({ value }: { value?: boolean | null }) {
  if (value == null) {
    return (
      <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-500">
        Nepoznato
      </span>
    );
  }

  return value ? (
    <span className="inline-flex rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700 ring-1 ring-emerald-200">
      Plaćeno
    </span>
  ) : (
    <span className="inline-flex rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-semibold text-amber-700 ring-1 ring-amber-200">
      Nije plaćeno
    </span>
  );
}

function DeductibleBadge({ value }: { value?: boolean | null }) {
  if (value == null) {
    return (
      <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-500">
        -
      </span>
    );
  }

  return value ? (
    <span className="inline-flex rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-700 ring-1 ring-blue-200">
      Priznat
    </span>
  ) : (
    <span className="inline-flex rounded-full bg-red-50 px-2.5 py-1 text-[11px] font-semibold text-red-700 ring-1 ring-red-200">
      Nepriznat
    </span>
  );
}

export default function InputInvoicesPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [year, setYear] = useState<number | undefined>(CURRENT_YEAR);
  const [month, setMonth] = useState<number | undefined>(CURRENT_MONTH);
  const [supplierFilter, setSupplierFilter] = useState("");
  const [expenseCategoryFilter, setExpenseCategoryFilter] = useState("");

  const [attachmentTargetInvoice, setAttachmentTargetInvoice] = useState<
    Record<number, number | "">
  >({});

  const {
    data: invoicesData,
    isLoading,
    isError,
    error,
    refetch,
    isRefetching,
  } = useQuery<InputInvoiceListResponse, Error>({
    queryKey: [
      "input-invoices",
      { year, month, supplierFilter, expenseCategoryFilter },
    ],
    queryFn: () =>
      fetchInputInvoicesList({
        year,
        month,
        supplierName: supplierFilter || undefined,
        expenseCategory: expenseCategoryFilter || undefined,
      }),
  });

  const {
    data: attachments,
    isLoading: isAttachmentsLoading,
    isError: isAttachmentsError,
    error: attachmentsError,
    refetch: refetchAttachments,
    isRefetching: isRefetchingAttachments,
  } = useQuery<InvoiceAttachmentItem[], Error>({
    queryKey: ["invoice-attachments"],
    queryFn: fetchInvoiceAttachments,
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadInvoiceAttachment(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoice-attachments"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteInvoiceAttachment(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoice-attachments"] });
    },
  });

  const linkMutation = useMutation({
    mutationFn: (params: { attachmentId: number; inputInvoiceId: number }) =>
      linkAttachmentToInputInvoice(params.attachmentId, params.inputInvoiceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoice-attachments"] });
      queryClient.invalidateQueries({ queryKey: ["input-invoices"] });
    },
  });

  const isUploading = uploadMutation.isPending;
  const uploadError = uploadMutation.error as Error | null;

  const isDeleting = deleteMutation.isPending;
  const deleteError = deleteMutation.error as Error | null;

  const isLinking = linkMutation.isPending;
  const linkError = linkMutation.error as Error | null;

  const handleFileChange = (evt: ChangeEvent<HTMLInputElement>) => {
    const file = evt.target.files?.[0];
    if (!file) return;

    uploadMutation.mutate(file);
    evt.target.value = "";
  };

  const handleDownloadAttachment = (id: number) => {
    void downloadInvoiceAttachment(id);
  };

  const handleDeleteAttachment = (id: number) => {
    if (!window.confirm("Da li ste sigurni da želite obrisati ovaj attachment?")) {
      return;
    }
    deleteMutation.mutate(id);
  };

  const handleLinkAttachment = (attachmentId: number) => {
    const invoiceId = attachmentTargetInvoice[attachmentId];
    if (!invoiceId || !Number.isFinite(invoiceId)) {
      window.alert("Odaberi ulaznu fakturu prije povezivanja dokumenta.");
      return;
    }

    linkMutation.mutate({
      attachmentId,
      inputInvoiceId: invoiceId as number,
    });
  };

  const items: InputInvoiceListItem[] = invoicesData?.items ?? [];
  const total = invoicesData?.total ?? 0;

  const unmatchedAttachments: InvoiceAttachmentItem[] =
    attachments?.filter((att) => att.input_invoice_id == null) ?? [];

  const totalAmount = items.reduce(
    (sum, inv) => sum + (inv.total_amount ?? 0),
    0,
  );
  const paidCount = items.filter((inv) => inv.is_paid === true).length;
  const unpaidCount = items.filter((inv) => inv.is_paid === false).length;

  const periodLabel =
    year && month
      ? `${MONTH_LABELS[month]} ${year}`
      : year
        ? `${year}`
        : month
          ? MONTH_LABELS[month]
          : "Svi periodi";

  const refreshAll = () => {
    refetch();
    refetchAttachments();
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 px-6 py-7 text-white sm:px-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <div className="inline-flex items-center rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs font-medium text-slate-200">
                Invoices ekosistem · Ulazne fakture
              </div>
              <div>
                <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                  Ulazne fakture i dokumenti dobavljača
                </h1>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                  Pregled troškova, statusa plaćanja, poreske priznatosti i
                  nepovezanih dokumenata za tenant{" "}
                  <span className="font-mono text-white">t-demo</span>.
                </p>
              </div>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row">
              <button
                type="button"
                onClick={() => navigate("/input-invoices/new")}
                className="inline-flex items-center justify-center rounded-2xl bg-white px-4 py-2.5 text-sm font-bold text-slate-950 shadow-sm transition hover:bg-slate-100"
              >
                + Nova ulazna faktura
              </button>
              <button
                type="button"
                onClick={refreshAll}
                disabled={
                  isLoading ||
                  isRefetching ||
                  isAttachmentsLoading ||
                  isRefetchingAttachments
                }
                className="inline-flex items-center justify-center rounded-2xl border border-white/15 bg-white/10 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-white/15 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isLoading ||
                isRefetching ||
                isAttachmentsLoading ||
                isRefetchingAttachments
                  ? "Osvježavam..."
                  : "Osvježi podatke"}
              </button>
            </div>
          </div>
        </div>

        <div className="grid gap-4 border-t border-slate-200 bg-slate-50 px-6 py-5 sm:grid-cols-2 lg:grid-cols-4 sm:px-8">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-medium text-slate-500">Period</p>
            <p className="mt-1 text-lg font-semibold text-slate-900">
              {periodLabel}
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-medium text-slate-500">Broj faktura</p>
            <p className="mt-1 text-lg font-semibold text-slate-900">{total}</p>
            <p className="mt-1 text-xs text-slate-400">
              Plaćeno {paidCount} · Neplaćeno {unpaidCount}
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-medium text-slate-500">Ukupan trošak</p>
            <p className="mt-1 font-mono text-lg font-semibold text-slate-900">
              {formatAmount(totalAmount)}
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-xs font-medium text-slate-500">
              Nepovezani dokumenti
            </p>
            <p className="mt-1 text-lg font-semibold text-slate-900">
              {unmatchedAttachments.length}
            </p>
          </div>
        </div>
      </div>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="mb-5 flex flex-col gap-2 border-b border-slate-100 pb-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-900">
              Filteri pregleda
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Filtriraj po periodu, dobavljaču i kategoriji troška.
            </p>
          </div>

          <button
            type="button"
            onClick={() => {
              setYear(CURRENT_YEAR);
              setMonth(CURRENT_MONTH);
              setSupplierFilter("");
              setExpenseCategoryFilter("");
            }}
            className="inline-flex w-fit items-center justify-center rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
          >
            Reset filtera
          </button>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
              Godina
            </label>
            <select
              value={year ?? ""}
              onChange={(e) => {
                const v = e.target.value;
                setYear(v === "" ? undefined : Number(v));
              }}
              className="input"
            >
              <option value="">Sve</option>
              <option value={CURRENT_YEAR}>{CURRENT_YEAR}</option>
              <option value={CURRENT_YEAR - 1}>{CURRENT_YEAR - 1}</option>
              <option value={CURRENT_YEAR - 2}>{CURRENT_YEAR - 2}</option>
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
              Mjesec
            </label>
            <select
              value={month ?? ""}
              onChange={(e) => {
                const v = e.target.value;
                setMonth(v === "" ? undefined : Number(v));
              }}
              className="input"
            >
              <option value="">Svi</option>
              {Object.entries(MONTH_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
              Dobavljač
            </label>
            <input
              type="text"
              value={supplierFilter}
              onChange={(e) => setSupplierFilter(e.target.value)}
              placeholder="npr. Elektro"
              className="input"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
              Kategorija troška
            </label>
            <select
              value={expenseCategoryFilter}
              onChange={(e) => setExpenseCategoryFilter(e.target.value)}
              className="input"
            >
              {EXPENSE_CATEGORY_OPTIONS.map((opt) => (
                <option key={opt || "all"} value={opt}>
                  {opt === "" ? "Sve kategorije" : opt}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,2fr)_390px]">
        <section className="rounded-3xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-col gap-2 border-b border-slate-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-base font-semibold text-slate-900">
                Lista ulaznih faktura
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Klik na red otvara detalje ulazne fakture.
              </p>
            </div>
            <span className="inline-flex w-fit rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
              {items.length} prikazano
            </span>
          </div>

          {isLoading && (
            <div className="p-6 text-sm text-slate-600">
              Učitavam ulazne fakture...
            </div>
          )}

          {isError && (
            <div className="m-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              Greška pri učitavanju ulaznih faktura: {error?.message}
            </div>
          )}

          {!isLoading && !isError && items.length === 0 && (
            <div className="p-8 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-xl">
                📄
              </div>
              <h3 className="mt-4 text-sm font-semibold text-slate-900">
                Nema ulaznih faktura za izabrane filtere
              </h3>
              <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
                Promijeni filtere ili kreiraj novu ulaznu fakturu za ovaj
                period.
              </p>
            </div>
          )}

          {items.length > 0 && (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide">
                      Faktura
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide">
                      Dobavljač
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide">
                      Datumi
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide">
                      Kategorija
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide">
                      Porez
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide">
                      Plaćanje
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide">
                      Iznos
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide">
                      Akcije
                    </th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {items.map((inv) => (
                    <tr
                      key={inv.id}
                      className="cursor-pointer transition hover:bg-slate-50"
                      onClick={() => navigate(`/input-invoices/${inv.id}`)}
                    >
                      <td className="px-4 py-4">
                        <div className="font-mono text-xs font-semibold text-slate-900">
                          {inv.number ?? `#${inv.id}`}
                        </div>
                        <div className="mt-1 text-[11px] text-slate-400">
                          ID {inv.id}
                        </div>
                      </td>

                      <td className="px-4 py-4">
                        <div className="max-w-[190px] truncate text-sm font-semibold text-slate-900">
                          {inv.supplier_name ?? "-"}
                        </div>
                      </td>

                      <td className="px-4 py-4 text-xs">
                        <div className="space-y-1">
                          <div>
                            <span className="text-slate-400">Faktura:</span>{" "}
                            <span className="font-medium text-slate-700">
                              {formatDate(inv.issue_date)}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-400">Knjiženje:</span>{" "}
                            <span className="font-medium text-slate-700">
                              {formatDate(inv.posting_date)}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-400">Rok:</span>{" "}
                            <span className="font-medium text-slate-700">
                              {formatDate(inv.due_date)}
                            </span>
                          </div>
                        </div>
                      </td>

                      <td className="px-4 py-4">
                        <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-700">
                          {inv.expense_category ?? "Bez kategorije"}
                        </span>
                      </td>

                      <td className="px-4 py-4">
                        <DeductibleBadge value={inv.is_tax_deductible} />
                      </td>

                      <td className="px-4 py-4">
                        <PaidBadge value={inv.is_paid} />
                      </td>

                      <td className="px-4 py-4 text-right">
                        <div className="font-mono text-sm font-bold text-slate-950">
                          {formatAmount(inv.total_amount)}
                        </div>
                      </td>

                      <td className="px-4 py-4 text-right">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/input-invoices/${inv.id}`);
                          }}
                          className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
                        >
                          Detalji
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-4">
              <div>
                <h2 className="text-base font-semibold text-slate-900">
                  Nepovezani dokumenti
                </h2>
                <p className="mt-1 text-sm leading-5 text-slate-500">
                  Upload računa i povezivanje sa ulaznom fakturom.
                </p>
              </div>

              <button
                type="button"
                onClick={() => refetchAttachments()}
                className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:opacity-60"
                disabled={isAttachmentsLoading || isRefetchingAttachments}
              >
                {isAttachmentsLoading || isRefetchingAttachments
                  ? "..."
                  : "Osvježi"}
              </button>
            </div>

            <div className="mt-4 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4">
              <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                Upload PDF-a ili slike
              </label>
              <input
                type="file"
                accept="application/pdf,image/*"
                onChange={handleFileChange}
                className="block w-full text-xs text-slate-700 file:mr-3 file:rounded-xl file:border-0 file:bg-slate-950 file:px-4 file:py-2 file:text-xs file:font-bold file:text-white hover:file:bg-slate-800"
                disabled={isUploading}
              />
              {isUploading && (
                <p className="mt-2 text-xs text-slate-500">
                  Uploadujem fajl...
                </p>
              )}
              {uploadError && (
                <p className="mt-2 text-xs text-red-600">
                  Greška pri uploadu: {uploadError.message}
                </p>
              )}
            </div>

            <div className="mt-4 max-h-[640px] space-y-3 overflow-y-auto pr-1">
              {isAttachmentsLoading && (
                <p className="text-sm text-slate-600">
                  Učitavam attachment-e...
                </p>
              )}

              {isAttachmentsError && (
                <p className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  Greška pri učitavanju attachment-a:{" "}
                  {attachmentsError?.message}
                </p>
              )}

              {!isAttachmentsLoading &&
                !isAttachmentsError &&
                unmatchedAttachments.length === 0 && (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-5 text-center">
                    <p className="text-sm font-semibold text-slate-800">
                      Nema nepovezanih dokumenata
                    </p>
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      Povezani dokumenti se vide na detaljima odgovarajuće
                      ulazne fakture.
                    </p>
                  </div>
                )}

              {unmatchedAttachments.map((att) => (
                <div
                  key={att.id}
                  className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-900">
                        {att.filename ?? `attachment-${att.id}`}
                      </p>
                      <p className="mt-1 text-xs text-slate-400">
                        {formatBytes(att.size_bytes)} · status:{" "}
                        <span className="font-semibold">
                          {att.status ?? "unmatched"}
                        </span>
                      </p>
                    </div>

                    <div className="flex shrink-0 items-center gap-1">
                      <button
                        type="button"
                        onClick={() => handleDownloadAttachment(att.id)}
                        className="rounded-lg border border-slate-200 px-2 py-1 text-[11px] font-semibold text-slate-700 hover:bg-slate-50"
                      >
                        Preuzmi
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteAttachment(att.id)}
                        disabled={isDeleting}
                        className="rounded-lg border border-red-100 px-2 py-1 text-[11px] font-semibold text-red-600 hover:bg-red-50 disabled:opacity-60"
                      >
                        Obriši
                      </button>
                    </div>
                  </div>

                  <div className="mt-3 border-t border-slate-100 pt-3">
                    <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Poveži sa ulaznom fakturom
                    </label>
                    <select
                      className="input bg-white text-xs"
                      value={attachmentTargetInvoice[att.id] ?? ""}
                      onChange={(e) =>
                        setAttachmentTargetInvoice((prev) => ({
                          ...prev,
                          [att.id]:
                            e.target.value === ""
                              ? ""
                              : Number(e.target.value),
                        }))
                      }
                      disabled={items.length === 0 || isLinking}
                    >
                      <option value="">— Odaberi ulaznu fakturu —</option>
                      {items.map((inv) => (
                        <option key={inv.id} value={inv.id}>
                          {inv.number
                            ? `${inv.number} · ${inv.supplier_name ?? ""}`.trim()
                            : `#${inv.id} · ${inv.supplier_name ?? ""}`}
                        </option>
                      ))}
                    </select>

                    <button
                      type="button"
                      onClick={() => handleLinkAttachment(att.id)}
                      disabled={isLinking || items.length === 0}
                      className="mt-3 w-full rounded-xl bg-slate-950 px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {isLinking ? "Povezujem..." : "Poveži dokument"}
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {(deleteError || linkError || isDeleting || isLinking) && (
              <p className="mt-3 rounded-2xl bg-slate-50 px-4 py-3 text-xs text-slate-600">
                {isDeleting
                  ? "Brišem attachment..."
                  : isLinking
                    ? "Povezujem attachment sa ulaznom fakturom..."
                    : deleteError
                      ? `Greška pri brisanju: ${deleteError.message}`
                      : linkError
                        ? `Greška pri povezivanju: ${linkError.message}`
                        : null}
              </p>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}