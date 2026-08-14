// /home/miso/dev/sp-app/sp-app/frontend/src/pages/ExportInspectionPage.tsx

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient, getApiBaseUrl } from "../services/apiClient";

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

  const { data: currentMonthly } = useQuery<DashboardMonthlyResponse, Error>({
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

  const fromDate = useMemo(
    () => firstDayOfMonth(initialYear, initialMonth),
    [initialYear, initialMonth],
  );

  const toDate = useMemo(
    () => lastDayOfMonth(initialYear, initialMonth),
    [initialYear, initialMonth],
  );

  const includedCount = 6;

  const exportOptions = [
    {
      title: "Izlazne fakture",
      description: "PDF kopije izlaznih faktura za odabrani period.",
    },
    {
      title: "Ulazni računi",
      description: "PDF dokumentacija ulaznih računa i dobavljača.",
    },
    {
      title: "KPR",
      description: "Knjiga prihoda i rashoda za inspekcijski period.",
    },
    {
      title: "Knjiga prometa",
      description: "KP-1042 / promet evidencija za izabrani period.",
    },
    {
      title: "Kasa / Banka",
      description: "Izvještaj tokova novca, blagajne i računa.",
    },
    {
      title: "Porezi i doprinosi",
      description: "Mjesečni/godišnji TAX/SAM obračuni za period.",
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
                Izvoz za inspekciju još nije dostupan. Stvarni generatori
                dokumenata još nisu implementirani.
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
                PLAN
              </p>
              <p className="mt-1 text-[11px] text-slate-400">
                Izlazne i ulazne fakture.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
              <p className="text-xs text-slate-300">Evidencije</p>
              <p className="mt-2 text-2xl font-semibold text-amber-300">
                PLAN
              </p>
              <p className="mt-1 text-[11px] text-slate-400">
                KPR, promet i kasa/banka.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
              <p className="text-xs text-slate-300">Porezi</p>
              <p className="mt-2 text-2xl font-semibold text-white">
                PLAN
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
              Pregled budućeg opsega dokumenata
            </h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Period dolazi iz tekućeg dashboard mjeseca i prikazan je samo kao
              pregled planirane funkcije.
            </p>
          </div>

          <button
            type="button"
            disabled
            className="cursor-not-allowed rounded-2xl border border-slate-200 bg-slate-100 px-5 py-3 text-sm font-semibold text-slate-400 shadow-sm"
            title="Izvoz za inspekciju još nije dostupan."
          >
            Izvoz nije dostupan
          </button>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2">
          <label className="space-y-1 text-xs font-medium text-slate-500">
            Period od
            <input
              type="date"
              value={fromDate}
              disabled
              readOnly
              className="w-full cursor-not-allowed rounded-2xl border border-slate-200 bg-slate-100 px-3 py-2 text-sm text-slate-500 shadow-sm"
            />
          </label>

          <label className="space-y-1 text-xs font-medium text-slate-500">
            Period do
            <input
              type="date"
              value={toDate}
              disabled
              readOnly
              className="w-full cursor-not-allowed rounded-2xl border border-slate-200 bg-slate-100 px-3 py-2 text-sm text-slate-500 shadow-sm"
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
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              Sadržaj ZIP paketa
            </p>
            <h2 className="mt-1 text-lg font-semibold text-slate-900">
              Planirani segmenti
            </h2>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Segmenti su prikazani kao pregled i trenutno nisu dostupni.
            </p>
          </div>

          <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-700">
            {includedCount}/6 planirano
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {exportOptions.map((option) => (
            <label
              key={option.title}
              className="cursor-not-allowed rounded-3xl border border-slate-200 bg-slate-50 p-4 shadow-sm"
            >
              <div className="flex items-start gap-3">
                <input
                  type="checkbox"
                  checked
                  disabled
                  readOnly
                  className="mt-1"
                />

                <div>
                  <p className="text-sm font-semibold text-slate-700">
                    {option.title}
                  </p>

                  <p className="mt-1 text-xs leading-5 text-slate-500">
                    {option.description}
                  </p>
                </div>
              </div>
            </label>
          ))}
        </div>

        <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-800">
          <span className="font-semibold">Nedostupno:</span> Izvoz za inspekciju
          još nije dostupan. Stvarni generatori dokumenata još nisu implementirani.
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
          Planirana funkcionalnost
        </p>
        <h2 className="mt-1 text-lg font-semibold text-slate-900">
          Budući inspekcijski paket
        </h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          Ova stranica prikazuje planirani period i segmente budućeg paketa.
          Preuzimanje će biti omogućeno tek kada stvarni generatori dokumenata
          budu implementirani.
        </p>
      </section>
    </div>
  );
}