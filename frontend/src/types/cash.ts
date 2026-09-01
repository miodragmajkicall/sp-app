// /home/miso/dev/sp-app/sp-app/frontend/src/types/cash.ts

export type CashKind = "income" | "expense";
export type CashAccount = "cash" | "bank";

export type CashRecognitionClass =
  | "business_activity"
  | "cash_only";

export type CashTaxTreatment =
  | "deductible"
  | "nondeductible"
  | "unresolved";

export type CashSourceType =
  | "manual"
  | "output_invoice_payment"
  | "input_invoice_payment";

export interface CashEntry {
  id: number;
  entry_date: string;
  kind: CashKind;
  amount: number | string;
  account: CashAccount;
  recognition_class: CashRecognitionClass | null;
  tax_treatment: CashTaxTreatment | null;
  invoice_id: number | null;
  input_invoice_id: number | null;
  note: string | null;
  created_at: string;
}

export interface CashListItem extends CashEntry {
  source_type: CashSourceType;
  source_document_id: number | null;
  source_document_number: string | null;
  source_party_name: string | null;
}

export interface CashListResponse {
  total: number;
  limit: number;
  offset: number;
  items: CashListItem[];
}

export interface CashSummary {
  income: number | string;
  expense: number | string;
  net: number | string;
  cash_net: number | string;
  bank_net: number | string;
  total_count: number;
}
