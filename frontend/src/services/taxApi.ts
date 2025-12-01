// /home/miso/dev/sp-app/sp-app/frontend/src/services/taxApi.ts
import { apiClient } from "./apiClient";

/**
 * Minimalni model za mjesečni TAX rezultat.
 * Ovo je generički tip – backend može vraćati i dodatna polja.
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
  status?: string | null;
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
 * GET /tax/monthly/auto
 * Pokreće automatski obračun (dummy logika u ovoj fazi) i vraća rezultat.
 * Usklađeno sa TaxPage ekranom koji koristi GET /tax/monthly/auto.
 */
export async function runTaxMonthlyAuto(
  params: TaxMonthlyParams,
): Promise<TaxMonthlyPreviewResult> {
  const res = await apiClient.get<TaxMonthlyPreviewResult>(
    "/tax/monthly/auto",
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
 * POST /tax/monthly/finalize
 * Finalizuje obračun za zadani mjesec i vraća rezultat (zaključan mjesec).
 */
export async function finalizeTaxMonthly(
  params: TaxMonthlyParams,
): Promise<TaxMonthlyPreviewResult> {
  const res = await apiClient.post<TaxMonthlyPreviewResult>(
    "/tax/monthly/finalize",
    {
      year: params.year,
      month: params.month,
    },
  );
  return res.data;
}

/**
 * GET /tax/monthly/history
 * Vraća istoriju mjesečnih obračuna (npr. za cijelu godinu).
 *
 * Backend može vraćati direktno listu ili objekat sa poljem `items`.
 * Ovdje vraćamo ono što API vrati (lista), a konkretno mapiranje se
 * može raditi u komponenti.
 */
export async function fetchTaxMonthlyHistory(
  params: { year?: number } = {},
): Promise<TaxMonthlyPreviewResult[]> {
  const res = await apiClient.get<TaxMonthlyPreviewResult[]>(
    "/tax/monthly/history",
    {
      params: params.year ? { year: params.year } : undefined,
    },
  );
  return res.data;
}
