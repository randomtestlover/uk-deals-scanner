"""CamelCamelCamel UK price-drop RSS scanner.

Primary source: CCC's free RSS feeds (no API key). Each entry typically
contains the product title, link, and current + previous prices in the
summary text, which we parse into current_price / ref_price.

If a feed fails entirely, and scrape_fallback is enabled, we fall back to
a light HTML read of the feed's HTML page equivalent. CCC is donation-run
with no uptime guarantee, so the fallback prevents a single point of failure.
"""

from __future__ import annotations

import re
from typing import Iterable

import feedparser
from selectolax.parser import HTMLParser

from core.models import RawDeal
from scanners.base import BaseScanner, parse_price

# CCC UK RSS entries read exactly like:
#   "<title> - down 13.09% (£1.63) to £10.82 from £12.45"
# So we parse the explicit % drop, the 'to' (current) price, and the
# 'from' (was) price directly, which is far more reliable than guessing.
_PCT_RE = re.compile(r"down\s+([0-9]+(?:\.[0-9]+)?)\s*%", re.IGNORECASE)
_TO_RE = re.compile(r"\bto\s*£\s?([0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.IGNORECASE)
_FROM_RE = re.compile(r"\bfrom\s*£\s?([0-9][0-9,]*(?:\.[0-9]{1,2})?)", re.IGNORECASE)


def _money(m) -> float | None:
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _extract_prices(text: str) -> tuple[float | None, float | None, float | None]:
    """Parse CCC's '... down N% (£x) to £CURRENT from £WAS' format.
    Returns (current, reference, pct_off). Falls back gracefully:
    if 'to'/'from' aren't found, uses the first £ as current."""
    text = text or ""
    pct = _money(_PCT_RE.search(text)) if _PCT_RE.search(text) else None

    current = _money(_TO_RE.search(text))
    ref = _money(_FROM_RE.search(text))

    # Fallback: no explicit 'to' price — take the first £ amount on the line.
    if current is None:
        current = parse_price(text)

    # Normalise if the two prices came out swapped.
    if current and ref and ref < current:
        current, ref = ref, current

    return current, ref, pct


class CamelScanner(BaseScanner):
    name = "ccc"

    def __init__(self, category: str, feeds: list[str], keywords_any: list[str],
                 user_agent: str, fallback_enabled: bool,
                 min_delay: float = 0.0, max_delay: float = 0.0):
        super().__init__(user_agent, min_delay, max_delay)
        self.category = category
        self.feeds = feeds
        self.keywords = [k.lower() for k in (keywords_any or [])]
        self.fallback_enabled = fallback_enabled

    def _matches_keywords(self, title: str) -> bool:
        if not self.keywords:
            return True
        t = title.lower()
        return any(k in t for k in self.keywords)

    def _parse_feed(self, feed_url: str) -> list[RawDeal]:
        deals: list[RawDeal] = []
        # feedparser fetches internally; pass our UA for politeness.
        parsed = feedparser.parse(feed_url, agent=self.user_agent)
        for entry in parsed.entries:
            raw_title = getattr(entry, "title", "") or ""
            link = getattr(entry, "link", "") or ""
            summary = getattr(entry, "summary", "") or ""
            if not raw_title or not link:
                continue

            blob = f"{raw_title} {summary}"
            current, ref, pct = _extract_prices(blob)
            if not current:
                continue

            # The product name is the part of the title before " - down ...".
            clean_title = re.split(r"\s+-\s+down\s", raw_title, flags=re.IGNORECASE)[0].strip()
            if not clean_title:
                clean_title = raw_title.strip()

            if not self._matches_keywords(clean_title):
                continue

            # If CCC gave a % drop but no explicit 'from' price, derive the
            # reference price from the % so discount filtering still works.
            if ref is None and pct and pct > 0 and pct < 100:
                ref = round(current / (1 - pct / 100.0), 2)

            try:
                deals.append(
                    RawDeal(
                        source=f"ccc:{self.category}",
                        category=self.category,
                        title=clean_title[:400],
                        url=link,
                        current_price=current,
                        ref_price=ref,
                        in_stock=True,  # CCC drop feeds imply availability
                    )
                )
            except Exception:
                # Validation failed for this entry — skip it, never crash.
                continue
        return deals

    def _scrape_fallback(self, feed_url: str) -> list[RawDeal]:
        if not self.fallback_enabled:
            return []
        html_url = feed_url.replace("/feed", "")
        self._polite_sleep()
        try:
            resp = self.fetch(html_url)
        except Exception:
            return []
        tree = HTMLParser(resp.text)
        deals: list[RawDeal] = []
        for row in tree.css("a[href*='/product/']"):
            title = row.text(strip=True)
            href = row.attributes.get("href", "")
            if not title or not href or not self._matches_keywords(title):
                continue
            if href.startswith("/"):
                href = "https://uk.camelcamelcamel.com" + href
            current = parse_price(title)
            if not current:
                continue
            try:
                deals.append(
                    RawDeal(
                        source=f"ccc-scrape:{self.category}",
                        category=self.category,
                        title=title,
                        url=href,
                        current_price=current,
                        ref_price=None,
                        in_stock=True,
                    )
                )
            except Exception:
                continue
        return deals

    def scan(self) -> Iterable[RawDeal]:
        seen_links: set[str] = set()
        for feed_url in self.feeds:
            self._polite_sleep()
            try:
                deals = self._parse_feed(feed_url)
                if not deals:
                    deals = self._scrape_fallback(feed_url)
            except Exception:
                deals = self._scrape_fallback(feed_url)
            for d in deals:
                if d.url in seen_links:
                    continue
                seen_links.add(d.url)
                yield d
