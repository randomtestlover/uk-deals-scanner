# Session handover — FlightDeals UK Stage 2 MVP

For continuation in a new Claude Code session linked to
`randomtestlover/flightscanner-C`. This directory is the complete, verified
build; it belongs at the **root** of flightscanner-C.

## First task for the new session

Copy everything in this `flightdeals/` directory (from
`randomtestlover/uk-deals-scanner`, branch
`claude/flight-price-drops-mvp-2b458t`) to the root of `flightscanner-C` and
push. If the new session only has flightscanner-C linked, ask the user to
paste/attach this tree or link both repos; the tree is also reproducible from
this branch.

## What this is

UK cash-fare flight-deal platform (handover concept: Roame-level polish,
cash fares NOT award, regional airports as the paid moat, Coolify on Hetzner,
never scrape consumer flight sites from the VPS — data APIs only).

- `db/migrations/001_init.sql` — full Postgres schema (flight data, Auth.js
  tables, subscriptions, alerts, search metering, click telemetry).
- `worker/` — Python pipeline: `python main.py migrate|seed|sweep|detect|post|alerts|prune|all [--shadow]`.
  Travelpayouts cached sweep → 90-day-median baseline (−25% sale) OR band
  floors (£20/£90/£280) → optional Kiwi verify → Telegram post → alert
  fan-out. Routes live in `worker/config.yaml` only (12 origins × 28 dests).
- `web/` — Next.js 15 App Router: deal board, /explore/[origin], Pro live
  search (SerpApi/Apify adapter via `LIVE_SEARCH_PROVIDER`), Auth.js v5
  (magic link + Google, env-gated), Stripe Plus/Pro (+webhook), /go/:dealId
  affiliate redirect with click logging, /api/health.
- `docker-compose.yml` + Dockerfiles — Coolify deployment (worker runs as a
  scheduled task: `docker compose run --rm worker python main.py all`).
- `ARCHITECTURE.md` — system design, schema, endpoints, UI architecture,
  scaling path. `UPGRADES.md` — ranked next features (shared live-search
  cache first). `README.md` — quickstart + deploy steps.

## Verification status (all passed in the build session, 2026-06-11)

- `worker/tests/test_detect.py`: 6/6 (sale, floor, min-samples, dedupe hash).
- Full pipeline against real Postgres 16: migrate + seed (336 routes) ran;
  synthetic fares fired `sale` (40% below £50 median) and `floor` (£15, no
  history); re-run deduped to 0; shadow post logged both.
- `npm run build`: clean, all 17 routes type-checked.
- Runtime smoke: all pages 200; /api/deals served worker-detected deals;
  /go/1 → 302 to correct Aviasales URL; click row recorded; /api/health
  showed fresh worker heartbeats.

## Not yet done (deliberate)

- No real API keys used — sweep/post/Stripe/live search are untested against
  live providers (adapters follow each provider's documented contracts;
  Apify actor input mapping is generic and needs aligning to the chosen actor).
- Telegram DM account-linking flow (table `telegram_links` exists; flow is
  UPGRADES.md item 4). Stripe Customer Portal (item 5).
- No CI workflow; suggest adding build + test checks after transfer.

## Build order already completed vs handover §12

Steps 1–7 of the handover's Stage 2 build order are implemented in code;
remaining work is deployment/config (Coolify provisioning, Stripe products,
API keys, domain) plus the UPGRADES.md backlog.
