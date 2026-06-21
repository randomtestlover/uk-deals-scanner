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


class VoucherCode(BaseModel):
    """A scraped voucher / discount code, validated before display.

    `code` is optional: some offers are automatic ("no code needed"), in
    which case it stays None and the page renders the offer without a code box.
    """

    source: str = Field(..., min_length=1)               # e.g. "scrape:MySource"
    merchant: str = Field(..., min_length=1, max_length=120)
    title: str = Field(..., min_length=2, max_length=300)
    code: Optional[str] = Field(None, max_length=60)
    category: str = "general"
    url: Optional[str] = None
    expires: Optional[str] = None                         # ISO date 'YYYY-MM-DD'

    @field_validator("merchant", "title", "category")
    @classmethod
    def _clean(cls, v: str) -> str:
        return re.sub(r"\s+", " ", v or "").strip()

    @field_validator("code")
    @classmethod
    def _clean_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = re.sub(r"\s+", "", v).upper()
        return v or None

    @field_validator("url")
    @classmethod
    def _clean_url(cls, v: Optional[str]) -> Optional[str]:
        if not v or not v.startswith(("http://", "https://")):
            return None
        return v

    @field_validator("expires")
    @classmethod
    def _clean_expires(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        m = re.search(r"\d{4}-\d{2}-\d{2}", v)
        return m.group(0) if m else None

    @property
    def dedupe_key(self) -> str:
        """Stable identity: a merchant + (code, else offer title)."""
        tail = (self.code or self.title or "").lower()
        return f"{self.merchant.lower()}|{tail}"
