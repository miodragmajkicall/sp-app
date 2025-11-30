export interface InputInvoiceListItem {
  id: number;
  number?: string;
  supplier_name?: string;
  issue_date?: string;
  received_date?: string | null;
  total_amount?: number;
  currency?: string;
}
