import { useEffect, useMemo, useState } from "react";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function Cashbook() {
  const [tenant, setTenant] = useState("acme");          // podrazumijevano
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [kind, setKind] = useState("income");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [items, setItems] = useState([]);
  const [balance, setBalance] = useState(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  const y = useMemo(() => Number(date.slice(0, 4)), [date]);
  const m = useMemo(() => Number(date.slice(5, 7)), [date]);

  async function loadEntries() {
    const res = await fetch(`${API}/cash/entries?tenant=${encodeURIComponent(tenant)}`);
    const data = await res.json();
    setItems(Array.isArray(data.items) ? data.items : []);
  }

  async function loadSummary() {
    const url = `${API}/cash/summary?tenant=${encodeURIComponent(tenant)}&year=${y}&month=${m}`;
    const res = await fetch(url);
    const data = await res.json();
    setBalance(data.balance ?? null);
  }

  async function onCreate(e) {
    e.preventDefault();
    setLoading(true);
    setMsg("");
    try {
      const payload = {
        tenant_code: tenant,
        entry_date: date,
        kind,
        amount: parseFloat(amount),
        description,
      };
      const res = await fetch(`${API}/cash/entries`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.text();
        throw new Error(err || `HTTP ${res.status}`);
      }
      await loadEntries();
      await loadSummary();
      setAmount("");
      setDescription("");
      setMsg("Upisano ✅");
    } catch (err) {
      setMsg(`Greška: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadEntries();
    loadSummary();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenant, y, m]);

  return (
    <section style={{ marginTop: 32 }}>
      <h2>Cashbook</h2>

      <div style={{ marginBottom: 12 }}>
        <label style={{ marginRight: 8 }}>
          tenant:
          <input
            value={tenant}
            onChange={(e) => setTenant(e.target.value)}
            style={{ marginLeft: 6 }}
          />
        </label>

        <label style={{ marginRight: 8 }}>
          mjesec:
          <input
            type="month"
            value={`${y}-${String(m).padStart(2, "0")}`}
            onChange={(e) => {
              const [yy, mm] = e.target.value.split("-");
              // zadržimo dan iz postojećeg datuma
              const day = date.slice(8, 10);
              setDate(`${yy}-${mm}-${day}`);
            }}
            style={{ marginLeft: 6 }}
          />
        </label>
        {balance !== null && (
          <strong style={{ marginLeft: 12 }}>
            Saldo ({y}-{String(m).padStart(2,"0")}): {balance}
          </strong>
        )}
      </div>

      <form onSubmit={onCreate} style={{ display: "grid", gap: 8, maxWidth: 600, gridTemplateColumns: "140px 120px 120px 1fr 120px" }}>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        <select value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="income">income</option>
          <option value="expense">expense</option>
        </select>
        <input
          type="number"
          step="0.01"
          placeholder="iznos"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          required
        />
        <input
          placeholder="opis"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <button disabled={loading} type="submit">
          {loading ? "Spremam..." : "Dodaj"}
        </button>
      </form>
      {msg && <div style={{ marginTop: 6 }}>{msg}</div>}

      <div style={{ marginTop: 16 }}>
        <table style={{ borderCollapse: "collapse", width: "100%", maxWidth: 900 }}>
          <thead>
            <tr>
              <th style={th}>Datum</th>
              <th style={th}>Vrsta</th>
              <th style={th}>Iznos</th>
              <th style={th}>Opis</th>
              <th style={th}>ID</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.id}>
                <td style={td}>{it.entry_date}</td>
                <td style={td}>{it.kind}</td>
                <td style={td}>{it.amount}</td>
                <td style={td}>{it.description}</td>
                <td style={td}>{it.id}</td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td style={td} colSpan={5}>Nema stavki za tenant: {tenant}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

const th = { borderBottom: "1px solid #ddd", textAlign: "left", padding: "6px 8px" };
const td = { borderBottom: "1px solid #eee", padding: "6px 8px", verticalAlign: "top" };
