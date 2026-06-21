"""Generic, configuration-driven voucher-code scanner.

Each source is declared in config.yaml under `voucher_sources`. For every
source we fetch its listing page and pull rows out with the CSS selectors you
provide, yielding validated VoucherCode objects.

Responsible-scraping guardrails (on by default):
  * robots.txt is fetched and obeyed per source (respect_robots: true). If a
    site disallows crawling — or we cannot verify it — the source is skipped.
  * polite randomised delays between requests (reuses scrape_fallback delays).
  * the bot identifies itself honestly via the configured User-Agent.
No anti-bot evasion is performed. You are responsible for only pointing this
at sources you are permitted to use.

NOTE: many voucher sites reveal the actual code only after a click/redirect
(it is not in the page HTML), so a plain scrape often captures the offer text
but not a usable code. Prefer sources that expose the code in the markup
(text or a data-* attribute), or use an affiliate-network promotions feed.
"""

from __future__ import annotations

from typing import Iterable
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from selectolax.parser import HTMLParser

from core.models import VoucherCode
from scanners.base import BaseScanner


class VoucherScanner(BaseScanner):
    name = "vouchers"

    def __init__(self, source: dict, user_agent: str, respect_robots: bool = True,
                 min_delay: float = 0.0, max_delay: float = 0.0, max_items: int = 200):
        super().__init__(user_agent, min_delay, max_delay, timeout=30.0)
        self.source_name = (source.get("name") or "vouchers").strip()
        self.list_url = (source.get("list_url") or "").strip()
        self.row_selector = source.get("row_selector") or ""
        self.title_selector = source.get("title_selector") or ""
        self.code_selector = source.get("code_selector") or ""
        self.code_attr = source.get("code_attr") or ""
        self.merchant_selector = source.get("merchant_selector") or ""
        self.merchant_default = (source.get("merchant") or "").strip()
        self.link_selector = source.get("link_selector") or ""
        self.expires_selector = source.get("expires_selector") or ""
        self.category = (source.get("category") or "general").strip()
        self.respect_robots = respect_robots
        self.max_items = max_items
        self._robots: dict = {}

    # --- robots.txt -----------------------------------------------------
    def _robots_ok(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        origin = "{0.scheme}://{0.netloc}".format(urlsplit(url))
        cached = self._robots.get(origin)
        if cached is None:
            cached = self._load_robots(origin)
            self._robots[origin] = cached
        if cached is False:          # could not verify / access restricted
            return False
        return cached.can_fetch(self.user_agent, url)

    def _load_robots(self, origin: str):
        try:
            resp = self._client.get(origin + "/robots.txt")
        except Exception:
            return False             # fail closed: cannot verify -> don't scrape
        if resp.status_code in (401, 403) or resp.status_code >= 500:
            return False
        rp = RobotFileParser()
        if resp.status_code >= 400:
            rp.parse([])             # no robots.txt -> everything allowed
        else:
            rp.parse(resp.text.splitlines())
        return rp

    # --- extraction helpers --------------------------------------------
    def _txt(self, node, selector: str) -> str:
        if not selector:
            return ""
        sub = node.css_first(selector)
        return sub.text(strip=True) if sub else ""

    def _extract_code(self, node):
        if self.code_attr:
            sub = node.css_first(self.code_selector) if self.code_selector else node
            if sub is not None:
                return ((sub.attributes.get(self.code_attr) or "").strip()) or None
            return None
        return self._txt(node, self.code_selector) or None

    def _extract_link(self, node, origin: str):
        if not self.link_selector:
            return None
        a = node.css_first(self.link_selector)
        if a is None:
            return None
        href = (a.attributes.get("href") or "").strip()
        if not href:
            return None
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("/"):
            return origin + href
        return href

    # --- scan -----------------------------------------------------------
    def scan(self) -> Iterable[VoucherCode]:
        if not self.list_url or not self.row_selector:
            return
        if not self._robots_ok(self.list_url):
            print(f"[vouchers] robots.txt disallows or could not be verified for "
                  f"'{self.source_name}' — skipping {self.list_url}")
            return

        self._polite_sleep()
        try:
            resp = self.fetch(self.list_url)
        except Exception as e:
            print(f"[vouchers] fetch failed for '{self.source_name}': {type(e).__name__}")
            return

        origin = "{0.scheme}://{0.netloc}".format(urlsplit(self.list_url))
        tree = HTMLParser(resp.text)
        count = 0
        for row in tree.css(self.row_selector):
            if count >= self.max_items:
                break
            title = self._txt(row, self.title_selector) if self.title_selector else row.text(strip=True)
            if not title:
                continue
            merchant = (self._txt(row, self.merchant_selector)
                        or self.merchant_default or self.source_name)
            try:
                voucher = VoucherCode(
                    source=f"scrape:{self.source_name}",
                    merchant=merchant,
                    title=title,
                    code=self._extract_code(row),
                    category=self.category,
                    url=self._extract_link(row, origin),
                    expires=self._txt(row, self.expires_selector) or None,
                )
            except Exception:
                continue            # validation failed for this row — skip it
            count += 1
            yield voucher
