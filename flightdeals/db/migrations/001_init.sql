-- FlightDeals UK — initial schema
-- Applied by the worker migrator (worker/db.py). Idempotence is handled by
-- schema_migrations, but DDL is still guarded for safe manual replays.

-- ============ flight data ============

CREATE TABLE IF NOT EXISTS airports (
  iata        CHAR(3) PRIMARY KEY,
  name        TEXT NOT NULL,
  city        TEXT NOT NULL,
  country     CHAR(2) NOT NULL DEFAULT 'GB',
  tier        TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'plus')),
  active      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS routes (
  id          SERIAL PRIMARY KEY,
  origin      CHAR(3) NOT NULL REFERENCES airports (iata),
  destination CHAR(3) NOT NULL,
  dest_name   TEXT NOT NULL,
  band        TEXT NOT NULL CHECK (band IN ('short', 'medium', 'long')),
  tier        TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free', 'plus')),
  active      BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE (origin, destination)
);

CREATE TABLE IF NOT EXISTS price_snapshots (
  id          BIGSERIAL PRIMARY KEY,
  route_id    INT NOT NULL REFERENCES routes (id),
  depart_date DATE NOT NULL,
  return_date DATE,
  price_gbp   NUMERIC(10,2) NOT NULL,
  airline     TEXT,
  source      TEXT NOT NULL,
  found_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS price_snapshots_route_found
  ON price_snapshots (route_id, found_at DESC);

CREATE TABLE IF NOT EXISTS route_baselines (
  route_id     INT PRIMARY KEY REFERENCES routes (id),
  median_gbp   NUMERIC(10,2),
  sample_count INT NOT NULL DEFAULT 0,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS deals (
  id                 BIGSERIAL PRIMARY KEY,
  route_id           INT NOT NULL REFERENCES routes (id),
  price_gbp          NUMERIC(10,2) NOT NULL,
  baseline_gbp       NUMERIC(10,2),
  discount_pct       NUMERIC(5,1),
  trigger            TEXT NOT NULL CHECK (trigger IN ('sale', 'floor')),
  depart_date        DATE NOT NULL,
  return_date        DATE,
  airline            TEXT,
  deep_link          TEXT,
  fare_hash          TEXT NOT NULL,
  found_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at         TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '48 hours',
  posted_telegram_at TIMESTAMPTZ
);
-- 7-day repost suppression is checked app-side (predicate with now() cannot
-- be indexed); this index makes that lookup cheap.
CREATE INDEX IF NOT EXISTS deals_fare_hash_found ON deals (fare_hash, found_at DESC);
CREATE INDEX IF NOT EXISTS deals_found ON deals (found_at DESC);

-- ============ auth (official @auth/pg-adapter schema) ============

CREATE TABLE IF NOT EXISTS verification_token (
  identifier TEXT NOT NULL,
  expires    TIMESTAMPTZ NOT NULL,
  token      TEXT NOT NULL,
  PRIMARY KEY (identifier, token)
);

CREATE TABLE IF NOT EXISTS users (
  id              SERIAL PRIMARY KEY,
  name            VARCHAR(255),
  email           VARCHAR(255) UNIQUE,
  "emailVerified" TIMESTAMPTZ,
  image           TEXT
);

CREATE TABLE IF NOT EXISTS accounts (
  id                  SERIAL PRIMARY KEY,
  "userId"            INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  type                VARCHAR(255) NOT NULL,
  provider            VARCHAR(255) NOT NULL,
  "providerAccountId" VARCHAR(255) NOT NULL,
  refresh_token       TEXT,
  access_token        TEXT,
  expires_at          BIGINT,
  id_token            TEXT,
  scope               TEXT,
  session_state       TEXT,
  token_type          TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
  id             SERIAL PRIMARY KEY,
  "userId"       INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  expires        TIMESTAMPTZ NOT NULL,
  "sessionToken" VARCHAR(255) NOT NULL UNIQUE
);

-- ============ billing & entitlements ============

CREATE TABLE IF NOT EXISTS subscriptions (
  user_id                INTEGER PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
  stripe_customer_id     TEXT UNIQUE,
  stripe_subscription_id TEXT,
  plan                   TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free', 'plus', 'pro')),
  status                 TEXT NOT NULL DEFAULT 'active',
  current_period_end     TIMESTAMPTZ,
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_airports (
  user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  iata    CHAR(3) NOT NULL REFERENCES airports (iata),
  PRIMARY KEY (user_id, iata)
);

CREATE TABLE IF NOT EXISTS alerts (
  id            BIGSERIAL PRIMARY KEY,
  user_id       INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  origin        CHAR(3) NOT NULL REFERENCES airports (iata),
  destination   CHAR(3),          -- NULL = any destination from origin
  max_price_gbp NUMERIC(10,2),    -- NULL = any below-baseline deal
  channels      TEXT[] NOT NULL DEFAULT '{email}',
  active        BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS alerts_active_origin ON alerts (origin) WHERE active;

-- Telegram DM linking (user runs /start <token> with the bot)
CREATE TABLE IF NOT EXISTS telegram_links (
  user_id          INTEGER PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
  telegram_chat_id BIGINT NOT NULL,
  linked_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Live-search metering, one row per user per calendar month
CREATE TABLE IF NOT EXISTS search_usage (
  user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  period  CHAR(7) NOT NULL,       -- 'YYYY-MM'
  used    INT NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, period)
);

-- Affiliate click telemetry (feeds route-selection upgrades later)
CREATE TABLE IF NOT EXISTS clicks (
  id         BIGSERIAL PRIMARY KEY,
  deal_id    BIGINT REFERENCES deals (id),
  user_id    INTEGER,
  referer    TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============ ops ============

CREATE TABLE IF NOT EXISTS worker_heartbeat (
  job     TEXT PRIMARY KEY,
  last_ok TIMESTAMPTZ NOT NULL DEFAULT now(),
  note    TEXT
);
