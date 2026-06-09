import Link from "next/link";
import DealCard from "@/components/DealCard";
import { currentDeals, type DealRow } from "@/lib/queries";

export const revalidate = 600; // cached layer: free tier costs ~nothing to serve

export default async function Home() {
  let deals: DealRow[] = [];
  try {
    deals = await currentDeals({ includePlus: false, limit: 9 });
  } catch {
    // DB unavailable (e.g. at build time) — render the empty state.
  }

  return (
    <div>
      <section className="py-10 text-center">
        <h1 className="mx-auto max-w-3xl text-4xl font-extrabold tracking-tight sm:text-5xl">
          Flight deals that are{" "}
          <span className="text-sky-400">actually below the normal price</span>
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-slate-400">
          We sweep fares from UK airports every day, compare them against each
          route&apos;s 90-day baseline, and only show you the ones that beat it. No
          ads dressed up as deals.
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <Link href="/deals" className="btn-primary">Browse today&apos;s deals</Link>
          <Link href="/pricing" className="btn-ghost">Unlock regional airports</Link>
        </div>
      </section>

      <section className="py-6">
        <div className="mb-4 flex items-end justify-between">
          <h2 className="text-xl font-bold">Latest deals from the big UK hubs</h2>
          <Link href="/deals" className="text-sm text-sky-400 hover:underline">
            See all →
          </Link>
        </div>
        {deals.length === 0 ? (
          <div className="card text-center text-slate-400">
            The deal board is refreshing — check back shortly, or join the free
            Telegram channel to get them pushed to you.
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {deals.map((d) => (
              <DealCard key={d.id} deal={d} />
            ))}
          </div>
        )}
      </section>

      <section className="grid gap-4 py-10 sm:grid-cols-3">
        <div className="card">
          <h3 className="font-bold">📊 Baseline-checked</h3>
          <p className="mt-2 text-sm text-slate-400">
            A deal only appears when the fare is at least 25% under its rolling
            90-day median — or under our error-fare floor.
          </p>
        </div>
        <div className="card">
          <h3 className="font-bold">🛫 Regional airports</h3>
          <p className="mt-2 text-sm text-slate-400">
            Bristol, Birmingham, Leeds, Newcastle, Edinburgh, Glasgow and more —
            underserved by London-centric deal sites. Plus members get them all.
          </p>
        </div>
        <div className="card">
          <h3 className="font-bold">⚡ Live search</h3>
          <p className="mt-2 text-sm text-slate-400">
            Pro members run real-time consolidated searches on any route, with
            our below-baseline detection applied to the results.
          </p>
        </div>
      </section>
    </div>
  );
}
