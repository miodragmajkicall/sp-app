// /home/miso/dev/sp-app/sp-app/frontend/src/services/kprApi.ts
import { apiClient } from "./apiClient";
import type {
  KprKind,
  KprListResponse,
  KprRowItem,
} from "../types/kpr";

export interface FetchKprListOptions {
  year?: number;
  month?: number;
  kind?: KprKind;
  limit?: number;
  offset?: number;
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
        : null,
    tax_treatment:
      raw.tax_treatment === "deductible" ||
      raw.tax_treatment === "nondeductible" ||
      raw.tax_treatment === "unresolved"
        ? raw.tax_treatment
        : null,
    source: raw.source ?? raw.category ?? "",
    source_id:
      typeof raw.source_id === "number"
        ? raw.source_id
        : Number(raw.source_id ?? 0),
  };
}

/**
 * GET /kpr – lista stavki za Knjigu prihoda i rashoda.
 * Backend vraća { total, summary, items }.
 */
export async function fetchKprList(
  options: FetchKprListOptions = {},
): Promise<KprListResponse> {
  const limit = options.limit ?? 1000;
  const offset = options.offset ?? 0;

  const res = await apiClient.get<{
    total: number;
    summary: {
      income: number | string;
      expense: number | string;
      net: number | string;
    };
    items: any[];
  }>("/kpr", {
    params: {
      year: options.year,
      month: options.month,
      kind: options.kind,
      limit,
      offset,
    },
  });

  const raw = res.data;

  return {
    total: raw.total ?? 0,
    summary: {
      income: Number(raw.summary.income),
      expense: Number(raw.summary.expense),
      net: Number(raw.summary.net),
    },
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

/**
 * GET /kpr/export-excel – preuzimanje CSV/Excel verzije KPR-a.
 */
export async function exportKprExcel(
  year?: number,
  month?: number,
): Promise<void> {
  const res = await apiClient.get<Blob>("/kpr/export-excel", {
    params: {
      year,
      month,
    },
    responseType: "blob",
  });

  const contentTypeHeader =
    (res.headers["content-type"] as string | undefined) ||
    "text/csv";

  const blob = new Blob([res.data], { type: contentTypeHeader });
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = "kpr.csv";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  URL.revokeObjectURL(url);
}
