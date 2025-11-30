// /home/miso/dev/sp-app/sp-app/frontend/src/types/invoice.ts

/** Stavka u tabeli izlaznih faktura (za UI listu) */
export interface InvoiceRowItem {
  id: number;
  /** Broj fakture – mapiran iz backend field-a `invoice_number` */
  number: string | null;
  buyer_name: string | null;
  issue_date: string | null;
  due_date: string | null;
  /** Ukupni iznos sa PDV-om u KM */
  total_amount: number | null;
  is_paid: boolean;
}

/** Odgovor za GET /invoices/list – za UI tabelu */
export interface InvoiceListResponse {
  total: number;
  items: InvoiceRowItem[];
}

/** payload za kreiranje fakture (forma → POST /invoices) */
export interface InvoiceCreatePayload {
  number: string;
  buyer_name: string;
  issue_date: string;
  due_date: string | null;
  total_amount: number;
}
