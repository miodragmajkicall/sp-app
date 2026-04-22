// /home/miso/dev/sp-app/sp-app/frontend/src/App.tsx
import React, { useCallback, useEffect, useState } from "react";
import {
  BrowserRouter,
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";

import {
  LayoutDashboard,
  FileText,
  Plus,
  Inbox,
  Wallet,
  BookOpen,
  Receipt,
  Landmark,
  BarChart3,
  Briefcase,
  Settings,
  Puzzle,
  Building2,
  Image as ImageIcon,
} from "lucide-react";

import DashboardPage from "./pages/DashboardPage";
import InvoicesListPage from "./pages/InvoicesListPage";
import CashPage from "./pages/CashPage";
import InputInvoicesPage from "./pages/InputInvoicesPage";
import InvoiceCreatePage from "./pages/InvoiceCreatePage";
import InvoiceDetailPage from "./pages/InvoiceDetailPage";
import InputInvoiceCreatePage from "./pages/InputInvoiceCreatePage";
import InputInvoiceDetailPage from "./pages/InputInvoiceDetailPage";
import TaxPage from "./pages/TaxPage";
import KprPage from "./pages/KprPage";
import PrometPage from "./pages/PrometPage";
import ReportsPage from "./pages/ReportsPage";
import ExportInspectionPage from "./pages/ExportInspectionPage";
import SettingsPage from "./pages/SettingsPage";
import AdminConstantsPage from "./pages/AdminConstantsPage";

import {
  getProfileSettings,
  fetchProfileLogoBlob,
} from "./services/settingsApi";
import type { ProfileSettingsRead } from "./types/settings";

import EvidentLogoOnDark from "./assets/evident-logo-horizontal.svg";

type NavItem = {
  to: string;
  label: string;
  icon: React.ReactNode;
  indent?: boolean;
};

function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}

