# YourDealsUK — Clean Relink Guide (Free Stack)

You've deleted the VPS. This rebuilds everything on the proven **£0 stack**:
GitHub Actions (scanner) + Supabase (database) + GitHub Pages (website).
Nothing here costs money. No VPS, no Coolify, no DATABASE_URL.

Work top to bottom. ~30 minutes.

---

## PART 1 — The code repo

### 1. Repo visibility
Your GitHub repo `uk-deals-scanner` must be **PUBLIC** (free Actions minutes +
GitHub Pages both need this). If it's private, Settings → bottom → make public.

### 2. Upload the code
Unzip the bundle. Upload these to your repo, replacing what's there. The folder
structure must be preserved exactly:

```
main.py
requirements.txt
config.yaml
.gitignore
.env.example
core/__init__.py   core/models.py   core/config.py
core/affiliate.py  core/dealscore.py  core/db.py
scanners/__init__.py  scanners/base.py  scanners/camel_rss.py  scanners/awin.py
bot/__init__.py    bot/telegram_poster.py
.github/workflows/scan.yml
```

These are the SUPABASE versions (use SUPABASE_URL / SUPABASE_SERVICE_KEY, not
DATABASE_URL). If your repo currently has the VPS/DATABASE_URL version from the
other chat, REPLACE those files with these.

### 3. Website files → into the `docs/` folder
GitHub Pages serves from `/docs`. Put these there:
```
docs/index.html
docs/privacy.html
docs/terms.html
docs/favicon.ico
docs/favicon-32.png
docs/apple-touch-icon.png
docs/assets/logo.svg   (optional)
```
(In the bundle they're under `website/` — on GitHub they go in `docs/`.)

---

## PART 2 — Supabase (database)

### 4. Create / reuse a Supabase project
- supabase.com → your project (or new free project).
- Settings → API Keys → **Legacy** tab → copy the **service_role** key (starts
  `eyJ...`). NOT the publishable/anon key.
- Settings → Data API → copy the **Project URL**. Use the BARE url:
  `https://xxxx.supabase.co` — NO trailing slash, NO `/rest/v1`.

### 5. Create the tables
Supabase → SQL Editor → New query → paste the SQL below → Run.
(You said data loss is fine, so if tables exist already this is harmless —
`create table if not exists` won't overwrite.)

```sql
create table if not exists deals (
    id            bigint generated always as identity primary key,
    dedupe_hash   text unique not null,
    source        text not null,
    category      text not null,
    title         text not null,
    url           text not null,
    affiliate_url text not null,
    asin          text,
    current_price numeric not null,
    ref_price     numeric,
    pct_off       numeric,
    deal_score    int not null,
    in_stock      boolean not null default true,
    created_at    timestamptz not null default now()
);
create index if not exists deals_category_idx on deals (category, created_at desc);

create table if not exists price_history (
    id          bigint generated always as identity primary key,
    asin        text,
    url         text not null,
    price       numeric not null,
    captured_at timestamptz not null default now()
);
create index if not exists price_history_asin_idx on price_history (asin, captured_at desc);

create table if not exists posts (
    id          bigint generated always as identity primary key,
    deal_id     bigint references deals(id) on delete cascade,
    channel     text not null,
    message_id  bigint,
    clicks      int not null default 0,
    posted_at   timestamptz not null default now()
);

create table if not exists subscribers (
    id          bigint generated always as identity primary key,
    tg_user_id  bigint unique not null,
    tier        text not null default 'free',
    categories  text[] not null default '{}',
    joined_at   timestamptz not null default now()
);
```

Expect "Success. No rows returned" — that's correct.

---

## PART 3 — GitHub Secrets

### 6. Add the secrets
Repo → Settings → Secrets and variables → Actions → New repository secret.
Add (names exactly):

| Secret | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | from @BotFather |
| `SUPABASE_URL` | bare project URL `https://xxxx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | the `eyJ...` service_role key |
| `ALERT_CHAT_ID` | your numeric Telegram ID (optional, for failure DMs) |

Do NOT add AWIN_FEED_URLS yet — only when an Awin advertiser approves you.

---

## PART 4 — Config

### 7. config.yaml is already set with:
- `amazon_tag: "sturnusek0d-21"`
- `main_channel: "-1003939145947"`
- thresholds lowered (`min_discount_pct: 15`, `min_deal_score: 8`) so CCC's
  small drops actually post while you have no price history yet.
- one `deals` category using CCC (source defaults to ccc).

Change the tag/channel only if they differ now. Otherwise leave it.

Make sure your **bot is an admin** of the Telegram channel (post permission),
and the **channel is public** (for Amazon's consent rule + growth).

---

## PART 5 — Website (GitHub Pages)

### 8. Enable Pages
Repo → Settings → Pages:
- Source: Deploy from a branch
- Branch: `main`, folder `/docs` → Save
- Custom domain: `yourdealsuk.co.uk` → Save → tick Enforce HTTPS once verified.

Confirm DNS in Cloudflare still points at GitHub Pages (A records to GitHub IPs
185.199.108–111.153 + CNAME www → randomtestlover.github.io). If you repointed
DNS at the VPS earlier, point it BACK to GitHub Pages.

---

## PART 6 — Run it

### 9. Test then go live
- Repo → Actions tab → enable workflows if prompted.
- "UK Deals Scan" → Run workflow.
- Open the run → "Run scan" step. Expect:
  `[info] N qualifying deals; posting N` then `[done] posted N deal(s).`
- Check your Telegram channel for the posts.

The schedule then runs automatically (:17 and :47 past the hour, 7am–10pm UK).

---

## Notes / known good state

- **CCC works from GitHub Actions** (it does NOT work from a VPS — that's why the
  VPS move failed). This is why the free stack is genuinely the right home for
  this scanner, not just the cheap one.
- **Awin scanner is built and dormant.** When an advertiser approves you:
  add `AWIN_FEED_URLS` secret + set the category `source: awin` in config.yaml.
- **Keepa** = future paid upgrade (~£17/mo) once you have an audience.
- Secrets live only in GitHub Secrets — never in committed code. `.env` is for
  local testing only and is git-ignored.

## If a run fails — quick map
- `Missing required secrets` → a secret name is wrong/missing.
- `Invalid API key` → used publishable key instead of service_role.
- `PGRST125 / Invalid path` → SUPABASE_URL has a trailing slash or /rest/v1; fix it.
- `chat not found` → bot isn't admin of the channel, or wrong channel ID.
- `0 deals` (no error) → fine; thresholds filtered everything, or quiet hours.
