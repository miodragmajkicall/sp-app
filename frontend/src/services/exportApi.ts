// /home/miso/dev/sp-app/sp-app/frontend/src/services/exportApi.ts

import { apiClient } from "./apiClient";

type ExportInspectionRequest = {
  from_date: string; // YYYY-MM-DD
  to_date: string; // YYYY-MM-DD
  include_outgoing_invoices_pdf: boolean;
  include_input_invoices_pdf: boolean;
  include_kpr_pdf: boolean;
  include_promet_pdf: boolean;
  include_cash_bank_pdf: boolean;
  include_taxes_pdf: boolean;
};

function buildFilename(fromDate: string, toDate: string): string {
  return `inspection_${fromDate}_${toDate}.zip`;
}

export async function downloadInspectionZip(
  req: ExportInspectionRequest,
): Promise<void> {
  // Očekivani backend endpoint:
  // POST /export/inspection  -> returns application/zip
  const res = await apiClient.post("/export/inspection", req, {
    responseType: "blob",
    headers: {
      Accept: "application/zip",
    },
  });

  const blob = new Blob([res.data], { type: "application/zip" });
  const url = window.URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = buildFilename(req.from_date, req.to_date);
  document.body.appendChild(a);
  a.click();
  a.remove();

  window.URL.revokeObjectURL(url);
}
