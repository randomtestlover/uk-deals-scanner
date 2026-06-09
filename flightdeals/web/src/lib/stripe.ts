import Stripe from "stripe";

// Lazy init so `next build` works without secrets.
let client: Stripe | null = null;

export function stripe(): Stripe {
  if (!client) {
    const key = process.env.STRIPE_SECRET_KEY;
    if (!key) throw new Error("STRIPE_SECRET_KEY is not configured");
    client = new Stripe(key);
  }
  return client;
}

export function priceIdForPlan(plan: "plus" | "pro"): string | undefined {
  return plan === "plus"
    ? process.env.STRIPE_PRICE_PLUS
    : process.env.STRIPE_PRICE_PRO;
}

export function planForPriceId(priceId: string): "plus" | "pro" | null {
  if (priceId === process.env.STRIPE_PRICE_PLUS) return "plus";
  if (priceId === process.env.STRIPE_PRICE_PRO) return "pro";
  return null;
}
