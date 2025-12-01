// /home/miso/dev/sp-app/sp-app/frontend/src/services/taxApi.ts
import { apiClient } from "./apiClient";

/**
 * Minimalni model za mjesečni TAX preview.
 * Polja su prilagođena dummy logici backend-a – ako nešto fali,
 * frontend će to jednostavno prikazati kao "-" ili u raw JSON dijelu.
 */
export interface TaxMonthlyPreviewResult {
  year: number;
  month: number;
  tenant_code: string;

  // osnovni agregati (nazivi su prilagođeni tipičnoj strukturi)
  total_income?: number | null;
  total_expenses?: number | null;
  taxable_base?: number | null;
  tax_amount?: number | null;
  contributions_amount?: number | null;
  total_due?: number | null;

  // status/info
  status?: string | null; // npr. "draft" / "finalized"
  is_finalized?: boolean | null;

  // fallback polje za sve ostalo što backend šalje
  [key: string]: unknown;
}

export interface TaxMonthlyParams {
  year: number;
  month: number;
}

/**
 * GET /tax/monthly/preview
 * Vraća preview obračuna poreza i doprinosa za zadani mjesec.
 */
export async function fetchTaxMonthlyPreview(
  params: TaxMonthlyParams,
): Promise<TaxMonthlyPreviewResult> {
  const res = await apiClient.get<TaxMonthlyPreviewResult>(
    "/tax/monthly/preview",
    {
      params: {
        year: params.year,
        month: params.month,
      },
    },
  );
  return res.data;
}

/**
 * POST /tax/monthly/auto
 * Pokreće automatski obračun (dummy logika u ovoj fazi) i vraća rezultat.
 */
export async function runTaxMonthlyAuto(
  params: TaxMonthlyParams,
): Promise<TaxMonthlyPreviewResult> {
  const res = await apiClient.post<TaxMonthlyPreviewResult>(
    "/tax/monthly/auto",
    {
      year: params.year,
      month: params.month,
    },
  );
  return res.data;
}
