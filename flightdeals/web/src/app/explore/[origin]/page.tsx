import Link from "next/link";
import { airports, exploreFrom, type AirportRow, type ExploreRow } from "@/lib/queries";

export const revalidate = 3600;

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso + "T00:00:00Z").toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
  });
}

export default async function ExplorePage({
  params,
}: {
  params: Promise<{ origin: string }>;
}) {
  const { origin } = await params;
  const code = origin.toUpperCase();

  let rows: ExploreRow[] = [];
  let airportList: AirportRow[] = [];
  try {
    [rows, airportList] = await Promise.all([exploreFrom(code), airports(true)]);
  } catch {}

  const current = airportList.find((a) => a.iata === code);

  return (
    <div>
      <h1 className="text-3xl font-extrabold">
        Where can I fly cheap from {current ? current.city : code}?
      </h1>
      <p className="mt-2 text-slate-400">
        Cheapest cached return fare per destination from the latest sweep. Green
        means it&apos;s under the route&apos;s typical price.
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        {airportList.map((a) => (
          <Link
            key={a.iata}
            href={`/explore/${a.iata}`}
            className={`badge ${a.iata === code ? "bg-sky-500 text-ink" : "border border-edge bg-panel text-slate-300"}`}
          >
            {a.iata}
          </Link>
        ))}
      </div>

      {rows.length === 0 ? (
        <div className="card mt-6 text-center text-slate-400">
          No cached fares for {code} yet — the nightly sweep will populate this page.
        </div>
      ) : (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((r) => {
            const price = Number(r.price_gbp);
            const median = r.median_gbp ? Number(r.median_gbp) : null;
            const below = median !== null && price < median;
            return (
              <div key={r.destination} className="card flex items-center justify-between">
                <div>
                  <h3 className="font-bold">{r.dest_name}</h3>
                  <p className="text-xs text-slate-500">
                    {code} → {r.destination} · {fmtDate(r.depart_date)}
                    {r.return_date ? `–${fmtDate(r.return_date)}` : ""}
                  </p>
                </div>
                <div className="text-right">
                  <p className={`text-xl font-extrabold ${below ? "text-emerald-400" : "text-slate-200"}`}>
                    £{Math.round(price)}
                  </p>
                  {median ? (
                    <p className="text-xs text-slate-500">typ. £{Math.round(median)}</p>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
