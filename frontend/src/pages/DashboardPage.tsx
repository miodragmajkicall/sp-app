// /home/miso/dev/sp-app/sp-app/frontend/src/pages/DashboardPage.tsx
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Building2,
  CheckCircle2,
  FilePlus2,
  Inbox,
  Landmark,
  Receipt,
  Settings,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
  Wallet,
} from "lucide-react";

import { apiClient } from "../services/apiClient";
import { fetchInvoicesList } from "../services/invoicesApi";
import { fetchInputInvoicesList } from "../services/inputInvoicesApi";
import {
  getProfileSettings,
  getTaxProfileSettings,
  getTaxProfileUiSchema,
} from "../services/settingsApi";
import type {
  ProfileSettingsRead,
  TaxProfileSettingsRead,
  TaxProfileUiSchemaResponse,
  UiResolvedValue,
} from "../types/settings";

interface MonthlyCashSummary {
  year: number;
  month: number;
  income_total?: number | string;
  expense_total?: number | string;
  net_cashflow?: number | string;
}

interface MonthlyInvoicesSummary {
  year: number;
  month: number;
  invoices_count?: number;
  total_amount?: number | string;
}

interface MonthlyTaxSummary {
  year: number;
  month: number;
  has_result: boolean;
  is_final: boolean;
  total_due?: number | string;
}

interface MonthlySamSummary {
  year: number;
  month: number;
  total_due?: number | string;
  has_result: boolean;
  is_final: boolean;
}

interface DashboardMonthlyResponse {
  tenant_code: string;
  year: number;
  month: number;
  cash?: MonthlyCashSummary;
  invoices?: MonthlyInvoicesSummary;
  tax?: MonthlyTaxSummary;
  sam?: MonthlySamSummary;
}

type MessageType = "warning" | "info" | "success";

function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

function toNumber(value: number | string | undefined | null): number {
  if (value === undefined || value === null) return 0;
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  const parsed = Number(String(value).replace(",", ".").replace(/[^\d.-]/g, ""));
  return Number.isNaN(parsed) ? 0 : parsed;
}

