import { NextRequest, NextResponse } from "next/server";
import { sessionUserId } from "@/lib/auth";
import { dealById, recordClick } from "@/lib/queries";
import { bookingUrl } from "@/lib/affiliate";

export const dynamic = "force-dynamic";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ dealId: string }> }
) {
  const { dealId } = await params;
  const id = Number(dealId);
  if (!Number.isInteger(id)) {
    return NextResponse.redirect(new URL("/", req.url));
  }
  const deal = await dealById(id);
  if (!deal) {
    return NextResponse.redirect(new URL("/?expired=1", req.url));
  }

  const userId = await sessionUserId().catch(() => null);
  // Click logging must never block the redirect.
  recordClick(id, userId, req.headers.get("referer")).catch(() => {});

  return NextResponse.redirect(bookingUrl(deal), { status: 302 });
}
