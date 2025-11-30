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
  note?: string | null;
}

export async function createCashEntry(
  payload: CashEntryCreatePayload
): Promise<CashEntry> {
  const res = await apiClient.post<CashEntry>("/cash", payload);
  return res.data;
}
