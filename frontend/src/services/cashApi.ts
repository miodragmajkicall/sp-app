// /home/miso/dev/sp-app/sp-app/frontend/src/services/cashApi.ts

import { apiClient } from "./apiClient";
import type { CashEntry } from "../types/cash";

export async function fetchCashEntries(): Promise<CashEntry[]> {
  const res = await apiClient.get<CashEntry[]>("/cash");
  return res.data;
}

export interface CashEntryCreatePayload {
  entry_date: string; // "YYYY-MM-DD"
  kind: "income" | "expense";
  amount: number;

  // opis ide kao "note" (backend ga mapira na description)
  note?: string | null;

  // novi dio – račun i povezane fakture (opciono)
  account?: "cash" | "bank";
  invoice_id?: number | null;
  input_invoice_id?: number | null;
}

export async function createCashEntry(
  payload: CashEntryCreatePayload
): Promise<CashEntry> {
  const res = await apiClient.post<CashEntry>("/cash", payload);
  return res.data;
}
