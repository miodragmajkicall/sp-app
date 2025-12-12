// /home/miso/dev/sp-app/sp-app/frontend/src/services/reportsApi.ts

import { apiClient } from "./apiClient";
import type {
  ReportsCashflowYearResponse,
  ReportsYearSummaryResponse,
} from "../types/reports";

export async function fetchReportsCashflowYear(
  year: number,
): Promise<ReportsCashflowYearResponse> {
  const res = await apiClient.get<ReportsCashflowYearResponse>(
    `/reports/cashflow/${year}`,
  );
  return res.data;
}

export async function fetchReportsYearSummary(
  year: number,
): Promise<ReportsYearSummaryResponse> {
  const res = await apiClient.get<ReportsYearSummaryResponse>(
    `/reports/year-summary/${year}`,
  );
  return res.data;
}

/**
 * CSV export ide preko browser-a (download). Koristimo API base iz apiClient konfiguracije.
 * Napomena: apiClient.ts već postavlja baseURL; ovdje radimo manualni download.
 */
export function buildReportsCashflowYearCsvUrl(
  apiBaseUrl: string,
  year: number,
): string {
  const base = apiBaseUrl.replace(/\/$/, "");
  return `${base}/reports/cashflow/${year}/export`;
}
