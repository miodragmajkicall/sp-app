// /home/miso/dev/sp-app/sp-app/frontend/src/types/reports.ts

export interface ReportsCashflowMonthlyItem {
  month: number;
  income: number | string;
  expense: number | string;
  profit: number | string;
  currency: string;
}

export interface ReportsCashflowYearResponse {
  year: number;
  tenant_code: string;
  items: ReportsCashflowMonthlyItem[];
}

export interface ReportsYearSummaryResponse {
  year: number;
  tenant_code: string;
  total_income: number | string;
  total_expense: number | string;
  profit: number | string;
  taxable_base: number | string;
  income_tax: number | string;
  contributions_total: number | string;
  total_due: number | string;
  currency: string;
}
