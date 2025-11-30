export interface InvoiceListItem {
  id: number;
  number?: string;
  issue_date?: string;
  due_date?: string | null;
  buyer_name?: string;
  total_amount?: number;
  currency?: string;
  is_paid?: boolean;
}
