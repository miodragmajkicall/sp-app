// /home/miso/dev/sp-app/sp-app/frontend/src/types/kpr.ts

export type KprKind = "income" | "expense";

export type KprTaxTreatment =
  | "deductible"
  | "nondeductible"
  | "unresolved";

export interface KprRowItem {
  /**
   * Datum u KPR-u (YYYY-MM-DD).
   * Backend šalje Pydantic date, koji dolazi kao string.
   */
  date: string;
  kind: KprKind;
  /**
   * Kategorija izvora:
   * - "invoice"
   * - "input_invoice"
   * - "cash"
   */
  category: string;
  counterparty: string | null;
  document_number: string | null;
  description: string | null;
  amount: number;
  currency: string;
  tax_deductible: boolean | null;
  tax_treatment: KprTaxTreatment | null;
  source: string;
  source_id: number;
}

export interface KprSummary {
  income: number;
  expense: number;
  net: number;
}

export interface KprListResponse {
  total: number;
  summary: KprSummary;
  items: KprRowItem[];
}
