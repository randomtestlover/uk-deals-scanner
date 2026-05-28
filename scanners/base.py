"""Shared scanner machinery: HTTP with retries, polite random delays,
and a £-price parser. Concrete scanners subclass BaseScanner."""

from __future__ import annotations

import random
import re
import time
from typing import Iterable

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.models import RawDeal

PRICE_RE = re.compile(r"£\s?([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)")


def parse_price(text: str) -> float | None:
    """Extract the first £ price from arbitrary text."""
    if not text:
        return None
    m = PRICE_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


class BaseScanner:
    name = "base"

    def __init__(self, user_agent: str, min_delay: float = 0.0,
                 max_delay: float = 0.0, timeout: float = 20.0):
        self.user_agent = user_agent
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout,
            follow_redirects=True,
        )

    def _polite_sleep(self) -> None:
        if self.max_delay > 0:
            time.sleep(random.uniform(self.min_delay, self.max_delay))

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError,)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.5, min=2, max=20),
        reraise=True,
    )
    def fetch(self, url: str) -> httpx.Response:
        resp = self._client.get(url)
        resp.raise_for_status()
        return resp

    def scan(self) -> Iterable[RawDeal]:  # pragma: no cover - interface
        raise NotImplementedError

    def close(self) -> None:
        self._client.close()
