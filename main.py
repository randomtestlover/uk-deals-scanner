"""Entry point. Run a single scan cycle:

  scan feeds -> validate -> record price history -> score
             -> filter -> dedupe -> persist -> post to Telegram

Usage:
  python main.py            # live run (posts to Telegram)
  python main.py --test     # dry run: scores + prints, never posts
  python main.py --limit 3  # override max_per_run for this run
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import traceback
from datetime import datetime, timezone

from bot.telegram_poster import TelegramPoster, format_message
from core.affiliate import build_outbound_url
from core.config import Config
from core.db import DB
from core.dealscore import score_deal
from core.models import RawDeal, ScoredDeal
from scanners.camel_rss import CamelScanner
from scanners.awin import AwinScanner


def in_quiet_hours(quiet_hours: list[int]) -> bool:
    return datetime.now(timezone.utc).hour in set(quiet_hours)


def _redact(text: str) -> str:
    """Strip anything secret-like from a string before it is logged, so
    API keys / tokens / feed URLs can never appear in CI logs even if an
    exception embeds them. Defense-in-depth: the scanners already swallow
    their own URL-bearing errors."""
    import re as _re
    s = str(text)
    # Full URLs (Awin feed URLs carry the API key in the path/query).
    s = _re.sub(r"https?://[^\s'\"]+", "[url-redacted]", s)
    # Long opaque tokens / JWTs / api keys.
    s = _re.sub(r"\b[A-Za-z0-9_-]{24,}\b", "[token-redacted]", s)
    # Telegram bot-token shape: digits:longstring
    s = _re.sub(r"\b[0-9]{6,}:[A-Za-z0-9_-]{10,}\b", "[token-redacted]", s)
    return s


def build_scanners(cfg: Config):
    """Build a scanner per enabled category. Each category declares a
    `source:` of either 'ccc' (CamelCamelCamel RSS) or 'awin' (Awin
    datafeed). Defaults to 'ccc' for backward compatibility."""
    ua = cfg.scrape_fallback.get("user_agent", "UKDealsScanner/1.0")
    fb = cfg.scrape_fallback.get("enabled", False)
    mn = float(cfg.scrape_fallback.get("min_delay_seconds", 0))
    mx = float(cfg.scrape_fallback.get("max_delay_seconds", 0))
    min_pct = float(cfg.filters.get("min_discount_pct", 0))

    awin_feeds = cfg.awin_feed_urls()  # parsed from AWIN_FEED_URLS secret

    scanners = []
    for category, conf in cfg.categories.items():
        if not conf.get("enabled", False):
            continue
        source = (conf.get("source") or "ccc").lower()

        if source == "awin":
            # Each awin category can name which feeds to use by index/label,
            # but the simplest model: all awin categories share the secret
            # feed list and rely on keyword filtering to separate them.
            if not awin_feeds:
                print(f"[warn] category '{category}' is source=awin but "
                      f"AWIN_FEED_URLS secret is empty — skipping.")
                continue
            scanners.append(
                AwinScanner(
                    category=category,
                    feed_urls=awin_feeds,
                    keywords_any=conf.get("keywords_any", []),
                    user_agent=ua,
                    min_discount_pct=min_pct,
                    min_delay=mn,
                    max_delay=mx,
                )
            )
        else:  # ccc
            scanners.append(
                CamelScanner(
                    category=category,
                    feeds=conf.get("feeds", []),
                    keywords_any=conf.get("keywords_any", []),
                    user_agent=ua,
                    fallback_enabled=fb,
                    min_delay=mn,
                    max_delay=mx,
                )
            )
    return scanners


def score_and_filter(cfg: Config, db: DB | None, raw: RawDeal) -> ScoredDeal | None:
    """Apply history, scoring and threshold filters. Returns a ScoredDeal
    or None if the deal should be skipped."""
    if cfg.filters.get("require_in_stock", True) and not raw.in_stock:
        return None

    pct = raw.pct_off
    if pct is not None and pct < cfg.filters["min_discount_pct"]:
        return None

    hist_low = hist_avg = None
    if db is not None:
        db.record_price(raw)                    # build history over time
        hist_low, hist_avg = db.history_stats(raw)

    score = score_deal(
        current_price=raw.current_price,
        pct_off=pct,
        ref_price=raw.ref_price,
        hist_low=hist_low,
        hist_avg=hist_avg,
    )
    if score < cfg.filters["min_deal_score"]:
        return None

    aff = cfg.affiliate
    ct = cfg.click_tracking
    outbound = build_outbound_url(
        raw.url,
        amazon_tag=aff["amazon_tag"],
        category=raw.category,
        tracking_enabled=ct.get("enabled", False),
        worker_base=ct.get("worker_base_url", ""),
    )

    return ScoredDeal(
        source=raw.source,
        category=raw.category,
        title=raw.title,
        url=raw.url,
        affiliate_url=outbound,
        current_price=raw.current_price,
        ref_price=raw.ref_price,
        pct_off=pct,
        deal_score=score,
        in_stock=raw.in_stock,
        asin=raw.asin,
        dedupe_hash=raw.dedupe_hash,
    )


async def run(test: bool, limit_override: int | None) -> int:
    cfg = Config.load()

    dry_run = test or cfg.posting.get("dry_run_default", False)
    max_per_run = limit_override or cfg.posting["max_per_run"]

    poster: TelegramPoster | None = None
    db: DB | None = None

    try:
        # DB is optional in dry-run so you can test with zero setup.
        if not dry_run:
            db = DB(cfg.secrets.supabase_url, cfg.secrets.supabase_service_key)
            poster = TelegramPoster(
                cfg.secrets.telegram_bot_token, cfg.secrets.alert_chat_id
            )
        else:
            # Still init DB if creds exist, to exercise the real path.
            try:
                db = DB(cfg.secrets.supabase_url, cfg.secrets.supabase_service_key)
            except Exception:
                db = None

        if not dry_run and in_quiet_hours(cfg.posting.get("quiet_hours_utc", [])):
            print("[skip] within quiet hours — no posting this run.")
            return 0

        scanners = build_scanners(cfg)
        candidates: list[ScoredDeal] = []

        for scanner in scanners:
            try:
                for raw in scanner.scan():
                    if db is not None and db.already_posted(raw.dedupe_hash):
                        continue
                    scored = score_and_filter(cfg, db, raw)
                    if scored is None:
                        continue
                    if db is not None and db.already_posted(scored.dedupe_hash):
                        continue
                    candidates.append(scored)
            except Exception as e:
                print(f"[warn] scanner '{scanner.name}' failed: {_redact(e)}")
            finally:
                scanner.close()

        # Best deals first; cap per run.
        candidates.sort(key=lambda d: d.deal_score, reverse=True)
        # De-dupe within this run by hash (a feed can repeat across categories).
        seen: set[str] = set()
        unique = []
        for c in candidates:
            if c.dedupe_hash in seen:
                continue
            seen.add(c.dedupe_hash)
            unique.append(c)
        selected = unique[:max_per_run]

        print(f"[info] {len(unique)} qualifying deals; posting {len(selected)} "
              f"(dry_run={dry_run}).")

        posted = 0
        for deal in selected:
            if dry_run:
                print("\n--- WOULD POST ---")
                print(format_message(deal, cfg.affiliate["disclosure"]))
                posted += 1
                continue

            channel = cfg.channel_for(deal.category)
            deal_id = db.save_deal(deal) if db else None
            message_id = await poster.post_deal(
                deal, channel, cfg.affiliate["disclosure"]
            )
            if deal_id and db:
                db.record_post(deal_id, channel, message_id)
            if message_id:
                posted += 1

        print(f"[done] posted {posted} deal(s).")
        return 0

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[error] run failed: {_redact(e)}\n{_redact(tb)}", file=sys.stderr)
        if poster is not None:
            await poster.alert(f"Scan run failed: {_redact(e)}")
        return 1


def main() -> None:
    ap = argparse.ArgumentParser(description="UK Deals Scanner")
    ap.add_argument("--test", action="store_true", help="dry run; print only")
    ap.add_argument("--limit", type=int, default=None, help="override max_per_run")
    args = ap.parse_args()
    sys.exit(asyncio.run(run(args.test, args.limit)))


if __name__ == "__main__":
    main()
