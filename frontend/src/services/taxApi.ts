// /home/miso/dev/sp-app/sp-app/frontend/src/services/taxApi.ts
import { apiClient } from "./apiClient";

/**
 * Usklađeno sa backend response_model=MonthlyTaxSummaryRead
 * (Decimal polja obično dolaze kao string iz JSON-a).
 */
export type MonthlyTaxSummaryRead = {
  year: number;
  month: number;
  tenant_code: string;

  total_income: string;
  total_expense: string;
  taxable_base: string;
  income_tax: string;
  contributions_total: string;
  total_due: string;

  is_final: boolean;
  currency: string;
};

export type YearlyTaxSummaryRead = {
  year: number;
  tenant_code: string;
  months_included: number;

  total_income: string;
  total_expense: string;
  taxable_base: string;
  income_tax: string;
  contributions_total: string;
  total_due: string;

  currency: string;
};

export type TaxMonthlyParams = {
  year: number;
  month: number;
};

export type TaxYearlyMode = "pausal" | "two_percent";

/**
 * GET /tax/monthly/auto
 */
export async function fetchTaxMonthlyAuto(
  params: TaxMonthlyParams,
): Promise<MonthlyTaxSummaryRead> {
  const res = await apiClient.get<MonthlyTaxSummaryRead>("/tax/monthly/auto", {
    params: { year: params.year, month: params.month },
  });
  return res.data;
}

/**
 * GET /tax/monthly/preview
 * (ručni preview kroz query parametre total_income i total_expense)
 */
export async function fetchTaxMonthlyPreview(params: {
  year: number;
  month: number;
  total_income: string | number;
  total_expense?: string | number;
}): Promise<MonthlyTaxSummaryRead> {
  const res = await apiClient.get<MonthlyTaxSummaryRead>("/tax/monthly/preview", {
    params: {
      year: params.year,
      month: params.month,
      total_income: params.total_income,
      total_expense: params.total_expense ?? 0,
    },
  });
  return res.data;
}

/**
 * POST /tax/monthly/finalize
 * VAŽNO: backend uzima year/month kao Query parametre, ne iz body-ja.
 */
export async function finalizeTaxMonthly(
  params: TaxMonthlyParams,
): Promise<MonthlyTaxSummaryRead> {
  const res = await apiClient.post<MonthlyTaxSummaryRead>(
    "/tax/monthly/finalize",
    null,
    { params: { year: params.year, month: params.month } },
  );
  return res.data;
}

/**
 * GET /tax/monthly/history
 */
export async function fetchTaxMonthlyHistory(params: {
  year: number;
}): Promise<MonthlyTaxSummaryRead[]> {
  const res = await apiClient.get<MonthlyTaxSummaryRead[]>("/tax/monthly/history", {
    params: { year: params.year },
  });
  return res.data;
}

/**
 * GET /tax/yearly/preview
 */
export async function fetchTaxYearlyPreview(params: {
  year: number;
}): Promise<YearlyTaxSummaryRead> {
  const res = await apiClient.get<YearlyTaxSummaryRead>("/tax/yearly/preview", {
    params: { year: params.year },
  });
  return res.data;
}

/**
 * POST /tax/yearly/finalize
 * VAŽNO: backend uzima year kao Query parametar.
 */
export async function finalizeTaxYearly(params: {
  year: number;
}): Promise<YearlyTaxSummaryRead> {
  const res = await apiClient.post<YearlyTaxSummaryRead>(
    "/tax/yearly/finalize",
    null,
    { params: { year: params.year } },
  );
  return res.data;
}
