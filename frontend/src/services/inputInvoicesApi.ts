// /home/miso/dev/sp-app/sp-app/frontend/src/services/inputInvoicesApi.ts
import { apiClient } from "./apiClient";
import type {
  InputInvoiceListItem,
  InputInvoiceListResponse,
  InputInvoiceDetail,
} from "../types/inputInvoice";

/**
 * Opcije za dohvat liste ulaznih faktura iz /input-invoices/list
 */
export interface FetchInputInvoicesListOptions {
  year?: number;
  month?: number;
  supplierName?: string;
  limit?: number;
  offset?: number;
}

/**
 * Payload za kreiranje nove ulazne fakture.
 * Mapira se na backend InputInvoiceCreate šemu.
 */
export interface InputInvoiceCreatePayload {
  supplier_name: string;
  supplier_tax_id?: string | null;
  supplier_address?: string | null;
  invoice_number: string;
  issue_date: string; // YYYY-MM-DD
  due_date: string | null; // može biti null
  total_base: number;
  total_vat: number;
  total_amount: number;
  currency: string;
  note?: string | null;
}

/**
 * Payload za ažuriranje postojeće ulazne fakture (PUT /input-invoices/{id}).
 * Sva polja su opcionalna – šaljemo samo ono što mijenjamo.
 */
export interface InputInvoiceUpdatePayload {
  supplier_name?: string;
  supplier_tax_id?: string | null;
  supplier_address?: string | null;

  invoice_number?: string;
  issue_date?: string;
  due_date?: string | null;

  total_base?: number;
  total_vat?: number;
  total_amount?: number;

  currency?: string;
  note?: string | null;
}

/**
 * Helper: mapiranje raw objekta sa backend-a u UI-friendly InputInvoiceListItem.
 */
function mapInputInvoiceListItem(raw: any): InputInvoiceListItem {
  return {
    id: typeof raw.id === "number" ? raw.id : Number(raw.id),
    number: raw.number ?? raw.invoice_number ?? null,
    supplier_name: raw.supplier_name ?? null,
    issue_date: raw.issue_date ?? null,
    due_date: raw.due_date ?? null,
    received_date: (raw as any).received_date ?? null,
    total_amount:
      raw.total_amount != null ? Number(raw.total_amount) : null,
    currency: raw.currency ?? null,
  };
}

/**
 * Helper: mapiranje raw objekta u detaljnu ulaznu fakturu.
 */
function mapInputInvoiceDetail(r: any): InputInvoiceDetail {
  return {
    id: r.id,
    tenant_code: r.tenant_code,
    supplier_name: r.supplier_name,
    supplier_tax_id: r.supplier_tax_id ?? null,
    supplier_address: r.supplier_address ?? null,
    invoice_number: r.invoice_number,
    issue_date: r.issue_date,
    due_date: r.due_date ?? null,
    total_base:
      r.total_base != null ? Number(r.total_base) : 0,
    total_vat:
      r.total_vat != null ? Number(r.total_vat) : 0,
    total_amount:
      r.total_amount != null ? Number(r.total_amount) : 0,
    currency: r.currency,
    note: r.note ?? null,
    created_at: r.created_at,
  };
}

/**
 * UI lista ulaznih faktura – koristi /input-invoices/list
 * i mapira odgovor u InputInvoiceListResponse za frontend tabelu.
 */
export async function fetchInputInvoicesList(
  options: FetchInputInvoicesListOptions = {},
): Promise<InputInvoiceListResponse> {
  const res = await apiClient.get<{
    total: number;
    items: any[];
  }>("/input-invoices/list", {
    params: {
      year: options.year,
      month: options.month,
      supplier_name: options.supplierName || undefined,
      limit: options.limit,
      offset: options.offset,
    },
  });

  const raw = res.data;

  return {
    total: raw.total,
    items: Array.isArray(raw.items)
      ? raw.items.map(mapInputInvoiceListItem)
      : [],
  };
}

/**
 * Alias ako negdje zatreba samo lista bez total-a.
 */
export async function fetchInputInvoices(
  options?: FetchInputInvoicesListOptions,
): Promise<InputInvoiceListItem[]> {
  const data = await fetchInputInvoicesList(options ?? {});
  return data.items;
}

/**
 * Kreiranje nove ulazne fakture.
 * Backend endpoint: POST /input-invoices
 * Vraća kreiranu fakturu (InputInvoiceDetail) radi daljeg linkovanja attachment-a.
 */
export async function createInputInvoice(
  payload: InputInvoiceCreatePayload,
): Promise<InputInvoiceDetail> {
  const body = {
    supplier_name: payload.supplier_name,
    supplier_tax_id: payload.supplier_tax_id ?? null,
    supplier_address: payload.supplier_address ?? null,
    invoice_number: payload.invoice_number,
    issue_date: payload.issue_date,
    due_date: payload.due_date,
    total_base: payload.total_base,
    total_vat: payload.total_vat,
    total_amount: payload.total_amount,
    currency: payload.currency,
    note: payload.note ?? null,
  };

  const res = await apiClient.post<any>("/input-invoices", body);
  return mapInputInvoiceDetail(res.data);
}

