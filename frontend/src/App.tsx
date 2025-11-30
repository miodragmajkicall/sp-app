import { BrowserRouter, NavLink, Navigate, Route, Routes } from "react-router-dom";
import DashboardPage from "./pages/DashboardPage";
import InvoicesListPage from "./pages/InvoicesListPage";
import CashPage from "./pages/CashPage";
import InputInvoicesPage from "./pages/InputInvoicesPage";
import InvoiceCreatePage from "./pages/InvoiceCreatePage";  // NOVO

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-100 flex">
        {/* Sidebar */}
        <aside className="w-64 bg-slate-900 text-slate-100 flex flex-col">
          <div className="px-6 py-4 border-b border-slate-800">
            <h1 className="text-lg font-semibold tracking-tight">SP App</h1>
            <p className="text-xs text-slate-400">Demo frontend V1</p>
          </div>

          <nav className="flex-1 px-3 py-4 space-y-1 text-sm">
            
            <NavLink
              to="/dashboard"
              className={({ isActive }) =>
                [
                  "flex items-center rounded-md px-3 py-2 transition-colors",
                  isActive
                    ? "bg-slate-800 text-slate-50"
                    : "text-slate-300 hover:bg-slate-800 hover:text-slate-50",
                ].join(" ")
              }
            >
              Dashboard
            </NavLink>

            <NavLink
              to="/invoices"
              className={({ isActive }) =>
                [
                  "flex items-center rounded-md px-3 py-2 transition-colors",
                  isActive
                    ? "bg-slate-800 text-slate-50"
                    : "text-slate-300 hover:bg-slate-800 hover:text-slate-50",
                ].join(" ")
              }
            >
              Izlazne fakture
            </NavLink>

            {/* 🔥 NOVA OPCIJA U MENIJU */}
            <NavLink
              to="/invoices/new"
              className={({ isActive }) =>
                [
                  "flex items-center rounded-md px-3 py-2 transition-colors",
                  isActive
                    ? "bg-emerald-700 text-white"
                    : "text-slate-300 hover:bg-slate-800 hover:text-slate-50",
                ].join(" ")
              }
            >
              ➕ Nova faktura
            </NavLink>

            <NavLink
              to="/input-invoices"
              className={({ isActive }) =>
                [
                  "flex items-center rounded-md px-3 py-2 transition-colors",
                  isActive
                    ? "bg-slate-800 text-slate-50"
                    : "text-slate-300 hover:bg-slate-800 hover:text-slate-50",
                ].join(" ")
              }
            >
              Ulazne fakture
            </NavLink>

            <NavLink
              to="/cash"
              className={({ isActive }) =>
                [
                  "flex items-center rounded-md px-3 py-2 transition-colors",
                  isActive
                    ? "bg-slate-800 text-slate-50"
                    : "text-slate-300 hover:bg-slate-800 hover:text-slate-50",
                ].join(" ")
              }
            >
              Kasa
            </NavLink>

            <NavLink
              to="/tax"
              className={({ isActive }) =>
                [
                  "flex items-center rounded-md px-3 py-2 transition-colors",
                  isActive
                    ? "bg-slate-800 text-slate-50"
                    : "text-slate-300 hover:bg-slate-800 hover:text-slate-50",
                ].join(" ")
              }
            >
              Porezi / SAM
            </NavLink>
          </nav>

          <div className="px-4 py-3 border-t border-slate-800 text-xs text-slate-500">
            <p>
              Tenant: <span className="font-mono text-slate-300">t-demo</span>
            </p>
          </div>
        </aside>

        {/* Main content */}
        <div className="flex-1 flex flex-col">
          <header className="h-14 border-b border-slate-200 bg-white flex items-center justify-between px-6">
            <div>
              <p className="text-sm font-medium text-slate-800">
                SP App – web frontend
              </p>
              <p className="text-xs text-slate-500">
                Backend V1 (bez auth) • demo tenant{" "}
                <span className="font-mono">t-demo</span>
              </p>
            </div>
          </header>

          <main className="flex-1 p-6">
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<DashboardPage />} />

              <Route path="/invoices" element={<InvoicesListPage />} />
              <Route path="/invoices/new" element={<InvoiceCreatePage />} /> {/* 🔥 NOVA RUTA */}
              <Route path="/input-invoices" element={<InputInvoicesPage />} />
              <Route path="/cash" element={<CashPage />} />

              <Route
                path="/tax"
                element={<div className="text-slate-600 text-sm">Ekran za poreze i SAM dolazi uskoro.</div>}
              />

              <Route
                path="*"
                element={<div className="text-sm text-red-600">404 – Stranica nije pronađena.</div>}
              />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;
