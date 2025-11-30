import { apiClient } from "./apiClient";
import type { CashEntry } from "../types/cash";

export async function fetchCashEntries(): Promise<CashEntry[]> {
  const res = await apiClient.get<CashEntry[]>("/cash");
  return res.data;
}
