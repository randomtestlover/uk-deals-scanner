# ✈️ FlightDeals UK

Cash-fare flight-deal platform for UK airports. A Python worker sweeps cached
fares nightly, a detection engine surfaces only **below-baseline** fares
(rolling 90-day median −25%, or an absolute error-fare floor), and a Next.js
site + free Telegram channel deliver them. Regional airports, saved-route
alerts and live consolidated search are the paid tiers.

**Docs:** [ARCHITECTURE.md](ARCHITECTURE.md) · [UPGRADES.md](UPGRADES.md) (handover analysis)

## Stack

| Layer | Choice |
|---|---|
| Web | Next.js 15 (App Router) + Tailwind, standalone Docker build |
| Auth | Auth.js v5 + Postgres adapter (magic link via Resend and/or Google, env-gated) |
| Payments | Stripe subscriptions (Plus / Pro) + webhook |
| DB | Self-hosted Postgres 16 (canonical store, auto-migrated by the worker) |
| Worker | Python 3.12 — sweep → detect → post → alerts, one CLI |
| Data | Travelpayouts (free cache) + Kiwi Tequila (live verify); SerpApi/Apify for paid live search |
| Hosting | Coolify on a Hetzner VPS (Traefik + Let's Encrypt built in) |

> **Rule (from the handover):** never scrape consumer flight sites from the
> VPS — Hetzner datacenter IPs get Cloudflare-blocked. Everything here uses
> data APIs server-to-server, or delegates scraping to Apify's infra.

## Quickstart (local)

```bash
# 1. Postgres
docker compose up -d db   # or any local Postgres

# 2. Worker — migrate, seed routes, dry-run the pipeline
cd worker
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env      # set DATABASE_URL (+ tokens when you have them)
.venv/bin/python main.py migrate
.venv/bin/python main.py seed
.venv/bin/python main.py all --shadow     # logs, never posts
.venv/bin/python tests/test_detect.py     # detection unit tests

# 3. Web
cd ../web
npm install
cp .env.example .env.local                # DATABASE_URL + AUTH_SECRET minimum
npm run dev                               # http://localhost:3000
```

## Deploy on Coolify (Hetzner)

1. **Postgres**: create from `docker-compose.yml` (service `db`) or as a
   Coolify database resource.
2. **Web app**: point Coolify at this repo, base directory `web/`,
   Dockerfile build. Attach your domain; TLS is automatic.
3. **Worker**: same repo, `worker/Dockerfile` (build context = repo root).
   Add a **Scheduled Task**: `python main.py all`, cron `15 2 * * *`.
   First run applies migrations and seeds airports/routes from
   `worker/config.yaml` — the only file you edit to change routes.
4. **Stripe**: create Plus/Pro products, set `STRIPE_PRICE_*`, point a
   webhook at `https://yourdomain/api/stripe/webhook`
   (events: `checkout.session.completed`, `customer.subscription.*`).
5. Watch `https://yourdomain/api/health` — it reports DB reachability and
   worker heartbeat freshness.

## Tiers

| | Free | Plus (~£4/mo) | Pro (~£9/mo) |
|---|---|---|---|
| Hub deals (LHR LGW STN LTN MAN) | ✓ | ✓ | ✓ |
| Telegram channel | ✓ | ✓ | ✓ |
| Regional airports (BHX BRS EMA LBA NCL EDI GLA) | — | ✓ | ✓ |
| Saved-route alerts | — | 5 | 20 |
| Live consolidated search | — | — | 100/mo |

Cost scales with routes and live searches, **not** free users — cached pages
are served from Postgres at near-zero marginal cost.
