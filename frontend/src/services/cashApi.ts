// /home/miso/dev/sp-app/sp-app/frontend/src/services/cashApi.ts

import { apiClient } from "./apiClient";
import type {
  CashAccount,
  CashEntry,
  CashKind,
  CashListResponse,
  CashRecognitionClass,
  CashSourceType,
  CashSummary,
  CashTaxTreatment,
} from "../types/cash";

export interface CashListParams {
  date_from?: string;
  date_to?: string;
  year?: number;
  month?: number;
  kind?: CashKind;
  account?: CashAccount;
  source_type?: CashSourceType;
  recognition_class?: CashRecognitionClass;
  tax_treatment?: CashTaxTreatment;
  limit?: number;
  offset?: number;
}

export interface CashSummaryParams {
  date_from?: string;
  date_to?: string;
}

export interface CashEntryCreatePayload {
  entry_date: string;
  kind: CashKind;
  amount: number;
  account: CashAccount;
  recognition_class: CashRecognitionClass;
  tax_treatment?: CashTaxTreatment | null;
  note?: string | null;
}

export interface CashEntryUpdatePayload {
  entry_date?: string;
  kind?: CashKind;
  amount?: number;
  account?: CashAccount;
  recognition_class?: CashRecognitionClass;
  tax_treatment?: CashTaxTreatment | null;
  note?: string | null;
}

export async function fetchCashEntries(
  params: CashListParams = {}
): Promise<CashListResponse> {
  const res = await apiClient.get<CashListResponse>("/cash/list", {
    params,
  });
  return res.data;
}

export async function fetchCashSummary(
  params: CashSummaryParams = {}
): Promise<CashSummary> {
  const res = await apiClient.get<CashSummary>("/cash/summary", {
    params,
  });
  return res.data;
}

export async function createCashEntry(
  payload: CashEntryCreatePayload
): Promise<CashEntry> {
  const res = await apiClient.post<CashEntry>("/cash", payload);
  return res.data;
}

export async function updateCashEntry(
  cashId: number,
  payload: CashEntryUpdatePayload
): Promise<CashEntry> {
  const res = await apiClient.patch<CashEntry>(
    `/cash/${cashId}`,
    payload
  );
  return res.data;
}

export async function deleteCashEntry(
  cashId: number
): Promise<void> {
  await apiClient.delete(`/cash/${cashId}`);
}
