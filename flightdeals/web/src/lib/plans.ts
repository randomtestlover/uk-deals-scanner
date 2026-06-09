import { pool } from "./db";

export type Plan = "free" | "plus" | "pro";

export const PLAN_FEATURES: Record<
  Plan,
  { label: string; alerts: number; liveSearchesPerMonth: number; regionalAirports: boolean }
> = {
  free: { label: "Free", alerts: 0, liveSearchesPerMonth: 0, regionalAirports: false },
  plus: { label: "Plus", alerts: 5, liveSearchesPerMonth: 0, regionalAirports: true },
  pro: { label: "Pro", alerts: 20, liveSearchesPerMonth: 100, regionalAirports: true },
};

const ACTIVE_STATUSES = new Set(["active", "trialing"]);

export async function getPlan(userId: number): Promise<Plan> {
  const { rows } = await pool.query(
    "SELECT plan, status FROM subscriptions WHERE user_id = $1",
    [userId]
  );
  const sub = rows[0];
  if (!sub || !ACTIVE_STATUSES.has(sub.status)) return "free";
  return sub.plan as Plan;
}

/**
 * Atomically consume one live search from the user's monthly quota.
 * Returns remaining searches, or null when the quota is exhausted.
 */
export async function consumeLiveSearch(
  userId: number,
  quota: number
): Promise<number | null> {
  const period = new Date().toISOString().slice(0, 7); // YYYY-MM
  const { rows } = await pool.query(
    `INSERT INTO search_usage (user_id, period, used)
     VALUES ($1, $2, 1)
     ON CONFLICT (user_id, period)
       DO UPDATE SET used = search_usage.used + 1
       WHERE search_usage.used < $3
     RETURNING used`,
    [userId, period, quota]
  );
  if (rows.length === 0) return null;
  return Math.max(quota - rows[0].used, 0);
}
