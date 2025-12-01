// /home/miso/dev/sp-app/sp-app/frontend/src/pages/InputInvoicesPage.tsx
import { useState, type ChangeEvent } from "react";
import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  fetchInputInvoicesList,
  fetchInvoiceAttachments,
  uploadInvoiceAttachment,
  downloadInvoiceAttachment,
  deleteInvoiceAttachment,
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

export default function InputInvoicesPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const [year, setYear] = useState<number | undefined>(CURRENT_YEAR);
  const [month, setMonth] = useState<number | undefined>(CURRENT_MONTH);
  const [supplierFilter, setSupplierFilter] = useState<string>("");

  const {
    data: invoicesData,
    isLoading,
    isError,
    error,
    refetch,
    isRefetching,
  } = useQuery<InputInvoiceListResponse, Error>({
    queryKey: ["input-invoices", { year, month, supplierFilter }],
    queryFn: () =>
      fetchInputInvoicesList({
        year,
        month,
        supplierName: supplierFilter || undefined,
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

  const isUploading = uploadMutation.isPending;
  const uploadError = uploadMutation.error as Error | null;

  const isDeleting = deleteMutation.isPending;
  const deleteError = deleteMutation.error as Error | null;

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

  const items: InputInvoiceListItem[] = invoicesData?.items ?? [];
  const total = invoicesData?.total ?? 0;

  return (
    <div className="space-y-6">
      {/* HEADER */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">
            Ulazne fakture
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Troškovi / ulazne fakture za tenant{" "}
            <span className="font-mono">t-demo</span>. Lista je filtrirana po
            godini, mjesecu i dobavljaču.
          </p>
          <p className="mt-0.5 text-[11px] text-slate-400">
            Ukupno zapisa (prema filterima):{" "}
            <span className="font-semibold text-slate-600">{total}</span>
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => navigate("/input-invoices/new")}
            className="inline-flex items-center rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white shadow-sm hover:bg-emerald-700"
          >
            ➕ Nova ulazna faktura
          </button>

          <button
            type="button"
            onClick={() => {
              refetch();
              refetchAttachments();
            }}
            className="inline-flex items-center rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-60"
            disabled={
              isLoading ||
              isRefetching ||
              isAttachmentsLoading ||
              isRefetchingAttachments
            }
          >
            {isLoading || isRefetching || isAttachmentsLoading || isRefetchingAttachments
              ? "Osvježavam..."
              : "Osvježi podatke"}
          </button>
        </div>
      </div>

      {/* FILTER BAR */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div className="flex flex-wrap items-end gap-3">
            {/* YEAR */}
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Godina
              </label>
              <select
                value={year ?? ""}
                onChange={(e) => {
                  const v = e.target.value;
                  setYear(v === "" ? undefined : Number(v));
                }}
                className="mt-1 w-24 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              >
                <option value="">Sve</option>
                <option value={CURRENT_YEAR}>{CURRENT_YEAR}</option>
                <option value={CURRENT_YEAR - 1}>{CURRENT_YEAR - 1}</option>
                <option value={CURRENT_YEAR - 2}>{CURRENT_YEAR - 2}</option>
              </select>
            </div>

            {/* MONTH */}
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Mjesec
              </label>
              <select
                value={month ?? ""}
                onChange={(e) => {
                  const v = e.target.value;
                  setMonth(v === "" ? undefined : Number(v));
                }}
                className="mt-1 w-28 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              >
                <option value="">Svi</option>
                <option value={1}>Januar</option>
                <option value={2}>Februar</option>
                <option value={3}>Mart</option>
                <option value={4}>April</option>
                <option value={5}>Maj</option>
                <option value={6}>Jun</option>
                <option value={7}>Jul</option>
                <option value={8}>Avgust</option>
                <option value={9}>Septembar</option>
                <option value={10}>Oktobar</option>
                <option value={11}>Novembar</option>
                <option value={12}>Decembar</option>
              </select>
            </div>

            {/* SUPPLIER NAME */}
            <div>
              <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Dobavljač (prefiks)
              </label>
              <input
                type="text"
                value={supplierFilter}
                onChange={(e) => setSupplierFilter(e.target.value)}
                placeholder="npr. Elektro"
                className="mt-1 w-48 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700 placeholder:text-slate-300 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              />
            </div>
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => {
                setYear(CURRENT_YEAR);
                setMonth(CURRENT_MONTH);
                setSupplierFilter("");
              }}
              className="rounded-md border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
            >
              Reset filtera
            </button>
          </div>
        </div>
      </div>

      {/* GLAVNI GRID */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        {/* TABELA ULAZNIH FAKTURA */}
        <div className="space-y-3">
          {isLoading && (
            <p className="text-sm text-slate-600">
              Učitavam ulazne fakture...
            </p>
          )}

          {isError && (
            <p className="text-sm text-red-600">
              Greška pri učitavanju ulaznih faktura: {error?.message}
            </p>
          )}

          {!isLoading && !isError && items.length === 0 && (
            <p className="text-sm text-slate-500">
              Trenutno nema ulaznih faktura za zadane filtere.
            </p>
          )}

          {items.length > 0 && (
            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-medium">
                      Broj
                    </th>
                    <th className="px-3 py-2 text-left text-xs font-medium">
                      Dobavljač
                    </th>
                    <th className="whitespace-nowrap px-3 py-2 text-left text-xs font-medium">
                      Datum fakture
                    </th>
                    <th className="whitespace-nowrap px-3 py-2 text-left text-xs font-medium">
                      Rok plaćanja
                    </th>
                    <th className="px-3 py-2 text-right text-xs font-medium">
                      Iznos
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {items.map((inv) => (
                    <tr
                      key={inv.id}
                      className="cursor-pointer hover:bg-slate-50"
                      onClick={() =>
                        navigate(`/input-invoices/${inv.id}`)
                      }
                    >
                      <td className="px-3 py-2 font-mono text-xs">
                        {inv.number ?? "-"}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {inv.supplier_name ?? (
                          <span className="text-slate-400">-</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {formatDate(inv.issue_date)}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {formatDate(inv.due_date)}
                      </td>
                      <td className="px-3 py-2 text-right text-xs font-medium">
                        {formatAmount(inv.total_amount)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ATTACHMENTS PANEL */}
        <div className="space-y-3">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold text-slate-800">
                  Uploadovani računi (attachments)
                </h3>
                <p className="mt-1 text-[11px] text-slate-500">
                  Skenirani / slikani računi za dalju obradu (OCR,
                  povezivanje sa ulaznim fakturama, itd.).
                </p>
              </div>

              <button
                type="button"
                onClick={() => refetchAttachments()}
                className="rounded-md border border-slate-200 px-2 py-1 text-[11px] text-slate-600 hover:bg-slate-50 disabled:opacity-60"
                disabled={isAttachmentsLoading || isRefetchingAttachments}
              >
                {isAttachmentsLoading || isRefetchingAttachments
                  ? "Osvježavam..."
                  : "Osvježi"}
              </button>
            </div>

            {/* UPLOAD */}
            <div className="mt-3">
              <label className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Upload fajla
              </label>
              <div className="mt-1 flex items-center gap-2">
                <input
                  type="file"
                  accept="application/pdf,image/*"
                  onChange={handleFileChange}
                  className="block w-full text-xs text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-white hover:file:bg-slate-800"
                  disabled={isUploading}
                />
              </div>
              {isUploading && (
                <p className="mt-1 text-[11px] text-slate-500">
                  Uploadujem fajl...
                </p>
              )}
              {uploadError && (
                <p className="mt-1 text-[11px] text-red-600">
                  Greška pri uploadu: {uploadError.message}
                </p>
              )}
            </div>

            {/* ATTACHMENTS LISTA */}
            <div className="mt-4 max-h-80 space-y-1 overflow-y-auto rounded-md border border-slate-100 bg-slate-50 p-2">
              {isAttachmentsLoading && (
                <p className="text-xs text-slate-600">
                  Učitavam attachment-e...
                </p>
              )}

              {isAttachmentsError && (
                <p className="text-xs text-red-600">
                  Greška pri učitavanju attachment-a:{" "}
                  {attachmentsError?.message}
                </p>
              )}

              {!isAttachmentsLoading &&
                !isAttachmentsError &&
                (attachments?.length ?? 0) === 0 && (
                  <p className="text-xs text-slate-500">
                    Još nema uploadovanih attachment-a.
                  </p>
                )}

              {attachments &&
                attachments.length > 0 &&
                attachments.map((att) => (
                  <div
                    key={att.id}
                    className="flex items-start justify-between gap-2 rounded-md bg-white px-2 py-1.5 text-xs text-slate-700 shadow-sm"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">
                        {att.filename ?? `attachment-${att.id}`}
                      </p>
                      <p className="mt-0.5 text-[11px] text-slate-400">
                        {formatBytes(att.size_bytes)} · status:{" "}
                        <span className="font-semibold">
                          {att.status ?? "unknown"}
                        </span>
                      </p>
                    </div>
                    <div className="flex flex-shrink-0 items-center gap-1">
                      <button
                        type="button"
                        onClick={() =>
                          handleDownloadAttachment(att.id)
                        }
                        className="rounded-md border border-slate-200 px-2 py-0.5 text-[11px] text-slate-700 hover:bg-slate-50"
                      >
                        Preuzmi
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          handleDeleteAttachment(att.id)
                        }
                        className="rounded-md border border-red-100 px-2 py-0.5 text-[11px] text-red-600 hover:bg-red-50 disabled:opacity-60"
                        disabled={isDeleting}
                      >
                        Obriši
                      </button>
                    </div>
                  </div>
                ))}
            </div>

            {(deleteError || isDeleting) && (
              <p className="mt-2 text-[11px] text-slate-500">
                {isDeleting
                  ? "Brišem attachment..."
                  : deleteError
                  ? `Greška pri brisanju: ${deleteError.message}`
                  : null}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
