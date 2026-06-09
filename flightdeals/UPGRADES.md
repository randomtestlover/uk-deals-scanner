# Handover analysis & upgrade recommendations

The handover's core calls are right: cash fares not award, cached+live hybrid,
regional airports as the paid moat, APIs-only from Hetzner, detection engine
as the product (not a raw fare dump). This build implements that spec. Below:
what was strengthened during the build, and the highest-leverage upgrades next.

## Already strengthened in this build

1. **Atomic quota metering.** Live-search metering is one
   `INSERT … ON CONFLICT … WHERE used < quota` statement — no check-then-
   increment race, no way to burn quota on a denied request.
2. **Click telemetry from day one.** Every booking goes through `/go/:dealId`
   and lands in `clicks`. This is the conversion dataset the route-selection
   upgrades below depend on — starting it now costs nothing.
3. **Build/runtime resilience.** The site builds and renders with no database
   (empty states), the worker has a single top-level failure path that pings
   the admin on Telegram, and `/api/health` exposes worker heartbeat
   freshness for Coolify/uptime monitoring.
4. **Kiwi verification is fail-open.** If Tequila is down, cached deals still
   post (flagged by source) rather than silently stalling the channel.

## High-leverage upgrades (ordered)

1. **Shared live-search cache (biggest cost lever).** Cache live results by
   `(origin, destination, dates)` with a 15-min TTL in Postgres. Identical
   Pro searches hit the cache instead of SerpApi — popular routes are exactly
   the ones searched repeatedly, so the metered-API bill drops 30–60% while
   *improving* perceived latency. Also serve a free "stale live" teaser from
   it on the deal page.
2. **Click-weighted sweep budget.** Allocate sweep depth (months ahead, fares
   per route) by `clicks` per route instead of uniformly. Routes nobody
   clicks get swept weekly; hot routes get swept deeper. Same API budget,
   strictly better deal coverage. Trivial once telemetry accumulates.
3. **MAD-based anomaly detection.** The fixed −25% threshold under-fires on
   stable routes (LHR–DUB barely moves) and over-fires on volatile ones.
   Upgrade: fire when `price < median − k·MAD` (median absolute deviation,
   k≈3) with the −25% rule as a fallback until a route has ~20 samples. Pure
   SQL/Python change inside `detect.py`; no schema impact.
4. **Telegram deep-link account linking.** `/start <signed-token>` from the
   bot links `telegram_chat_id` to the web account (`telegram_links` table is
   already in the schema). Unlocks the Plus differentiator — alert DMs — and
   makes the free channel a funnel into accounts. Small bot webhook on the
   Next.js side (`/api/telegram/webhook`), no separate daemon.
5. **Stripe Customer Portal.** One endpoint
   (`stripe.billingPortal.sessions.create`) gives self-serve cancel/upgrade/
   card-update — materially reduces support load and involuntary churn. Add a
   "Manage billing" button on `/account`.
6. **Snapshot partitioning + retention automation.** `price_snapshots` is the
   only unbounded table (~300 routes × ~20 fares × 365 days ≈ 2M rows/yr —
   fine for a year). Before scale: monthly `PARTITION BY RANGE (found_at)`,
   drop old partitions instead of `DELETE`. The worker already prunes at 120
   days, so this is an ops upgrade, not a behaviour change.
7. **Per-user personalised digest.** Plus users pick `user_airports` (table
   exists); a weekly email digest of the best deals from *their* airports is
   the single stickiest retention feature for this product category and reuses
   the existing alert fan-out machinery.
8. **Observability beyond heartbeat.** Emit per-stage counters (snapshots
   inserted, deals found, posts, alert sends) into a `worker_runs` table and
   chart them on a private `/admin` page. The failure mode that kills deal
   channels is silent degradation (API quietly returning fewer fares), and a
   counter trendline catches it in a glance.

## Explicitly deferred (agree with the handover)

- **Award/points search** (seats.aero) — different product, different data
  contract; revisit only as a pivot.
- **Being an OTA / holding inventory** — affiliate redirect keeps liability,
  PCI and support burden near zero at MVP scale.
- **6,500-route Roame-scale sweep** — start at ~300; the sweep is one config
  file and a cost line, scale it when click data says which routes earn it.
