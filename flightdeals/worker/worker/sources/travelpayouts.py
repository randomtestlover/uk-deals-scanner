"""Travelpayouts (Aviasales Data API v3) — primary cached-fare layer. Free."""
from __future__ import annotations

import logging
from datetime import date

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..models import FareSnapshot
from .base import FareSource

log = logging.getLogger(__name__)

API_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


class RetryableHTTP(Exception):
    pass


class TravelpayoutsSource(FareSource):
    name = "travelpayouts"

    def __init__(self, token: str, marker: str | None = None, months_ahead: int = 2):
        self.token = token
        self.marker = marker
        self.months_ahead = months_ahead
        self.client = httpx.Client(timeout=20)

    def _months(self) -> list[str]:
        today = date.today()
        out = []
        y, m = today.year, today.month
        for _ in range(self.months_ahead):
            out.append(f"{y:04d}-{m:02d}")
            m += 1
            if m > 12:
                y, m = y + 1, 1
        return out

    @retry(
        retry=retry_if_exception_type(RetryableHTTP),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, max=20),
        reraise=True,
    )
    def _fetch(self, params: dict) -> list[dict]:
        resp = self.client.get(API_URL, params=params)
        if resp.status_code in (429, 500, 502, 503, 504):
            raise RetryableHTTP(f"travelpayouts {resp.status_code}")
        resp.raise_for_status()
        body = resp.json()
        if not body.get("success", False):
            log.warning("travelpayouts error: %s", body.get("error"))
            return []
        return body.get("data", [])

    def sweep(self, origin: str, destination: str) -> list[FareSnapshot]:
        snapshots: list[FareSnapshot] = []
        for month in self._months():
            params = {
                "origin": origin,
                "destination": destination,
                "departure_at": month,
                "currency": "gbp",
                "one_way": "false",
                "sorting": "price",
                "limit": 10,
                "token": self.token,
            }
            try:
                rows = self._fetch(params)
            except (httpx.HTTPError, RetryableHTTP) as exc:
                log.warning("travelpayouts sweep failed %s-%s: %s", origin, destination, exc)
                continue
            for row in rows:
                try:
                    link = row.get("link") or ""
                    deep_link = f"https://www.aviasales.com{link}" if link else None
                    if deep_link and self.marker:
                        sep = "&" if "?" in deep_link else "?"
                        deep_link = f"{deep_link}{sep}marker={self.marker}"
                    snapshots.append(
                        FareSnapshot(
                            origin=origin,
                            destination=destination,
                            depart_date=date.fromisoformat(row["departure_at"][:10]),
                            return_date=(
                                date.fromisoformat(row["return_at"][:10])
                                if row.get("return_at")
                                else None
                            ),
                            price_gbp=float(row["price"]),
                            airline=row.get("airline"),
                            source=self.name,
                            deep_link=deep_link,
                        )
                    )
                except (KeyError, ValueError) as exc:
                    log.debug("skipping malformed row: %s", exc)
        return snapshots