function AppShell() {
  const location = useLocation();
  const isDev = import.meta.env.DEV;

  const linkBase =
    "grid grid-cols-[20px_1fr] items-center gap-3 rounded-md px-3 py-2 transition-colors";
  const linkInactive =
    "text-slate-300 hover:bg-slate-800/60 hover:text-white";
  const linkActive = "bg-slate-800/80 text-white";

  const iconCls = "h-5 w-5 shrink-0";

  const sectionTitleCls =
    "px-3 mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500";

  const tenant = "t-demo";

  const navPoslovanje: NavItem[] = [
    {
      to: "/invoices",
      label: "Izlazne fakture",
      icon: <FileText className={iconCls} aria-hidden="true" />,
    },
    {
      to: "/invoices/new",
      label: "Nova izlazna faktura",
      icon: <Plus className={iconCls} aria-hidden="true" />,
      indent: true,
    },
    {
      to: "/input-invoices",
      label: "Ulazne fakture",
      icon: <Inbox className={iconCls} aria-hidden="true" />,
    },
    {
      to: "/input-invoices/new",
      label: "Nova ulazna faktura",
      icon: <Plus className={iconCls} aria-hidden="true" />,
      indent: true,
    },
    {
      to: "/cash",
      label: "Kasa",
      icon: <Wallet className={iconCls} aria-hidden="true" />,
    },
  ];

  const navKnjigovodstvo: NavItem[] = [
    {
      to: "/kpr",
      label: "KPR",
      icon: <BookOpen className={iconCls} aria-hidden="true" />,
    },
    {
      to: "/promet",
      label: "Knjiga prometa",
      icon: <Receipt className={iconCls} aria-hidden="true" />,
    },
    {
      to: "/tax",
      label: "Porezi i doprinosi",
      icon: <Landmark className={iconCls} aria-hidden="true" />,
    },
    {
      to: "/reports",
      label: "Izvještaji",
      icon: <BarChart3 className={iconCls} aria-hidden="true" />,
    },
  ];

  const navAlati: NavItem[] = [
    {
      to: "/export/inspection",
      label: "Izvoz za inspekciju",
      icon: <Briefcase className={iconCls} aria-hidden="true" />,
    },
  ];

  const navSistem: NavItem[] = [
    {
      to: "/settings",
      label: "Postavke",
      icon: <Settings className={iconCls} aria-hidden="true" />,
    },
    {
      to: "/admin/constants",
      label: "Admin: konstante",
      icon: <Puzzle className={iconCls} aria-hidden="true" />,
    },
  ];

  function NavItemLink({ item }: { item: NavItem }) {
    return (
      <NavLink
        to={item.to}
        className={({ isActive }) =>
          [
            item.indent ? "ml-6" : "",
            linkBase,
            isActive ? linkActive : linkInactive,
          ].join(" ")
        }
      >
        {item.icon}
        <span className="min-w-0 truncate">{item.label}</span>
      </NavLink>
    );
  }

  const [profile, setProfile] = useState<ProfileSettingsRead | null>(null);
  const [profileErr, setProfileErr] = useState<string | null>(null);
  const [logoSrc, setLogoSrc] = useState<string | null>(null);
  const [logoFailed, setLogoFailed] = useState(false);

  const refreshProfile = useCallback(async () => {
    try {
      const p = await getProfileSettings();
      setProfile(p);
      setProfileErr(null);
    } catch {
      setProfile(null);
      setProfileErr("Profil firme nije dostupan.");
    }
  }, []);

  const refreshLogo = useCallback(async () => {
    try {
      const blob = await fetchProfileLogoBlob();

      if (!blob || blob.size === 0) {
        setLogoSrc((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return null;
        });
        return;
      }

      const objectUrl = URL.createObjectURL(blob);

      setLogoSrc((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return objectUrl;
      });
      setLogoFailed(false);
    } catch {
      setLogoSrc((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
    }
  }, []);

  const refreshAll = useCallback(async () => {
    await refreshProfile();
    await refreshLogo();
  }, [refreshProfile, refreshLogo]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  useEffect(() => {
    if (location.pathname === "/settings") {
      refreshAll();
    }
  }, [location.pathname, refreshAll]);

  useEffect(() => {
    function sync() {
      refreshAll();
    }

    function onVisible() {
      if (document.visibilityState === "visible") {
        refreshAll();
      }
    }

    window.addEventListener(
      "profile-settings-updated",
      sync as EventListener,
    );
    window.addEventListener("focus", sync);
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      window.removeEventListener(
        "profile-settings-updated",
        sync as EventListener,
      );
      window.removeEventListener("focus", sync);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [refreshAll]);

  useEffect(() => {
    if (!isDev) return;

    const id = window.setInterval(() => {
      refreshAll();
    }, 15000);

    return () => window.clearInterval(id);
  }, [isDev, refreshAll]);

  useEffect(() => {
    setLogoFailed(false);
  }, [logoSrc]);

  useEffect(() => {
    return () => {
      if (logoSrc) URL.revokeObjectURL(logoSrc);
    };
  }, [logoSrc]);

  const businessName = (profile?.business_name ?? "").trim();
  const displayBusinessName = businessName ? businessName : `SP ${tenant}`;

  return (
    <div className="min-h-screen bg-slate-100 flex">
      <aside className="w-64 text-slate-100 flex flex-col bg-gradient-to-b from-slate-950 to-slate-900">
        <div className="px-5 py-4 border-b border-slate-800/70">
          <img
            src={EvidentLogoOnDark}
            alt="Evident"
            className="h-12 w-auto"
          />
          <p className="text-[13px] text-slate-400 mt-1 whitespace-nowrap">
            Poslovanje • Knjigovodstvo • Porezi
          </p>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-6 text-sm">
          <NavLink
            to="/dashboard"
            className={({ isActive }) =>
              [linkBase, isActive ? linkActive : linkInactive].join(" ")
            }
          >
            <LayoutDashboard className={iconCls} aria-hidden="true" />
            <span className="min-w-0 truncate">Kontrolna tabla</span>
          </NavLink>

          <div className="space-y-1">
            <div className={sectionTitleCls}>Poslovanje</div>
            {navPoslovanje.map((item) => (
              <NavItemLink key={item.to} item={item} />
            ))}
          </div>

          <div className="space-y-1">
            <div className={sectionTitleCls}>Knjigovodstvo</div>
            {navKnjigovodstvo.map((item) => (
              <NavItemLink key={item.to} item={item} />
            ))}
          </div>

          <div className="space-y-1">
            <div className={sectionTitleCls}>Alati</div>
            {navAlati.map((item) => (
              <NavItemLink key={item.to} item={item} />
            ))}
          </div>

          <div className="space-y-1">
            <div className={sectionTitleCls}>Sistem</div>
            {navSistem.map((item) => (
              <NavItemLink key={item.to} item={item} />
            ))}

            <div className="grid grid-cols-[20px_1fr] items-center gap-3 rounded-md px-3 py-2 text-slate-500 cursor-default">
              <span
                className="h-5 w-5 rounded border border-slate-700"
                aria-hidden="true"
              />
              <span className="min-w-0 truncate">Pomoć (uskoro)</span>
            </div>
          </div>
        </nav>

        {isDev && (
          <div className="px-4 py-3 border-t border-slate-800/70 text-xs text-slate-500">
            <p className="min-w-0 truncate" title={`Tenant: ${tenant}`}>
              Tenant: <span className="font-mono text-slate-300">{tenant}</span>
            </p>
          </div>
        )}
      </aside>

      <div className="flex-1 flex flex-col">
        <header className="h-14 border-b border-slate-200 bg-white flex items-center justify-between px-6">
          <div className="min-w-0 flex items-center gap-2">
            <p className="text-sm font-semibold text-slate-900 truncate">
              Evident
            </p>

            {isDev && (
              <span
                className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600"
                title={`Demo okruženje • tenant ${tenant}`}
              >
                Demo
              </span>
            )}
          </div>

          <NavLink
            to="/settings"
            className="flex items-center gap-3 rounded-md px-2 py-1 hover:bg-slate-50 transition-colors"
            title="Postavke firme"
          >
            <div className="text-right leading-tight min-w-0">
              <p className="text-sm font-semibold text-slate-900 truncate max-w-[360px]">
                {profileErr ? "SP (nije dostupno)" : displayBusinessName}
              </p>
              <p className="text-xs text-slate-500 truncate max-w-[360px]">
                Postavke profila i logotipa
              </p>
            </div>

            <div className="h-9 w-9 rounded-md border border-slate-200 bg-white grid place-items-center overflow-hidden shrink-0">
              {logoSrc && !logoFailed ? (
                <img
                  src={logoSrc}
                  alt="Logo firme"
                  className="h-full w-full object-contain"
                  onError={() => setLogoFailed(true)}
                />
              ) : (
                <div className="h-full w-full grid place-items-center bg-slate-50">
                  {logoSrc ? (
                    <ImageIcon className="h-5 w-5 text-slate-400" />
                  ) : (
                    <Building2 className="h-5 w-5 text-slate-400" />
                  )}
                </div>
              )}
            </div>
          </NavLink>
        </header>

        <main className="flex-1 p-6">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />

            <Route path="/invoices" element={<InvoicesListPage />} />
            <Route path="/invoices/new" element={<InvoiceCreatePage />} />
            <Route path="/invoices/:id" element={<InvoiceDetailPage />} />

            <Route path="/input-invoices" element={<InputInvoicesPage />} />
            <Route
              path="/input-invoices/new"
              element={<InputInvoiceCreatePage />}
            />
            <Route
              path="/input-invoices/:id"
              element={<InputInvoiceDetailPage />}
            />

            <Route path="/cash" element={<CashPage />} />
            <Route path="/kpr" element={<KprPage />} />
            <Route path="/promet" element={<PrometPage />} />
            <Route path="/tax" element={<TaxPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route
              path="/export/inspection"
              element={<ExportInspectionPage />}
            />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/admin/constants" element={<AdminConstantsPage />} />

            <Route
              path="*"
              element={
                <div className="text-sm text-red-600">
                  404 – Stranica nije pronađena.
                </div>
              }
            />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default App;