import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const RESOURCE_PATH = "/cash/"; // obavezno trailing slash

export default function Cashbook() {
  const [tenants, setTenants] = useState([]);
  const [tenantCode, setTenantCode] = useState("");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  async function loadTenants() {
    try {
      setErr(null);
      const res = await fetch(`${API_URL}/tenants`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setTenants(Array.isArray(data) ? data : []);
      if (Array.isArray(data) && data.length > 0 && !tenantCode) {
        setTenantCode(data[0].code);
      }
    } catch (e) {
      setErr(e.message || String(e));
    }
  }

  async function loadCash(code) {
    const useCode = code || tenantCode;
    if (!useCode) {
      setRows([]);
      setErr("Nije odabran tenant (X-Tenant-Code).");
      return;
    }
    try {
      setLoading(true);
      setErr(null);
      const res = await fetch(`${API_URL}${RESOURCE_PATH}`, {
        headers: { "X-Tenant-Code": useCode },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRows(Array.isArray(data) ? data : []);
    } catch (e) {
      setErr(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTenants();
  }, []);

  useEffect(() => {
    if (tenantCode) loadCash(tenantCode);
  }, [tenantCode]);

  return (
    <div style={{ padding: "1rem", maxWidth: 900, margin: "0 auto" }}>
      <h2>Cashbook</h2>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12 }}>
        <label htmlFor="tenantSel" style={{ fontSize: 14 }}>Tenant:</label>
        <select
          id="tenantSel"
          value={tenantCode}
          onChange={(e) => setTenantCode(e.target.value)}
          style={{ padding: "6px 8px" }}
        >
          <option value="">-- izaberi --</option>
          {tenants.map((t) => (
            <option key={t.code} value={t.code}>
              {t.code} — {t.name}
            </option>
          ))}
        </select>
        <button onClick={() => loadCash()}>Reload</button>
      </div>

      {loading && <div>Učitavam…</div>}
      {err && <div style={{ color: "red" }}>Greška: {err}</div>}

      {!loading && !err && (
        <>
          <div style={{ fontSize: 14, opacity: 0.8, marginBottom: "0.5rem" }}>
            (Stub komponenta — PATCH/DELETE dugmad dodajemo poslije)
          </div>
          <pre
            style={{
              background: "#f5f5f5",
              padding: "0.75rem",
              borderRadius: 8,
              overflowX: "auto",
            }}
          >
            {JSON.stringify(rows, null, 2)}
          </pre>
        </>
      )}
    </div>
  );
}
