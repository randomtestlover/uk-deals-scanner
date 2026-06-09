import type { DealRow } from "@/lib/queries";

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso + "T00:00:00Z").toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

export default function DealCard({ deal }: { deal: DealRow }) {
  const pct = deal.discount_pct ? Math.round(Number(deal.discount_pct)) : null;
  return (
    <a href={`/go/${deal.id}`} target="_blank" rel="noopener" className="card block">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm text-slate-400">
            {deal.origin} → {deal.destination}
          </p>
          <h3 className="mt-0.5 text-lg font-bold">{deal.dest_name}</h3>
        </div>
        <div className="text-right">
          <p className="text-2xl font-extrabold text-sky-400">
            £{Math.round(Number(deal.price_gbp))}
          </p>
          <p className="text-xs text-slate-500">return</p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {deal.trigger === "floor" ? (
          <span className="badge bg-rose-500/15 text-rose-300">🔥 exceptional fare</span>
        ) : null}
        {pct ? (
          <span className="badge bg-emerald-500/15 text-emerald-300">
            {pct}% below typical
            {deal.baseline_gbp ? ` £${Math.round(Number(deal.baseline_gbp))}` : ""}
          </span>
        ) : null}
        {deal.tier === "plus" ? (
          <span className="badge bg-amber-500/15 text-amber-300">regional</span>
        ) : null}
      </div>
      <p className="mt-3 text-sm text-slate-400">
        Out {fmtDate(deal.depart_date)}
        {deal.return_date ? ` · Back ${fmtDate(deal.return_date)}` : " · one-way"}
        {deal.airline ? ` · ${deal.airline}` : ""}
      </p>
    </a>
  );
}
