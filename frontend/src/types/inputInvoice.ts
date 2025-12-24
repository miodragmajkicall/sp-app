// /home/miso/dev/sp-app/sp-app/frontend/src/types/inputInvoice.ts

/**
 * Pojedinačni red u listi ulaznih faktura (UI projekcija).
 */
export interface InputInvoiceListItem {
  id: number;
  number: string | null;
  supplier_name: string | null;
  issue_date: string | null;
  due_date: string | null;
  posting_date: string | null;
  total_amount: number | null;
  currency: string | null;
  expense_category: string | null;
  is_tax_deductible: boolean | null;
  is_paid: boolean | null;
}

/**
 * Response model za UI listu ulaznih faktura (/input-invoices/list).
 */
export interface InputInvoiceListResponse {
  total: number;
  items: InputInvoiceListItem[];
}

/**
 * Detaljna šema ulazne fakture (mapira se na backend InputInvoiceRead).
 */
export interface InputInvoiceDetail {
  id: number;
  tenant_code: string;

  supplier_name: string;
  supplier_tax_id: string | null;
  supplier_address: string | null;

  invoice_number: string;
  issue_date: string; // YYYY-MM-DD
  posting_date: string | null; // YYYY-MM-DD ili null
  due_date: string | null; // YYYY-MM-DD ili null

  expense_category: string | null;
  is_tax_deductible: boolean;
  is_paid: boolean;

  total_base: number;
  total_vat: number;
  total_amount: number;

  currency: string;
  note: string | null;

  created_at: string; // ISO datetime string
}
