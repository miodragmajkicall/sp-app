// /home/miso/dev/sp-app/sp-app/frontend/src/services/invoicesApi.ts
import { apiClient } from "./apiClient";
import type {
  InvoiceListResponse,
  InvoiceRowItem,
  InvoiceDetail,
  InvoiceCreatePayload,
} from "../types/invoice";

export interface InvoicesListParams {
  year?: number;
  month?: number;
  unpaid_only?: boolean;
  date_from?: string;
  date_to?: string;
  buyer_query?: string;
  page?: number;
  page_size?: number;
}

/**
 * Helperi za konverziju backend vrijednosti (string/Decimal) u broj.
 */
function toNumberOrNull(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  const n = Number(value);
  if (Number.isNaN(n)) return null;
  return n;
}

function toNumberOrZero(value: unknown): number {
  const n = Number(value);
  if (Number.isNaN(n)) return 0;
  return n;
}

/**
 * Mapiranje jednog reda iz backend /invoices/list u UI InvoiceRowItem.
 *
 * Backend vraća:
 *  - invoice_number
 *  - total_amount kao string (Decimal) itd.
 *
 * UI očekuje:
 *  - number (broj fakture) kao string | null
 *  - total_amount kao number | null
 */
function mapInvoiceRowItem(raw: any): InvoiceRowItem {
  return {
    id: raw.id,
    number: raw.invoice_number ?? null,
    buyer_name: raw.buyer_name ?? null,
    issue_date: raw.issue_date ?? null,
    due_date: raw.due_date ?? null,
    total_amount: toNumberOrNull(raw.total_amount),
    is_paid: Boolean(raw.is_paid),
  };
}

/**
 * Mapiranje detaljne fakture (GET /invoices/{id}) u InvoiceDetail.
 *
 * Backend vraća Decimal polja kao stringove, ovdje ih pretvaramo u number
 * tako da UI kod može normalno da radi sa njima (toFixed, sabiranje, grafici…).
 */
function mapInvoiceDetail(raw: any): InvoiceDetail {
  return {
    id: raw.id,
    tenant_code: raw.tenant_code,
    invoice_number: raw.invoice_number,
    issue_date: raw.issue_date,
    due_date: raw.due_date ?? null,
    buyer_name: raw.buyer_name,
    buyer_address: raw.buyer_address ?? null,
    buyer_tax_id: raw.buyer_tax_id ?? null,
    total_base: toNumberOrZero(raw.total_base),
    total_vat: toNumberOrZero(raw.total_vat),
    total_amount: toNumberOrZero(raw.total_amount),
    is_paid: Boolean(raw.is_paid),
    note: raw.note ?? null,
    items: Array.isArray(raw.items)
      ? raw.items.map((it: any) => ({
          id: it.id,
          description: it.description,
          quantity: toNumberOrZero(it.quantity),
          unit_price: toNumberOrZero(it.unit_price),
          vat_rate: toNumberOrZero(it.vat_rate),
          base_amount: toNumberOrZero(it.base_amount),
          vat_amount: toNumberOrZero(it.vat_amount),
          total_amount: toNumberOrZero(it.total_amount),
          discount_percent: toNumberOrZero(it.discount_percent),
        }))
      : [],
  };
}

/**
 * UI lista faktura – koristi novi backend endpoint /invoices/list.
 * Vraća total + items (InvoiceRowItem) SA MAPIRANJEM na očekivane tipove.
 */
export async function fetchInvoicesList(
  params: InvoicesListParams = {},
): Promise<InvoiceListResponse> {
  const response = await apiClient.get("/invoices/list", { params });
  const raw = response.data as any;

  const items: InvoiceRowItem[] = Array.isArray(raw.items)
    ? raw.items.map(mapInvoiceRowItem)
    : [];

  const total =
    typeof raw.total === "number" && Number.isFinite(raw.total)
      ? raw.total
      : items.length;

  return {
    total,
    items,
  };
}

/**
 * Detaljna faktura – GET /invoices/{id}
 */
export async function fetchInvoiceById(
  id: number,
): Promise<InvoiceDetail> {
  const response = await apiClient.get(`/invoices/${id}`);
  return mapInvoiceDetail(response.data);
}

/**
 * Kreiranje nove fakture – POST /invoices
 *
 * Napomena: frontend payload ima polje `number`,
 * a backend očekuje `invoice_number`.
 */
export async function createInvoice(
  payload: InvoiceCreatePayload,
): Promise<InvoiceDetail> {
  const backendPayload = {
    invoice_number: payload.number,
    buyer_name: payload.buyer_name,
    buyer_address: payload.buyer_address ?? null,
    buyer_tax_id: payload.buyer_tax_id ?? null,
    issue_date: payload.issue_date,
    due_date: payload.due_date ?? null,
    note: payload.note ?? null,
    items: payload.items,
  };

  const response = await apiClient.post("/invoices", backendPayload);
  return mapInvoiceDetail(response.data);
}

/**
 * Označavanje fakture kao plaćene – POST /invoices/{id}/mark-paid
 */
export async function markInvoicePaid(
  id: number,
): Promise<InvoiceDetail> {
  const response = await apiClient.post(`/invoices/${id}/mark-paid`);
  return mapInvoiceDetail(response.data);
}

/**
 * Export liste faktura – /invoices/export (CSV za Excel).
 * Vraća Blob koji možeš preuzeti ili otvoriti.
 */
export async function exportInvoicesExcel(
  params: InvoicesListParams = {},
): Promise<Blob> {
  const response = await apiClient.get("/invoices/export", {
    params,
    responseType: "blob",
  });
  return response.data;
}
