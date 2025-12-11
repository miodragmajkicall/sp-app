// /home/miso/dev/sp-app/sp-app/frontend/src/services/prometApi.ts
import { apiClient } from "./apiClient";

export type PrometRow = {
  date: string;
  document_number: string;
  partner_name: string;
  amount: number | string;
  note?: string | null;
};

export type PrometListResponse = {
  total: number;
  items: PrometRow[];
};

export async function fetchPromet(params: Record<string, any>) {
  const response = await apiClient.get<PrometListResponse>("/promet", {
    params,
  });
  return response.data;
}

export async function exportPrometCsv(params: Record<string, any>) {
  const response = await apiClient.get("/promet/export", {
    params,
    responseType: "blob",
  });
  return response.data;
}
