"""Postgres data-access layer (psycopg3) + SQL-file migrator."""
from __future__ import annotations

import logging
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .models import DealCandidate, FareSnapshot

log = logging.getLogger(__name__)

def _find_migrations_dir() -> Path:
    here = Path(__file__).resolve().parent
    # repo layout: <repo>/worker/worker/db.py -> <repo>/db/migrations
    # container layout: /app/worker/db.py -> /app/db/migrations
    for base in (here.parent.parent, here.parent):
        candidate = base / "db" / "migrations"
        if candidate.is_dir():
            return candidate
    return here.parent.parent / "db" / "migrations"


MIGRATIONS_DIR = _find_migrations_dir()


class DB:
    def __init__(self, database_url: str):
        self.conn = psycopg.connect(database_url, row_factory=dict_row, autocommit=False)

    def close(self) -> None:
        self.conn.close()

    # ---------- migrations ----------

    def migrate(self, migrations_dir: Path | None = None) -> list[str]:
        migrations_dir = migrations_dir or MIGRATIONS_DIR
        applied: list[str] = []
        with self.conn.cursor() as cur:
            cur.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                     version TEXT PRIMARY KEY,
                     applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                   )"""
            )
            cur.execute("SELECT version FROM schema_migrations")
            done = {r["version"] for r in cur.fetchall()}
            for path in sorted(migrations_dir.glob("*.sql")):
                if path.name in done:
                    continue
                log.info("applying migration %s", path.name)
                cur.execute(path.read_text())
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,)
                )
                applied.append(path.name)
        self.conn.commit()
        return applied

    # ---------- seeding (config -> airports/routes) ----------

    def seed(self, airports: list[dict], routes: list[dict]) -> None:
        with self.conn.cursor() as cur:
            for a in airports:
                cur.execute(
                    """INSERT INTO airports (iata, name, city, tier)
                       VALUES (%(iata)s, %(name)s, %(city)s, %(tier)s)
                       ON CONFLICT (iata) DO UPDATE
                         SET name = EXCLUDED.name, city = EXCLUDED.city,
                             tier = EXCLUDED.tier, active = TRUE""",
                    a,
                )
            for r in routes:
                cur.execute(
                    """INSERT INTO routes (origin, destination, dest_name, band, tier)
                       VALUES (%(origin)s, %(destination)s, %(dest_name)s, %(band)s, %(tier)s)
                       ON CONFLICT (origin, destination) DO UPDATE
                         SET dest_name = EXCLUDED.dest_name, band = EXCLUDED.band,
                             tier = EXCLUDED.tier, active = TRUE""",
                    r,
                )
        self.conn.commit()

    def active_routes(self) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT r.id, r.origin, r.destination, r.dest_name, r.band, r.tier,
                          b.median_gbp, COALESCE(b.sample_count, 0) AS sample_count
                   FROM routes r
                   LEFT JOIN route_baselines b ON b.route_id = r.id
                   WHERE r.active
                   ORDER BY r.id"""
            )
            return cur.fetchall()

    # ---------- snapshots & baselines ----------

    def insert_snapshots(self, route_id: int, snapshots: list[FareSnapshot]) -> int:
        if not snapshots:
            return 0
        with self.conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO price_snapshots
                     (route_id, depart_date, return_date, price_gbp, airline, source)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                [
                    (route_id, s.depart_date, s.return_date, s.price_gbp, s.airline, s.source)
                    for s in snapshots
                ],
            )
        self.conn.commit()
        return len(snapshots)

    def recompute_baselines(self, baseline_days: int = 90) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO route_baselines (route_id, median_gbp, sample_count, updated_at)
                   SELECT route_id,
                          percentile_cont(0.5) WITHIN GROUP (ORDER BY price_gbp),
                          count(*),
                          now()
                   FROM price_snapshots
                   WHERE found_at > now() - make_interval(days => %s)
                   GROUP BY route_id
                   ON CONFLICT (route_id) DO UPDATE
                     SET median_gbp = EXCLUDED.median_gbp,
                         sample_count = EXCLUDED.sample_count,
                         updated_at = now()""",
                (baseline_days,),
            )
            n = cur.rowcount
        self.conn.commit()
        return n

    def prune_snapshots(self, retention_days: int = 120) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM price_snapshots WHERE found_at < now() - make_interval(days => %s)",
                (retention_days,),
            )
            n = cur.rowcount
        self.conn.commit()
        return n

    # ---------- deals ----------

    def fare_hash_seen_recently(self, fare_hash: str, dedupe_days: int = 7) -> bool:
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT 1 FROM deals
                   WHERE fare_hash = %s
                     AND found_at > now() - make_interval(days => %s)
                   LIMIT 1""",
                (fare_hash, dedupe_days),
            )
            return cur.fetchone() is not None

    def insert_deal(self, c: DealCandidate, fare_hash: str) -> int:
        s = c.snapshot
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO deals
                     (route_id, price_gbp, baseline_gbp, discount_pct, trigger,
                      depart_date, return_date, airline, deep_link, fare_hash)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (
                    c.route_id, s.price_gbp, c.baseline_gbp, c.discount_pct, c.trigger,
                    s.depart_date, s.return_date, s.airline, s.deep_link, fare_hash,
                ),
            )
            deal_id = cur.fetchone()["id"]
        self.conn.commit()
        return deal_id

    def unposted_deals(self, tier: str = "free", limit: int = 6) -> list[dict]:
        """Fresh deals not yet posted to Telegram. Free channel gets hub routes only."""
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT d.*, r.origin, r.destination, r.dest_name, r.band, r.tier
                   FROM deals d JOIN routes r ON r.id = d.route_id
                   WHERE d.posted_telegram_at IS NULL
                     AND d.expires_at > now()
                     AND r.tier = %s
                   ORDER BY d.discount_pct DESC NULLS LAST, d.price_gbp ASC
                   LIMIT %s""",
                (tier, limit),
            )
            return cur.fetchall()

    def mark_posted(self, deal_id: int) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE deals SET posted_telegram_at = now() WHERE id = %s", (deal_id,)
            )
        self.conn.commit()

    # ---------- alerts ----------

    def matching_alerts(self, deal: dict) -> list[dict]:
        """Active alerts matched by origin, optional destination, optional price cap."""
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT a.id AS alert_id, a.user_id, a.channels,
                          u.email, t.telegram_chat_id
                   FROM alerts a
                   JOIN users u ON u.id = a.user_id
                   LEFT JOIN telegram_links t ON t.user_id = a.user_id
                   WHERE a.active
                     AND a.origin = %s
                     AND (a.destination IS NULL OR a.destination = %s)
                     AND (a.max_price_gbp IS NULL OR a.max_price_gbp >= %s)""",
                (deal["origin"], deal["destination"], deal["price_gbp"]),
            )
            return cur.fetchall()

    def recent_unnotified_deals(self, hours: int = 24) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT d.*, r.origin, r.destination, r.dest_name, r.band, r.tier
                   FROM deals d JOIN routes r ON r.id = d.route_id
                   WHERE d.found_at > now() - make_interval(hours => %s)
                     AND d.expires_at > now()""",
                (hours,),
            )
            return cur.fetchall()

    # ---------- ops ----------

    def heartbeat(self, job: str, note: str = "") -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO worker_heartbeat (job, last_ok, note)
                   VALUES (%s, now(), %s)
                   ON CONFLICT (job) DO UPDATE SET last_ok = now(), note = EXCLUDED.note""",
                (job, note),
            )
        self.conn.commit()
