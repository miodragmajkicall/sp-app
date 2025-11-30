import { apiClient } from "./apiClient";
import type { InputInvoiceListItem } from "../types/inputInvoice";

export async function fetchInputInvoices(): Promise<InputInvoiceListItem[]> {
  const res = await apiClient.get<InputInvoiceListItem[]>("/input-invoices");
  return res.data;
}
