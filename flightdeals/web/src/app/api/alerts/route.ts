import { NextRequest, NextResponse } from "next/server";
import { pool } from "@/lib/db";
import { sessionUserId } from "@/lib/auth";
import { getPlan, PLAN_FEATURES } from "@/lib/plans";

export const dynamic = "force-dynamic";

const IATA = /^[A-Za-z]{3}$/;

export async function GET() {
  const userId = await sessionUserId();
  if (!userId) return NextResponse.json({ error: "Sign in required" }, { status: 401 });
  const { rows } = await pool.query(
    `SELECT id, origin, destination, max_price_gbp, channels, active, created_at
     FROM alerts WHERE user_id = $1 ORDER BY created_at DESC`,
    [userId]
  );
  return NextResponse.json({ alerts: rows });
}

export async function POST(req: NextRequest) {
  const userId = await sessionUserId();
  if (!userId) return NextResponse.json({ error: "Sign in required" }, { status: 401 });

  const plan = await getPlan(userId);
  const maxAlerts = PLAN_FEATURES[plan].alerts;
  if (maxAlerts === 0) {
    return NextResponse.json(
      { error: "Saved-route alerts are a Plus feature", upgrade: "/pricing" },
      { status: 403 }
    );
  }

  const body = await req.json().catch(() => null);
  const origin = (body?.origin ?? "").toUpperCase();
  const destination = body?.destination ? String(body.destination).toUpperCase() : null;
  const maxPrice = body?.max_price_gbp ? Number(body.max_price_gbp) : null;
  if (!IATA.test(origin) || (destination && !IATA.test(destination))) {
    return NextResponse.json({ error: "Invalid airport code" }, { status: 400 });
  }
  if (maxPrice !== null && (!Number.isFinite(maxPrice) || maxPrice <= 0)) {
    return NextResponse.json({ error: "Invalid max price" }, { status: 400 });
  }

  const { rows: countRows } = await pool.query(
    "SELECT count(*)::int AS n FROM alerts WHERE user_id = $1 AND active",
    [userId]
  );
  if (countRows[0].n >= maxAlerts) {
    return NextResponse.json(
      { error: `Your plan allows ${maxAlerts} active alerts` },
      { status: 403 }
    );
  }

  const { rows } = await pool.query(
    `INSERT INTO alerts (user_id, origin, destination, max_price_gbp)
     VALUES ($1, $2, $3, $4)
     RETURNING id, origin, destination, max_price_gbp, channels, active, created_at`,
    [userId, origin, destination, maxPrice]
  );
  return NextResponse.json({ alert: rows[0] }, { status: 201 });
}

export async function DELETE(req: NextRequest) {
  const userId = await sessionUserId();
  if (!userId) return NextResponse.json({ error: "Sign in required" }, { status: 401 });
  const id = Number(req.nextUrl.searchParams.get("id"));
  if (!Number.isInteger(id)) {
    return NextResponse.json({ error: "id required" }, { status: 400 });
  }
  await pool.query("DELETE FROM alerts WHERE id = $1 AND user_id = $2", [id, userId]);
  return NextResponse.json({ ok: true });
}
