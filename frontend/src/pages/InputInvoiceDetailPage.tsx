// /home/miso/dev/sp-app/sp-app/frontend/src/pages/InputInvoiceDetailPage.tsx
import { useState, type ChangeEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import type {
  InputInvoiceDetail,
  InputInvoicePaymentCreatePayload,
  InputInvoicePaymentDetail,
} from "../types/inputInvoice";
import {
  createInputInvoicePayment,
  deleteInputInvoice,
  deleteInputInvoicePayment,
  deleteInvoiceAttachment,
  downloadInvoiceAttachment,
  fetchInvoiceAttachments,
  getInputInvoice,
  getInputInvoicePayment,
  linkAttachmentToInputInvoice,
  previewInvoiceAttachment,
  uploadInvoiceAttachment,
  type InvoiceAttachmentItem,
} from "../services/inputInvoicesApi";

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

function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleString("sr-Latn-BA");
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

function StatusBadge({
  children,
  tone = "slate",
}: {
  children: string;
  tone?: "slate" | "emerald" | "amber" | "blue";
}) {
  const classes =
    tone === "emerald"
      ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
      : tone === "amber"
        ? "bg-amber-50 text-amber-700 ring-amber-200"
        : tone === "blue"
          ? "bg-blue-50 text-blue-700 ring-blue-200"
          : "bg-slate-100 text-slate-600 ring-slate-200";

  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ${classes}`}
    >
      {children}
    </span>
  );
}

function getApiErrorDetail(
  error: unknown,
  fallback: string,
): string {
  const detail = (
    error as {
      response?: {
        data?: {
          detail?: unknown;
        };
      };
    }
  )?.response?.data?.detail;

  return typeof detail === "string" && detail.trim()
    ? detail
    : fallback;
}

export default function InputInvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const numericId = id ? Number(id) : null;

  const [paymentDate, setPaymentDate] = useState(() => {
    const now = new Date();
    const localTime = new Date(
      now.getTime() - now.getTimezoneOffset() * 60_000,
    );
    return localTime.toISOString().slice(0, 10);
  });
  const [paymentAccount, setPaymentAccount] = useState<"cash" | "bank">(
    "bank",
  );
  const [paymentNote, setPaymentNote] = useState("");

  const {
    data: invoice,
    isLoading,
    isError,
    error,
  } = useQuery<InputInvoiceDetail>({
    queryKey: ["input-invoice-detail", numericId],
    enabled: numericId != null && Number.isFinite(numericId),
    queryFn: () => getInputInvoice(numericId as number),
  });

  const {
    data: payment,
    isLoading: isPaymentLoading,
    isError: isPaymentError,
    error: paymentError,
  } = useQuery<InputInvoicePaymentDetail, Error>({
    queryKey: ["input-invoice-payment", numericId],
    enabled:
      numericId != null &&
      Number.isFinite(numericId) &&
      invoice?.is_paid === true,
    queryFn: () => getInputInvoicePayment(numericId as number),
    retry: false,
  });

  const {
    data: attachments,
    isLoading: isAttachmentsLoading,
    isError: isAttachmentsError,
    error: attachmentsError,
  } = useQuery<InvoiceAttachmentItem[], Error>({
    queryKey: ["invoice-attachments", { inputInvoiceId: numericId }],
    enabled: numericId != null && Number.isFinite(numericId),
    queryFn: () =>
      fetchInvoiceAttachments({
        inputInvoiceId: numericId as number,
      }),
  });

  const invalidatePaymentRelatedQueries = async () => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: ["input-invoice-detail", numericId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["input-invoice-payment", numericId],
      }),
      queryClient.invalidateQueries({
        queryKey: ["input-invoices"],
      }),
      queryClient.invalidateQueries({
        queryKey: ["cash"],
      }),
      queryClient.invalidateQueries({
        queryKey: ["dashboard"],
      }),
      queryClient.invalidateQueries({
        queryKey: ["reports"],
      }),
    ]);
  };

  const createPaymentMutation = useMutation({
    mutationFn: (payload: InputInvoicePaymentCreatePayload) =>
      createInputInvoicePayment(numericId as number, payload),
    onSuccess: async () => {
      await invalidatePaymentRelatedQueries();
    },
  });

  const deletePaymentMutation = useMutation({
    mutationFn: () => deleteInputInvoicePayment(numericId as number),
    onSuccess: async () => {
      await invalidatePaymentRelatedQueries();
    },
  });

  const uploadAttachmentMutation = useMutation({
    mutationFn: async (file: File) => {
      let uploaded: InvoiceAttachmentItem;

      try {
        uploaded = await uploadInvoiceAttachment(file);
      } catch (error) {
        throw new Error(
          getApiErrorDetail(error, "Upload dokumenta nije uspio."),
        );
      }

      try {
        return await linkAttachmentToInputInvoice(
          uploaded.id,
          numericId as number,
        );
      } catch (error) {
        throw new Error(
          `Dokument je uploadovan, ali povezivanje sa fakturom nije uspjelo. Dokument je sačuvan među nepovezanim dokumentima. ${getApiErrorDetail(
            error,
            "",
          )}`.trim(),
        );
      }
    },
    onSettled: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["invoice-attachments"],
      });
    },
  });

  const deleteAttachmentMutation = useMutation({
    mutationFn: (attachmentId: number) =>
      deleteInvoiceAttachment(attachmentId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["invoice-attachments"],
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (invoiceId: number) => deleteInputInvoice(invoiceId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["input-invoices"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["invoice-attachments"],
        }),
      ]);
      navigate("/input-invoices");
    },
  });

  const handleCreatePayment = () => {
    if (
      numericId == null ||
      !Number.isFinite(numericId) ||
      paymentDate.trim() === "" ||
      createPaymentMutation.isPending
    ) {
      return;
    }

    createPaymentMutation.mutate({
      payment_date: paymentDate,
      account: paymentAccount,
      note: paymentNote.trim() || null,
    });
  };

  const handleUndoPayment = () => {
    if (!invoice || deletePaymentMutation.isPending) {
      return;
    }

    const confirmed = window.confirm(
      `Da li želite poništiti evidentirano plaćanje fakture ${invoice.invoice_number}?`,
    );

    if (!confirmed) {
      return;
    }

    deletePaymentMutation.mutate();
  };

  const handleAttachmentFileChange = (
    event: ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0];

    if (!file || uploadAttachmentMutation.isPending) {
      return;
    }

    uploadAttachmentMutation.mutate(file);
    event.target.value = "";
  };

  const handleDeleteAttachment = (attachment: InvoiceAttachmentItem) => {
    if (deleteAttachmentMutation.isPending) {
      return;
    }

    const confirmed = window.confirm(
      `Da li želite obrisati dokument ${
        attachment.filename ?? `attachment-${attachment.id}`
      }?`,
    );

    if (!confirmed) {
      return;
    }

    deleteAttachmentMutation.mutate(attachment.id);
  };

  if (numericId == null || !Number.isFinite(numericId)) {
    return (
      <div className="mx-auto max-w-4xl rounded-3xl border border-red-200 bg-red-50 p-6 shadow-sm">
        <h1 className="text-lg font-semibold text-red-800">
          Nevalidan ID ulazne fakture
        </h1>
        <p className="mt-2 text-sm text-red-700">
          URL ne sadrži ispravan identifikator ulazne fakture.
        </p>
        <button
          type="button"
          onClick={() => navigate("/input-invoices")}
          className="mt-4 rounded-xl border border-red-200 bg-white px-4 py-2 text-sm font-semibold text-red-700 shadow-sm hover:bg-red-50"
        >
          ← Nazad na listu ulaznih faktura
        </button>
      </div>
    );
  }

  const linkedAttachments = attachments ?? [];

  const handleDelete = () => {
    if (!invoice || deleteMutation.isPending) {
      return;
    }

    const confirmed = window.confirm(
      `Da li ste sigurni da želite obrisati ulaznu fakturu ${invoice.invoice_number} dobavljača ${invoice.supplier_name}? Ovu radnju nije moguće poništiti.`,
    );

    if (!confirmed) {
      return;
    }

    deleteMutation.mutate(invoice.id);
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 px-6 py-7 text-white sm:px-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <div className="inline-flex items-center rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs font-medium text-slate-200">
                Ulazne fakture · Detalji
              </div>
              <div>
                <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
                  {invoice
                    ? `Ulazna faktura ${invoice.invoice_number}`
                    : "Detalj ulazne fakture"}
                </h1>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
                  Pregled dobavljača, datuma, finansijskih iznosa, tehničkih
                  podataka i povezanih dokumenata za tenant{" "}
                  <span className="font-mono text-white">t-demo</span>.
                </p>
              </div>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row">
              {invoice && (
                <button
                  type="button"
                  onClick={() =>
                    navigate(`/input-invoices/${invoice.id}/edit`)
                  }
                  className="inline-flex items-center justify-center rounded-2xl border border-white/20 bg-white/10 px-4 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-white/20"
                >
                  Uredi fakturu
                </button>
              )}

              <button
                type="button"
                onClick={() => navigate("/input-invoices")}
                className="inline-flex items-center justify-center rounded-2xl bg-white px-4 py-2.5 text-sm font-bold text-slate-950 shadow-sm transition hover:bg-slate-100"
              >
                ← Nazad na listu
              </button>
            </div>
          </div>
        </div>

        {invoice && (
          <div className="grid gap-4 border-t border-slate-200 bg-slate-50 px-6 py-5 sm:grid-cols-2 lg:grid-cols-4 sm:px-8">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs font-medium text-slate-500">
                Dobavljač
              </p>
              <p className="mt-1 truncate text-lg font-semibold text-slate-900">
                {invoice.supplier_name || "-"}
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs font-medium text-slate-500">
                Osnovica
              </p>
              <p className="mt-1 font-mono text-lg font-semibold text-slate-900">
                {formatAmount(invoice.total_base)}
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs font-medium text-slate-500">PDV</p>
              <p className="mt-1 font-mono text-lg font-semibold text-slate-900">
                {formatAmount(invoice.total_vat)}
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs font-medium text-slate-500">
                Ukupno
              </p>
              <p className="mt-1 font-mono text-lg font-semibold text-slate-900">
                {formatAmount(invoice.total_amount)}
              </p>
            </div>
          </div>
        )}
      </div>

      {isLoading && (
        <div className="rounded-3xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">
          Učitavam detalje ulazne fakture...
        </div>
      )}

      {isError && (
        <div className="rounded-3xl border border-red-200 bg-red-50 p-6 text-sm text-red-700 shadow-sm">
          Greška pri učitavanju ulazne fakture:{" "}
          {error instanceof Error ? error.message : "Nepoznata greška"}
        </div>
      )}

      {invoice && (
        <div className="grid gap-6 lg:grid-cols-[1fr,380px]">
          <div className="space-y-6">
            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
              <div className="mb-5 border-b border-slate-100 pb-4">
                <h2 className="text-base font-semibold text-slate-900">
                  Dobavljač i dokument
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Osnovni podaci o ulaznoj fakturi i dobavljaču.
                </p>
              </div>

              <div className="grid gap-5 md:grid-cols-2">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Dobavljač
                  </p>
                  <p className="mt-2 text-lg font-semibold text-slate-900">
                    {invoice.supplier_name || "-"}
                  </p>
                  {invoice.supplier_address && (
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      {invoice.supplier_address}
                    </p>
                  )}
                  {invoice.supplier_tax_id && (
                    <p className="mt-2 text-sm text-slate-500">
                      PIB/JIB:{" "}
                      <span className="font-mono font-semibold text-slate-700">
                        {invoice.supplier_tax_id}
                      </span>
                    </p>
                  )}
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Dokument
                  </p>
                  <p className="mt-2 font-mono text-lg font-semibold text-slate-900">
                    {invoice.invoice_number || "-"}
                  </p>
                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                    <div>
                      <p className="text-xs text-slate-400">Datum izdavanja</p>
                      <p className="mt-1 text-sm font-semibold text-slate-800">
                        {formatDate(invoice.issue_date)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400">Datum knjiženja</p>
                      <p className="mt-1 text-sm font-semibold text-slate-800">
                        {formatDate(invoice.posting_date)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400">Rok dospijeća</p>
                      <p className="mt-1 text-sm font-semibold text-slate-800">
                        {formatDate(invoice.due_date)}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {invoice.note && (
                <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Interna napomena
                  </p>
                  <p className="mt-2 whitespace-pre-line text-sm leading-6 text-slate-700">
                    {invoice.note}
                  </p>
                </div>
              )}
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
              <div className="mb-5 border-b border-slate-100 pb-4">
                <h2 className="text-base font-semibold text-slate-900">
                  Obračun i metapodaci
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Finansijski pregled i tehnički trag zapisa u sistemu.
                </p>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Osnovica bez PDV-a
                  </p>
                  <p className="mt-2 font-mono text-lg font-semibold text-slate-900">
                    {formatAmount(invoice.total_base)}
                  </p>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    PDV iznos
                  </p>
                  <p className="mt-2 font-mono text-lg font-semibold text-slate-900">
                    {formatAmount(invoice.total_vat)}
                  </p>
                </div>

                <div className="rounded-2xl border border-slate-900 bg-slate-950 p-4 text-white">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    Ukupno
                  </p>
                  <p className="mt-2 font-mono text-xl font-bold">
                    {formatAmount(invoice.total_amount)}
                  </p>
                  <p className="mt-1 text-xs text-slate-400">
                    Valuta: {invoice.currency || "KM"}
                  </p>
                </div>
              </div>

              <div className="mt-5 grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 text-sm sm:grid-cols-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    ID fakture
                  </p>
                  <p className="mt-1 font-mono font-semibold text-slate-700">
                    {invoice.id}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    Tenant
                  </p>
                  <p className="mt-1 font-mono font-semibold text-slate-700">
                    {invoice.tenant_code}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    Kreirano
                  </p>
                  <p className="mt-1 font-mono text-xs font-semibold text-slate-700">
                    {formatDateTime(invoice.created_at)}
                  </p>
                </div>
              </div>
            </section>
          </div>

          <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="border-b border-slate-100 pb-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Dokumentacija
                </p>
                <h2 className="mt-1 text-base font-semibold text-slate-900">
                  Priloženi dokumenti
                </h2>
                <p className="mt-1 text-sm leading-5 text-slate-500">
                  PDF, JPEG ili PNG dokumenti povezani sa ovom ulaznom fakturom.
                </p>
              </div>

              <div className="mt-4 rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-4">
                <label className="mb-2 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Dodaj dokument
                </label>

                <input
                  type="file"
                  accept="application/pdf,image/jpeg,image/png"
                  onChange={handleAttachmentFileChange}
                  disabled={uploadAttachmentMutation.isPending}
                  className="block w-full text-xs text-slate-700 file:mr-3 file:rounded-xl file:border-0 file:bg-slate-950 file:px-4 file:py-2 file:text-xs file:font-bold file:text-white hover:file:bg-slate-800 disabled:opacity-60"
                />

                {uploadAttachmentMutation.isPending && (
                  <p className="mt-2 text-xs text-slate-500">
                    Uploadujem i povezujem dokument...
                  </p>
                )}

                {uploadAttachmentMutation.isError && (
                  <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs leading-5 text-red-700">
                    {uploadAttachmentMutation.error instanceof Error
                      ? uploadAttachmentMutation.error.message
                      : "Dodavanje dokumenta nije uspjelo."}
                  </div>
                )}
              </div>

              <div className="mt-4">
                {isAttachmentsLoading && (
                  <p className="text-sm text-slate-600">
                    Učitavam priložene dokumente...
                  </p>
                )}

                {isAttachmentsError && (
                  <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    Greška pri učitavanju priloženih dokumenata:{" "}
                    {attachmentsError?.message}
                  </div>
                )}

                {deleteAttachmentMutation.isError && (
                  <div className="mb-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-xs leading-5 text-red-700">
                    {getApiErrorDetail(
                      deleteAttachmentMutation.error,
                      "Brisanje dokumenta nije uspjelo.",
                    )}
                  </div>
                )}

                {!isAttachmentsLoading &&
                  !isAttachmentsError &&
                  linkedAttachments.length === 0 && (
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-5 text-center">
                      <p className="text-sm font-semibold text-slate-800">
                        Nema povezanih dokumenata
                      </p>
                      <p className="mt-1 text-xs leading-5 text-slate-500">
                        Dodaj PDF, JPEG ili PNG dokument direktno uz ovu
                        ulaznu fakturu.
                      </p>
                    </div>
                  )}

                {linkedAttachments.length > 0 && (
                  <div className="space-y-3">
                    {linkedAttachments.map((att) => (
                      <div
                        key={att.id}
                        className="rounded-2xl border border-slate-200 bg-slate-50 p-4"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-slate-900">
                              {att.filename ?? `attachment-${att.id}`}
                            </p>
                            <p className="mt-1 text-xs text-slate-500">
                              {formatBytes(att.size_bytes)}
                            </p>
                          </div>

                          <StatusBadge tone="blue">
                            {att.status ?? "unknown"}
                          </StatusBadge>
                        </div>

                        <div className="mt-4 grid grid-cols-3 gap-2">
                          <button
                            type="button"
                            onClick={() => previewInvoiceAttachment(att.id)}
                            className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-bold text-slate-700 shadow-sm transition hover:bg-slate-50"
                          >
                            Pregledaj
                          </button>

                          <button
                            type="button"
                            onClick={() => downloadInvoiceAttachment(att.id)}
                            className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-bold text-slate-700 shadow-sm transition hover:bg-slate-50"
                          >
                            Preuzmi
                          </button>

                          <button
                            type="button"
                            onClick={() => handleDeleteAttachment(att)}
                            disabled={deleteAttachmentMutation.isPending}
                            className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs font-bold text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {deleteAttachmentMutation.isPending
                              ? "Brišem..."
                              : "Obriši"}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="border-b border-slate-100 pb-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Plaćanje
                    </p>
                    <h2 className="mt-1 text-base font-semibold text-slate-900">
                      Plaćanje fakture
                    </h2>
                  </div>

                  <StatusBadge
                    tone={invoice.is_paid ? "emerald" : "amber"}
                  >
                    {invoice.is_paid ? "Plaćeno" : "Nije plaćeno"}
                  </StatusBadge>
                </div>
              </div>

              {invoice.is_paid ? (
                <div className="mt-4 space-y-4">
                  {isPaymentLoading && (
                    <p className="text-sm text-slate-600">
                      Učitavam podatke o plaćanju...
                    </p>
                  )}

                  {isPaymentError && (
                    <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-xs leading-5 text-red-700">
                      {getApiErrorDetail(
                        paymentError,
                        "Podaci o evidentiranom plaćanju nisu dostupni.",
                      )}
                    </div>
                  )}

                  {payment && (
                    <div className="space-y-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-emerald-700">
                          Datum plaćanja
                        </span>
                        <span className="font-semibold text-emerald-950">
                          {formatDate(payment.payment_date)}
                        </span>
                      </div>

                      <div className="flex items-center justify-between gap-3">
                        <span className="text-emerald-700">
                          Račun
                        </span>
                        <span className="font-semibold text-emerald-950">
                          {payment.account === "cash"
                            ? "Gotovina"
                            : "Banka"}
                        </span>
                      </div>

                      <div className="flex items-center justify-between gap-3">
                        <span className="text-emerald-700">
                          Iznos
                        </span>
                        <span className="font-mono font-semibold text-emerald-950">
                          {formatAmount(payment.amount)}
                        </span>
                      </div>

                      {payment.note && (
                        <div className="border-t border-emerald-200 pt-3">
                          <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">
                            Napomena
                          </p>
                          <p className="mt-1 whitespace-pre-line text-sm text-emerald-950">
                            {payment.note}
                          </p>
                        </div>
                      )}
                    </div>
                  )}

                  {deletePaymentMutation.isError && (
                    <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-xs leading-5 text-red-700">
                      {getApiErrorDetail(
                        deletePaymentMutation.error,
                        "Poništavanje plaćanja nije uspjelo.",
                      )}
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={handleUndoPayment}
                    disabled={deletePaymentMutation.isPending}
                    className="w-full rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-bold text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {deletePaymentMutation.isPending
                      ? "Poništavam..."
                      : "Poništi plaćanje"}
                  </button>
                </div>
              ) : (
                <div className="mt-4 space-y-4">
                  <div>
                    <label
                      htmlFor="input-invoice-payment-date"
                      className="text-xs font-semibold uppercase tracking-wide text-slate-500"
                    >
                      Datum plaćanja
                    </label>
                    <input
                      id="input-invoice-payment-date"
                      type="date"
                      value={paymentDate}
                      onChange={(event) =>
                        setPaymentDate(event.target.value)
                      }
                      className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-slate-500"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="input-invoice-payment-account"
                      className="text-xs font-semibold uppercase tracking-wide text-slate-500"
                    >
                      Način plaćanja
                    </label>
                    <select
                      id="input-invoice-payment-account"
                      value={paymentAccount}
                      onChange={(event) =>
                        setPaymentAccount(
                          event.target.value as "cash" | "bank",
                        )
                      }
                      className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-slate-500"
                    >
                      <option value="bank">Banka</option>
                      <option value="cash">Gotovina</option>
                    </select>
                  </div>

                  <div>
                    <label
                      htmlFor="input-invoice-payment-note"
                      className="text-xs font-semibold uppercase tracking-wide text-slate-500"
                    >
                      Napomena
                    </label>
                    <textarea
                      id="input-invoice-payment-note"
                      rows={3}
                      value={paymentNote}
                      onChange={(event) =>
                        setPaymentNote(event.target.value)
                      }
                      placeholder="Opcionalna napomena o plaćanju"
                      className="mt-2 w-full resize-y rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-slate-500"
                    />
                  </div>

                  {createPaymentMutation.isError && (
                    <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-xs leading-5 text-red-700">
                      {getApiErrorDetail(
                        createPaymentMutation.error,
                        "Evidentiranje plaćanja nije uspjelo.",
                      )}
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={handleCreatePayment}
                    disabled={
                      createPaymentMutation.isPending ||
                      paymentDate.trim() === ""
                    }
                    className="w-full rounded-xl bg-slate-950 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {createPaymentMutation.isPending
                      ? "Evidentiram..."
                      : "Evidentiraj plaćanje"}
                  </button>
                </div>
              )}
            </section>

            <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-900">
                Brze informacije
              </h3>

              <div className="mt-4 space-y-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-slate-500">Broj dokumenata</span>
                  <span className="font-semibold text-slate-900">
                    {linkedAttachments.length}
                  </span>
                </div>

                <div className="flex items-center justify-between gap-3">
                  <span className="text-slate-500">Broj fakture</span>
                  <span className="font-mono text-xs font-semibold text-slate-900">
                    {invoice.invoice_number || "-"}
                  </span>
                </div>

                <div className="flex items-center justify-between gap-3">
                  <span className="text-slate-500">Dobavljač</span>
                  <span className="max-w-[160px] truncate font-semibold text-slate-900">
                    {invoice.supplier_name || "-"}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-slate-500">Plaćanje</span>
                  <StatusBadge tone={invoice.is_paid ? "emerald" : "amber"}>
                    {invoice.is_paid ? "Plaćeno" : "Nije plaćeno"}
                  </StatusBadge>
                </div>

                <div className="flex items-center justify-between gap-3">
                  <span className="text-slate-500">Poreski status</span>
                  <StatusBadge tone={invoice.is_tax_deductible ? "blue" : "amber"}>
                    {invoice.is_tax_deductible ? "Priznat" : "Nepriznat"}
                  </StatusBadge>
                </div>

                <div className="flex items-center justify-between gap-3">
                  <span className="text-slate-500">Kategorija</span>
                  <StatusBadge>
                    {invoice.expense_category || "Bez kategorije"}
                  </StatusBadge>
                </div>
              </div>
            </section>
            <section className="rounded-3xl border border-red-200 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-900">
                Upravljanje fakturom
              </h3>

              <p className="mt-1 text-xs leading-5 text-slate-500">
                Brisanje ulazne fakture je trajna radnja i nije je moguće
                poništiti.
              </p>

              {deleteMutation.isError && (
                <div className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-xs leading-5 text-red-700">
                  {(
                    deleteMutation.error as {
                      response?: {
                        data?: {
                          detail?: string;
                        };
                      };
                    }
                  ).response?.data?.detail ||
                    "Brisanje ulazne fakture nije uspjelo."}
                </div>
              )}

              <button
                type="button"
                onClick={handleDelete}
                disabled={deleteMutation.isPending}
                className="mt-4 w-full rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-bold text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {deleteMutation.isPending
                  ? "Brišem..."
                  : "Obriši ulaznu fakturu"}
              </button>
            </section>

            <div className="text-xs text-slate-500">
              <Link
                to="/input-invoices"
                className="underline underline-offset-2 hover:text-slate-700"
              >
                ← Nazad na listu ulaznih faktura
              </Link>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}