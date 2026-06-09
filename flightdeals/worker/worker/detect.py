"""Detection engine.

A fare is a deal when EITHER:
  - sale:  baseline exists with >= min_samples snapshots and
           price <= baseline * (1 - sale_discount)
  - floor: price <= the absolute GBP floor for the route's haul band
           (fires even with zero history — catches error fares on new routes)

Dedupe: a fare_hash that already produced a deal in the last dedupe_days is
suppressed (checked against the deals table by the pipeline).
"""
from __future__ import annotations

from .models import DealCandidate, FareSnapshot


def evaluate(
    snapshot: FareSnapshot,
    *,
    route_id: int,
    dest_name: str,
    band: str,
    tier: str,
    baseline_gbp: float | None,
    sample_count: int,
    floor_gbp: float,
    min_samples: int = 5,
    sale_discount: float = 0.25,
) -> DealCandidate | None:
    price = snapshot.price_gbp

    floor_hit = floor_gbp > 0 and price <= floor_gbp
    sale_hit = (
        baseline_gbp is not None
        and sample_count >= min_samples
        and price <= baseline_gbp * (1 - sale_discount)
    )

    if not (floor_hit or sale_hit):
        return None

    discount_pct = None
    if baseline_gbp and baseline_gbp > 0:
        discount_pct = round((1 - price / baseline_gbp) * 100, 1)

    return DealCandidate(
        snapshot=snapshot,
        route_id=route_id,
        dest_name=dest_name,
        band=band,
        tier=tier,
        # floor wins the label: an absolute-floor hit is the stronger claim
        trigger="floor" if floor_hit else "sale",
        baseline_gbp=baseline_gbp,
        discount_pct=discount_pct,
    )
