/**
 * Live consolidated search — metered, Pro only.
 *
 * Provider adapter pattern (handover §5: APIs / delegated scraping only,
 * never scrape consumer flight sites from our own IP):
 *  - serpapi: Google Flights via SerpApi (gold-standard data, ~$50/1k)
 *  - apify:   Google Flights actor on Apify's proxied infra (~$8-12/1k)
 * Selected by LIVE_SEARCH_PROVIDER.
 */

export interface LiveSearchParams {
  origin: string;
  destination: string;
  departDate: string; // YYYY-MM-DD
  returnDate?: string;
}

export interface LiveFlight {
  price: number;
  currency: string;
  airline: string;
  departTime: string;
  arriveTime: string;
  durationMinutes: number;
  stops: number;
  bookingHint: string | null;
}

export class LiveSearchUnavailable extends Error {}

export async function liveSearch(params: LiveSearchParams): Promise<LiveFlight[]> {
  const provider = process.env.LIVE_SEARCH_PROVIDER ?? "serpapi";
  if (provider === "serpapi") return serpapiSearch(params);
  if (provider === "apify") return apifySearch(params);
  throw new LiveSearchUnavailable(`unknown provider: ${provider}`);
}

/* eslint-disable @typescript-eslint/no-explicit-any */

async function serpapiSearch(p: LiveSearchParams): Promise<LiveFlight[]> {
  const key = process.env.SERPAPI_KEY;
  if (!key) throw new LiveSearchUnavailable("SERPAPI_KEY not configured");
  const qs = new URLSearchParams({
    engine: "google_flights",
    departure_id: p.origin,
    arrival_id: p.destination,
    outbound_date: p.departDate,
    currency: "GBP",
    hl: "en-GB",
    api_key: key,
    ...(p.returnDate ? { return_date: p.returnDate, type: "1" } : { type: "2" }),
  });
  const resp = await fetch(`https://serpapi.com/search.json?${qs}`, {
    signal: AbortSignal.timeout(30_000),
  });
  if (!resp.ok) throw new LiveSearchUnavailable(`serpapi ${resp.status}`);
  const body: any = await resp.json();
  const flights = [...(body.best_flights ?? []), ...(body.other_flights ?? [])];
  return flights.slice(0, 12).map((f: any): LiveFlight => {
    const legs = f.flights ?? [];
    const first = legs[0] ?? {};
    const last = legs[legs.length - 1] ?? {};
    return {
      price: Number(f.price ?? 0),
      currency: "GBP",
      airline: first.airline ?? "—",
      departTime: first.departure_airport?.time ?? "",
      arriveTime: last.arrival_airport?.time ?? "",
      durationMinutes: Number(f.total_duration ?? 0),
      stops: Math.max(legs.length - 1, 0),
      bookingHint: null, // SerpApi has no booking links; user books via Google Flights
    };
  });
}

async function apifySearch(p: LiveSearchParams): Promise<LiveFlight[]> {
  const token = process.env.APIFY_TOKEN;
  const actor = process.env.APIFY_ACTOR; // e.g. "username~google-flights-scraper"
  if (!token || !actor) throw new LiveSearchUnavailable("APIFY_TOKEN/APIFY_ACTOR not configured");
  const resp = await fetch(
    `https://api.apify.com/v2/acts/${actor}/run-sync-get-dataset-items?token=${token}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        origin: p.origin,
        destination: p.destination,
        departureDate: p.departDate,
        returnDate: p.returnDate ?? null,
        currency: "GBP",
      }),
      signal: AbortSignal.timeout(90_000),
    }
  );
  if (!resp.ok) throw new LiveSearchUnavailable(`apify ${resp.status}`);
  const items: any[] = await resp.json();
  return items.slice(0, 12).map((it: any): LiveFlight => ({
    price: Number(it.price ?? it.totalPrice ?? 0),
    currency: it.currency ?? "GBP",
    airline: it.airline ?? it.carrier ?? "—",
    departTime: it.departureTime ?? it.departure_time ?? "",
    arriveTime: it.arrivalTime ?? it.arrival_time ?? "",
    durationMinutes: Number(it.durationMinutes ?? it.duration ?? 0),
    stops: Number(it.stops ?? 0),
    bookingHint: it.bookingUrl ?? it.url ?? null,
  }));
}
