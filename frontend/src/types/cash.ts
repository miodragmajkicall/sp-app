// /home/miso/dev/sp-app/sp-app/frontend/src/types/cash.ts

export interface CashEntry {
  id: number;

  // backend koristi entry_date, a negdje se pojavljivao i occurred_at – podržavamo oba
  entry_date?: string;
  occurred_at?: string;

  kind?: "income" | "expense" | string;
  amount?: number | string;

  // vrsta računa: kasa / banka
  account?: "cash" | "bank" | string;

  // opcione veze na fakture
  invoice_id?: number | null;
  input_invoice_id?: number | null;

  // backend U ODGOVORU šalje opis kao "note",
  // ali ostavljamo i "description" radi kompatibilnosti
  note?: string | null;
  description?: string | null;

  created_at?: string;
}
