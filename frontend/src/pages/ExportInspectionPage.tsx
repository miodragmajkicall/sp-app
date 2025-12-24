// /home/miso/dev/sp-app/sp-app/frontend/src/pages/ExportInspectionPage.tsx

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient, getApiBaseUrl } from "../services/apiClient";
import { downloadInspectionZip } from "../services/exportApi";

interface DashboardMonthlyResponse {
  tenant_code: string;
  year: number;
  month: number;
}

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function toIsoDate(d: Date): string {
  const yyyy = d.getFullYear();
  const mm = pad2(d.getMonth() + 1);
  const dd = pad2(d.getDate());
  return `${yyyy}-${mm}-${dd}`;
}

function firstDayOfMonth(year: number, month: number): string {
  return `${year}-${pad2(month)}-01`;
}

function lastDayOfMonth(year: number, month: number): string {
  // month is 1-12
  const d = new Date(year, month, 0); // last day of given month
  return toIsoDate(d);
}

export default function ExportInspectionPage() {
  const apiBaseUrl = getApiBaseUrl();

  const {
    data: currentMonthly,
    isLoading: isLoadingCurrent,
    isError: isErrorCurrent,
    error: errorCurrent,
  } = useQuery<DashboardMonthlyResponse, Error>({
    queryKey: ["export", "bootstrap", "dashboard-monthly-current"],
    queryFn: async () => {
      const res = await apiClient.get<DashboardMonthlyResponse>(
        "/dashboard/monthly/current",
      );
      return res.data;
    },
    staleTime: 60_000,
  });

  const initialYear = currentMonthly?.year ?? new Date().getFullYear();
  const initialMonth = currentMonthly?.month ?? new Date().getMonth() + 1;

  const defaultFrom = useMemo(
    () => firstDayOfMonth(initialYear, initialMonth),
    [initialYear, initialMonth],
  );
  const defaultTo = useMemo(
    () => lastDayOfMonth(initialYear, initialMonth),
    [initialYear, initialMonth],
  );

  const [fromDate, setFromDate] = useState<string>(defaultFrom);
  const [toDate, setToDate] = useState<string>(defaultTo);

  useEffect(() => {
    // kad bootstrap stigne sa servera, resetujemo na smislen default period (tekući mjesec)
    setFromDate(defaultFrom);
    setToDate(defaultTo);
  }, [defaultFrom, defaultTo]);

  const [includeOutgoing, setIncludeOutgoing] = useState(true);
  const [includeIncoming, setIncludeIncoming] = useState(true);
  const [includeKpr, setIncludeKpr] = useState(true);
  const [includePromet, setIncludePromet] = useState(true);
  const [includeCashBank, setIncludeCashBank] = useState(true);
  const [includeTaxes, setIncludeTaxes] = useState(true);

  const [isDownloading, setIsDownloading] = useState(false);
  const [errorText, setErrorText] = useState<string>("");

  async function handleDownload() {
    setErrorText("");

    if (!fromDate || !toDate) {
      setErrorText("Molim izaberi period (od / do).");
      return;
    }
    if (fromDate > toDate) {
      setErrorText("Neispravan period: datum 'od' ne može biti poslije datuma 'do'.");
      return;
    }

    try {
      setIsDownloading(true);

      await downloadInspectionZip({
        from_date: fromDate,
        to_date: toDate,
        include_outgoing_invoices_pdf: includeOutgoing,
        include_input_invoices_pdf: includeIncoming,
        include_kpr_pdf: includeKpr,
        include_promet_pdf: includePromet,
        include_cash_bank_pdf: includeCashBank,
        include_taxes_pdf: includeTaxes,
      });
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        "Neuspješno preuzimanje ZIP-a.";
      setErrorText(String(msg));
    } finally {
      setIsDownloading(false);
    }
  }

  const isLoading = isLoadingCurrent;
  const isError = isErrorCurrent;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-2">
        <h2 className="text-2xl font-semibold text-slate-900 tracking-tight">
          Izvoz za inspekciju
        </h2>

        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
          <span>
            API: <span className="font-mono">{apiBaseUrl}</span>
          </span>

          {currentMonthly && (
            <span className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1">
              <span className="text-[10px] uppercase tracking-wide text-slate-500">
                Tenant
              </span>
              <span className="font-semibold text-slate-700">
                <span className="font-mono">{currentMonthly.tenant_code}</span>
              </span>
            </span>
          )}
        </div>

        <p className="text-sm text-slate-600">
          Kreira ZIP fajl sa dokumentima za odabrani period (fakture PDF, ulazni računi,
          KPR, knjiga prometa, kasa/banka, porezi i doprinosi).
        </p>
      </div>

      {/* Filters */}
      <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4 space-y-4">
        <div className="grid gap-3 md:grid-cols-3">
          <div>
            <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wide mb-1">
              Period od
            </label>
            <input
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-600 uppercase tracking-wide mb-1">
              Period do
            </label>
            <input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800"
            />
          </div>

          <div className="flex items-end">
            <button
              type="button"
              onClick={handleDownload}
              disabled={isDownloading || isLoading || isError}
              className={
                "w-full rounded-md px-3 py-2 text-sm font-medium border " +
                (isDownloading || isLoading || isError
                  ? "bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed"
                  : "bg-slate-900 text-white border-slate-900 hover:bg-slate-800")
              }
              title={
                isError
                  ? "Ne mogu učitati početne informacije sa servera."
                  : "Kreiraj ZIP i preuzmi."
              }
            >
              {isDownloading ? "Kreiram ZIP..." : "Preuzmi ZIP"}
            </button>
          </div>
        </div>

        {/* Options */}
        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-2">
          <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
            Šta uključiti u ZIP
          </p>

          <div className="grid gap-2 md:grid-cols-2 text-sm text-slate-700">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeOutgoing}
                onChange={(e) => setIncludeOutgoing(e.target.checked)}
              />
              <span>Izlazne fakture (PDF)</span>
            </label>

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeIncoming}
                onChange={(e) => setIncludeIncoming(e.target.checked)}
              />
              <span>Ulazni računi (PDF)</span>
            </label>

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeKpr}
                onChange={(e) => setIncludeKpr(e.target.checked)}
              />
              <span>KPR (PDF)</span>
            </label>

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includePromet}
                onChange={(e) => setIncludePromet(e.target.checked)}
              />
              <span>Knjiga prometa (PDF)</span>
            </label>

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeCashBank}
                onChange={(e) => setIncludeCashBank(e.target.checked)}
              />
              <span>Kasa/Banka izvještaj (PDF)</span>
            </label>

            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeTaxes}
                onChange={(e) => setIncludeTaxes(e.target.checked)}
              />
              <span>Porezi i doprinosi (PDF)</span>
            </label>
          </div>

          <p className="text-[11px] text-slate-500 mt-2">
            Napomena: Ako neki PDF generator još nije implementiran u backendu, backend treba
            vratiti jasnu grešku ili izostaviti taj segment (po dogovoru). Mi ćemo to
            standardizovati kad krenemo na backend implementaciju.
          </p>
        </div>

        {isLoading && (
          <p className="text-sm text-slate-600">Učitavam početne podatke...</p>
        )}

        {isError && (
          <p className="text-sm text-red-600">
            Greška: {errorCurrent?.message ?? "Neuspješno učitavanje."}
          </p>
        )}

        {errorText && <p className="text-sm text-red-600">Greška: {errorText}</p>}
      </div>

      {/* Info */}
      <div className="rounded-xl bg-white shadow-sm border border-slate-200 p-4">
        <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wide">
          Cilj
        </p>
        <p className="text-sm text-slate-700 mt-1">
          Jedan klik → ZIP fajl sa svim relevantnim dokumentima za inspekciju, spremno za slanje/print.
        </p>
      </div>
    </div>
  );
}
