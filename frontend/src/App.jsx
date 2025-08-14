import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function App() {
  const [health, setHealth] = useState("loading...");
  const [tenants, setTenants] = useState([]);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadHealth() {
    try {
      const r = await fetch(`${API_URL}/health`);
      const j = await r.json();
      setHealth(j.status || "ok");
    } catch (e) {
      setHealth("error");
      console.error(e);
    }
  }

  async function loadTenants() {
    try {
      const r = await fetch(`${API_URL}/tenants`);
      if (!r.ok) throw new Error(`Fetch tenants failed: ${r.status}`);
      const j = await r.json();
      setTenants(j);
    } catch (e) {
      console.error(e);
      setError("Greška pri čitanju tenant-a.");
    }
  }

  useEffect(() => {
    loadHealth();
    loadTenants();
  }, []);

  async function onCreate(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const r = await fetch(`${API_URL}/tenants`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, name }),
      });
      if (!r.ok) {
        const t = await r.text();
        throw new Error(t || `Create failed: ${r.status}`);
      }
      setCode("");
      setName("");
      await loadTenants();
    } catch (e) {
      setError(e.message);
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function onDelete(id) {
    if (!confirm("Obriši tenant?")) return;
    try {
      const r = await fetch(`${API_URL}/tenants/${id}`, { method: "DELETE" });
      if (!r.ok && r.status !== 204) {
        const t = await r.text();
        throw new Error(t || `Delete failed: ${r.status}`);
      }
      await loadTenants();
    } catch (e) {
      setError(e.message);
      console.error(e);
    }
  }

  return (
    <div style={{ padding: "2rem", fontFamily: "system-ui, sans-serif", lineHeight: 1.6 }}>
      <h1>SP App (frontend)</h1>

      {/* HEALTH */}
      <p><b>API_URL:</b> {API_URL}</p>
      <p><b>API /health:</b> {health}</p>

      <hr />

      {/* TENANTS LIST + CREATE */}
      <h2>Tenants</h2>

      <form onSubmit={onCreate} style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
        <label>
          code<br />
          <input value={code} onChange={e => setCode(e.target.value)} required placeholder="npr. acme" />
        </label>
        <label>
          name<br />
          <input value={name} onChange={e => setName(e.target.value)} required placeholder="npr. ACME d.o.o." />
        </label>
        <button disabled={loading}>{loading ? "Spašavam..." : "Create"}</button>
      </form>

      {error && <p style={{ color: "crimson" }}>{error}</p>}

      <ul style={{ paddingLeft: 0, listStyle: "none", marginTop: 12 }}>
        {tenants.map(t => (
          <li key={t.id} style={{ display: "flex", gap: 16, alignItems: "center", padding: "6px 0", borderBottom: "1px solid #eee" }}>
            <span style={{ minWidth: 120, fontFamily: "ui-monospace, monospace" }}>{t.code}</span>
            <span style={{ minWidth: 260 }}>{t.name}</span>
            <button onClick={() => onDelete(t.id)} style={{ marginLeft: "auto" }}>Delete</button>
          </li>
        ))}
        {tenants.length === 0 && <li>Nema tenant-a.</li>}
      </ul>
    </div>
  );
}
