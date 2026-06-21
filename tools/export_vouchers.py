"""Scrape the configured voucher sources, merge with the previous snapshot,
and write docs/vouchers.json for the static codes page (docs/codes.html).

Run from the repo root, after the scan:

    python -m tools.export_vouchers

File-based and resilient: codes are merged into the previous snapshot, so a
transient scrape failure never blanks the page. Expired and stale codes are
dropped. No database is involved — sources are defined in config.yaml under
`voucher_sources`, which is OFF until you configure and enable it.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from scanners.vouchers import VoucherScanner

CONFIG_PATH = "config.yaml"
OUT_PATH = Path("docs/vouchers.json")
FRESH_DAYS = 14        # drop codes not re-seen within this many days


def _key(merchant, code, title) -> str:
    tail = (code or title or "").lower()
    return f"{(merchant or '').lower()}|{tail}"


def _is_expired(expires) -> bool:
    if not expires:
        return False
    try:
        return date.fromisoformat(str(expires)[:10]) < date.today()
    except ValueError:
        return False


def _is_stale(last_seen) -> bool:
    try:
        seen = datetime.fromisoformat(str(last_seen).replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return True
    return (datetime.now(timezone.utc) - seen).days >= FRESH_DAYS


def _load_existing() -> dict:
    if not OUT_PATH.exists():
        return {}
    try:
        data = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for v in data.get("vouchers", []):
        out[_key(v.get("merchant", ""), v.get("code"), v.get("title", ""))] = v
    return out


def _build_scanners(cfg: dict):
    vs = cfg.get("voucher_sources") or {}
    if not vs.get("enabled", False):
        return [], vs
    sf = cfg.get("scrape_fallback") or {}
    ua = sf.get("user_agent", "UKDealsScanner/1.0")
    mn = float(sf.get("min_delay_seconds", 0) or 0)
    mx = float(sf.get("max_delay_seconds", 0) or 0)
    respect = bool(vs.get("respect_robots", True))
    scanners = []
    for src in (vs.get("sources") or []):
        if not src.get("enabled", True):
            continue
        scanners.append(
            VoucherScanner(src, user_agent=ua, respect_robots=respect,
                           min_delay=mn, max_delay=mx)
        )
    return scanners, vs


def main() -> int:
    try:
        cfg = yaml.safe_load(Path(CONFIG_PATH).read_text(encoding="utf-8")) or {}
    except Exception as e:
        print(f"[vouchers] cannot read config.yaml: {type(e).__name__}")
        return 0

    scanners, vs = _build_scanners(cfg)
    if not vs.get("enabled", False):
        print("[vouchers] voucher_sources.enabled is false — nothing to do.")
        return 0
    if not scanners:
        print("[vouchers] no enabled sources configured.")
        return 0

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing = _load_existing()
    merged: dict = {}

    scraped = 0
    for sc in scanners:
        try:
            for v in sc.scan():
                prev = existing.get(v.dedupe_key)
                merged[v.dedupe_key] = {
                    "merchant": v.merchant,
                    "title": v.title,
                    "code": v.code,
                    "category": v.category,
                    "url": v.url,
                    "expires": v.expires,
                    "first_seen": prev.get("first_seen") if prev else now,
                    "last_seen": now,
                }
                scraped += 1
        except Exception as e:
            print(f"[vouchers] source failed: {type(e).__name__}")
        finally:
            sc.close()

    # Carry over still-fresh, unexpired codes we didn't re-scrape this run.
    carried = 0
    for k, prev in existing.items():
        if k in merged:
            continue
        if _is_expired(prev.get("expires")) or _is_stale(prev.get("last_seen", "")):
            continue
        merged[k] = prev
        carried += 1

    vouchers = [v for v in merged.values() if not _is_expired(v.get("expires"))]
    vouchers.sort(key=lambda v: (v.get("last_seen") or "", v.get("merchant") or ""), reverse=True)

    payload = {"generated_at": now, "count": len(vouchers), "vouchers": vouchers}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"[vouchers] scraped {scraped}, carried {carried}, wrote {len(vouchers)} code(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
