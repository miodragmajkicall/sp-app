// /home/miso/dev/sp-app/sp-app/frontend/src/App.tsx
import {
  BrowserRouter,
  NavLink,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";
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

function App() {
  const linkBaseClasses =
    "flex items-center rounded-md px-3 py-2 transition-colors";
  const linkInactiveClasses =
    "text-slate-300 hover:bg-slate-800 hover:text-slate-50";
  const linkActiveClasses = "bg-slate-800 text-slate-50";

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

          <nav className="flex-1 px-3 py-4 space-y-4 text-sm">
            {/* Glavna stavka – Kontrolna tabla */}
            <NavLink
              to="/dashboard"
              className={({ isActive }) =>
                [
                  linkBaseClasses,
                  isActive ? linkActiveClasses : linkInactiveClasses,
                ].join(" ")
              }
            >
              <span className="mr-2" aria-hidden="true">
                📊
              </span>
              <span>Kontrolna tabla</span>
            </NavLink>

            {/* POSLOVANJE */}
            <div>
              <div className="px-3 mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Poslovanje
              </div>

              <NavLink
                to="/invoices"
                className={({ isActive }) =>
                  [
                    linkBaseClasses,
                    isActive ? linkActiveClasses : linkInactiveClasses,
                  ].join(" ")
                }
              >
                <span className="mr-2" aria-hidden="true">
                  📄
                </span>
                <span>Izlazne fakture</span>
              </NavLink>

              <NavLink
                to="/invoices/new"
                className={({ isActive }) =>
                  [
                    "ml-6 mt-1",
                    linkBaseClasses,
                    isActive ? linkActiveClasses : linkInactiveClasses,
                  ].join(" ")
                }
              >
                <span className="mr-2" aria-hidden="true">
                  ➕
                </span>
                <span>Nova izlazna faktura</span>
              </NavLink>

              <NavLink
                to="/input-invoices"
                className={({ isActive }) =>
                  [
                    linkBaseClasses,
                    isActive ? linkActiveClasses : linkInactiveClasses,
                  ].join(" ")
                }
              >
                <span className="mr-2" aria-hidden="true">
                  📥
                </span>
                <span>Ulazne fakture</span>
              </NavLink>

              <NavLink
                to="/input-invoices/new"
                className={({ isActive }) =>
                  [
                    "ml-6 mt-1",
                    linkBaseClasses,
                    isActive ? linkActiveClasses : linkInactiveClasses,
                  ].join(" ")
                }
              >
                <span className="mr-2" aria-hidden="true">
                  ➕
                </span>
                <span>Nova ulazna faktura</span>
              </NavLink>

              <NavLink
                to="/cash"
                className={({ isActive }) =>
                  [
                    linkBaseClasses,
                    isActive ? linkActiveClasses : linkInactiveClasses,
                  ].join(" ")
                }
              >
                <span className="mr-2" aria-hidden="true">
                  💰
                </span>
                <span>Kasa</span>
              </NavLink>
            </div>

            {/* KNJIGOVODSTVO */}
            <div>
              <div className="px-3 mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Knjigovodstvo
              </div>

              <NavLink
                to="/kpr"
                className={({ isActive }) =>
                  [
                    linkBaseClasses,
                    isActive ? linkActiveClasses : linkInactiveClasses,
                  ].join(" ")
                }
              >
                <span className="mr-2" aria-hidden="true">
                  📘
                </span>
                <span>KPR</span>
              </NavLink>

              <NavLink
                to="/promet"
                className={({ isActive }) =>
                  [
                    linkBaseClasses,
                    isActive ? linkActiveClasses : linkInactiveClasses,
                  ].join(" ")
                }
              >
                <span className="mr-2" aria-hidden="true">
                  🧾
                </span>
                <span>Knjiga prometa</span>
              </NavLink>

              <NavLink
                to="/tax"
                className={({ isActive }) =>
                  [
                    linkBaseClasses,
                    isActive ? linkActiveClasses : linkInactiveClasses,
                  ].join(" ")
                }
              >
                <span className="mr-2" aria-hidden="true">
                  📑
                </span>
                <span>Porezi i doprinosi</span>
              </NavLink>

              <div className="flex items-center rounded-md px-3 py-2 text-slate-500 cursor-default">
                <span className="mr-2" aria-hidden="true">
                  📈
                </span>
                <span>Izvještaji (uskoro)</span>
              </div>
            </div>

            {/* DODATNE EVIDENCIJE */}
            <div>
              <div className="px-3 mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Dodatne evidencije
              </div>

              <div className="flex items-center rounded-md px-3 py-2 text-slate-500 cursor-default">
                <span className="mr-2" aria-hidden="true">
                  🧱
                </span>
                <span>Osnovna sredstva (uskoro)</span>
              </div>

              <div className="flex items-center rounded-md px-3 py-2 text-slate-500 cursor-default">
                <span className="mr-2" aria-hidden="true">
                  📁
                </span>
                <span>Dokumenti (uskoro)</span>
              </div>
            </div>

            {/* SISTEM */}
            <div>
              <div className="px-3 mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                Sistem
              </div>

              <div className="flex items-center rounded-md px-3 py-2 text-slate-500 cursor-default">
                <span className="mr-2" aria-hidden="true">
                  ⚙️
                </span>
                <span>Postavke (uskoro)</span>
              </div>

              <div className="flex items-center rounded-md px-3 py-2 text-slate-500 cursor-default">
                <span className="mr-2" aria-hidden="true">
                  ❓
                </span>
                <span>Pomoć (uskoro)</span>
              </div>
            </div>
          </nav>

          <div className="px-4 py-3 border-t border-slate-800 text-xs text-slate-500">
            <p>
              Tenant:{" "}
              <span className="font-mono text-slate-300">t-demo</span>
            </p>
          </div>
        </aside>

        {/* Main content */}
        <div className="flex-1 flex flex-col">
          <header className="h-14 border-b border-slate-200 bg-white flex items-center justify-between px-6">
            <div>
              <p className="text-sm font-medium text-slate-800">
                SP App – kontrolna tabla
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

              {/* Izlazne fakture */}
              <Route path="/invoices" element={<InvoicesListPage />} />
              <Route path="/invoices/new" element={<InvoiceCreatePage />} />
              <Route path="/invoices/:id" element={<InvoiceDetailPage />} />

              {/* Ulazne fakture */}
              <Route path="/input-invoices" element={<InputInvoicesPage />} />
              <Route
                path="/input-invoices/new"
                element={<InputInvoiceCreatePage />}
              />
              <Route
                path="/input-invoices/:id"
                element={<InputInvoiceDetailPage />}
              />

              {/* Kasa */}
              <Route path="/cash" element={<CashPage />} />

              {/* KPR */}
              <Route path="/kpr" element={<KprPage />} />

              {/* Promet */}
              <Route path="/promet" element={<PrometPage />} />

              {/* Porezi */}
              <Route path="/tax" element={<TaxPage />} />

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