/**
 * Dohvat jedne ulazne fakture po ID-u.
 * Backend endpoint: GET /input-invoices/{id}
 */
export async function getInputInvoice(
  id: number,
): Promise<InputInvoiceDetail> {
  const res = await apiClient.get<any>(`/input-invoices/${id}`);
  return mapInputInvoiceDetail(res.data);
}

/**
 * Ažuriranje postojeće ulazne fakture.
 * Backend endpoint: PUT /input-invoices/{id}
 */
export async function updateInputInvoice(
  id: number,
  payload: InputInvoiceUpdatePayload,
): Promise<void> {
  const body: Record<string, unknown> = {};

  if (payload.supplier_name !== undefined) {
    body.supplier_name = payload.supplier_name;
  }
  if (payload.supplier_tax_id !== undefined) {
    body.supplier_tax_id = payload.supplier_tax_id;
  }
  if (payload.supplier_address !== undefined) {
    body.supplier_address = payload.supplier_address;
  }

  if (payload.invoice_number !== undefined) {
    body.invoice_number = payload.invoice_number;
  }
  if (payload.issue_date !== undefined) {
    body.issue_date = payload.issue_date;
  }
  if (payload.due_date !== undefined) {
    body.due_date = payload.due_date;
  }

  if (payload.total_base !== undefined) {
    body.total_base = payload.total_base;
  }
  if (payload.total_vat !== undefined) {
    body.total_vat = payload.total_vat;
  }
  if (payload.total_amount !== undefined) {
    body.total_amount = payload.total_amount;
  }

  if (payload.currency !== undefined) {
    body.currency = payload.currency;
  }
  if (payload.note !== undefined) {
    body.note = payload.note;
  }

  await apiClient.put(`/input-invoices/${id}`, body);
}

/* ======================================================
 *  ATTACHMENTS – tenant-wide lista + upload/download/delete/link
 *  (koristi /invoice-attachments backend rute)
 * ====================================================== */

/**
 * Minimalni model attachment-a ulazne/izlazne fakture za UI.
 * Povezan je sa tenantom, a opcionalno i sa izlaznom ili ulaznom fakturom.
 */
export interface InvoiceAttachmentItem {
  id: number;
  filename: string | null;
  content_type: string | null;
  size_bytes: number | null;
  status: string | null;
  created_at: string | null;
  invoice_id: number | null;
  input_invoice_id: number | null;
}

/**
 * Dohvata sve attachment-e za jednog tenanta.
 */
export async function fetchInvoiceAttachments(): Promise<
  InvoiceAttachmentItem[]
> {
  const res = await apiClient.get<InvoiceAttachmentItem[]>(
    "/invoice-attachments",
  );
  return res.data;
}

/**
 * Upload jednog fajla kao attachment-a (PDF/slika).
 * Backend endpoint: POST /invoice-attachments
 */
export async function uploadInvoiceAttachment(
  file: File,
): Promise<InvoiceAttachmentItem> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await apiClient.post<InvoiceAttachmentItem>(
    "/invoice-attachments",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    },
  );

  return res.data;
}

/**
 * Download/preview fajla attachment-a.
 * Backend route: GET /invoice-attachments/{attachment_id}/download
 */
export async function downloadInvoiceAttachment(
  attachmentId: number,
): Promise<void> {
  const res = await apiClient.get(
    `/invoice-attachments/${attachmentId}/download`,
    {
      responseType: "blob",
    },
  );

  const contentTypeHeader =
    (res.headers["content-type"] as string | undefined) ||
    "application/octet-stream";

  let filename = "attachment";
  const contentDisposition = res.headers[
    "content-disposition"
  ] as string | undefined;

  if (contentDisposition) {
    const match = /filename="?([^"]+)"?/i.exec(contentDisposition);
    if (match && match[1]) {
      filename = decodeURIComponent(match[1]);
    }
  }

  const blob = new Blob([res.data], { type: contentTypeHeader });
  const url = URL.createObjectURL(blob);

  if (
    contentTypeHeader.startsWith("application/pdf") ||
    contentTypeHeader.startsWith("image/")
  ) {
    window.open(url, "_blank", "noopener,noreferrer");
  }

  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "attachment";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  URL.revokeObjectURL(url);
}

/**
 * Brisanje jednog attachment-a.
 * Backend route: DELETE /invoice-attachments/{attachment_id}
 */
export async function deleteInvoiceAttachment(
  attachmentId: number,
): Promise<void> {
  await apiClient.delete(`/invoice-attachments/${attachmentId}`);
}

/**
 * Povezivanje attachment-a sa KONKRETNOM ulaznom fakturom.
 * Backend route: POST /invoice-attachments/{attachment_id}/link-to-input-invoice
 */
export async function linkAttachmentToInputInvoice(
  attachmentId: number,
  inputInvoiceId: number,
): Promise<InvoiceAttachmentItem> {
  const res = await apiClient.post<InvoiceAttachmentItem>(
    `/invoice-attachments/${attachmentId}/link-to-input-invoice`,
    { input_invoice_id: inputInvoiceId },
  );
  return res.data;
}
