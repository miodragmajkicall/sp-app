import { apiClient } from "./apiClient";
import type { InvoiceListItem } from "../types/invoice";

export async function fetchInvoices(): Promise<InvoiceListItem[]> {
  const res = await apiClient.get<InvoiceListItem[]>("/invoices");
  return res.data;
}
