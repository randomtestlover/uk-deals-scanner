import { NextRequest, NextResponse } from "next/server";
import { pool } from "@/lib/db";
import { auth } from "@/lib/auth";
import { stripe, priceIdForPlan } from "@/lib/stripe";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const session = await auth();
  if (!session?.user?.id || !session.user.email) {
    return NextResponse.json({ error: "Sign in required" }, { status: 401 });
  }
  const userId = Number(session.user.id);

  const body = await req.json().catch(() => null);
  const plan = body?.plan as "plus" | "pro" | undefined;
  if (plan !== "plus" && plan !== "pro") {
    return NextResponse.json({ error: "plan must be plus or pro" }, { status: 400 });
  }
  const priceId = priceIdForPlan(plan);
  if (!priceId) {
    return NextResponse.json({ error: "Billing not configured" }, { status: 503 });
  }

  // Reuse the Stripe customer if this user already has one.
  const { rows } = await pool.query(
    "SELECT stripe_customer_id FROM subscriptions WHERE user_id = $1",
    [userId]
  );
  let customerId: string | undefined = rows[0]?.stripe_customer_id ?? undefined;
  if (!customerId) {
    const customer = await stripe().customers.create({
      email: session.user.email,
      metadata: { userId: String(userId) },
    });
    customerId = customer.id;
    await pool.query(
      `INSERT INTO subscriptions (user_id, stripe_customer_id)
       VALUES ($1, $2)
       ON CONFLICT (user_id) DO UPDATE SET stripe_customer_id = EXCLUDED.stripe_customer_id`,
      [userId, customerId]
    );
  }

  const base = process.env.SITE_BASE_URL ?? req.nextUrl.origin;
  const checkout = await stripe().checkout.sessions.create({
    mode: "subscription",
    customer: customerId,
    line_items: [{ price: priceId, quantity: 1 }],
    subscription_data: { metadata: { userId: String(userId), plan } },
    metadata: { userId: String(userId), plan },
    success_url: `${base}/account?upgraded=1`,
    cancel_url: `${base}/pricing`,
  });

  return NextResponse.json({ url: checkout.url });
}
