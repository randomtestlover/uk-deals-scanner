import { auth } from "@/lib/auth";
import CheckoutButton from "@/components/CheckoutButton";

export const dynamic = "force-dynamic";

const TIERS = [
  {
    plan: null,
    name: "Free",
    price: "£0",
    blurb: "The deal board and Telegram channel",
    features: [
      "Below-baseline deals from LHR, LGW, STN, LTN, MAN",
      "Explore cheapest destinations",
      "Free Telegram channel",
    ],
  },
  {
    plan: "plus" as const,
    name: "Plus",
    price: "£4/mo",
    blurb: "Your airports, your alerts",
    features: [
      "Everything in Free",
      "Regional airports: BHX, BRS, EMA, LBA, NCL, EDI, GLA",
      "5 saved-route alerts (email + Telegram DM)",
      "Wider date flexibility",
    ],
  },
  {
    plan: "pro" as const,
    name: "Pro",
    price: "£9/mo",
    blurb: "Real-time search on any route",
    features: [
      "Everything in Plus",
      "100 live consolidated searches / month",
      "20 saved-route alerts",
      "Widest search window",
    ],
  },
];

export default async function PricingPage() {
  const session = await auth().catch(() => null);
  const signedIn = Boolean(session?.user);

  return (
    <div>
      <h1 className="text-center text-3xl font-extrabold">Pricing</h1>
      <p className="mx-auto mt-2 max-w-xl text-center text-slate-400">
        Free users get the big hubs. Members get the airports the London-centric
        deal sites ignore — and the tools to act fast.
      </p>
      <div className="mt-8 grid gap-4 md:grid-cols-3">
        {TIERS.map((t) => (
          <div key={t.name} className={`card flex flex-col ${t.plan === "plus" ? "border-sky-600" : ""}`}>
            <h2 className="text-xl font-bold">{t.name}</h2>
            <p className="mt-1 text-3xl font-extrabold text-sky-400">{t.price}</p>
            <p className="mt-1 text-sm text-slate-400">{t.blurb}</p>
            <ul className="mt-4 flex-1 space-y-2 text-sm text-slate-300">
              {t.features.map((f) => (
                <li key={f}>✓ {f}</li>
              ))}
            </ul>
            <div className="mt-5">
              {t.plan ? (
                <CheckoutButton plan={t.plan} signedIn={signedIn} />
              ) : (
                <a href="/deals" className="btn-ghost w-full">Browse deals</a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
