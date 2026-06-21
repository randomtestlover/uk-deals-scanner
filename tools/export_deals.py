"""Export a public deals snapshot (docs/deals.json) for the website.

Reads recent deals from Supabase and writes a compact, de-duplicated JSON
file that the static deals page (docs/deals.html) fetches client-side. This
keeps every database credential server-side: the browser only ever sees a
flat file, served free (and CDN-cached) from GitHub Pages.

Run from the repo root, after the scan:

    python -m tools.export_deals

Best-effort by design: on any failure it logs a warning and exits 0,
leaving the previous snapshot in place so the page keeps serving the last
good data instead of going blank.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from core.config import Secrets
from core.db import DB

OUT_PATH = Path("docs/deals.json")
DAYS = 30               # only surface reasonably fresh deals
MAX_DEALS = 400         # cap the file size after de-duplication


def _shape(rows: list[dict]) -> list[dict]:
    """De-duplicate to the most recent row per product (ASIN, else URL) and
    project each to the compact shape the page renders. Rows arrive newest
    first, so the first time we see a product is its latest price."""
    seen: set[str] = set()
    out: list[dict] = []
    for r in rows:
        key = (r.get("asin") or r.get("url") or "").strip()
        if not key or key in seen:
            continue
        try:
            price = float(r["current_price"])
        except (TypeError, KeyError, ValueError):
            continue
        if price <= 0:
            continue
        seen.add(key)

        was = r.get("ref_price")
        pct = r.get("pct_off")
        out.append(
            {
                "title": (r.get("title") or "").strip(),
                "category": (r.get("category") or "deals").strip(),
                "price": round(price, 2),
                "was": round(float(was), 2) if was is not None else None,
                "pct": round(float(pct)) if pct is not None else None,
                "score": int(r.get("deal_score") or 0),
                "in_stock": bool(r.get("in_stock", True)),
                "url": (r.get("affiliate_url") or r.get("url") or "").strip(),
                "added": r.get("created_at") or "",
            }
        )
        if len(out) >= MAX_DEALS:
            break
    return out


def main() -> int:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    if not url or not key:
        print("[export] SUPABASE_URL / SUPABASE_SERVICE_KEY missing — skipping.")
        return 0

    try:
        db = DB(Secrets._clean_url(url), key)
        deals = _shape(db.recent_deals(days=DAYS))
    except Exception as e:  # never fail the CI job over a snapshot refresh
        print(f"[export] failed ({type(e).__name__}) — keeping existing snapshot.")
        return 0

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": len(deals),
        "deals": deals,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"[export] wrote {OUT_PATH} with {len(deals)} deal(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
