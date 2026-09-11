// /home/miso/dev/sp-app/sp-app/frontend/src/services/prometApi.ts
import axios from "axios";

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

export type ExportPrometParams = Omit<
  FetchPrometParams,
  "limit" | "offset"
>;

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

export async function exportPrometCsv(
  params: ExportPrometParams,
): Promise<Blob> {
  try {
    const response = await apiClient.get<Blob>("/promet/export", {
      params,
      responseType: "blob",
    });

    return response.data;
  } catch (error: unknown) {
    // Axios sa responseType="blob" vraća i JSON greške kao Blob.
    // Pretvori ih nazad u JSON kako bi PrometPage mogao koristiti
    // isti backend error contract kao GET /promet.
    if (
      axios.isAxiosError(error) &&
      error.response?.data instanceof Blob &&
      error.response.data.type.includes("json")
    ) {
      try {
        error.response.data = JSON.parse(
          await error.response.data.text(),
        );
      } catch {
        // Ako body nije validan JSON, zadrži originalni Axios error.
      }
    }

    throw error;
  }
}
