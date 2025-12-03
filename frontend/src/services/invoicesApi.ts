// /home/miso/dev/sp-app/sp-app/frontend/src/services/invoicesApi.ts
import { apiClient } from "./apiClient";
import type {
  InvoiceListResponse,
  InvoiceRowItem,
  InvoiceCreatePayload,
  InvoiceDetail,
  InvoiceItemDetail,
} from "../types/invoice";

export interface FetchInvoicesListOptions {
  /** ako je true – backend vraća samo neplaćene (unpaid_only) */
  unpaidOnly?: boolean;
}

/**
 * GET – UI-friendly lista izlaznih faktura
 * Koristi backend endpoint /invoices/list koji vraća { total, items }.
 */
export async function fetchInvoicesList(
  options?: FetchInvoicesListOptions,
): Promise<InvoiceListResponse> {
  const unpaidOnly = options?.unpaidOnly === true;

  const res = await apiClient.get<{
    total: number;
    items: Array<{
      id: number;
      invoice_number: string | null;
      buyer_name: string | null;
      issue_date: string | null;
      due_date: string | null;
      total_amount: string | number | null;
      is_paid: boolean | null;
    }>;
  }>("/invoices/list", {
    params: {
      unpaid_only: unpaidOnly ? true : undefined,
      page: 1,
      page_size: 200,
    },
  });

  const raw = res.data;

  const items: InvoiceRowItem[] = raw.items.map((item) => ({
    id: item.id,
    number: item.invoice_number ?? null,
    buyer_name: item.buyer_name ?? null,
    issue_date: item.issue_date ?? null,
    due_date: item.due_date ?? null,
    total_amount:
      item.total_amount != null ? Number(item.total_amount) : null,
    is_paid: item.is_paid ?? false,
  }));

  return {
    total: raw.total,
    items,
  };
}

/**
 * Alias ako nam negdje zatreba samo lista bez metapodataka.
 */
export async function fetchInvoices(): Promise<InvoiceRowItem[]> {
  const data = await fetchInvoicesList();
  return data.items;
}

/**
 * POST – kreiranje nove izlazne fakture
 *
 * Sada šaljemo SVE stavke koje je korisnik unio:
 * - quantity = količina
 * - unit_price = cijena bez PDV-a
 * - vat_rate = 0.17 (17%)
 *
 * Backend SAM računa total_base / total_vat / total_amount.
 * Više nema duplog PDV-a.
 */
export async function createInvoice(
  payload: InvoiceCreatePayload,
): Promise<void> {
  const body = {
    invoice_number: payload.number,
    buyer_name: payload.buyer_name,
    buyer_address: payload.buyer_address ?? null,
    issue_date: payload.issue_date,
    due_date: payload.due_date,
    items: payload.items.map((item) => ({
      description: item.description,
      quantity: item.quantity,
      unit_price: item.unit_price,
      vat_rate: item.vat_rate,
    })),
  };

  await apiClient.post("/invoices", body);
}

/**
 * GET /invoices/{id} – puni detalj fakture + stavke
 */
export async function fetchInvoiceById(
  invoiceId: number,
): Promise<InvoiceDetail> {
  const res = await apiClient.get<{
    id: number;
    tenant_code: string;
    invoice_number: string;
    issue_date: string;
    due_date: string | null;
    buyer_name: string;
    buyer_address: string | null;
    total_base: string | number;
    total_vat: string | number;
    total_amount: string | number;
    is_paid: boolean;
    items: Array<{
      id: number;
      description: string;
      quantity: string | number;
      unit_price: string | number;
      vat_rate: string | number;
      base_amount: string | number;
      vat_amount: string | number;
      total_amount: string | number;
    }>;
  }>(`/invoices/${invoiceId}`);

  const raw = res.data;

  const items: InvoiceItemDetail[] = raw.items.map((i) => ({
    id: i.id,
    description: i.description,
    quantity: Number(i.quantity),
    unit_price: Number(i.unit_price),
    vat_rate: Number(i.vat_rate),
    base_amount: Number(i.base_amount),
    vat_amount: Number(i.vat_amount),
    total_amount: Number(i.total_amount),
  }));

  const detail: InvoiceDetail = {
    id: raw.id,
    tenant_code: raw.tenant_code,
    invoice_number: raw.invoice_number,
    issue_date: raw.issue_date,
    due_date: raw.due_date,
    buyer_name: raw.buyer_name,
    buyer_address: raw.buyer_address,
    total_base: Number(raw.total_base),
    total_vat: Number(raw.total_vat),
    total_amount: Number(raw.total_amount),
    is_paid: raw.is_paid,
    items,
  };

  return detail;
}

/**
 * POST – označi fakturu kao plaćenu
 */
export async function markInvoicePaid(invoiceId: number): Promise<void> {
  await apiClient.post(`/invoices/${invoiceId}/mark-paid`, null);
}
