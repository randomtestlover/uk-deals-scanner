"""Postgres data layer (self-hosted, via psycopg).

All reads/writes go through this module so the rest of the code never
touches the DB client directly. Call DB.init_schema() once on startup to
create the tables if they don't exist (idempotent).
"""

from __future__ import annotations

from typing import Optional

import psycopg
from psycopg.rows import dict_row

from .models import RawDeal, ScoredDeal

# ---------------------------------------------------------------------------
# Schema. Created automatically by init_schema() on first run (idempotent).
# ---------------------------------------------------------------------------
SCHEMA_SQL = """
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
"""


class DB:
    def __init__(self, database_url: str):
        # autocommit so each statement persists immediately; matches the
        # previous fire-and-forget Supabase behaviour.
        self.conn = psycopg.connect(database_url, autocommit=True, row_factory=dict_row)

    # --- schema ---------------------------------------------------------
    def init_schema(self) -> None:
        """Create tables/indexes if absent. Safe to call every run."""
        with self.conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)

    # --- dedupe ---------------------------------------------------------
    def already_posted(self, dedupe_hash: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute(
                "select 1 from deals where dedupe_hash = %s limit 1",
                (dedupe_hash,),
            )
            return cur.fetchone() is not None

    # --- price history --------------------------------------------------
    def record_price(self, deal: RawDeal) -> None:
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "insert into price_history (asin, url, price) values (%s, %s, %s)",
                    (deal.asin, deal.url, deal.current_price),
                )
        except Exception:
            # Recording history is best-effort; never abort a scan.
            pass

    def history_stats(self, deal: RawDeal) -> tuple[Optional[float], Optional[float]]:
        """Return (hist_low, hist_avg) from stored price history, or (None, None).
        Keyed on ASIN only; products without an ASIN report no history yet."""
        if not deal.asin:
            return None, None
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "select price from price_history where asin = %s "
                    "order by captured_at desc limit 200",
                    (deal.asin,),
                )
                rows = cur.fetchall()
        except Exception:
            return None, None
        prices = [float(r["price"]) for r in (rows or []) if r.get("price") is not None]
        if len(prices) < 3:  # not enough signal yet
            return None, None
        return min(prices), sum(prices) / len(prices)

    # --- persistence ----------------------------------------------------
    def save_deal(self, deal: ScoredDeal) -> Optional[int]:
        with self.conn.cursor() as cur:
            cur.execute(
                "insert into deals (dedupe_hash, source, category, title, url, "
                "affiliate_url, asin, current_price, ref_price, pct_off, deal_score, "
                "in_stock) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "on conflict (dedupe_hash) do nothing returning id",
                (
                    deal.dedupe_hash,
                    deal.source,
                    deal.category,
                    deal.title,
                    deal.url,
                    deal.affiliate_url,
                    deal.asin,
                    deal.current_price,
                    deal.ref_price,
                    deal.pct_off,
                    deal.deal_score,
                    deal.in_stock,
                ),
            )
            row = cur.fetchone()
            return row["id"] if row else None

    def record_post(self, deal_id: int, channel: str, message_id: Optional[int]) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "insert into posts (deal_id, channel, message_id) values (%s, %s, %s)",
                (deal_id, channel, message_id),
            )

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
