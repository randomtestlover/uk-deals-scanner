#!/usr/bin/env python3
"""FlightDeals UK worker CLI.

Usage (Coolify scheduled task runs `python main.py all` nightly):
  python main.py migrate            # apply db/migrations/*.sql
  python main.py seed               # upsert airports/routes from config.yaml
  python main.py sweep [--limit N]  # cached-fare sweep -> price_snapshots
  python main.py detect             # detection engine -> deals
  python main.py post [--limit N]   # post hub deals to the free Telegram channel
  python main.py alerts             # saved-route alert fan-out (email + TG DM)
  python main.py prune              # snapshot retention
  python main.py all [--shadow]     # full pipeline

--shadow (or SHADOW_MODE=1): log would-post/would-alert, send nothing.
"""
from __future__ import annotations

import argparse
import logging
import sys

from worker.config import Config, ConfigError, redact
from worker.db import DB
from worker.telegram import admin_alert
from worker import pipeline

log = logging.getLogger("main")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="FlightDeals UK worker")
    p.add_argument("stage", choices=[
        "migrate", "seed", "sweep", "detect", "post", "alerts", "prune", "all",
    ])
    p.add_argument("--shadow", action="store_true", help="log instead of posting")
    p.add_argument("--limit", type=int, default=None, help="cap routes/posts this run")
    p.add_argument("--config", default="config.yaml")
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = build_parser().parse_args(argv)

    try:
        cfg = Config.load(args.config, shadow=args.shadow)
    except ConfigError as exc:
        log.error("config error: %s", exc)
        return 2

    db = DB(cfg.secrets.database_url)
    try:
        if args.stage in ("migrate", "all"):
            applied = db.migrate()
            log.info("migrations applied: %s", applied or "none (up to date)")
        if args.stage in ("seed", "all"):
            pipeline.stage_seed(db, cfg)
        if args.stage in ("sweep", "all"):
            pipeline.stage_sweep(db, cfg, limit=args.limit)
        if args.stage in ("detect", "all"):
            pipeline.stage_detect(db, cfg)
        if args.stage in ("post", "all"):
            pipeline.stage_post(db, cfg, limit=args.limit)
        if args.stage in ("alerts", "all"):
            pipeline.stage_alerts(db, cfg)
        if args.stage in ("prune", "all"):
            pipeline.stage_prune(db, cfg)
        db.heartbeat(args.stage, "ok")
        return 0
    except Exception as exc:  # noqa: BLE001 — single top-level catch: alert + fail
        msg = redact(f"{args.stage} failed: {exc!r}", cfg.secrets)
        log.exception(msg)
        admin_alert(cfg.secrets.telegram_bot_token, cfg.secrets.admin_chat_id, msg)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
