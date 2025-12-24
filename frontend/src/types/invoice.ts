// /home/miso/dev/sp-app/sp-app/frontend/src/types/invoice.ts

// Red za tabelu "Izlazne fakture"
export interface InvoiceRowItem {
  id: number;
  number: string | null;
  buyer_name: string | null;
  issue_date: string | null;
  due_date: string | null;
  total_amount: number | null;
  is_paid: boolean;
}

// Odgovor za UI listu faktura
export interface InvoiceListResponse {
  total: number;
  items: InvoiceRowItem[];
}

// Stavka fakture za kreiranje
export interface InvoiceCreateItemPayload {
  description: string;
  quantity: number;
  unit_price: number;      // cijena bez PDV-a
  vat_rate: number;        // npr. 0.17
  discount_percent?: number; // popust u %, npr. 0–100
}

// Payload za kreiranje fakture sa više stavki
export interface InvoiceCreatePayload {
  number: string;
  buyer_name: string;
  buyer_address?: string | null;
  buyer_tax_id?: string | null;
  issue_date: string;       // "YYYY-MM-DD"
  due_date: string | null;  // ili null
  note?: string | null;
  items: InvoiceCreateItemPayload[];
}

// Detaljna stavka fakture (za ekran detalja / PDF)
export interface InvoiceItemDetail {
  id: number;
  description: string;
  quantity: number;
  unit_price: number;
  vat_rate: number;
  base_amount: number;
  vat_amount: number;
  total_amount: number;
  discount_percent: number; // 0–100, ako BE ne šalje, mapiramo na 0
}

// Detaljna faktura (GET /invoices/{id})
export interface InvoiceDetail {
  id: number;
  tenant_code: string;
  invoice_number: string;
  issue_date: string;
  due_date: string | null;
  buyer_name: string;
  buyer_address: string | null;
  buyer_tax_id: string | null;
  total_base: number;
  total_vat: number;
  total_amount: number;
  is_paid: boolean;
  note: string | null;
  items: InvoiceItemDetail[];
}
