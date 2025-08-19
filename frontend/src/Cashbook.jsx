import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function Cashbook() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  async function load() {
    try {
      setLoading(true);
      setErr(null);
      const res = await fetch(`${API_URL}/cash`);
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
    load();
  }, []);

  return (
    <div style={{ padding: "1rem", maxWidth: 900, margin: "0 auto" }}>
      <h2>Cashbook</h2>
      <div style={{ marginBottom: "0.75rem" }}>
        <button onClick={load}>Reload</button>
      </div>

      {loading && <div>Učitavam…</div>}
      {err && <div style={{ color: "red" }}>Greška: {err}</div>}

      {!loading && !err && (
        <>
          <div style={{ fontSize: 14, opacity: 0.8, marginBottom: "0.5rem" }}>
            (Stub komponenta – PATCH/DELETE dugmad dodajemo poslije)
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
