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
  const d = new Date(year, month, 0);
  return toIsoDate(d);
}

function formatDateLabel(value: string): string {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("sr-Latn-BA");
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

  const includedCount = [
    includeOutgoing,
    includeIncoming,
    includeKpr,
    includePromet,
    includeCashBank,
    includeTaxes,
  ].filter(Boolean).length;

  const isLoading = isLoadingCurrent;
  const isError = isErrorCurrent;

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

    if (includedCount === 0) {
      setErrorText("Mora biti izabran barem jedan segment za ZIP export.");
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

  const exportOptions = [
    {
      title: "Izlazne fakture",
      description: "PDF kopije izlaznih faktura za odabrani period.",
      checked: includeOutgoing,
      setChecked: setIncludeOutgoing,
    },
    {
      title: "Ulazni računi",
      description: "PDF dokumentacija ulaznih računa i dobavljača.",
      checked: includeIncoming,
      setChecked: setIncludeIncoming,
    },
    {
      title: "KPR",
      description: "Knjiga prihoda i rashoda za inspekcijski period.",
      checked: includeKpr,
      setChecked: setIncludeKpr,
    },
    {
      title: "Knjiga prometa",
      description: "KP-1042 / promet evidencija za izabrani period.",
      checked: includePromet,
      setChecked: setIncludePromet,
    },
    {
      title: "Kasa / Banka",
      description: "Izvještaj tokova novca, blagajne i računa.",
      checked: includeCashBank,
      setChecked: setIncludeCashBank,
    },
    {
      title: "Porezi i doprinosi",
      description: "Mjesečni/godišnji TAX/SAM obračuni za period.",
      checked: includeTaxes,
      setChecked: setIncludeTaxes,
    },
  ];

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 px-5 py-6 text-white sm:px-6">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
            <div className="max-w-3xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-300">
                Evident · inspekcijski paket
              </p>

              <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
                Izvoz za inspekciju
              </h1>

              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
                Kreiranje ZIP paketa sa relevantnim dokumentima za odabrani
                period: fakture, ulazni računi, KPR, knjiga prometa, kasa/banka
                i poreski obračuni.
              </p>

              <div className="mt-4 flex flex-wrap items-center gap-2 text-[11px] text-slate-300">
                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1">
                  API: <span className="font-mono text-white">{apiBaseUrl}</span>
                </span>

                {currentMonthly && (
                  <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1">
                    Tenant:{" "}
                    <span className="font-mono font-semibold text-white">
                      {currentMonthly.tenant_code}
                    </span>
                  </span>
                )}

                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1">
                  Segmenti:{" "}
                  <span className="font-semibold text-white">{includedCount}/6</span>
                </span>
              </div>
            </div>

            <div className="grid gap-2 sm:grid-cols-2 xl:min-w-[420px]">
              <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
                <p className="text-xs text-slate-300">Period od</p>
                <p className="mt-1 text-lg font-semibold text-white">
                  {formatDateLabel(fromDate)}
                </p>
                <p className="mt-1 text-[11px] text-slate-400">
                  Početak inspekcijskog perioda.
                </p>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
                <p className="text-xs text-slate-300">Period do</p>
                <p className="mt-1 text-lg font-semibold text-white">
                  {formatDateLabel(toDate)}
                </p>
                <p className="mt-1 text-[11px] text-slate-400">
                  Kraj inspekcijskog perioda.
                </p>
              </div>
            </div>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
              <p className="text-xs text-slate-300">ZIP paket</p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {includedCount} seg.
              </p>
              <p className="mt-1 text-[11px] text-slate-400">
                Broj uključenih izvještaja.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
              <p className="text-xs text-slate-300">Fakture</p>
              <p className="mt-2 text-2xl font-semibold text-emerald-300">
                {includeOutgoing || includeIncoming ? "DA" : "NE"}
              </p>
              <p className="mt-1 text-[11px] text-slate-400">
                Izlazne i ulazne fakture.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
              <p className="text-xs text-slate-300">Evidencije</p>
              <p className="mt-2 text-2xl font-semibold text-amber-300">
                {includeKpr || includePromet || includeCashBank ? "DA" : "NE"}
              </p>
              <p className="mt-1 text-[11px] text-slate-400">
                KPR, promet i kasa/banka.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
              <p className="text-xs text-slate-300">Porezi</p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {includeTaxes ? "DA" : "NE"}
              </p>
              <p className="mt-1 text-[11px] text-slate-400">
                TAX/SAM obračuni.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              Period exporta
            </p>
            <h2 className="mt-1 text-lg font-semibold text-slate-900">
              Odaberi opseg dokumenata
            </h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              ZIP se kreira za dokumente i evidencije u odabranom periodu. Default
              period dolazi iz tekućeg dashboard mjeseca.
            </p>
          </div>

          <button
            type="button"
            onClick={handleDownload}
            disabled={isDownloading || isLoading || isError}
            className={
              "rounded-2xl px-5 py-3 text-sm font-semibold shadow-sm transition " +
              (isDownloading || isLoading || isError
                ? "cursor-not-allowed border border-slate-200 bg-slate-100 text-slate-400"
                : "bg-slate-950 text-white hover:bg-slate-800")
            }
            title={
              isError
                ? "Ne mogu učitati početne informacije sa servera."
                : "Kreiraj ZIP i preuzmi."
            }
          >
            {isDownloading ? "Kreiram ZIP..." : "Preuzmi ZIP paket"}
          </button>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2">
          <label className="space-y-1 text-xs font-medium text-slate-600">
            Period od
            <input
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
            />
          </label>

          <label className="space-y-1 text-xs font-medium text-slate-600">
            Period do
            <input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
            />
          </label>
        </div>

        <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-600">
          Pregled:{" "}
          <span className="font-semibold text-slate-900">
            {formatDateLabel(fromDate)} — {formatDateLabel(toDate)}
          </span>{" "}
          · Uključeno:{" "}
          <span className="font-semibold text-slate-900">
            {includedCount} od 6 segmenata
          </span>
        </div>

        {isLoading && (
          <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
            Učitavam početne podatke...
          </div>
        )}

        {isError && (
          <div className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            Greška: {errorCurrent?.message ?? "Neuspješno učitavanje."}
          </div>
        )}

        {errorText && (
          <div className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            Greška: {errorText}
          </div>
        )}
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              Sadržaj ZIP paketa
            </p>
            <h2 className="mt-1 text-lg font-semibold text-slate-900">
              Šta uključiti u export
            </h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Izaberi segmente koje želiš uključiti u inspekcijski paket.
            </p>
          </div>

          <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-700">
            {includedCount}/6 aktivno
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {exportOptions.map((option) => (
            <label
              key={option.title}
              className={
                "cursor-pointer rounded-3xl border p-4 shadow-sm transition " +
                (option.checked
                  ? "border-emerald-200 bg-emerald-50"
                  : "border-slate-200 bg-white hover:bg-slate-50")
              }
            >
              <div className="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked={option.checked}
                  onChange={(e) => option.setChecked(e.target.checked)}
                  className="mt-1"
                />

                <div>
                  <p
                    className={
                      "text-sm font-semibold " +
                      (option.checked ? "text-emerald-900" : "text-slate-900")
                    }
                  >
                    {option.title}
                  </p>

                  <p
                    className={
                      "mt-1 text-xs leading-5 " +
                      (option.checked ? "text-emerald-700" : "text-slate-500")
                    }
                  >
                    {option.description}
                  </p>
                </div>
              </div>
            </label>
          ))}
        </div>

        <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-800">
          <span className="font-semibold">Napomena:</span> Ako neki PDF generator
          još nije implementiran u backendu, backend treba vratiti jasnu grešku
          ili izostaviti taj segment. To ćemo standardizovati u backend export
          sprintu.
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
          Cilj modula
        </p>
        <h2 className="mt-1 text-lg font-semibold text-slate-900">
          Jedan klik do inspekcijskog paketa
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          Ova stranica treba da omogući korisniku da brzo pripremi kompletan
          paket dokumenata za kontrolu, slanje, arhivu ili print. Trenutni UI je
          spreman za produkcijski tok, dok ćemo backend export engine širiti po
          segmentima.
        </p>
      </section>
    </div>
  );
}