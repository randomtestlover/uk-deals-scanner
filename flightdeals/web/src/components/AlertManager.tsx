"use client";

import { useCallback, useEffect, useState } from "react";

interface Alert {
  id: number;
  origin: string;
  destination: string | null;
  max_price_gbp: string | null;
  active: boolean;
}

export default function AlertManager({
  canCreate,
  airports,
}: {
  canCreate: boolean;
  airports: { iata: string; name: string }[];
}) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [origin, setOrigin] = useState(airports[0]?.iata ?? "LHR");
  const [destination, setDestination] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const resp = await fetch("/api/alerts");
    if (resp.ok) {
      const body = await resp.json();
      setAlerts(body.alerts);
    }
  }, []);

  useEffect(() => {
    load().catch(() => {});
  }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const resp = await fetch("/api/alerts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          origin,
          destination: destination.trim() || null,
          max_price_gbp: maxPrice ? Number(maxPrice) : null,
        }),
      });
      const body = await resp.json();
      if (!resp.ok) {
        setError(body.error ?? "Could not save alert");
        return;
      }
      setDestination("");
      setMaxPrice("");
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    await fetch(`/api/alerts?id=${id}`, { method: "DELETE" });
    await load();
  }

  return (
    <div className="space-y-4">
      {canCreate ? (
        <form onSubmit={create} className="card grid gap-3 sm:grid-cols-4">
          <div>
            <label className="mb-1 block text-xs text-slate-400">From</label>
            <select value={origin} onChange={(e) => setOrigin(e.target.value)} className="input">
              {airports.map((a) => (
                <option key={a.iata} value={a.iata}>
                  {a.iata} — {a.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">To (optional IATA)</label>
            <input
              value={destination}
              onChange={(e) => setDestination(e.target.value.toUpperCase())}
              maxLength={3}
              placeholder="any"
              className="input"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Max £ (optional)</label>
            <input
              value={maxPrice}
              onChange={(e) => setMaxPrice(e.target.value.replace(/[^\d]/g, ""))}
              inputMode="numeric"
              placeholder="any"
              className="input"
            />
          </div>
          <div className="flex items-end">
            <button type="submit" disabled={busy} className="btn-primary w-full disabled:opacity-50">
              {busy ? "Saving…" : "Add alert"}
            </button>
          </div>
          {error ? <p className="col-span-full text-xs text-rose-400">{error}</p> : null}
        </form>
      ) : (
        <div className="card text-sm text-slate-400">
          <a href="/pricing" className="text-sky-400 hover:underline">Upgrade to Plus</a>{" "}
          to set saved-route alerts.
        </div>
      )}

      {alerts.length > 0 ? (
        <ul className="space-y-2">
          {alerts.map((a) => (
            <li key={a.id} className="card flex items-center justify-between py-3">
              <span className="text-sm">
                <strong>{a.origin}</strong> → {a.destination ?? "anywhere"}
                {a.max_price_gbp ? ` · under £${Math.round(Number(a.max_price_gbp))}` : ""}
              </span>
              <button onClick={() => remove(a.id)} className="text-xs text-rose-400 hover:underline">
                Remove
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
