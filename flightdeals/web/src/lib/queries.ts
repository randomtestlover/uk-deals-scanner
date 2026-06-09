import { pool } from "./db";

export interface DealRow {
  id: number;
  origin: string;
  destination: string;
  dest_name: string;
  band: string;
  tier: string;
  price_gbp: string;
  baseline_gbp: string | null;
  discount_pct: string | null;
  trigger: "sale" | "floor";
  depart_date: string;
  return_date: string | null;
  airline: string | null;
  found_at: string;
}

export interface ExploreRow {
  destination: string;
  dest_name: string;
  band: string;
  price_gbp: string;
  depart_date: string;
  return_date: string | null;
  median_gbp: string | null;
}

export interface AirportRow {
  iata: string;
  name: string;
  city: string;
  tier: "free" | "plus";
}

/** Live (unexpired) deals, newest discount first. Free tier sees hub routes only. */
export async function currentDeals(opts: {
  includePlus: boolean;
  origin?: string;
  limit?: number;
}): Promise<DealRow[]> {
  const params: unknown[] = [];
  let where = "d.expires_at > now()";
  if (!opts.includePlus) where += " AND r.tier = 'free'";
  if (opts.origin) {
    params.push(opts.origin.toUpperCase());
    where += ` AND r.origin = $${params.length}`;
  }
  params.push(opts.limit ?? 30);
  const { rows } = await pool.query(
    `SELECT d.id, r.origin, r.destination, r.dest_name, r.band, r.tier,
            d.price_gbp, d.baseline_gbp, d.discount_pct, d.trigger,
            d.depart_date::text, d.return_date::text, d.airline, d.found_at
     FROM deals d JOIN routes r ON r.id = d.route_id
     WHERE ${where}
     ORDER BY d.found_at DESC, d.discount_pct DESC NULLS LAST
     LIMIT $${params.length}`,
    params
  );
  return rows;
}

/** Cheapest cached fare per destination from an origin (last 36h sweep data). */
export async function exploreFrom(origin: string): Promise<ExploreRow[]> {
  const { rows } = await pool.query(
    `SELECT DISTINCT ON (r.destination)
            r.destination, r.dest_name, r.band,
            ps.price_gbp, ps.depart_date::text, ps.return_date::text,
            b.median_gbp
     FROM price_snapshots ps
     JOIN routes r ON r.id = ps.route_id
     LEFT JOIN route_baselines b ON b.route_id = r.id
     WHERE r.origin = $1 AND ps.found_at > now() - interval '36 hours'
     ORDER BY r.destination, ps.price_gbp ASC`,
    [origin.toUpperCase()]
  );
  return rows.sort((a, b) => Number(a.price_gbp) - Number(b.price_gbp));
}

export async function airports(includePlus = true): Promise<AirportRow[]> {
  const { rows } = await pool.query(
    `SELECT iata, name, city, tier FROM airports
     WHERE active ${includePlus ? "" : "AND tier = 'free'"}
     ORDER BY tier, iata`
  );
  return rows;
}

export async function dealById(id: number): Promise<
  (DealRow & { deep_link: string | null }) | null
> {
  const { rows } = await pool.query(
    `SELECT d.id, r.origin, r.destination, r.dest_name, r.band, r.tier,
            d.price_gbp, d.baseline_gbp, d.discount_pct, d.trigger,
            d.depart_date::text, d.return_date::text, d.airline, d.found_at,
            d.deep_link
     FROM deals d JOIN routes r ON r.id = d.route_id
     WHERE d.id = $1`,
    [id]
  );
  return rows[0] ?? null;
}

export async function recordClick(
  dealId: number,
  userId: number | null,
  referer: string | null
): Promise<void> {
  await pool.query(
    "INSERT INTO clicks (deal_id, user_id, referer) VALUES ($1, $2, $3)",
    [dealId, userId, referer]
  );
}
