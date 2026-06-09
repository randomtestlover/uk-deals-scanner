"use client";

import { useState } from "react";

interface LiveFlight {
  price: number;
  currency: string;
  airline: string;
  departTime: string;
  arriveTime: string;
  durationMinutes: number;
  stops: number;
  bookingHint: string | null;
}

export default function SearchForm({
  enabled,
  airports,
}: {
  enabled: boolean;
  airports: { iata: string; name: string }[];
}) {
  const [origin, setOrigin] = useState(airports[0]?.iata ?? "LHR");
  const [destination, setDestination] = useState("");
  const [departDate, setDepartDate] = useState("");
  const [returnDate, setReturnDate] = useState("");
  const [flights, setFlights] = useState<LiveFlight[] | null>(null);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setFlights(null);
    try {
      const resp = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          origin,
          destination: destination.trim(),
          departDate,
          returnDate: returnDate || undefined,
        }),
      });
      const body = await resp.json();
      if (!resp.ok) {
        setError(body.error ?? "Search failed");
        return;
      }
      setFlights(body.flights);
      setRemaining(body.remaining);
    } catch {
      setError("Network error — try again");
    } finally {
      setBusy(false);
    }
  }

  const fmtDuration = (m: number) =>
    m > 0 ? `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m` : "—";

  return (
    <div className="space-y-4">
      <form onSubmit={run} className="card grid gap-3 sm:grid-cols-5">
        <div>
          <label className="mb-1 block text-xs text-slate-400">From</label>
          <select value={origin} onChange={(e) => setOrigin(e.target.value)} className="input">
            {airports.map((a) => (
              <option key={a.iata} value={a.iata}>{a.iata}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-400">To (IATA)</label>
          <input
            value={destination}
            onChange={(e) => setDestination(e.target.value.toUpperCase())}
            maxLength={3}
            required
            placeholder="BCN"
            className="input"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-400">Depart</label>
          <input type="date" value={departDate} required
            onChange={(e) => setDepartDate(e.target.value)} className="input" />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-400">Return (opt.)</label>
          <input type="date" value={returnDate}
            onChange={(e) => setReturnDate(e.target.value)} className="input" />
        </div>
        <div className="flex items-end">
          <button type="submit" disabled={!enabled || busy}
            className="btn-primary w-full disabled:opacity-50">
            {busy ? "Searching…" : "Search"}
          </button>
        </div>
      </form>

      {error ? <p className="text-sm text-rose-400">{error}</p> : null}
      {remaining !== null ? (
        <p className="text-xs text-slate-500">{remaining} live searches left this month</p>
      ) : null}

      {flights ? (
        flights.length === 0 ? (
          <div className="card text-center text-slate-400">No flights found.</div>
        ) : (
          <ul className="space-y-2">
            {flights.map((f, i) => (
              <li key={i} className="card flex items-center justify-between py-3">
                <div className="text-sm">
                  <p className="font-semibold">{f.airline}</p>
                  <p className="text-slate-400">
                    {f.departTime} → {f.arriveTime} · {fmtDuration(f.durationMinutes)} ·{" "}
                    {f.stops === 0 ? "direct" : `${f.stops} stop${f.stops > 1 ? "s" : ""}`}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xl font-extrabold text-sky-400">£{Math.round(f.price)}</p>
                  {f.bookingHint ? (
                    <a href={f.bookingHint} target="_blank" rel="noopener"
                      className="text-xs text-sky-400 hover:underline">
                      Book →
                    </a>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )
      ) : null}
    </div>
  );
}
