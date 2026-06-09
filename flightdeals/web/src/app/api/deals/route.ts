import { NextRequest, NextResponse } from "next/server";
import { sessionUserId } from "@/lib/auth";
import { getPlan, PLAN_FEATURES } from "@/lib/plans";
import { currentDeals } from "@/lib/queries";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const origin = req.nextUrl.searchParams.get("origin") ?? undefined;
  const limit = Math.min(Number(req.nextUrl.searchParams.get("limit") ?? 30), 100);

  // Regional (plus-tier) origins are the paid differentiator.
  let includePlus = false;
  const userId = await sessionUserId();
  if (userId) {
    const plan = await getPlan(userId);
    includePlus = PLAN_FEATURES[plan].regionalAirports;
  }

  const deals = await currentDeals({ includePlus, origin, limit });
  return NextResponse.json({ deals });
}
