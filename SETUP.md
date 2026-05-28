# UK Deals Scanner — Setup Guide

A £0 automated deal-finder that scans Amazon UK price drops, scores them by
quality, and posts the best to your Telegram channel(s). Runs free on GitHub
Actions. No server, no upfront cost.

> **Time to set up:** ~30 minutes. You only ever edit one file: `config.yaml`.

---

## What you get

- Pulls **CamelCamelCamel UK** price-drop feeds (free, no API key).
- Scores each deal **0–100** so only genuinely good ones get posted.
- Posts to a **main public channel** + optional **per-category channels**.
- Adds your **Amazon affiliate tag** and a compliant **disclosure** automatically.
- Stores **price history** in Supabase so scoring gets smarter over time.
- Optional **click tracking** via a free Cloudflare Worker.
- DMs **you** if a run fails.

---

## Before you start — read this (compliance)

These rules keep your Amazon Associates account alive. Breaking them = ban.

1. **Keep your main channel public.** Affiliate links must reach people who
   arrived voluntarily. Don't put affiliate links behind a paywall. Your
   *premium tier later* should sell **speed/filters**, not the links.
2. **The disclosure stays on every post** (already automated). Also add it to
   your channel bio.
3. **Never click your own affiliate links to buy.** Self-purchases get you banned.
4. **Prices can go stale.** Deals link straight to Amazon, where the live price
   shows — we don't post a frozen price as gospel. Keep it that way.

---

## Step 1 — Get the code onto GitHub

1. Create a **new GitHub repository** (keep it **Public** — public repos get
   unlimited free Actions minutes; private burns your monthly quota).
2. Upload all these files, or push them:
   ```bash
   git init
   git add .
   git commit -m "initial commit"
   git branch -M main
   git remote add origin https://github.com/YOURNAME/uk-deals-scanner.git
   git push -u origin main
   ```

## Step 2 — Create your Telegram bot + channel

1. In Telegram, message **@BotFather** → `/newbot` → follow prompts.
2. Copy the **bot token** it gives you (looks like `123456:ABC-DEF...`).
3. Create a **public channel** (e.g. `@your_main_deals_channel`).
4. Add your bot to the channel as an **Administrator** (needs "Post messages").
5. (Optional) Message **@userinfobot** to get **your own numeric user ID** —
   used for failure alerts.

## Step 3 — Create your free Supabase database

1. Go to **supabase.com** → new project (free tier).
2. Open **Project Settings → API**. Copy the **Project URL** and the
   **`service_role` secret key**.
3. Open **SQL Editor → New query**, paste the schema below, click **Run**:

   > The exact SQL is in `core/db.py` (the `SCHEMA_SQL` block). Copy everything
   > between the triple-quotes and run it once. It creates the
   > `deals`, `price_history`, `posts`, and `subscribers` tables.

## Step 4 — Add your secrets to GitHub

In your repo: **Settings → Secrets and variables → Actions → New repository
secret**. Add these (names must match exactly):

| Secret name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | from BotFather |
| `SUPABASE_URL` | Supabase Project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service_role key |
| `ALERT_CHAT_ID` | your numeric Telegram ID (optional) |

> Secrets are never committed to the repo. The `.env` file is for local testing
> only and is git-ignored.

## Step 5 — Configure (the only file you edit)

Open **`config.yaml`** and set:

- `affiliate.amazon_tag` → **your Amazon Associates tag** (e.g. `yourtag-21`).
- `channels.main_channel` → your channel (e.g. `@your_main_deals_channel`).
- (Optional) `channels.per_category.*` → separate channels per category.
- Tune `filters.min_discount_pct` and `filters.min_deal_score` to taste.

Commit and push your changes.

## Step 6 — (Optional) Click tracking with Cloudflare

Only if you want click stats before monetising.

1. Install Wrangler: `npm i -g wrangler` then `wrangler login`.
2. `cd cloudflare-worker`
3. `wrangler kv namespace create CLICKS` → paste the returned `id` into
   `wrangler.toml`.
4. `wrangler deploy` → copy the deployed URL.
5. In `config.yaml`, set `click_tracking.enabled: true` and
   `click_tracking.worker_base_url` to that URL.
6. View stats anytime at `https://YOUR-WORKER-URL/stats?c=tech`.

## Step 7 — Test it (no posting)

Locally:
```bash
pip install -r requirements.txt
cp .env.example .env      # fill in your secrets
python main.py --test     # scores + prints deals, posts NOTHING
```

You'll see `--- WOULD POST ---` blocks. If deals look good, you're ready.

## Step 8 — Go live

- **Manual run:** Repo → **Actions** tab → **UK Deals Scan** → **Run workflow**.
- **Automatic:** it's already scheduled (`:17` and `:47` past the hour, 7am–10pm UK).

---

## Tuning notes

- **Too few deals?** Lower `min_deal_score` (e.g. 55) or `min_discount_pct` (e.g. 25).
- **Too spammy?** Raise `max_per_run` down, or raise the thresholds.
- **Quiet at night** is controlled by `posting.quiet_hours_utc`.
- Scoring is **conservative until price history builds** (a few days). Quality
  improves automatically as the `price_history` table fills.

## Good to know about GitHub Actions (free tier realities)

- Scheduled runs can be **delayed 10–30 min** at peak — fine for deals, not
  second-critical. We already schedule off-peak minutes to minimise this.
- Scheduled workflows **auto-disable after 60 days of repo inactivity** — the
  workflow includes a monthly keep-alive commit to prevent that.
- GitHub **doesn't alert you on failure** — so we DM you via `ALERT_CHAT_ID`.

## When to spend money (not before you need to)

| Trigger | Upgrade | Rough cost |
|---|---|---|
| CCC feeds flaky / want reliable Amazon data | Keepa entry API | ~£17/mo |
| Scraping unreliable / want always-on | Oracle Cloud free VM | £0 |
| Launching paid premium tier | Stripe | fees only |

## Project layout

```
config.yaml              ← you edit this
core/        models, config, db, scoring, affiliate logic
scanners/    CamelCamelCamel RSS + scrape fallback
bot/         Telegram formatting + posting
cloudflare-worker/   optional click tracking
.github/workflows/scan.yml   the scheduler
main.py      orchestrator (run with --test to dry-run)
```

## Troubleshooting

- **"Missing required secrets"** → a GitHub Secret name is wrong/empty.
- **Nothing posts but no error** → likely within `quiet_hours_utc`, or no deal
  cleared your thresholds. Run `python main.py --test --limit 20` to inspect.
- **Telegram "chat not found"** → bot isn't an admin of the channel, or the
  channel handle is wrong.
- **Supabase insert errors** → re-run the schema SQL from `core/db.py`.

---

*Not legal advice. Read the Amazon Associates Operating Agreement yourself; it
changes. You are responsible for compliance.*