function formatAmount(value: number): string {
  return value.toLocaleString("sr-Latn-BA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatCompactAmount(value: number): string {
  return value.toLocaleString("sr-Latn-BA", {
    maximumFractionDigits: 0,
  });
}

function computePreviousYearMonth(
  year: number,
  month: number,
): { year: number; month: number } {
  if (month === 1) return { year: year - 1, month: 12 };
  return { year, month: month - 1 };
}

function getShortMonthLabel(month: number): string {
  const d = new Date(2025, month - 1, 1);
  return d.toLocaleDateString("sr-Latn-BA", { month: "short" });
}

function getEntityLabel(entity?: string | null): string {
  if (entity === "RS") return "Republika Srpska";
  if (entity === "FBiH") return "Federacija BiH";
  if (entity === "Brcko") return "Brčko distrikt";
  return "Nije podešeno";
}

function getScenarioLabel(scenarioKey?: string | null): string {
  const map: Record<string, string> = {
    rs_primary: "RS – Osnovna djelatnost",
    rs_supplementary: "RS – Dopunska djelatnost",
    fbih_obrt: "FBiH – Obrt",
    fbih_slobodna: "FBiH – Slobodna djelatnost",
    bd_samostalna: "Brčko – Samostalna djelatnost",
  };

  if (!scenarioKey) return "Scenario nije podešen";
  return map[scenarioKey] ?? scenarioKey;
}

function readResolvedNumber(
  values: UiResolvedValue[] | undefined,
  options: {
    keyIncludes?: string[];
    labelIncludes?: string[];
    section?: UiResolvedValue["section"];
  },
): number | null {
  const items = values ?? [];

  const found = items.find((item) => {
    const key = item.key.toLowerCase();
    const label = item.label.toLowerCase();

    if (options.section && item.section !== options.section) return false;

    const keyOk =
      !options.keyIncludes ||
      options.keyIncludes.some((part) => key.includes(part.toLowerCase()));

    const labelOk =
      !options.labelIncludes ||
      options.labelIncludes.some((part) => label.includes(part.toLowerCase()));

    return keyOk && labelOk;
  });

  if (!found) return null;

  const parsed = toNumber(found.value ?? null);
  return Number.isFinite(parsed) ? parsed : null;
}

function readResolvedPercent(
  values: UiResolvedValue[] | undefined,
  options: {
    keyIncludes?: string[];
    labelIncludes?: string[];
    section?: UiResolvedValue["section"];
  },
): number | null {
  const n = readResolvedNumber(values, options);
  if (n == null) return null;

  if (n > 1) return n / 100;
  return n;
}

function computeResolvedContributionsPlan(
  schema: TaxProfileUiSchemaResponse | undefined,
): number | null {
  const values = schema?.resolved_values ?? [];
  if (values.length === 0) return null;

  const explicitBase =
    readResolvedNumber(values, {
      section: "base",
      keyIncludes: ["calculated_contrib_base", "monthly_contrib_base"],
    }) ??
    readResolvedNumber(values, {
      section: "base",
      labelIncludes: ["osnovica"],
    });

  const avgGross =
    readResolvedNumber(values, {
      section: "base",
      keyIncludes: ["avg_gross"],
    }) ??
    readResolvedNumber(values, {
      section: "base",
      labelIncludes: ["prosječna bruto plata", "prosječna bruto"],
    });

  const basePercent =
    readResolvedPercent(values, {
      section: "base",
      keyIncludes: ["percent"],
    }) ??
    readResolvedPercent(values, {
      section: "base",
      labelIncludes: ["% prosječne", "procenat", "postotak"],
    });

  const base =
    explicitBase != null
      ? explicitBase
      : avgGross != null && basePercent != null
        ? avgGross * basePercent
        : null;

  if (base == null || base <= 0) return null;

  const pensionRate =
    readResolvedPercent(values, {
      section: "contributions",
      keyIncludes: ["pension"],
    }) ??
    readResolvedPercent(values, {
      section: "contributions",
      labelIncludes: ["pio", "penzion"],
    }) ??
    0;

  const healthRate =
    readResolvedPercent(values, {
      section: "contributions",
      keyIncludes: ["health"],
    }) ??
    readResolvedPercent(values, {
      section: "contributions",
      labelIncludes: ["zdrav"],
    }) ??
    0;

  const unemploymentRate =
    readResolvedPercent(values, {
      section: "contributions",
      keyIncludes: ["unemployment"],
    }) ??
    readResolvedPercent(values, {
      section: "contributions",
      labelIncludes: ["nezaposlen"],
    }) ??
    0;

  const totalRate = pensionRate + healthRate + unemploymentRate;
  if (totalRate <= 0) return null;

  return base * totalRate;
}

function readResolvedMonthlyTax(
  schema: TaxProfileUiSchemaResponse | undefined,
): number | null {
  const values = schema?.resolved_values ?? [];
  if (values.length === 0) return null;

  return (
    readResolvedNumber(values, {
      section: "tax",
      keyIncludes: ["flat_tax_monthly"],
    }) ??
    readResolvedNumber(values, {
      section: "tax",
      labelIncludes: ["paušalni porez", "mjesečno"],
    })
  );
}

function buildAiComment(
  current: DashboardMonthlyResponse | undefined,
  previous: DashboardMonthlyResponse | undefined,
): string | null {
  if (!current) return null;

  const curIncome = toNumber(current.cash?.income_total);
  const curExpense = toNumber(current.cash?.expense_total);
  const curNet = toNumber(current.cash?.net_cashflow);

  if (!previous) {
    if (curIncome === 0 && curExpense === 0) {
      return "Nema još dovoljno prometa za analizu ovog mjeseca. Kako se gomilaju prihodi i troškovi, ovdje ćeš dobijati kratak sažetak kretanja.";
    }
    if (curNet >= 0) {
      return `Ovaj mjesec si u plusu ${formatAmount(
        curNet,
      )} KM. Prati da li se ovaj trend zadrži i u narednim mjesecima.`;
    }
    return `Ovaj mjesec si u minusu ${formatAmount(
      Math.abs(curNet),
    )} KM. Provjeri najveće troškove i razmisli šta možeš optimizovati.`;
  }

  const prevIncome = toNumber(previous.cash?.income_total);
  const prevExpense = toNumber(previous.cash?.expense_total);
  const prevNet = toNumber(previous.cash?.net_cashflow);

  const incomeDelta = curIncome - prevIncome;
  const expenseDelta = curExpense - prevExpense;
  const netDelta = curNet - prevNet;

  const incomePct =
    prevIncome !== 0 ? (incomeDelta / Math.abs(prevIncome)) * 100 : null;
  const expensePct =
    prevExpense !== 0 ? (expenseDelta / Math.abs(prevExpense)) * 100 : null;

  const incomePart =
    incomePct === null
      ? null
      : incomePct > 5
        ? `Prihodi su veći za oko ${incomePct.toFixed(1)}% u odnosu na prošli mjesec.`
        : incomePct < -5
          ? `Prihodi su manji za oko ${Math.abs(incomePct).toFixed(1)}% u odnosu na prošli mjesec.`
          : "Prihodi su na sličnom nivou kao prošli mjesec.";

  const expensePart =
    expensePct === null
      ? null
      : expensePct > 5
        ? `Troškovi su veći za oko ${expensePct.toFixed(1)}% u odnosu na prošli mjesec.`
        : expensePct < -5
          ? `Troškovi su manji za oko ${Math.abs(expensePct).toFixed(1)}% u odnosu na prošli mjesec.`
          : "Troškovi su na sličnom nivou kao prošli mjesec.";

  let netPart: string;
  if (curNet > 0 && netDelta >= 0) {
    netPart = `Neto rezultat je pozitivan (${formatAmount(
      curNet,
    )} KM) i bolji je nego prošli mjesec.`;
  } else if (curNet > 0 && netDelta < 0) {
    netPart = `Neto rezultat je i dalje pozitivan (${formatAmount(
      curNet,
    )} KM), ali je slabiji nego prošli mjesec.`;
  } else if (curNet <= 0 && netDelta >= 0) {
    netPart = `Ovaj mjesec si blizu nule ili u manjim gubicima (${formatAmount(
      curNet,
    )} KM), ali je bolje nego prošli mjesec.`;
  } else {
    netPart = `Neto rezultat je negativan (${formatAmount(
      curNet,
    )} KM) i lošiji je nego prošli mjesec.`;
  }

  const parts = [incomePart, expensePart, netPart].filter(
    (p): p is string => p !== null,
  );

  return parts.length > 0 ? parts.join(" ") : null;
}

function Card({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "rounded-2xl border border-slate-200 bg-white shadow-sm",
        className,
      )}
    >
      {children}
    </div>
  );
}

