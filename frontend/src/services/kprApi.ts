// /home/miso/dev/sp-app/sp-app/frontend/src/services/kprApi.ts
import { apiClient } from "./apiClient";
import type { KprListResponse, KprRowItem } from "../types/kpr";

export interface FetchKprListOptions {
  year?: number;
  month?: number;
  page?: number;
  pageSize?: number;
}

/**
 * Mapira raw stavku iz /kpr u KprRowItem za UI.
 */
function mapKprRowItem(raw: any): KprRowItem {
  return {
    date: raw.date ?? raw.entry_date ?? "",
    kind: raw.kind ?? "income",
    category: raw.category ?? raw.source ?? "",
    counterparty: raw.counterparty ?? null,
    document_number: raw.document_number ?? null,
    description: raw.description ?? null,
    amount:
      raw.amount != null
        ? Number(raw.amount)
        : 0,
    currency: raw.currency ?? "BAM",
    tax_deductible:
      typeof raw.tax_deductible === "boolean"
        ? raw.tax_deductible
        : raw.kind === "expense",
    source: raw.source ?? raw.category ?? "",
    source_id:
      typeof raw.source_id === "number"
        ? raw.source_id
        : Number(raw.source_id ?? 0),
  };
}

/**
 * GET /kpr – lista stavki za Knjigu prihoda i rashoda.
 * Backend vraća { total, items }.
 */
export async function fetchKprList(
  options: FetchKprListOptions = {},
): Promise<KprListResponse> {
  const page = options.page ?? 1;
  const pageSize = options.pageSize ?? 500;

  const res = await apiClient.get<{
    total: number;
    items: any[];
  }>("/kpr", {
    params: {
      year: options.year,
      month: options.month,
      page,
      page_size: pageSize,
    },
  });

  const raw = res.data;

  return {
    total: raw.total ?? 0,
    items: Array.isArray(raw.items)
      ? raw.items.map(mapKprRowItem)
      : [],
  };
}

/**
 * GET /kpr/export – preuzimanje PDF verzije KPR-a.
 * Ako su year i month zadati – export za taj mjesec.
 */
export async function exportKprPdf(
  year?: number,
  month?: number,
): Promise<void> {
  const res = await apiClient.get<Blob>("/kpr/export", {
    params: {
      year,
      month,
    },
    responseType: "blob",
  });

  const contentTypeHeader =
    (res.headers["content-type"] as string | undefined) ||
    "application/pdf";

  const blob = new Blob([res.data], { type: contentTypeHeader });
  const url = URL.createObjectURL(blob);

  // Otvori u novom tabu (PDF pregled)
  window.open(url, "_blank", "noopener,noreferrer");

  // I pripremi download link (opciono)
  const link = document.createElement("a");
  link.href = url;
  link.download = "kpr.pdf";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  URL.revokeObjectURL(url);
}
