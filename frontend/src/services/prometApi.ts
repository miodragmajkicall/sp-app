// /home/miso/dev/sp-app/sp-app/frontend/src/services/prometApi.ts
import { apiClient } from "./apiClient";

export type PrometRow = {
  date: string;
  document_number: string | null;
  partner_name: string | null;
  amount: number | string;
  note?: string | null;
};

export type PrometSummary = {
  total_amount: number | string;
  cash_amount: number | string;
  bank_amount: number | string;
};

export type FetchPrometParams = {
  year?: number;
  month?: number;
  date_from?: string;
  date_to?: string;
  partner_query?: string;
  limit?: number;
  offset?: number;
};

export type PrometListResponse = {
  total: number;
  summary: PrometSummary;
  items: PrometRow[];
};

export async function fetchPromet(
  params: FetchPrometParams,
): Promise<PrometListResponse> {
  const response = await apiClient.get<PrometListResponse>("/promet", {
    params,
  });
  return response.data;
}
