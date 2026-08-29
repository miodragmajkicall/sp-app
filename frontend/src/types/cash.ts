// /home/miso/dev/sp-app/sp-app/frontend/src/types/cash.ts

export type CashKind = "income" | "expense";
export type CashAccount = "cash" | "bank";

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
