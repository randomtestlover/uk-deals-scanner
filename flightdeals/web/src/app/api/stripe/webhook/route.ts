import { NextRequest, NextResponse } from "next/server";
import type Stripe from "stripe";
import { pool } from "@/lib/db";
import { stripe, planForPriceId } from "@/lib/stripe";

export const dynamic = "force-dynamic";

async function upsertFromSubscription(sub: Stripe.Subscription) {
  const customerId =
    typeof sub.customer === "string" ? sub.customer : sub.customer.id;
  const item = sub.items.data[0];
  const plan =
    (sub.metadata?.plan as "plus" | "pro" | undefined) ??
    (item ? planForPriceId(item.price.id) : null) ??
    "free";
  // current_period_end lives on the item in newer Stripe API versions.
  const periodEnd =
    (item as unknown as { current_period_end?: number })?.current_period_end ??
    (sub as unknown as { current_period_end?: number }).current_period_end;

  const effectivePlan = sub.status === "canceled" ? "free" : plan;

  await pool.query(
    `UPDATE subscriptions
     SET stripe_subscription_id = $2, plan = $3, status = $4,
         current_period_end = to_timestamp($5), updated_at = now()
     WHERE stripe_customer_id = $1`,
    [customerId, sub.id, effectivePlan, sub.status, periodEnd ?? null]
  );
}

export async function POST(req: NextRequest) {
  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!secret) {
    return NextResponse.json({ error: "webhook not configured" }, { status: 503 });
  }
  const signature = req.headers.get("stripe-signature");
  if (!signature) {
    return NextResponse.json({ error: "missing signature" }, { status: 400 });
  }

  let event: Stripe.Event;
  try {
    const payload = await req.text();
    event = stripe().webhooks.constructEvent(payload, signature, secret);
  } catch {
    return NextResponse.json({ error: "invalid signature" }, { status: 400 });
  }

  switch (event.type) {
    case "checkout.session.completed": {
      const session = event.data.object as Stripe.Checkout.Session;
      if (session.mode === "subscription" && session.subscription) {
        const sub = await stripe().subscriptions.retrieve(
          typeof session.subscription === "string"
            ? session.subscription
            : session.subscription.id
        );
        await upsertFromSubscription(sub);
      }
      break;
    }
    case "customer.subscription.updated":
    case "customer.subscription.deleted": {
      await upsertFromSubscription(event.data.object as Stripe.Subscription);
      break;
    }
    default:
      break; // ignore unrelated events
  }

  return NextResponse.json({ received: true });
}
