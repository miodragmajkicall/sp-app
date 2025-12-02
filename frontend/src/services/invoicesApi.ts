// /home/miso/dev/sp-app/sp-app/frontend/src/services/invoicesApi.ts
import { apiClient } from "./apiClient";
import type {
  InvoiceListResponse,
  InvoiceRowItem,
  InvoiceCreatePayload,
} from "../types/invoice";

export interface FetchInvoicesListOptions {
  /** ako je true – backend vraća samo neplaćene (unpaid_only) */
  unpaidOnly?: boolean;
}

/**
 * GET – UI-friendly lista izlaznih faktura
 * Koristi backend endpoint /invoices/list koji vraća { total, items }.
 *
 * Opcioni filter:
 * - unpaidOnly: ako je true, šaljemo ?unpaid_only=true (samo neplaćene)
 *
 * Napomena: backend ima paginaciju, pa ovdje tražimo prvu stranicu
 * sa većim page_size (npr. 200) kako bismo u UI-u vidjeli sve fakture
 * dok ne uvedemo pravu paginaciju.
 */
export async function fetchInvoicesList(
  options?: FetchInvoicesListOptions,
): Promise<InvoiceListResponse> {
  const unpaidOnly = options?.unpaidOnly === true;

  const res = await apiClient.get<{
    total: number;
    items: Array<{
      id: number;
      invoice_number?: string | null;
      buyer_name?: string | null;
      issue_date?: string | null;
      due_date?: string | null;
      total_amount?: string | number | null;
      is_paid?: boolean;
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
    // backend šalje `invoice_number` – mapiramo ga na `number` za UI
    number: item.invoice_number ?? null,
    buyer_name: item.buyer_name ?? null,
    issue_date: item.issue_date ?? null,
    due_date: item.due_date ?? null,
    // total_amount stiže kao string (Decimal) – parsiramo u number
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
 * Alias ako nam negdje zatreba samo lista bez metapodataka
 * (trenutno ga ne koristi UI, ali ostavljamo za kasnije).
 */
export async function fetchInvoices(): Promise<InvoiceRowItem[]> {
  const data = await fetchInvoicesList();
  return data.items;
}

/**
 * POST – kreiranje nove izlazne fakture
 *
 * Forma radi sa "number" i "total_amount",
 * a backend očekuje "invoice_number" + "items" sa vat_rate=0.17.
 */
export async function createInvoice(
  payload: InvoiceCreatePayload,
): Promise<void> {
  const body = {
    // mapiranje na backend polja
    invoice_number: payload.number,
    buyer_name: payload.buyer_name,
    issue_date: payload.issue_date,
    due_date: payload.due_date,
    total_amount: payload.total_amount,
    currency: "BAM",

    // minimalna jedna stavka – sa ispravnim vat_rate = 0.17 (17%)
    items: [
      {
        description: "Stavka 1",
        quantity: 1,
        unit_price: payload.total_amount,
        vat_rate: 0.17,
      },
    ],
  };

  await apiClient.post("/invoices", body);
}

/**
 * POST – označi fakturu kao plaćenu
 * koristi backend /invoices/{id}/mark-paid
 */
export async function markInvoicePaid(invoiceId: number): Promise<void> {
  await apiClient.post(`/invoices/${invoiceId}/mark-paid`, null);
}