function SectionTitle({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          {title}
        </p>
        {subtitle && <p className="mt-1 text-xs text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

function KpiCard({
  title,
  value,
  subtitle,
  icon,
  tone,
}: {
  title: string;
  value: string;
  subtitle: string;
  icon: ReactNode;
  tone: "emerald" | "rose" | "sky" | "slate" | "amber";
}) {
  const toneClasses = {
    emerald: "bg-emerald-50 text-emerald-700 ring-emerald-100",
    rose: "bg-rose-50 text-rose-700 ring-rose-100",
    sky: "bg-sky-50 text-sky-700 ring-sky-100",
    slate: "bg-slate-100 text-slate-700 ring-slate-200",
    amber: "bg-amber-50 text-amber-700 ring-amber-100",
  };

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-500">{title}</p>
          <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
            {value}
          </p>
          <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
        </div>

        <div
          className={cx(
            "grid h-10 w-10 shrink-0 place-items-center rounded-xl ring-1",
            toneClasses[tone],
          )}
        >
          {icon}
        </div>
      </div>
    </Card>
  );
}

function QuickActionButton({
  label,
  description,
  icon,
  onClick,
  primary,
}: {
  label: string;
  description: string;
  icon: ReactNode;
  onClick: () => void;
  primary?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cx(
        "group flex min-h-[76px] items-center justify-between gap-3 rounded-2xl border px-4 py-3 text-left shadow-sm transition",
        primary
          ? "border-slate-900 bg-slate-950 text-white hover:bg-slate-800"
          : "border-slate-200 bg-white text-slate-900 hover:border-slate-300 hover:bg-slate-50",
      )}
    >
      <div className="flex min-w-0 items-center gap-3">
        <div
          className={cx(
            "grid h-10 w-10 shrink-0 place-items-center rounded-xl",
            primary ? "bg-white/10 text-white" : "bg-slate-100 text-slate-700",
          )}
        >
          {icon}
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold">{label}</p>
          <p
            className={cx(
              "mt-0.5 text-xs",
              primary ? "text-slate-300" : "text-slate-500",
            )}
          >
            {description}
          </p>
        </div>
      </div>

      <ArrowRight
        className={cx(
          "h-4 w-4 shrink-0 transition group-hover:translate-x-0.5",
          primary ? "text-white" : "text-slate-400",
        )}
      />
    </button>
  );
}

export default function DashboardPage() {
  const navigate = useNavigate();

  const profileQuery = useQuery<ProfileSettingsRead, Error>({
    queryKey: ["settings", "profile"],
    queryFn: getProfileSettings,
    staleTime: 60_000,
  });

  const taxProfileQuery = useQuery<TaxProfileSettingsRead, Error>({
    queryKey: ["settings", "tax"],
    queryFn: getTaxProfileSettings,
    staleTime: 60_000,
  });

  const taxUiSchemaQuery = useQuery<TaxProfileUiSchemaResponse, Error>({
    queryKey: ["settings", "tax", "ui-schema"],
    queryFn: () => getTaxProfileUiSchema(),
    staleTime: 60_000,
  });

  const manualPension = taxProfileQuery.data?.monthly_pension ?? null;
  const manualHealth = taxProfileQuery.data?.monthly_health ?? null;
  const manualUnemployment = taxProfileQuery.data?.monthly_unemployment ?? null;

  const hasAnyManualContrib =
    manualPension != null || manualHealth != null || manualUnemployment != null;

  const manualContributionsPlan = hasAnyManualContrib
    ? toNumber(manualPension) +
      toNumber(manualHealth) +
      toNumber(manualUnemployment)
    : null;

  const resolvedContributionsPlan = computeResolvedContributionsPlan(
    taxUiSchemaQuery.data,
  );

  const contributionsPlan =
    resolvedContributionsPlan ?? manualContributionsPlan ?? null;

  const resolvedMonthlyTax = readResolvedMonthlyTax(taxUiSchemaQuery.data);

  const hasResolvedTaxProfile =
    Boolean(taxUiSchemaQuery.data?.constants_set_id) ||
    (taxUiSchemaQuery.data?.resolved_values?.length ?? 0) > 0;

  const { data, isLoading, isError, error } = useQuery<
    DashboardMonthlyResponse,
    Error
  >({
    queryKey: ["dashboard", "monthly", "current"],
    queryFn: async () => {
      const res = await apiClient.get<DashboardMonthlyResponse>(
        "/dashboard/monthly/current",
      );
      return res.data;
    },
  });

  const { data: previousMonthlyData } = useQuery<
    DashboardMonthlyResponse,
    Error
  >({
    queryKey: ["dashboard", "monthly", "previous", data?.year, data?.month],
    enabled: !!data,
    queryFn: async () => {
      if (!data) throw new Error("Missing current month data");
      const { year, month } = computePreviousYearMonth(data.year, data.month);
      const res = await apiClient.get<DashboardMonthlyResponse>(
        `/dashboard/monthly/${year}/${month}`,
      );
      return res.data;
    },
    staleTime: 60_000,
  });

  const { data: invoicesListData } = useQuery({
    queryKey: ["dashboard", "invoices", "recent"],
    queryFn: () => fetchInvoicesList(),
    staleTime: 60_000,
  });

  const { data: inputInvoicesListData } = useQuery({
    queryKey: [
      "dashboard",
      "input-invoices",
      "current-month",
      data?.year,
      data?.month,
    ],
    enabled: !!data,
    queryFn: async () => {
      if (!data) throw new Error("Missing dashboard data");
      return fetchInputInvoicesList({
        year: data.year,
        month: data.month,
        limit: 200,
        offset: 0,
      });
    },
    staleTime: 60_000,
  });

  const { data: yearlyCashByMonth } = useQuery<
    (DashboardMonthlyResponse | null)[]
  >({
    queryKey: ["dashboard", "cash", "yearly-by-month", data?.year],
    enabled: !!data,
    queryFn: async () => {
      if (!data) throw new Error("Missing dashboard data");
      const year = data.year;
      const months = Array.from({ length: 12 }, (_, idx) => idx + 1);
      const results = await Promise.all(
        months.map((m) =>
          apiClient
            .get<DashboardMonthlyResponse>(`/dashboard/monthly/${year}/${m}`)
            .then((res) => res.data)
            .catch(() => null),
        ),
      );
      return results;
    },
    staleTime: 60_000,
  });

  const monthLabel = (() => {
    if (!data) return "";
    const d = new Date(data.year, data.month - 1, 1);
    if (Number.isNaN(d.getTime())) return `${data.year}-${data.month}`;
    return d.toLocaleDateString("sr-Latn-BA", {
      month: "long",
      year: "numeric",
    });
  })();

  const businessName = (profileQuery.data?.business_name ?? "").trim();
  const displayBusinessName = businessName || "Vaša firma";
  const entityLabel = getEntityLabel(taxProfileQuery.data?.entity);
  const scenarioLabel = getScenarioLabel(taxProfileQuery.data?.scenario_key);

    const rawCashIncome = toNumber(data?.cash?.income_total);
  const rawCashExpense = toNumber(data?.cash?.expense_total);
  const rawCashNet = toNumber(data?.cash?.net_cashflow);

  const invoicesCount = data?.invoices?.invoices_count ?? 0;
  const invoicesTotal = toNumber(data?.invoices?.total_amount);

  const inputInvoicesCount = inputInvoicesListData?.items?.length ?? 0;
  const inputInvoicesTotal =
    inputInvoicesListData?.items?.reduce((acc: number, inv: any) => {
      return acc + toNumber(inv?.total_amount);
    }, 0) ?? 0;

  const hasInvoiceFallbackData = invoicesTotal > 0 || inputInvoicesTotal > 0;

  const cashIncome =
    rawCashIncome > 0 || !hasInvoiceFallbackData ? rawCashIncome : invoicesTotal;

  const cashExpense =
    rawCashExpense > 0 || !hasInvoiceFallbackData
      ? rawCashExpense
      : inputInvoicesTotal;

  const cashNet =
    rawCashIncome > 0 || rawCashExpense > 0 || !hasInvoiceFallbackData
      ? rawCashNet
      : invoicesTotal - inputInvoicesTotal;

  const taxDue = toNumber(data?.tax?.total_due);
  const samDue = toNumber(data?.sam?.total_due);

  const totalTaxPlan =
    taxDue ||
    samDue ||
    contributionsPlan != null ||
    resolvedMonthlyTax != null
      ? taxDue + samDue + toNumber(contributionsPlan) + toNumber(resolvedMonthlyTax)
      : null;

  const netClass =
    cashNet > 0
      ? "text-emerald-600"
      : cashNet < 0
        ? "text-rose-600"
        : "text-slate-700";

  const lastOutgoingInvoices = invoicesListData?.items.slice(0, 5) ?? [];
  const lastInputInvoices = inputInvoicesListData?.items.slice(0, 5) ?? [];

  const overdueUnpaidCount =
    invoicesListData?.items.filter((inv: any) => {
      if (!inv.due_date) return false;
      if (inv.is_paid) return false;
      const due = new Date(inv.due_date);
      if (Number.isNaN(due.getTime())) return false;
      const today = new Date();
      const diffDays = (today.getTime() - due.getTime()) / (1000 * 60 * 60 * 24);
      return diffDays > 30;
    }).length ?? 0;

  const incomeSeries =
    yearlyCashByMonth?.map((m, idx) => {
      const month = idx + 1;
      const income = m ? toNumber(m.cash?.income_total) : 0;
      return {
        month,
        label: getShortMonthLabel(month),
        value: income,
      };
    }) ?? [];

  const maxIncomeValue = Math.max(
    ...incomeSeries.map((i) => Math.abs(i.value)),
    0,
  );

  const expenseBySupplierMap = new Map<string, number>();
  if (inputInvoicesListData) {
    for (const inv of inputInvoicesListData.items) {
      const name = inv.supplier_name || "Ostalo";
      const amount = toNumber(inv.total_amount);
      expenseBySupplierMap.set(name, (expenseBySupplierMap.get(name) ?? 0) + amount);
    }
  }

  const expenseSuppliers = Array.from(expenseBySupplierMap.entries())
    .map(([name, total]) => ({ name, total }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 6);

  const maxExpenseSupplier = Math.max(
    ...expenseSuppliers.map((c) => Math.abs(c.total)),
    0,
  );

  const topCustomers = (() => {
    const map = new Map<string, number>();
    if (invoicesListData) {
      for (const inv of invoicesListData.items) {
        const name = inv.buyer_name || "Nepoznat kupac";
        const amount = toNumber(inv.total_amount);
        map.set(name, (map.get(name) ?? 0) + amount);
      }
    }
    return Array.from(map.entries())
      .map(([name, total]) => ({ name, total }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 5);
  })();

  const topSuppliers = (() => {
    const map = new Map<string, number>();
    if (inputInvoicesListData) {
      for (const inv of inputInvoicesListData.items) {
        const name = inv.supplier_name || "Nepoznat dobavljač";
        const amount = toNumber(inv.total_amount);
        map.set(name, (map.get(name) ?? 0) + amount);
      }
    }
    return Array.from(map.entries())
      .map(([name, total]) => ({ name, total }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 5);
  })();

  const messages: { type: MessageType; text: string }[] = [];

  if (cashNet < 0) {
    messages.push({
      type: "warning",
      text: "Neto kretanje gotovine za trenutni mjesec je negativno – rashodi su veći od prihoda.",
    });
  }

  if (overdueUnpaidCount > 0) {
    messages.push({
      type: "warning",
      text: `Imaš ${overdueUnpaidCount} neplaćenih izlaznih faktura sa rokom dospijeća starijim od 30 dana.`,
    });
  }

  if (hasResolvedTaxProfile) {
    messages.push({
      type: "success",
      text: `Poreski profil je povezan sa Admin Constants setom${
        taxUiSchemaQuery.data?.constants_set_id
          ? ` #${taxUiSchemaQuery.data.constants_set_id}`
          : ""
      }: ${scenarioLabel}. ${
        contributionsPlan != null
          ? `Procijenjeni mjesečni doprinosi: ${formatAmount(contributionsPlan)} KM.`
          : "Sistem koristi aktivne obračunske parametre iz podešenog scenarija."
      }`,
    });
  } else if (taxProfileQuery.data?.scenario_key) {
    messages.push({
      type: "info",
      text: `Poreski scenario je izabran (${scenarioLabel}), ali za njega trenutno nisu pronađene resolved vrijednosti iz Admin Constants. Provjeri da li postoji aktivan set konstanti za današnji datum.`,
    });
  } else {
    messages.push({
      type: "warning",
      text: "Poreski profil nije kompletiran. Otvori Postavke i izaberi entitet i scenario obračuna.",
    });
  }

  const aiComment = buildAiComment(data, previousMonthlyData);

  const cashChartItems = [
    { key: "Prihodi", value: cashIncome, colorClass: "bg-emerald-500" },
    { key: "Rashodi", value: cashExpense, colorClass: "bg-rose-500" },
    {
      key: "Neto",
      value: cashNet,
      colorClass: cashNet >= 0 ? "bg-sky-500" : "bg-slate-700",
    },
  ];

  const maxCashAbs = Math.max(...cashChartItems.map((i) => Math.abs(i.value)), 0);

  return (
    <div className="space-y-6">
      <div className="overflow-hidden rounded-3xl border border-slate-200 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 shadow-sm">
        <div className="grid gap-6 p-6 lg:grid-cols-[1.4fr_0.9fr]">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-slate-200 ring-1 ring-white/10">
              <ShieldCheck className="h-4 w-4" />
              EVIDENT komandna tabla
            </div>

            <h2 className="mt-4 text-3xl font-semibold tracking-tight text-white">
              {displayBusinessName}
            </h2>

            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
              Pregled poslovanja za{" "}
              <span className="font-semibold text-white">
                {monthLabel || "tekući mjesec"}
              </span>
              : promet, fakture, troškovi, poreski status i najvažnija upozorenja
              na jednom mjestu.
            </p>

            <div className="mt-5 flex flex-wrap gap-2">
              <span className="inline-flex items-center rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-slate-200 ring-1 ring-white/10">
                <Building2 className="mr-1.5 h-3.5 w-3.5" />
                {entityLabel}
              </span>
              <span className="inline-flex items-center rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-slate-200 ring-1 ring-white/10">
                <Landmark className="mr-1.5 h-3.5 w-3.5" />
                {scenarioLabel}
              </span>
              <span className="inline-flex items-center rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-slate-200 ring-1 ring-white/10">
                <Wallet className="mr-1.5 h-3.5 w-3.5" />
                Neto: {formatAmount(cashNet)} KM
              </span>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-300">
              Brzi status
            </p>

            <div className="mt-4 grid gap-3">
              <div className="flex items-center justify-between gap-3 rounded-xl bg-white/10 px-3 py-2">
                <span className="text-xs text-slate-300">Prihodi</span>
                <span className="text-sm font-semibold text-emerald-300">
                  {formatAmount(cashIncome)} KM
                </span>
              </div>

              <div className="flex items-center justify-between gap-3 rounded-xl bg-white/10 px-3 py-2">
                <span className="text-xs text-slate-300">Rashodi</span>
                <span className="text-sm font-semibold text-rose-300">
                  {formatAmount(cashExpense)} KM
                </span>
              </div>

              <div className="flex items-center justify-between gap-3 rounded-xl bg-white/10 px-3 py-2">
                <span className="text-xs text-slate-300">
                  Fakture / ulazni računi
                </span>
                <span className="text-sm font-semibold text-white">
                  {invoicesCount} / {inputInvoicesCount}
                </span>
              </div>

              <div className="flex items-center justify-between gap-3 rounded-xl bg-white/10 px-3 py-2">
                <span className="text-xs text-slate-300">Upozorenja</span>
                <span
                  className={cx(
                    "text-sm font-semibold",
                    overdueUnpaidCount > 0 ? "text-amber-300" : "text-emerald-300",
                  )}
                >
                  {overdueUnpaidCount > 0
                    ? `${overdueUnpaidCount} aktivno`
                    : "Nema kritičnih"}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {isLoading && (
        <Card className="p-4">
          <p className="text-sm text-slate-600">
            Učitavam mjesečne podatke za kontrolnu tablu...
          </p>
        </Card>
      )}

      {isError && (
        <Card className="border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">
            Greška pri učitavanju kontrolne table: {error.message}
          </p>
        </Card>
      )}

      {!isLoading && !isError && data && (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              title="Ukupni prihodi"
              value={`${formatAmount(cashIncome)} KM`}
              subtitle={monthLabel || `${data.year}-${data.month}`}
              icon={<TrendingUp className="h-5 w-5" />}
              tone="emerald"
            />

            <KpiCard
              title="Ukupni rashodi"
              value={`${formatAmount(cashExpense)} KM`}
              subtitle={`${inputInvoicesCount} ulaznih računa u mjesecu`}
              icon={<TrendingDown className="h-5 w-5" />}
              tone="rose"
            />

            <KpiCard
              title="Neto rezultat"
              value={`${formatAmount(cashNet)} KM`}
              subtitle={cashNet >= 0 ? "Pozitivno kretanje" : "Potrebna kontrola"}
              icon={<Wallet className="h-5 w-5" />}
              tone={cashNet >= 0 ? "sky" : "amber"}
            />

            <KpiCard
              title="Poreski status"
              value={
                totalTaxPlan != null ? `${formatAmount(totalTaxPlan)} KM` : "Aktivan"
              }
              subtitle={
                hasResolvedTaxProfile
                  ? "Admin Constants povezane"
                  : "Provjeri poreski profil"
              }
              icon={<Landmark className="h-5 w-5" />}
              tone={hasResolvedTaxProfile ? "slate" : "amber"}
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <QuickActionButton
              primary
              label="Nova faktura"
              description="Kreiraj izlaznu fakturu"
              icon={<FilePlus2 className="h-5 w-5" />}
              onClick={() => navigate("/invoices/new")}
            />

            <QuickActionButton
              label="Novi ulazni račun"
              description="Dodaj trošak ili dokument"
              icon={<Inbox className="h-5 w-5" />}
              onClick={() => navigate("/input-invoices/new")}
            />

            <QuickActionButton
              label="Kasa"
              description="Pregled prometa"
              icon={<Wallet className="h-5 w-5" />}
              onClick={() => navigate("/cash")}
            />

            <QuickActionButton
              label="Porezi"
              description="SAM i obračuni"
              icon={<Landmark className="h-5 w-5" />}
              onClick={() => navigate("/tax")}
            />

            <QuickActionButton
              label="Postavke"
              description="Firma i poreski profil"
              icon={<Settings className="h-5 w-5" />}
              onClick={() => navigate("/settings")}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <Card className="p-4">
              <SectionTitle
                title="Asistent – status mjeseca"
                subtitle={monthLabel || `${data.year}-${data.month}`}
              />

              <div className="mt-4 space-y-3">
                {messages.length > 0 && (
                  <ul className="space-y-2">
                    {messages.map((m, idx) => (
                      <li
                        key={idx}
                        className={cx(
                          "flex items-start gap-3 rounded-xl border px-3 py-2.5",
                          m.type === "warning" &&
                            "border-amber-200 bg-amber-50 text-amber-900",
                          m.type === "info" &&
                            "border-slate-200 bg-slate-50 text-slate-800",
                          m.type === "success" &&
                            "border-emerald-200 bg-emerald-50 text-emerald-900",
                        )}
                      >
                        <span
                          className={cx(
                            "mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full text-white",
                            m.type === "warning" && "bg-amber-500",
                            m.type === "info" && "bg-slate-400",
                            m.type === "success" && "bg-emerald-500",
                          )}
                          aria-hidden="true"
                        >
                          {m.type === "warning" ? (
                            <AlertTriangle className="h-3.5 w-3.5" />
                          ) : m.type === "success" ? (
                            <CheckCircle2 className="h-3.5 w-3.5" />
                          ) : (
                            <BarChart3 className="h-3.5 w-3.5" />
                          )}
                        </span>
                        <span className="text-sm leading-5">{m.text}</span>
                      </li>
                    ))}
                  </ul>
                )}

                <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
                  <p className="text-sm leading-6 text-slate-700">
                    {aiComment ??
                      "Nema dovoljno podataka za detaljniji komentar. Kako se gomilaju mjeseci i promet, ovdje ćeš imati kratak sažetak kretanja prihoda, troškova i neto rezultata."}
                  </p>
                </div>
              </div>
            </Card>

            <Card className="p-4">
              <SectionTitle
                title="Poreski profil"
                subtitle="Podaci povezani iz Postavki i Admin Constants"
                action={
                  <button
                    type="button"
                    onClick={() => navigate("/settings")}
                    className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Uredi
                  </button>
                }
              />

              <div className="mt-4 space-y-3 text-sm">
                <div className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2">
                  <span className="text-slate-500">Entitet</span>
                  <span className="text-right font-semibold text-slate-900">
                    {entityLabel}
                  </span>
                </div>

                <div className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2">
                  <span className="text-slate-500">Scenario</span>
                  <span className="text-right font-semibold text-slate-900">
                    {scenarioLabel}
                  </span>
                </div>

                <div className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2">
                  <span className="text-slate-500">Admin Constants</span>
                  <span className="text-right font-semibold text-slate-900">
                    {hasResolvedTaxProfile
                      ? taxUiSchemaQuery.data?.constants_set_id
                        ? `Set #${taxUiSchemaQuery.data.constants_set_id}`
                        : "Aktivno"
                      : "Nije povezano"}
                  </span>
                </div>

                <div className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2">
                  <span className="text-slate-500">Doprinosi mjesečno</span>
                  <span className="text-right font-semibold text-slate-900">
                    {contributionsPlan != null
                      ? `${formatAmount(contributionsPlan)} KM`
                      : hasResolvedTaxProfile
                        ? "Prema aktivnim parametrima"
                        : "Nije podešeno"}
                  </span>
                </div>

                <button
                  type="button"
                  onClick={() => navigate("/export/inspection")}
                  className="mt-1 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-rose-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-rose-700"
                >
                  <Receipt className="h-4 w-4" />
                  Izvoz za inspekciju
                </button>
              </div>
            </Card>
          </div>

          {/* Ostatak funkcionalnosti ostaje isti */}
          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="p-4">
              <SectionTitle
                title="Kasa"
                subtitle={monthLabel || `${data.year}-${data.month}`}
              />
              <p className={cx("mt-4 text-3xl font-semibold", netClass)}>
                {formatAmount(cashNet)} KM
              </p>
              <p className="mt-2 text-xs text-slate-500">
                Prihodi:{" "}
                <span className="font-semibold text-emerald-600">
                  {formatAmount(cashIncome)} KM
                </span>{" "}
                • Rashodi:{" "}
                <span className="font-semibold text-rose-600">
                  {formatAmount(cashExpense)} KM
                </span>
              </p>

              <div className="mt-4 h-36 rounded-xl border border-slate-100 bg-slate-50 px-5 py-4">
                {maxCashAbs === 0 ? (
                  <div className="flex h-full items-center justify-center text-xs text-slate-500">
                    Nema dovoljno podataka za prikaz grafa.
                  </div>
                ) : (
                  <div className="flex h-full items-end justify-around gap-5">
                    {cashChartItems.map((item) => {
                      const heightPercent =
                        maxCashAbs > 0
                          ? Math.max(10, (Math.abs(item.value) / maxCashAbs) * 100)
                          : 0;

                      return (
                        <div
                          key={item.key}
                          className="flex h-full flex-col items-center justify-end gap-1"
                          title={`${item.key}: ${formatAmount(item.value)} KM`}
                        >
                          <div className="flex h-full w-10 flex-col justify-end">
                            <div
                              className={cx(
                                "mx-auto w-8 rounded-t-lg shadow-sm transition-all",
                                item.colorClass,
                              )}
                              style={{ height: `${heightPercent}%` }}
                            />
                          </div>
                          <span className="text-[11px] font-medium text-slate-700">
                            {item.key}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </Card>

            <Card className="p-4">
              <SectionTitle
                title="Izlazne fakture"
                subtitle={monthLabel || `${data.year}-${data.month}`}
                action={
                  <button
                    type="button"
                    onClick={() => navigate("/invoices")}
                    className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Otvori
                  </button>
                }
              />
              <p className="mt-4 text-3xl font-semibold text-slate-950">
                {invoicesCount}
              </p>
              <p className="mt-2 text-xs text-slate-500">
                Ukupan iznos:{" "}
                <span className="font-semibold text-slate-900">
                  {formatAmount(invoicesTotal)} KM
                </span>
              </p>
              <div className="mt-4 rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600">
                Neplaćene starije od 30 dana:{" "}
                <span
                  className={cx(
                    "font-semibold",
                    overdueUnpaidCount > 0 ? "text-amber-700" : "text-emerald-700",
                  )}
                >
                  {overdueUnpaidCount}
                </span>
              </div>
            </Card>

            <Card className="p-4">
              <SectionTitle
                title="Ulazni računi"
                subtitle={monthLabel || `${data.year}-${data.month}`}
                action={
                  <button
                    type="button"
                    onClick={() => navigate("/input-invoices")}
                    className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Otvori
                  </button>
                }
              />
              <p className="mt-4 text-3xl font-semibold text-slate-950">
                {inputInvoicesCount}
              </p>
              <p className="mt-2 text-xs text-slate-500">
                Ukupan iznos:{" "}
                <span className="font-semibold text-slate-900">
                  {formatAmount(inputInvoicesTotal)} KM
                </span>
              </p>
              <div className="mt-4 rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600">
                Prosjek po računu:{" "}
                <span className="font-semibold text-slate-900">
                  {inputInvoicesCount > 0
                    ? `${formatAmount(inputInvoicesTotal / inputInvoicesCount)} KM`
                    : "—"}
                </span>
              </div>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card className="p-4">
              <SectionTitle title={`Prihodi po mjesecima – ${data.year}`} />

              <div className="mt-4 h-48 overflow-x-auto rounded-xl border border-slate-100 bg-slate-50 px-4 py-4">
                {incomeSeries.length === 0 || maxIncomeValue === 0 ? (
                  <div className="flex h-full items-center justify-center text-xs text-slate-500">
                    Nema dovoljno podataka za prikaz ovog grafa.
                  </div>
                ) : (
                  <div className="flex h-full min-w-[520px] items-end gap-2">
                    {incomeSeries.map((item) => {
                      const heightPercent =
                        (Math.abs(item.value) / maxIncomeValue) * 100;
                      const isActiveMonth = item.month === data.month;

                      return (
                        <div
                          key={item.month}
                          className="flex h-full flex-1 flex-col items-center justify-end gap-1"
                          title={`${item.label}: ${formatAmount(item.value)} KM`}
                        >
                          <span
                            className={cx(
                              "text-[10px] font-semibold",
                              isActiveMonth ? "text-slate-800" : "text-slate-400",
                            )}
                          >
                            {isActiveMonth
                              ? `${formatCompactAmount(item.value)}`
                              : ""}
                          </span>

                          <div className="flex h-full w-full flex-col justify-end">
                            <div
                              className={cx(
                                "mx-auto rounded-t-md shadow-sm",
                                isActiveMonth
                                  ? "w-5 bg-emerald-600"
                                  : "w-3 bg-emerald-400",
                              )}
                              style={{
                                height: `${Math.max(8, heightPercent)}%`,
                              }}
                            />
                          </div>

                          <span
                            className={cx(
                              "text-[10px]",
                              isActiveMonth ? "text-slate-800" : "text-slate-500",
                            )}
                          >
                            {item.label}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </Card>

            <Card className="p-4">
              <SectionTitle title={`Rashodi po dobavljačima – ${monthLabel}`} />

              <div className="mt-4 h-48 overflow-x-auto rounded-xl border border-slate-100 bg-slate-50 px-4 py-4">
                {expenseSuppliers.length === 0 || maxExpenseSupplier === 0 ? (
                  <div className="flex h-full items-center justify-center text-xs text-slate-500">
                    Nema dovoljno podataka za prikaz ovog grafa.
                  </div>
                ) : (
                  <div className="flex h-full min-w-[420px] items-end gap-4">
                    {expenseSuppliers.map((cat) => {
                      const heightPercent =
                        (Math.abs(cat.total) / maxExpenseSupplier) * 100;
                      return (
                        <div
                          key={cat.name}
                          className="flex h-full min-w-[60px] flex-col items-center justify-end gap-1"
                          title={`${cat.name}: ${formatAmount(cat.total)} KM`}
                        >
                          <span className="text-[10px] font-semibold text-slate-800">
                            {formatCompactAmount(cat.total)}
                          </span>

                          <div className="flex h-full w-full flex-col justify-end">
                            <div
                              className="mx-auto w-8 rounded-t-md bg-rose-500 shadow-sm"
                              style={{
                                height: `${Math.max(10, heightPercent)}%`,
                              }}
                            />
                          </div>

                          <span className="line-clamp-2 text-center text-[10px] text-slate-600">
                            {cat.name}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card className="p-4">
              <SectionTitle
                title="Zadnjih 5 izlaznih faktura"
                action={
                  <button
                    type="button"
                    onClick={() => navigate("/invoices")}
                    className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Sve fakture
                  </button>
                }
              />

              {lastOutgoingInvoices.length === 0 ? (
                <p className="mt-4 text-xs text-slate-500">
                  Nema izlaznih faktura za prikaz. Kreiraj prvu fakturu u modulu
                  izlaznih faktura.
                </p>
              ) : (
                <div className="mt-4 overflow-x-auto">
                  <table className="min-w-full text-left text-xs text-slate-700">
                    <thead>
                      <tr className="border-b border-slate-100 text-slate-500">
                        <th className="py-2 pr-3">Datum</th>
                        <th className="py-2 pr-3">Broj</th>
                        <th className="py-2 pr-3">Kupac</th>
                        <th className="py-2 text-right">Iznos</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lastOutgoingInvoices.map((inv: any) => (
                        <tr
                          key={inv.id}
                          className="border-b border-slate-50 last:border-0"
                        >
                          <td className="py-2 pr-3 text-slate-600">
                            {inv.issue_date ?? "-"}
                          </td>
                          <td className="py-2 pr-3 font-mono text-slate-800">
                            {inv.number ?? "-"}
                          </td>
                          <td className="py-2 pr-3 text-slate-700">
                            {inv.buyer_name ?? "-"}
                          </td>
                          <td className="py-2 text-right text-slate-800">
                            {inv.total_amount != null
                              ? `${formatAmount(toNumber(inv.total_amount))} KM`
                              : "-"}
                            {!inv.is_paid && (
                              <span className="ml-1 inline-flex rounded-full bg-rose-50 px-2 py-[1px] text-[10px] font-medium text-rose-700">
                                neplaćena
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            <Card className="p-4">
              <SectionTitle
                title="Zadnjih 5 ulaznih računa"
                action={
                  <button
                    type="button"
                    onClick={() => navigate("/input-invoices")}
                    className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Svi ulazni računi
                  </button>
                }
              />

              {lastInputInvoices.length === 0 ? (
                <p className="mt-4 text-xs text-slate-500">
                  Nema ulaznih računa za prikaz. Dodaj prvi račun u modulu ulaznih
                  faktura.
                </p>
              ) : (
                <div className="mt-4 overflow-x-auto">
                  <table className="min-w-full text-left text-xs text-slate-700">
                    <thead>
                      <tr className="border-b border-slate-100 text-slate-500">
                        <th className="py-2 pr-3">Datum</th>
                        <th className="py-2 pr-3">Broj</th>
                        <th className="py-2 pr-3">Dobavljač</th>
                        <th className="py-2 text-right">Iznos</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lastInputInvoices.map((inv: any) => (
                        <tr
                          key={inv.id}
                          className="border-b border-slate-50 last:border-0"
                        >
                          <td className="py-2 pr-3 text-slate-600">
                            {inv.issue_date ?? "-"}
                          </td>
                          <td className="py-2 pr-3 font-mono text-slate-800">
                            {inv.number ?? "-"}
                          </td>
                          <td className="py-2 pr-3 text-slate-700">
                            {inv.supplier_name ?? "-"}
                          </td>
                          <td className="py-2 text-right text-slate-800">
                            {inv.total_amount != null
                              ? `${formatAmount(toNumber(inv.total_amount))} KM`
                              : "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>

                    <div className="grid gap-4 xl:grid-cols-2">
            <Card className="p-4">
              <SectionTitle
                title="Top kupci"
                subtitle="Rangirano po ukupnom iznosu izlaznih faktura"
              />

              {topCustomers.length === 0 ? (
                <div className="mt-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center">
                  <FilePlus2 className="mx-auto h-8 w-8 text-slate-400" />
                  <p className="mt-3 text-sm font-semibold text-slate-800">
                    Još nema dovoljno podataka o kupcima.
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Kada kreiraš izlazne fakture, ovdje će se prikazati kupci sa
                    najvećim prometom.
                  </p>
                  <button
                    type="button"
                    onClick={() => navigate("/invoices/new")}
                    className="mt-4 inline-flex items-center justify-center rounded-xl bg-slate-950 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-800"
                  >
                    Kreiraj fakturu
                  </button>
                </div>
              ) : (
                <ul className="mt-4 space-y-3">
                  {topCustomers.map((c, idx) => {
                    const maxTotal = Math.max(
                      ...topCustomers.map((item) => Math.abs(item.total)),
                      1,
                    );
                    const widthPercent = Math.max(
                      8,
                      (Math.abs(c.total) / maxTotal) * 100,
                    );

                    return (
                      <li
                        key={c.name}
                        className="rounded-2xl border border-slate-100 bg-slate-50 px-3 py-3"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex min-w-0 items-center gap-3">
                            <span
                              className={cx(
                                "grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-semibold",
                                idx === 0
                                  ? "bg-slate-950 text-white"
                                  : "bg-white text-slate-600 ring-1 ring-slate-200",
                              )}
                            >
                              {idx + 1}
                            </span>
                            <div className="min-w-0">
                              <p className="truncate text-sm font-semibold text-slate-900">
                                {c.name}
                              </p>
                              <p className="text-[11px] text-slate-500">
                                Kupac #{idx + 1}
                              </p>
                            </div>
                          </div>

                          <span className="shrink-0 text-sm font-semibold text-slate-950">
                            {formatAmount(c.total)} KM
                          </span>
                        </div>

                        <div className="mt-3 h-2 overflow-hidden rounded-full bg-white ring-1 ring-slate-100">
                          <div
                            className="h-full rounded-full bg-slate-900"
                            style={{ width: `${widthPercent}%` }}
                          />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </Card>

            <Card className="p-4">
              <SectionTitle
                title="Top dobavljači"
                subtitle="Tekući mjesec, rangirano po ulaznim računima"
              />

              {topSuppliers.length === 0 ? (
                <div className="mt-4 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center">
                  <Inbox className="mx-auto h-8 w-8 text-slate-400" />
                  <p className="mt-3 text-sm font-semibold text-slate-800">
                    Još nema dovoljno podataka o dobavljačima.
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Kada uneseš ulazne račune, ovdje će se prikazati dobavljači
                    sa najvećim troškovima u mjesecu.
                  </p>
                  <button
                    type="button"
                    onClick={() => navigate("/input-invoices/new")}
                    className="mt-4 inline-flex items-center justify-center rounded-xl bg-slate-950 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-800"
                  >
                    Dodaj ulazni račun
                  </button>
                </div>
              ) : (
                <ul className="mt-4 space-y-3">
                  {topSuppliers.map((s, idx) => {
                    const maxTotal = Math.max(
                      ...topSuppliers.map((item) => Math.abs(item.total)),
                      1,
                    );
                    const widthPercent = Math.max(
                      8,
                      (Math.abs(s.total) / maxTotal) * 100,
                    );

                    return (
                      <li
                        key={s.name}
                        className="rounded-2xl border border-slate-100 bg-slate-50 px-3 py-3"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex min-w-0 items-center gap-3">
                            <span
                              className={cx(
                                "grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-semibold",
                                idx === 0
                                  ? "bg-rose-600 text-white"
                                  : "bg-white text-slate-600 ring-1 ring-slate-200",
                              )}
                            >
                              {idx + 1}
                            </span>
                            <div className="min-w-0">
                              <p className="truncate text-sm font-semibold text-slate-900">
                                {s.name}
                              </p>
                              <p className="text-[11px] text-slate-500">
                                Dobavljač #{idx + 1}
                              </p>
                            </div>
                          </div>

                          <span className="shrink-0 text-sm font-semibold text-slate-950">
                            {formatAmount(s.total)} KM
                          </span>
                        </div>

                        <div className="mt-3 h-2 overflow-hidden rounded-full bg-white ring-1 ring-slate-100">
                          <div
                            className="h-full rounded-full bg-rose-500"
                            style={{ width: `${widthPercent}%` }}
                          />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </Card>
          </div>
        </>
      )}

      {!isLoading && !isError && !data && (
        <Card className="p-4">
          <p className="text-sm text-slate-500">
            Nema dostupnih podataka za kontrolnu tablu.
          </p>
        </Card>
      )}
    </div>
  );
}