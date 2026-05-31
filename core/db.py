"""Supabase/Postgres data layer.

Run the SQL in SCHEMA_SQL once in the Supabase SQL editor (SETUP.md walks
through this). All reads/writes go through this module so the rest of the
code never touches the DB client directly.
"""

from __future__ import annotations

from typing import Optional

from supabase import Client, create_client

from .models import RawDeal, ScoredDeal

# ---------------------------------------------------------------------------
# One-time schema. Paste into Supabase -> SQL Editor -> Run.
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

-- Premium-ready; unused by the MVP but architected now.
create table if not exists subscribers (
    id          bigint generated always as identity primary key,
    tg_user_id  bigint unique not null,
    tier        text not null default 'free',
    categories  text[] not null default '{}',
    joined_at   timestamptz not null default now()
);
"""


class DB:
    def __init__(self, url: str, service_key: str):
        self.client: Client = create_client(url, service_key)

    # --- dedupe ---------------------------------------------------------
    def already_posted(self, dedupe_hash: str) -> bool:
        res = (
            self.client.table("deals")
            .select("id")
            .eq("dedupe_hash", dedupe_hash)
            .limit(1)
            .execute()
        )
        return bool(res.data)

    # --- price history --------------------------------------------------
    def record_price(self, deal: RawDeal) -> None:
        try:
            self.client.table("price_history").insert(
                {"asin": deal.asin, "url": deal.url, "price": deal.current_price}
            ).execute()
        except Exception:
            # Recording history is best-effort; never let it abort a scan.
            pass

    def history_stats(self, deal: RawDeal) -> tuple[Optional[float], Optional[float]]:
        """Return (hist_low, hist_avg) from stored price history, or (None, None).

        History is keyed on ASIN only. Raw product URLs contain query strings
        (?, &, =) that break PostgREST's URL path, so we never filter by URL.
        When there is no ASIN, we simply report no history yet (scoring then
        falls back to discount depth, which is the intended behaviour)."""
        if not deal.asin:
            return None, None
        try:
            res = (
                self.client.table("price_history")
                .select("price")
                .eq("asin", deal.asin)
                .order("captured_at", desc=True)
                .limit(200)
                .execute()
            )
        except Exception:
            return None, None
        prices = [float(r["price"]) for r in (res.data or []) if r.get("price")]
        if len(prices) < 3:               # not enough signal yet
            return None, None
        return min(prices), sum(prices) / len(prices)

    # --- persistence ----------------------------------------------------
    def save_deal(self, deal: ScoredDeal) -> Optional[int]:
        res = (
            self.client.table("deals")
            .insert(
                {
                    "dedupe_hash": deal.dedupe_hash,
                    "source": deal.source,
                    "category": deal.category,
                    "title": deal.title,
                    "url": deal.url,
                    "affiliate_url": deal.affiliate_url,
                    "asin": deal.asin,
                    "current_price": deal.current_price,
                    "ref_price": deal.ref_price,
                    "pct_off": deal.pct_off,
                    "deal_score": deal.deal_score,
                    "in_stock": deal.in_stock,
                }
            )
            .execute()
        )
        return res.data[0]["id"] if res.data else None

    def record_post(self, deal_id: int, channel: str, message_id: Optional[int]) -> None:
        self.client.table("posts").insert(
            {"deal_id": deal_id, "channel": channel, "message_id": message_id}
        ).execute()
