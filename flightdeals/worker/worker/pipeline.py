"""Pipeline stages. Each stage is independently runnable from the CLI."""
from __future__ import annotations

import logging
import time

from .alerts import run_alerts
from .config import Config
from .db import DB
from .detect import evaluate
from .sources.kiwi import KiwiVerifier
from .sources.travelpayouts import TravelpayoutsSource
from .telegram import TelegramPoster

log = logging.getLogger(__name__)

SWEEP_PAUSE_SECONDS = 0.15  # polite pacing between route queries


def stage_seed(db: DB, cfg: Config) -> None:
    db.seed(cfg.airports, cfg.routes())
    log.info("seeded %d airports, %d routes", len(cfg.airports), len(cfg.routes()))


def stage_sweep(db: DB, cfg: Config, limit: int | None = None) -> int:
    """Sweep cached fares for every active route into price_snapshots."""
    if not cfg.secrets.travelpayouts_token:
        log.warning("TRAVELPAYOUTS_TOKEN not set — skipping sweep")
        return 0
    source = TravelpayoutsSource(
        cfg.secrets.travelpayouts_token,
        cfg.secrets.travelpayouts_marker,
        months_ahead=int(cfg.detection.get("sweep_months_ahead", 2)),
    )
    routes = db.active_routes()
    if limit:
        routes = routes[:limit]
    total = 0
    for route in routes:
        snaps = source.sweep(route["origin"], route["destination"])
        total += db.insert_snapshots(route["id"], snaps)
        time.sleep(SWEEP_PAUSE_SECONDS)
    db.recompute_baselines(int(cfg.detection.get("baseline_days", 90)))
    log.info("sweep complete: %d snapshots across %d routes", total, len(routes))
    return total


def stage_detect(db: DB, cfg: Config) -> int:
    """Evaluate the cheapest recent snapshot per route; store new deals."""
    det = cfg.detection
    min_samples = int(det.get("min_samples", 5))
    sale_discount = float(det.get("sale_discount", 0.25))
    dedupe_days = int(det.get("dedupe_days", 7))
    bucket = int(det.get("price_bucket_gbp", 10))

    verifier = (
        KiwiVerifier(cfg.secrets.kiwi_api_key) if cfg.secrets.kiwi_api_key else None
    )

    found = 0
    with db.conn.cursor() as cur:
        cur.execute(
            """SELECT DISTINCT ON (route_id)
                 route_id, depart_date, return_date, price_gbp, airline, source,
                 r.origin, r.destination, r.dest_name, r.band, r.tier
               FROM price_snapshots ps
               JOIN routes r ON r.id = ps.route_id
               WHERE ps.found_at > now() - interval '36 hours'
               ORDER BY route_id, price_gbp ASC"""
        )
        cheapest = cur.fetchall()
    baselines = {r["id"]: r for r in db.active_routes()}

    from .models import FareSnapshot

    for row in cheapest:
        route = baselines.get(row["route_id"])
        if not route:
            continue
        snapshot = FareSnapshot(
            origin=row["origin"],
            destination=row["destination"],
            depart_date=row["depart_date"],
            return_date=row["return_date"],
            price_gbp=float(row["price_gbp"]),
            airline=row["airline"],
            source=row["source"],
        )
        candidate = evaluate(
            snapshot,
            route_id=row["route_id"],
            dest_name=row["dest_name"],
            band=row["band"],
            tier=row["tier"],
            baseline_gbp=float(route["median_gbp"]) if route["median_gbp"] else None,
            sample_count=route["sample_count"],
            floor_gbp=cfg.floor_for_band(row["band"]),
            min_samples=min_samples,
            sale_discount=sale_discount,
        )
        if not candidate:
            continue
        fare_hash = snapshot.fare_hash(bucket)
        if db.fare_hash_seen_recently(fare_hash, dedupe_days):
            continue
        if verifier:
            verified = verifier.verify(snapshot)
            if verified is None:
                log.info("kiwi could not verify %s-%s £%.0f — dropping",
                         snapshot.origin, snapshot.destination, snapshot.price_gbp)
                continue
            candidate.snapshot = verified
        deal_id = db.insert_deal(candidate, fare_hash)
        found += 1
        log.info(
            "DEAL #%s %s→%s £%.0f trigger=%s pct=%s",
            deal_id, snapshot.origin, snapshot.destination,
            candidate.snapshot.price_gbp, candidate.trigger, candidate.discount_pct,
        )
    log.info("detect complete: %d new deals", found)
    return found


def stage_post(db: DB, cfg: Config, limit: int | None = None) -> int:
    """Post fresh hub-route deals to the free Telegram channel."""
    max_posts = limit or int(cfg.detection.get("max_posts_per_run", 6))
    deals = db.unposted_deals(tier="free", limit=max_posts)
    if not deals:
        log.info("nothing to post")
        return 0
    if cfg.shadow or not (cfg.secrets.telegram_bot_token and cfg.secrets.telegram_channel_id):
        for d in deals:
            log.info("[shadow] would post: %s→%s £%.0f",
                     d["origin"], d["destination"], float(d["price_gbp"]))
        return 0
    poster = TelegramPoster(
        cfg.secrets.telegram_bot_token,
        cfg.secrets.telegram_channel_id,
        cfg.secrets.site_base_url,
    )
    posted = 0
    for d in deals:
        if poster.post_deal(d):
            db.mark_posted(d["id"])
            posted += 1
    log.info("posted %d deals to telegram", posted)
    return posted


def stage_alerts(db: DB, cfg: Config) -> int:
    poster = None
    if cfg.secrets.telegram_bot_token and cfg.secrets.telegram_channel_id:
        poster = TelegramPoster(
            cfg.secrets.telegram_bot_token,
            cfg.secrets.telegram_channel_id,
            cfg.secrets.site_base_url,
        )
    return run_alerts(db, cfg.secrets, poster, shadow=cfg.shadow)


def stage_prune(db: DB, cfg: Config) -> int:
    return db.prune_snapshots(int(cfg.detection.get("snapshot_retention_days", 120)))
