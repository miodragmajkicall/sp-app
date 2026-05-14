// /home/miso/dev/sp-app/sp-app/frontend/src/pages/KprPage.tsx
import { useMemo, useState, type FormEvent } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { fetchKprList, exportKprPdf, exportKprExcel } from "../services/kprApi";
import { createCashEntry } from "../services/cashApi";
import type { CashEntryCreatePayload } from "../services/cashApi";
import type { KprListResponse, KprRowItem } from "../types/kpr";

const CURRENT_YEAR = new Date().getFullYear();
const CURRENT_MONTH = new Date().getMonth() + 1;

type KindFilter = "ALL" | "INCOME" | "EXPENSE";

function formatDate(value?: string | null): string {
  if (!value) return "-";
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleDateString("sr-Latn-BA");
  } catch {
    return value ?? "-";
  }
}

function formatAmount(value?: number | null): string {
  if (value == null) return "-";
  return `${value.toFixed(2)} KM`;
}

function formatKind(kind: string): string {
  if (kind === "income") return "Prihod";
  if (kind === "expense") return "Rashod";
  return kind;
}

function formatCategory(category: string): string {
  switch (category) {
    case "invoice":
      return "Izlazna faktura";
    case "input_invoice":
      return "Ulazna faktura";
    case "cash":
      return "Novac / cash";
    default:
      return category || "-";
  }
}

function formatAccount(row: KprRowItem): string {
  if (row.kind === "income") return "Prihod";
  if (row.kind === "expense") return "Rashod";
  return "Ostalo";
}

