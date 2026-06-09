import Link from "next/link";
import DealCard from "@/components/DealCard";
import { sessionUserId } from "@/lib/auth";
import { getPlan, PLAN_FEATURES } from "@/lib/plans";
import { airports, currentDeals, type AirportRow, type DealRow } from "@/lib/queries";

export const dynamic = "force-dynamic";

export default async function DealsPage({
  searchParams,
}: {
  searchParams: Promise<{ origin?: string }>;
}) {
  const { origin } = await searchParams;

  let includePlus = false;
  try {
    const userId = await sessionUserId();
    if (userId) includePlus = PLAN_FEATURES[await getPlan(userId)].regionalAirports;
  } catch {}

  let deals: DealRow[] = [];
  let airportList: AirportRow[] = [];
  try {
    [deals, airportList] = await Promise.all([
      currentDeals({ includePlus, origin, limit: 60 }),
      airports(true),
    ]);
  } catch {}

  return (
    <div>
      <h1 className="text-3xl font-extrabold">Today&apos;s deals</h1>
      <p className="mt-2 text-slate-400">
        Every fare here is below its route baseline or under our exceptional-fare floor.
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        <Link href="/deals" className={`badge ${!origin ? "bg-sky-500 text-ink" : "bg-panel text-slate-300 border border-edge"}`}>
          All airports
        </Link>
        {airportList.map((a) => {
          const locked = a.tier === "plus" && !includePlus;
          return locked ? (
            <Link key={a.iata} href="/pricing" title={`${a.name} — Plus members`}
              className="badge border border-edge bg-panel text-slate-500">
              {a.iata} 🔒
            </Link>
          ) : (
            <Link key={a.iata} href={`/deals?origin=${a.iata}`}
              className={`badge ${origin === a.iata ? "bg-sky-500 text-ink" : "border border-edge bg-panel text-slate-300"}`}>
              {a.iata}
            </Link>
          );
        })}
      </div>

      {!includePlus ? (
        <p className="mt-3 text-sm text-slate-500">
          🔒 Regional airports (Bristol, Edinburgh, Glasgow…) are included in{" "}
          <Link href="/pricing" className="text-sky-400 hover:underline">Plus</Link>.
        </p>
      ) : null}

      {deals.length === 0 ? (
        <div className="card mt-6 text-center text-slate-400">
          No live deals match right now. The sweep runs nightly — new fares land daily.
        </div>
      ) : (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {deals.map((d) => (
            <DealCard key={d.id} deal={d} />
          ))}
        </div>
      )}
    </div>
  );
}
