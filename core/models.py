"""Data models. Every scraped record is validated here before it can
proceed. Bad data raises ValidationError and is dropped, never posted."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

ASIN_RE = re.compile(r"/([A-Z0-9]{10})(?:[/?]|$)")


class RawDeal(BaseModel):
    """A candidate deal as pulled from a feed/scrape, pre-scoring."""

    source: str = Field(..., min_length=1)              # e.g. "ccc:tech"
    category: str = Field(..., min_length=1)
    title: str = Field(..., min_length=3, max_length=400)
    url: str = Field(..., min_length=8)
    current_price: float = Field(..., gt=0)
    ref_price: Optional[float] = Field(None, gt=0)       # historical/avg ref
    in_stock: bool = True
    asin: Optional[str] = None

    @field_validator("title")
    @classmethod
    def _clean_title(cls, v: str) -> str:
        return re.sub(r"\s+", " ", v).strip()

    @field_validator("url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("url must be absolute http(s)")
        return v

    @model_validator(mode="after")
    def _derive_asin(self) -> "RawDeal":
        if self.asin is None:
            m = ASIN_RE.search(self.url)
            if m:
                self.asin = m.group(1)
        return self

    @property
    def pct_off(self) -> Optional[float]:
        if self.ref_price and self.ref_price > self.current_price:
            return round((1 - self.current_price / self.ref_price) * 100, 1)
        return None

    @property
    def dedupe_hash(self) -> str:
        """Stable identity so the same deal is never posted twice.
        Keyed on ASIN (or URL) + integer price, so a genuine new price
        drop on the same product DOES re-qualify."""
        key = (self.asin or self.url) + f"|{int(round(self.current_price))}"
        return hashlib.sha256(key.encode()).hexdigest()[:32]


class ScoredDeal(BaseModel):
    """A RawDeal that passed scoring and is ready to persist/post."""

    source: str
    category: str
    title: str
    url: str
    affiliate_url: str
    current_price: float
    ref_price: Optional[float]
    pct_off: Optional[float]
    deal_score: int = Field(..., ge=0, le=100)
    in_stock: bool
    asin: Optional[str]
    dedupe_hash: str
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
