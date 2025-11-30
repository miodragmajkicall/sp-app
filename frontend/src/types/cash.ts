export interface CashEntry {
  id: number;
  occurred_at?: string; // datum transakcije
  kind?: "income" | "expense" | string;
  amount?: number;
  description?: string | null;
}
