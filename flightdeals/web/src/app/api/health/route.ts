import { NextResponse } from "next/server";
import { pool } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const { rows } = await pool.query(
      `SELECT job, last_ok,
              last_ok > now() - interval '36 hours' AS fresh
       FROM worker_heartbeat ORDER BY last_ok DESC LIMIT 5`
    );
    return NextResponse.json({ ok: true, worker: rows });
  } catch {
    return NextResponse.json({ ok: false, error: "database unreachable" }, { status: 503 });
  }
}
