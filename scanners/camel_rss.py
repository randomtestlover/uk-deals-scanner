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

# CCC summaries often read like:
#   "Lowest new price: £49.99 (was £79.99)"  — order can vary.
_WAS_RE = re.compile(r"was\s*£\s?([0-9][0-9,]*\.?[0-9]{0,2})", re.IGNORECASE)


def _extract_prices(text: str) -> tuple[float | None, float | None]:
    """Return (current, reference). Current = first £ found; reference =
    the 'was' price if present, else None."""
    current = parse_price(text)
    ref = None
    m = _WAS_RE.search(text or "")
    if m:
        try:
            ref = float(m.group(1).replace(",", ""))
        except ValueError:
            ref = None
    # If both found but ordering put the higher one first, normalise:
    if current and ref and ref < current:
        current, ref = ref, current
    return current, ref


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
            title = getattr(entry, "title", "") or ""
            link = getattr(entry, "link", "") or ""
            summary = getattr(entry, "summary", "") or ""
            if not title or not link:
                continue
            if not self._matches_keywords(title):
                continue
            current, ref = _extract_prices(f"{title} {summary}")
            if not current:
                continue
            try:
                deals.append(
                    RawDeal(
                        source=f"ccc:{self.category}",
                        category=self.category,
                        title=title,
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
