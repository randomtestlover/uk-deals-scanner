# FlightDeals UK — System Architecture

## 1. System overview

```
                       ┌────────────────────────── Hetzner VPS (Coolify) ──────────────────────────┐
                       │                                                                           │
  Travelpayouts API ──▶│  ┌───────────────┐  nightly cron   ┌──────────────┐                       │
  Kiwi Tequila API  ──▶│  │ Python worker │ ───────────────▶│  Postgres 16 │◀──────────┐           │
                       │  │ sweep→detect→ │                 │  (canonical) │           │           │
  Telegram Bot API ◀───│  │ post→alerts   │                 └──────┬───────┘           │           │
  Resend (email)  ◀────│  └───────────────┘                        │ SQL               │           │
                       │                                          ▼                    │           │
   users ◀─ Traefik ───│──────────────────────────────▶ ┌──────────────────┐           │           │
   (TLS/LE)            │                                │  Next.js 15 app  │── Stripe ─┤ webhooks  │
                       │                                │  SSR + ISR + API │── SerpApi/Apify (live)│
                       │                                └──────────────────┘                       │
                       └───────────────────────────────────────────────────────────────────────────┘
```

Two data layers (Roame's cached+live hybrid, scaled down):

- **Cached layer** — the worker sweeps ~300 routes nightly via Travelpayouts
  (free) into `price_snapshots`, recomputes per-route baselines, and runs the
  detection engine. Serves the deal board, Explore pages, Telegram channel and
  alerts at near-zero marginal cost per user.
- **Live layer** — on-demand consolidated search via SerpApi or an Apify
  Google Flights actor (both Hetzner-safe: no scraping from our IP). Metered
  per user per month, gated to Pro.

Booking is always an **affiliate redirect** (`/go/:dealId` → Travelpayouts/
Aviasales deep link with our marker). We hold no inventory.

## 2. File structure

```
flightdeals-uk/
├── docker-compose.yml          # db + web + worker (worker = scheduled task)
├── db/migrations/001_init.sql  # full schema; applied by the worker migrator
├── worker/                     # Python 3.12 pipeline
│   ├── main.py                 # CLI: migrate|seed|sweep|detect|post|alerts|prune|all
│   ├── config.yaml             # airports, destinations, bands, detection params
│   ├── worker/
│   │   ├── config.py           # Secrets.from_env() + YAML config
│   │   ├── db.py               # psycopg3 DAL + SQL-file migrator
│   │   ├── models.py           # FareSnapshot (fare_hash), DealCandidate
│   │   ├── detect.py           # baseline −25% OR band-floor triggers
│   │   ├── pipeline.py         # stage orchestration
│   │   ├── telegram.py         # channel poster + admin failure alerts
│   │   ├── alerts.py           # saved-route fan-out (Resend email + TG DM)
│   │   └── sources/            # FareSource adapters
│   │       ├── travelpayouts.py  # cached cheapest fares (primary, free)
│   │       └── kiwi.py           # live verification before posting
│   └── tests/test_detect.py
└── web/                        # Next.js 15 App Router (TypeScript, Tailwind)
    └── src/
        ├── lib/                # db pool, auth, plans, stripe, queries,
        │                       # affiliate links, liveSearch provider adapter
        ├── components/         # Nav, Footer, DealCard, SearchForm, AlertManager…
        └── app/
            ├── page.tsx                  # landing + latest hub deals
            ├── deals/  explore/[origin]/ # cached layer (free)
            ├── search/                   # live layer (Pro, metered)
            ├── pricing/ account/ signin/
            ├── go/[dealId]/route.ts      # click log + affiliate 302
            └── api/                      # endpoints below
```

## 3. Database schema

Flight data: `airports` (tier free/plus) → `routes` (band short/medium/long,
unique origin+destination) → `price_snapshots` (append-only fare time series,
pruned at 120 days) → `route_baselines` (materialised 90-day median per
route) → `deals` (detected below-baseline fares, `fare_hash` for 7-day repost
suppression, `expires_at` 48h, `posted_telegram_at`).

Users & billing: Auth.js standard tables (`users`, `accounts`, `sessions`,
`verification_token`) plus `subscriptions` (Stripe customer/sub ids, plan,
status, period end), `alerts` (origin, optional destination, optional price
cap, channels), `user_airports`, `telegram_links` (DM linking),
`search_usage` (user × month live-search metering), `clicks` (affiliate
telemetry), `worker_heartbeat`, `schema_migrations`.

Full DDL: [`db/migrations/001_init.sql`](db/migrations/001_init.sql).

## 4. API endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/deals?origin=&limit=` | public | live deals; regional origins only for Plus+ |
| GET | `/api/explore?origin=LHR` | public | cheapest cached fare per destination |
| POST | `/api/search` | Pro | metered live search (`{origin,destination,departDate,returnDate?}`) |
| GET/POST/DELETE | `/api/alerts` | Plus+ | saved-route alerts CRUD (plan-capped) |
| POST | `/api/checkout` | user | Stripe Checkout session for plus/pro |
| POST | `/api/stripe/webhook` | Stripe sig | subscription lifecycle → `subscriptions` |
| GET | `/go/:dealId` | public | click log + 302 to affiliate deep link |
| GET | `/api/health` | public | DB ping + worker heartbeat freshness |
| * | `/api/auth/*` | — | Auth.js (magic link / Google) |

Plan gating is enforced **server-side** in queries and route handlers, never
client-only. Live-search quota consumption is a single atomic
`INSERT … ON CONFLICT … WHERE used < quota RETURNING` — no race window.

## 5. UI architecture

- **Server components by default.** The cached layer (landing, deals board,
  explore) renders on the server straight from Postgres; the landing page is
  ISR (10 min). DB failures degrade to friendly empty states — the site
  builds and runs with no database.
- **Client islands only where interactive:** `SearchForm` (live search),
  `AlertManager` (CRUD), `CheckoutButton` (Stripe redirect).
- **Design system:** dark "deal board" aesthetic (Tailwind, ink/panel/edge
  palette, sky accent), `DealCard` with price, % -below-baseline badge,
  exceptional-fare badge, dates, airline → `/go/:id`.
- Sign-in/sign-out via Auth.js v5 server actions (no client auth state).

## 6. Detection engine

Per route: baseline = rolling 90-day **median** of snapshots (≥5 samples to
fire). Triggers: `sale` when price ≤ baseline × 0.75; `floor` when price ≤
band floor (short £20 / medium £90 / long £280) — fires with zero history.
Dedupe: sha256(route|dates|£10-price-bucket), 7-day repost suppression.
Optional Kiwi live verification before a deal is stored/posted. Shadow mode
logs everything and sends nothing.

## 7. Scaling path (to millions of users)

The free tier is read-only cached data → already CDN/ISR-shaped:

1. **Now (1 VPS):** ISR + Postgres comfortably serves tens of thousands of
   daily readers; cost scales with routes swept, not users.
2. **Next:** put Cloudflare in front (cache `/`, `/deals`, `/explore/*`,
   `/api/deals`, `/api/explore` for 5–10 min); add a Postgres read replica
   for the web app; move `price_snapshots` to monthly partitions.
3. **Later:** split worker stages into queue-driven jobs (sweep fan-out per
   route), shared short-TTL cache for live searches (one Pro user's search
   serves identical searches for 15 min — directly cuts the SerpApi bill),
   multi-region read replicas. The schema and adapter seams already support
   each step without rewrites.
