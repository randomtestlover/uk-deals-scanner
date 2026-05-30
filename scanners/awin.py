"""Awin datafeed scanner.

Reads an Awin "Create-a-Feed" product datafeed (CSV, optionally gzipped)
and yields RawDeal objects. Unlike CCC, the affiliate tracking link is
already baked into the feed (the 'aw_deep_link' column), so no tag
injection is needed — clicks are attributed to you automatically.

The feed URL contains your API key, so it lives in GitHub Secrets
(AWIN_FEED_URLS), not in config.yaml. Multiple feeds (one per retailer)
are supported, separated by '|'.

Feed columns we use (Awin's standard names):
  - product_name
  - aw_deep_link        -> the affiliate link (what we post)
  - search_price        -> current price
  - rrp_price           -> reference / was price (may be blank)
  - merchant_name       -> retailer
  - merchant_category   -> category hint
  - in_stock            -> "1"/"0" or "yes"/"no"
  - aw_product_id       -> stable id for dedupe
"""

from __future__ import annotations

import csv
import gzip
import io
from typing import Iterable

from core.models import RawDeal
from scanners.base import BaseScanner


def _to_float(value: str) -> float | None:
    if not value:
        return None
    cleaned = value.strip().replace("£", "").replace(",", "")
    try:
        f = float(cleaned)
        return f if f > 0 else None
    except ValueError:
        return None


def _in_stock(value: str) -> bool:
    if value is None:
        return True
    v = value.strip().lower()
    if v in ("0", "no", "false", "out of stock", "n"):
        return False
    return True


class AwinScanner(BaseScanner):
    name = "awin"

    def __init__(self, category: str, feed_urls: list[str], keywords_any: list[str],
                 user_agent: str, min_discount_pct: float,
                 max_rows: int = 50000, min_delay: float = 0.0, max_delay: float = 0.0):
        super().__init__(user_agent, min_delay, max_delay, timeout=60.0)
        self.category = category
        self.feed_urls = feed_urls
        self.keywords = [k.lower() for k in (keywords_any or [])]
        self.min_discount_pct = min_discount_pct
        self.max_rows = max_rows

    def _matches_keywords(self, text: str) -> bool:
        if not self.keywords:
            return True
        t = text.lower()
        return any(k in t for k in self.keywords)

    def _read_feed_text(self, url: str) -> str | None:
        """Fetch a feed; transparently handle gzip."""
        self._polite_sleep()
        try:
            resp = self.fetch(url)
        except Exception:
            return None
        content = resp.content
        # Awin feeds are often gzipped regardless of extension.
        if content[:2] == b"\x1f\x8b":
            try:
                content = gzip.decompress(content)
            except Exception:
                return None
        try:
            return content.decode("utf-8", errors="replace")
        except Exception:
            return None

    def _parse_feed(self, url: str) -> list[RawDeal]:
        text = self._read_feed_text(url)
        if not text:
            return []

        deals: list[RawDeal] = []
        reader = csv.DictReader(io.StringIO(text))
        for i, row in enumerate(reader):
            if i >= self.max_rows:
                break

            name = (row.get("product_name") or "").strip()
            link = (row.get("aw_deep_link") or "").strip()
            if not name or not link:
                continue

            current = _to_float(row.get("search_price", ""))
            rrp = _to_float(row.get("rrp_price", ""))
            if not current:
                continue

            # Only keep genuine discounts: current must be below RRP by
            # at least the configured threshold. No RRP -> not a "deal".
            if not rrp or rrp <= current:
                continue
            pct_off = (1 - current / rrp) * 100
            if pct_off < self.min_discount_pct:
                continue

            merchant = (row.get("merchant_name") or "").strip()
            cat_hint = (row.get("merchant_category") or "").strip()
            if not self._matches_keywords(f"{name} {cat_hint}"):
                continue

            title = f"{name}" + (f" ({merchant})" if merchant else "")

            try:
                deals.append(
                    RawDeal(
                        source=f"awin:{self.category}",
                        category=self.category,
                        title=title[:400],
                        url=link,
                        current_price=current,
                        ref_price=rrp,
                        in_stock=_in_stock(row.get("in_stock", "")),
                        # aw_product_id gives a stable dedupe identity.
                        asin=(row.get("aw_product_id") or "").strip() or None,
                    )
                )
            except Exception:
                continue
        return deals

    def scan(self) -> Iterable[RawDeal]:
        seen: set[str] = set()
        for url in self.feed_urls:
            for d in self._parse_feed(url):
                if d.url in seen:
                    continue
                seen.add(d.url)
                yield d
