import { redirect } from "next/navigation";
import { auth, signOut } from "@/lib/auth";
import { getPlan, PLAN_FEATURES } from "@/lib/plans";
import { airports, type AirportRow } from "@/lib/queries";
import AlertManager from "@/components/AlertManager";

export const dynamic = "force-dynamic";

export default async function AccountPage() {
  const session = await auth().catch(() => null);
  if (!session?.user) redirect("/signin");

  const userId = Number(session.user.id);
  const plan = await getPlan(userId);
  const features = PLAN_FEATURES[plan];

  let airportList: AirportRow[] = [];
  try {
    airportList = await airports(true);
  } catch {}

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-extrabold">Account</h1>
        <form
          action={async () => {
            "use server";
            await signOut({ redirectTo: "/" });
          }}
        >
          <button type="submit" className="btn-ghost text-sm">Sign out</button>
        </form>
      </div>

      <div className="card mt-6">
        <p className="text-sm text-slate-400">Signed in as</p>
        <p className="font-semibold">{session.user.email}</p>
        <div className="mt-3 flex items-center gap-3">
          <span className="badge bg-sky-500/15 text-sky-300">
            {features.label} plan
          </span>
          {plan === "free" ? (
            <a href="/pricing" className="text-sm text-sky-400 hover:underline">
              Upgrade for regional airports &amp; alerts →
            </a>
          ) : null}
        </div>
      </div>

      <h2 className="mt-8 text-xl font-bold">Saved-route alerts</h2>
      <p className="mt-1 text-sm text-slate-400">
        {features.alerts > 0
          ? `Your plan includes ${features.alerts} active alerts. We email you the moment a matching below-baseline fare appears.`
          : "Alerts are included in Plus and Pro."}
      </p>
      <div className="mt-4">
        <AlertManager
          canCreate={features.alerts > 0}
          airports={airportList.map((a) => ({ iata: a.iata, name: a.name }))}
        />
      </div>
    </div>
  );
}
