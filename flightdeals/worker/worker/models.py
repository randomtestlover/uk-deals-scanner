"""Pydantic models shared across the pipeline."""
from __future__ import annotations

import hashlib
from datetime import date

from pydantic import BaseModel, Field, field_validator


class FareSnapshot(BaseModel):
    """One observed fare for a route, as returned by a source adapter."""

    origin: str
    destination: str
    depart_date: date
    return_date: date | None = None
    price_gbp: float = Field(gt=0)
    airline: str | None = None
    source: str
    deep_link: str | None = None

    @field_validator("origin", "destination")
    @classmethod
    def _upper_iata(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 3:
            raise ValueError(f"invalid IATA code: {v!r}")
        return v

    def fare_hash(self, bucket_gbp: int = 10) -> str:
        """Stable identity for dedupe: route + dates + price bucket.

        Bucketing means a £19 fare and a £21 fare on the same dates collide,
        so small price wobbles don't evade the 7-day repost suppression.
        """
        bucket = int(self.price_gbp // max(bucket_gbp, 1))
        key = f"{self.origin}|{self.destination}|{self.depart_date}|{self.return_date}|{bucket}"
        return hashlib.sha256(key.encode()).hexdigest()[:20]


class DealCandidate(BaseModel):
    """A snapshot that passed detection and is ready to store/post."""

    snapshot: FareSnapshot
    route_id: int
    dest_name: str
    band: str
    tier: str
    trigger: str  # 'sale' | 'floor'
    baseline_gbp: float | None = None
    discount_pct: float | None = None

    @property
    def headline_pct(self) -> int | None:
        return round(self.discount_pct) if self.discount_pct is not None else None
