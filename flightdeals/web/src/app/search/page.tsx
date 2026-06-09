import { sessionUserId } from "@/lib/auth";
import { getPlan, PLAN_FEATURES } from "@/lib/plans";
import { airports, type AirportRow } from "@/lib/queries";
import SearchForm from "@/components/SearchForm";

export const dynamic = "force-dynamic";

export default async function SearchPage() {
  let isPro = false;
  let signedIn = false;
  try {
    const userId = await sessionUserId();
    if (userId) {
      signedIn = true;
      isPro = PLAN_FEATURES[await getPlan(userId)].liveSearchesPerMonth > 0;
    }
  } catch {}

  let airportList: AirportRow[] = [];
  try {
    airportList = await airports(true);
  } catch {}

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-3xl font-extrabold">Live search</h1>
      <p className="mt-2 text-slate-400">
        Real-time consolidated fares on any route — Google-Flights-grade data,
        metered per month. A Pro feature.
      </p>

      {!isPro ? (
        <div className="card mt-6 text-sm text-slate-300">
          {signedIn ? (
            <>
              Live search is included in <strong>Pro</strong>.{" "}
              <a href="/pricing" className="text-sky-400 hover:underline">Upgrade →</a>
            </>
          ) : (
            <>
              <a href="/signin" className="text-sky-400 hover:underline">Sign in</a> with a
              Pro plan to run live searches.
            </>
          )}
        </div>
      ) : null}

      <div className="mt-6">
        <SearchForm
          enabled={isPro}
          airports={airportList.map((a) => ({ iata: a.iata, name: a.name }))}
        />
      </div>
    </div>
  );
}