function formatReference(row: KprRowItem): string {
  const category = row.category || row.source || "";

  if (category === "invoice") {
    return "Faktura";
  }
  if (category === "input_invoice") {
    return "Ulazni račun";
  }
  if (category === "cash") {
    return "Ručni unos (cash)";
  }
  return "Ostalo";
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function KprPage() {
  const [year, setYear] = useState<number | undefined>(CURRENT_YEAR);
  const [month, setMonth] = useState<number | undefined>(CURRENT_MONTH);
  const [kindFilter, setKindFilter] = useState<KindFilter>("ALL");

  const [isManualModalOpen, setIsManualModalOpen] = useState(false);
  const [manualDate, setManualDate] = useState<string>(todayIso());
  const [manualKind, setManualKind] = useState<"income" | "expense">(
    "expense",
  );
  const [manualAccount, setManualAccount] = useState<"cash" | "bank">(
    "cash",
  );
  const [manualAmount, setManualAmount] = useState<string>("");
  const [manualDescription, setManualDescription] = useState<string>("");
  const [manualError, setManualError] = useState<string>("");

  const queryClient = useQueryClient();

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    isRefetching,
  } = useQuery<KprListResponse, Error>({
    queryKey: ["kpr", { year, month }],
    queryFn: () =>
      fetchKprList({
        year,
        month,
      }),
  });

  const {
    mutateAsync: createManualEntry,
    isPending: isSavingManual,
  } = useMutation({
    mutationFn: async (payload: CashEntryCreatePayload) =>
      createCashEntry(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cash"] });
      queryClient.invalidateQueries({ queryKey: ["kpr"] });
      queryClient.invalidateQueries({
        queryKey: ["dashboard", "monthly", "current"],
      });
    },
  });

  const allItems: KprRowItem[] = data?.items ?? [];

  const filteredItems = useMemo(() => {
    if (kindFilter === "ALL") return allItems;
    if (kindFilter === "INCOME") {
      return allItems.filter((r) => r.kind === "income");
    }
    return allItems.filter((r) => r.kind === "expense");
  }, [allItems, kindFilter]);

  const total = data?.total ?? 0;

  const totals = useMemo(() => {
    let income = 0;
    let expense = 0;

    for (const row of allItems) {
      if (row.kind === "income") {
        income += row.amount ?? 0;
      } else if (row.kind === "expense") {
        expense += row.amount ?? 0;
      }
    }

    return {
      income,
      expense,
      net: income - expense,
    };
  }, [allItems]);

  const handleExportPdf = async () => {
    if (!year || !month) {
      window.alert(
        "Za PDF export trenutno zahtijevamo odabranu godinu i mjesec.",
      );
      return;
    }

    try {
      await exportKprPdf(year, month);
    } catch (err) {
      console.error("Greška pri exportKprPdf:", err);
      const anyErr = err as any;
      const msg =
        anyErr?.response?.data?.detail ||
        anyErr?.message ||
        "Nepoznata greška pri exportu PDF-a.";
      window.alert(msg);
    }
  };

  const handleExportExcel = async () => {
    if (!year || !month) {
      window.alert(
        "Za Excel/CSV export trenutno zahtijevamo odabranu godinu i mjesec.",
      );
      return;
    }

    try {
      await exportKprExcel(year, month);
    } catch (err) {
      console.error("Greška pri exportKprExcel:", err);
      const anyErr = err as any;
      const msg =
        anyErr?.response?.data?.detail ||
        anyErr?.message ||
        "Nepoznata greška pri exportu Excel fajla.";
      window.alert(msg);
    }
  };

  async function handleManualSubmit(e: FormEvent) {
    e.preventDefault();
    setManualError("");

    const parsed = Number(manualAmount);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setManualError("Iznos mora biti veći od nule.");
      return;
    }

    const payload: CashEntryCreatePayload = {
      entry_date: manualDate,
      kind: manualKind,
      amount: parsed,
      note: manualDescription.trim() || null,
      account: manualAccount,
    };

    try {
      await createManualEntry(payload);
      setManualAmount("");
      setManualDescription("");
      await refetch();
      setIsManualModalOpen(false);
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        "Greška pri snimanju unosa.";
      setManualError(String(msg));
    }
  }

  return (
    <div className="relative space-y-6">
      {isManualModalOpen && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/40 px-4 backdrop-blur-sm">
          <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
            <div className="border-b border-slate-100 bg-slate-50 px-5 py-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                    Ručni unos
                  </p>
                  <h3 className="mt-1 text-base font-semibold text-slate-900">
                    Novi KPR unos
                  </h3>
                  <p className="mt-1 text-xs text-slate-500">
                    Za provizije, naknade i druge prihode/rashode koji se ručno
                    evidentiraju kroz cash modul.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => setIsManualModalOpen(false)}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
                >
                  Zatvori
                </button>
              </div>
            </div>

            <form onSubmit={handleManualSubmit} className="space-y-4 p-5">
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="space-y-1 text-xs font-medium text-slate-600">
                  Datum
                  <input
                    type="date"
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                    value={manualDate}
                    onChange={(e) => setManualDate(e.target.value)}
                    required
                  />
                </label>

                <label className="space-y-1 text-xs font-medium text-slate-600">
                  Tip
                  <select
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                    value={manualKind}
                    onChange={(e) =>
                      setManualKind(e.target.value as "income" | "expense")
                    }
                  >
                    <option value="income">Prihod</option>
                    <option value="expense">Rashod</option>
                  </select>
                </label>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="space-y-1 text-xs font-medium text-slate-600">
                  Račun
                  <select
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                    value={manualAccount}
                    onChange={(e) =>
                      setManualAccount(e.target.value as "cash" | "bank")
                    }
                  >
                    <option value="cash">Kasa</option>
                    <option value="bank">Tekući račun</option>
                  </select>
                </label>

                <label className="space-y-1 text-xs font-medium text-slate-600">
                  Iznos KM
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                    value={manualAmount}
                    onChange={(e) => setManualAmount(e.target.value)}
                    required
                  />
                </label>
              </div>

              <label className="space-y-1 text-xs font-medium text-slate-600">
                Opis
                <input
                  type="text"
                  className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
                  value={manualDescription}
                  onChange={(e) => setManualDescription(e.target.value)}
                  placeholder="npr. Bankarska provizija za kartično plaćanje"
                />
              </label>

              {manualError && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                  {manualError}
                </div>
              )}

              <div className="flex items-center justify-end gap-2 border-t border-slate-100 pt-4">
                <button
                  type="button"
                  onClick={() => setIsManualModalOpen(false)}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50"
                >
                  Otkaži
                </button>

                <button
                  type="submit"
                  disabled={isSavingManual}
                  className="rounded-xl bg-slate-950 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSavingManual ? "Spašavam..." : "Snimi unos"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 px-5 py-6 text-white sm:px-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-300">
                Evident · Finansijska evidencija
              </p>

              <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
                Knjiga prihoda i rashoda
              </h1>

              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
                Centralni pregled svih prihodovnih i rashodovnih stavki iz
                izlaznih faktura, ulaznih faktura i ručnih cash unosa za tenant{" "}
                <span className="font-mono text-white">t-demo</span>.
              </p>

              <div className="mt-4 flex flex-wrap items-center gap-2 text-[11px] text-slate-300">
                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1">
                  Ukupno stavki:{" "}
                  <span className="font-semibold text-white">{total}</span>
                </span>

                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1">
                  Godina:{" "}
                  <span className="font-semibold text-white">
                    {year ?? "Sve"}
                  </span>
                </span>

                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1">
                  Mjesec:{" "}
                  <span className="font-semibold text-white">
                    {month ?? "Svi"}
                  </span>
                </span>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setIsManualModalOpen(true)}
                className="rounded-2xl bg-emerald-500 px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-emerald-400"
              >
                + Novi KPR unos
              </button>

              <button
                type="button"
                onClick={() => refetch()}
                disabled={isLoading || isRefetching}
                className="rounded-2xl border border-white/10 bg-white/10 px-4 py-2 text-xs font-semibold text-white backdrop-blur transition hover:bg-white/15 disabled:opacity-60"
              >
                {isLoading || isRefetching
                  ? "Osvježavam..."
                  : "Osvježi podatke"}
              </button>

              <button
                type="button"
                onClick={handleExportPdf}
                className="rounded-2xl border border-white/10 bg-white/10 px-4 py-2 text-xs font-semibold text-white backdrop-blur transition hover:bg-white/15"
              >
                PDF
              </button>

              <button
                type="button"
                onClick={handleExportExcel}
                className="rounded-2xl border border-white/10 bg-white/10 px-4 py-2 text-xs font-semibold text-white backdrop-blur transition hover:bg-white/15"
              >
                Excel
              </button>
            </div>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
              <p className="text-xs text-slate-300">Ukupni prihodi</p>
              <p className="mt-2 text-2xl font-semibold text-emerald-300">
                {formatAmount(totals.income)}
              </p>
              <p className="mt-1 text-[11px] text-slate-400">
                Prihodi iz faktura i ručnih unosa.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
              <p className="text-xs text-slate-300">Ukupni rashodi</p>
              <p className="mt-2 text-2xl font-semibold text-amber-300">
                {formatAmount(totals.expense)}
              </p>
              <p className="mt-1 text-[11px] text-slate-400">
                Rashodi iz ulaznih faktura i ručnih unosa.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
              <p className="text-xs text-slate-300">Neto rezultat</p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {formatAmount(totals.net)}
              </p>
              <p className="mt-1 text-[11px] text-slate-400">
                Prihodi minus rashodi.
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
              <p className="text-xs text-slate-300">Prikazane stavke</p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {filteredItems.length}
              </p>
              <p className="mt-1 text-[11px] text-slate-400">
                Trenutno filtrirane stavke.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              Filteri pregleda
            </p>
            <h2 className="mt-1 text-lg font-semibold text-slate-900">
              Period i vrsta stavke
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Filteri kontrolišu period učitavanja i lokalni prikaz
              prihodovnih/rashodovnih stavki.
            </p>
          </div>

          <button
            type="button"
            onClick={() => {
              setYear(CURRENT_YEAR);
              setMonth(CURRENT_MONTH);
              setKindFilter("ALL");
            }}
            className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 sm:w-auto"
          >
            Reset filtera
          </button>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-3">
          <label className="space-y-1 text-xs font-medium text-slate-600">
            Godina
            <select
              value={year ?? ""}
              onChange={(e) => {
                const v = e.target.value;
                setYear(v === "" ? undefined : Number(v));
              }}
              className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
            >
              <option value="">Sve godine</option>
              <option value={CURRENT_YEAR}>{CURRENT_YEAR}</option>
              <option value={CURRENT_YEAR - 1}>{CURRENT_YEAR - 1}</option>
              <option value={CURRENT_YEAR - 2}>{CURRENT_YEAR - 2}</option>
            </select>
          </label>

          <label className="space-y-1 text-xs font-medium text-slate-600">
            Mjesec
            <select
              value={month ?? ""}
              onChange={(e) => {
                const v = e.target.value;
                setMonth(v === "" ? undefined : Number(v));
              }}
              className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 shadow-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
            >
              <option value="">Svi mjeseci</option>
              <option value={1}>Januar</option>
              <option value={2}>Februar</option>
              <option value={3}>Mart</option>
              <option value={4}>April</option>
              <option value={5}>Maj</option>
              <option value={6}>Jun</option>
              <option value={7}>Jul</option>
              <option value={8}>Avgust</option>
              <option value={9}>Septembar</option>
              <option value={10}>Oktobar</option>
              <option value={11}>Novembar</option>
              <option value={12}>Decembar</option>
            </select>
          </label>

          <div className="space-y-1">
            <p className="text-xs font-medium text-slate-600">Vrsta</p>
            <div className="grid grid-cols-3 gap-1 rounded-2xl border border-slate-200 bg-slate-50 p-1">
              <button
                type="button"
                onClick={() => setKindFilter("ALL")}
                className={[
                  "rounded-xl px-2 py-2 text-xs font-semibold transition",
                  kindFilter === "ALL"
                    ? "bg-white text-slate-950 shadow-sm"
                    : "text-slate-500 hover:text-slate-800",
                ].join(" ")}
              >
                Sve
              </button>

              <button
                type="button"
                onClick={() => setKindFilter("INCOME")}
                className={[
                  "rounded-xl px-2 py-2 text-xs font-semibold transition",
                  kindFilter === "INCOME"
                    ? "bg-white text-emerald-700 shadow-sm"
                    : "text-slate-500 hover:text-slate-800",
                ].join(" ")}
              >
                Prihodi
              </button>

              <button
                type="button"
                onClick={() => setKindFilter("EXPENSE")}
                className={[
                  "rounded-xl px-2 py-2 text-xs font-semibold transition",
                  kindFilter === "EXPENSE"
                    ? "bg-white text-amber-700 shadow-sm"
                    : "text-slate-500 hover:text-slate-800",
                ].join(" ")}
              >
                Rashodi
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-100 bg-slate-50 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
              KPR stavke
            </p>
            <h2 className="mt-1 text-base font-semibold text-slate-900">
              Detaljna evidencija
            </h2>
          </div>

          <p className="text-xs text-slate-500">
            Ukupno:{" "}
            <span className="font-semibold text-slate-800">{total}</span> ·
            Prikazano:{" "}
            <span className="font-semibold text-slate-800">
              {filteredItems.length}
            </span>
          </p>
        </div>

        {isLoading && (
          <div className="p-8 text-center">
            <p className="text-sm font-medium text-slate-700">
              Učitavam KPR stavke...
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Podaci se učitavaju iz evidencije faktura i cash unosa.
            </p>
          </div>
        )}

        {isError && (
          <div className="m-5 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Greška pri učitavanju KPR podataka:{" "}
            {error?.message ?? "Nepoznata greška"}
          </div>
        )}

        {!isLoading && !isError && total === 0 && (
          <div className="p-10 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-xl">
              📘
            </div>
            <h3 className="mt-4 text-base font-semibold text-slate-900">
              Nema KPR stavki za odabrani period
            </h3>
            <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
              Kada se kreiraju izlazne fakture, ulazne fakture ili ručni cash
              unosi, ovdje će se pojaviti evidencija prihoda i rashoda.
            </p>
          </div>
        )}

        {!isLoading && !isError && total > 0 && filteredItems.length === 0 && (
          <div className="p-8 text-center">
            <h3 className="text-base font-semibold text-slate-900">
              Nema stavki za odabrani filter
            </h3>
            <p className="mt-2 text-sm text-slate-500">
              Promijeni filter vrste ili resetuj filtere da vidiš sve stavke.
            </p>
          </div>
        )}

        {!isLoading && !isError && filteredItems.length > 0 && (
          <div className="max-h-[560px] overflow-auto">
            <table className="min-w-full text-xs">
              <thead className="sticky top-0 z-10 bg-white text-slate-500 shadow-sm">
                <tr className="border-b border-slate-100">
                  <th className="whitespace-nowrap px-4 py-3 text-left font-semibold">
                    Datum
                  </th>
                  <th className="px-4 py-3 text-left font-semibold">Vrsta</th>
                  <th className="px-4 py-3 text-left font-semibold">Konto</th>
                  <th className="px-4 py-3 text-left font-semibold">
                    Kategorija
                  </th>
                  <th className="px-4 py-3 text-left font-semibold">
                    Referenca
                  </th>
                  <th className="px-4 py-3 text-left font-semibold">
                    Kupac / dobavljač
                  </th>
                  <th className="px-4 py-3 text-left font-semibold">
                    Dok. broj
                  </th>
                  <th className="px-4 py-3 text-left font-semibold">Opis</th>
                  <th className="px-4 py-3 text-right font-semibold">Iznos</th>
                  <th className="whitespace-nowrap px-4 py-3 text-center font-semibold">
                    Poreski priznat
                  </th>
                </tr>
              </thead>

              <tbody className="divide-y divide-slate-100 text-slate-700">
                {filteredItems.map((row) => (
                  <tr
                    key={`${row.source}-${row.source_id}-${row.date}`}
                    className="transition hover:bg-slate-50"
                  >
                    <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-900">
                      {formatDate(row.date)}
                    </td>

                    <td className="whitespace-nowrap px-4 py-3">
                      <span
                        className={[
                          "inline-flex rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide",
                          row.kind === "income"
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-amber-50 text-amber-700",
                        ].join(" ")}
                      >
                        {formatKind(row.kind)}
                      </span>
                    </td>

                    <td className="whitespace-nowrap px-4 py-3 text-[11px]">
                      {formatAccount(row)}
                    </td>

                    <td className="whitespace-nowrap px-4 py-3 text-[11px]">
                      {formatCategory(row.category)}
                    </td>

                    <td className="whitespace-nowrap px-4 py-3 text-[11px]">
                      {formatReference(row)}
                    </td>

                    <td className="px-4 py-3 text-[11px]">
                      {row.counterparty ?? (
                        <span className="text-slate-400">-</span>
                      )}
                    </td>

                    <td className="px-4 py-3 font-mono text-[11px]">
                      {row.document_number ?? (
                        <span className="text-slate-400">-</span>
                      )}
                    </td>

                    <td className="max-w-[280px] px-4 py-3 text-[11px]">
                      {row.description ?? (
                        <span className="text-slate-400">-</span>
                      )}
                    </td>

                    <td className="whitespace-nowrap px-4 py-3 text-right font-semibold text-slate-900">
                      {formatAmount(row.amount)}
                    </td>

                    <td className="px-4 py-3 text-center">
                      {row.tax_deductible ? (
                        <span className="inline-flex rounded-full bg-emerald-50 px-2.5 py-1 text-[10px] font-bold text-emerald-700">
                          DA
                        </span>
                      ) : (
                        <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-500">
                          NE
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}