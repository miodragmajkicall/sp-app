// /home/miso/dev/sp-app/sp-app/frontend/src/App.tsx
import {
  BrowserRouter,
  NavLink,
  Navigate,
  Route,
  Routes,
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

type NavItem = {
  to: string;
  label: string;
  icon: React.ReactNode;
  indent?: boolean;
};

function App() {
  const linkBase =
    "grid grid-cols-[20px_1fr] items-center gap-3 rounded-md px-3 py-2 transition-colors";
  const linkInactive =
    "text-slate-300 hover:bg-slate-800 hover:text-slate-50";
  const linkActive = "bg-slate-800 text-slate-50";

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

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-100 flex">
        {/* Sidebar */}
        <aside className="w-64 bg-slate-900 text-slate-100 flex flex-col">
          <div className="px-6 py-4 border-b border-slate-800">
            <h1 className="text-lg font-semibold tracking-tight">SP App</h1>
            <p className="text-xs text-slate-400">
              Kontrolna tabla za SP preduzetnike
            </p>
          </div>

          <nav className="flex-1 px-3 py-4 space-y-6 text-sm">
            {/* Glavna stavka – Kontrolna tabla */}
            <NavLink
              to="/dashboard"
              className={({ isActive }) =>
                [linkBase, isActive ? linkActive : linkInactive].join(" ")
              }
            >
              <LayoutDashboard className={iconCls} aria-hidden="true" />
              <span className="min-w-0 truncate">Kontrolna tabla</span>
            </NavLink>

            {/* POSLOVANJE */}
            <div className="space-y-1">
              <div className={sectionTitleCls}>Poslovanje</div>
              {navPoslovanje.map((item) => (
                <NavItemLink key={item.to} item={item} />
              ))}
            </div>

            {/* KNJIGOVODSTVO */}
            <div className="space-y-1">
              <div className={sectionTitleCls}>Knjigovodstvo</div>
              {navKnjigovodstvo.map((item) => (
                <NavItemLink key={item.to} item={item} />
              ))}
            </div>

            {/* ALATI */}
            <div className="space-y-1">
              <div className={sectionTitleCls}>Alati</div>
              {navAlati.map((item) => (
                <NavItemLink key={item.to} item={item} />
              ))}
            </div>

            {/* SISTEM */}
            <div className="space-y-1">
              <div className={sectionTitleCls}>Sistem</div>
              {navSistem.map((item) => (
                <NavItemLink key={item.to} item={item} />
              ))}

              <div className="grid grid-cols-[20px_1fr] items-center gap-3 rounded-md px-3 py-2 text-slate-500 cursor-default">
                {/* placeholder icon (monochrome) */}
                <span className="h-5 w-5 rounded border border-slate-700" aria-hidden="true" />
                <span className="min-w-0 truncate">Pomoć (uskoro)</span>
              </div>
            </div>
          </nav>

          <div className="px-4 py-3 border-t border-slate-800 text-xs text-slate-500">
            <p className="min-w-0 truncate" title={`Tenant: ${tenant}`}>
              Tenant: <span className="font-mono text-slate-300">{tenant}</span>
            </p>
          </div>
        </aside>

        {/* Main content */}
        <div className="flex-1 flex flex-col">
          <header className="h-14 border-b border-slate-200 bg-white flex items-center justify-between px-6">
            <div className="min-w-0">
              <p className="text-sm font-medium text-slate-800 truncate">
                SP App – kontrolna tabla
              </p>
              <p className="text-xs text-slate-500 truncate">
                Backend V1 (bez auth) • demo tenant{" "}
                <span className="font-mono">{tenant}</span>
              </p>
            </div>
          </header>

          <main className="flex-1 p-6">
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<DashboardPage />} />

              {/* Izlazne fakture */}
              <Route path="/invoices" element={<InvoicesListPage />} />
              <Route path="/invoices/new" element={<InvoiceCreatePage />} />
              <Route path="/invoices/:id" element={<InvoiceDetailPage />} />

              {/* Ulazne fakture */}
              <Route path="/input-invoices" element={<InputInvoicesPage />} />
              <Route path="/input-invoices/new" element={<InputInvoiceCreatePage />} />
              <Route path="/input-invoices/:id" element={<InputInvoiceDetailPage />} />

              {/* Kasa */}
              <Route path="/cash" element={<CashPage />} />

              {/* KPR */}
              <Route path="/kpr" element={<KprPage />} />

              {/* Promet */}
              <Route path="/promet" element={<PrometPage />} />

              {/* Porezi */}
              <Route path="/tax" element={<TaxPage />} />

              {/* Izvještaji */}
              <Route path="/reports" element={<ReportsPage />} />

              {/* Izvoz */}
              <Route path="/export/inspection" element={<ExportInspectionPage />} />

              {/* Postavke */}
              <Route path="/settings" element={<SettingsPage />} />

              {/* Admin constants */}
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
    </BrowserRouter>
  );
}

export default App;
