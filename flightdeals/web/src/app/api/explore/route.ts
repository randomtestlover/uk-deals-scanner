import { NextRequest, NextResponse } from "next/server";
import { exploreFrom } from "@/lib/queries";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const origin = req.nextUrl.searchParams.get("origin");
  if (!origin || !/^[A-Za-z]{3}$/.test(origin)) {
    return NextResponse.json({ error: "origin must be a 3-letter IATA code" }, { status: 400 });
  }
  const destinations = await exploreFrom(origin);
  return NextResponse.json({ origin: origin.toUpperCase(), destinations });
}
