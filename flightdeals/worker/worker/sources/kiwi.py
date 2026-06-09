"""Kiwi Tequila — live verification of the best cached candidate before posting.

Virtual interlining gives LCC coverage (Ryanair / easyJet / Wizz) that cached
Travelpayouts data can miss. Optional: if no API key is configured, deals are
posted on cached data alone.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import httpx

from ..models import FareSnapshot

log = logging.getLogger(__name__)

API_URL = "https://api.tequila.kiwi.com/v2/search"


class KiwiVerifier:
    def __init__(self, api_key: str, affil_id: str | None = None):
        self.api_key = api_key
        self.affil_id = affil_id
        self.client = httpx.Client(timeout=25, headers={"apikey": api_key})

    def verify(self, snapshot: FareSnapshot, tolerance: float = 1.25) -> FareSnapshot | None:
        """Re-search the fare live. Returns a (possibly re-priced) snapshot if a
        live fare exists within `tolerance` x cached price, else None."""
        fmt = "%d/%m/%Y"
        depart = snapshot.depart_date
        params = {
            "fly_from": snapshot.origin,
            "fly_to": snapshot.destination,
            "date_from": depart.strftime(fmt),
            "date_to": (depart + timedelta(days=1)).strftime(fmt),
            "curr": "GBP",
            "limit": 3,
            "sort": "price",
        }
        if snapshot.return_date:
            params["return_from"] = snapshot.return_date.strftime(fmt)
            params["return_to"] = (snapshot.return_date + timedelta(days=1)).strftime(fmt)
        try:
            resp = self.client.get(API_URL, params=params)
            resp.raise_for_status()
            data = resp.json().get("data", [])
        except httpx.HTTPError as exc:
            log.warning("kiwi verify failed %s-%s: %s — passing cached fare through",
                        snapshot.origin, snapshot.destination, exc)
            return snapshot  # verification unavailable ≠ deal invalid
        if not data:
            return None
        best = data[0]
        live_price = float(best.get("price", 0))
        if live_price <= 0 or live_price > snapshot.price_gbp * tolerance:
            return None
        airlines = best.get("airlines") or []
        return snapshot.model_copy(
            update={
                "price_gbp": live_price,
                "airline": airlines[0] if airlines else snapshot.airline,
                "deep_link": best.get("deep_link") or snapshot.deep_link,
                "source": "kiwi-verified",
            }
        )
