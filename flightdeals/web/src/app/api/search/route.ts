import { NextRequest, NextResponse } from "next/server";
import { sessionUserId } from "@/lib/auth";
import { consumeLiveSearch, getPlan, PLAN_FEATURES } from "@/lib/plans";
import { liveSearch, LiveSearchUnavailable } from "@/lib/liveSearch";

export const dynamic = "force-dynamic";

const IATA = /^[A-Za-z]{3}$/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

export async function POST(req: NextRequest) {
  const userId = await sessionUserId();
  if (!userId) {
    return NextResponse.json({ error: "Sign in required" }, { status: 401 });
  }
  const plan = await getPlan(userId);
  const quota = PLAN_FEATURES[plan].liveSearchesPerMonth;
  if (quota === 0) {
    return NextResponse.json(
      { error: "Live search is a Pro feature", upgrade: "/pricing" },
      { status: 403 }
    );
  }

  const body = await req.json().catch(() => null);
  const { origin, destination, departDate, returnDate } = body ?? {};
  if (
    !IATA.test(origin ?? "") ||
    !IATA.test(destination ?? "") ||
    !ISO_DATE.test(departDate ?? "") ||
    (returnDate && !ISO_DATE.test(returnDate))
  ) {
    return NextResponse.json({ error: "Invalid search parameters" }, { status: 400 });
  }

  const remaining = await consumeLiveSearch(userId, quota);
  if (remaining === null) {
    return NextResponse.json(
      { error: `Monthly live-search quota (${quota}) reached` },
      { status: 429 }
    );
  }

  try {
    const flights = await liveSearch({
      origin: origin.toUpperCase(),
      destination: destination.toUpperCase(),
      departDate,
      returnDate: returnDate || undefined,
    });
    return NextResponse.json({ flights, remaining });
  } catch (err) {
    if (err instanceof LiveSearchUnavailable) {
      return NextResponse.json(
        { error: "Live search is temporarily unavailable" },
        { status: 503 }
      );
    }
    throw err;
  }
}
