"""Deal-quality scoring (0-100). This is the core differentiator:
most channels just repost everything. We rank by how good a deal
actually is, using discount depth, price vs historical reference,
and a price-anchoring sanity check.

Score components (weighted):
  - discount depth   (0-55)  how big is the % off
  - history position (0-30)  is current price near the historical low
  - absolute saving  (0-15)  bigger £ savings nudged up (capped)

If no reference price is known yet (first time we see a product),
we fall back to discount depth only and cap the score so unproven
deals can't dominate until history accrues.
"""

from __future__ import annotations

from typing import Optional


def _discount_component(pct_off: Optional[float]) -> float:
    if not pct_off or pct_off <= 0:
        return 0.0
    # 30% -> ~25, 50% -> ~40, 70%+ -> ~55 (diminishing returns)
    return min(55.0, 18.0 + (pct_off - 30.0) * 0.92) if pct_off >= 30 else pct_off * 0.6


def _history_component(current: float, hist_low: Optional[float],
                       hist_avg: Optional[float]) -> float:
    if not hist_low or not hist_avg or hist_avg <= 0:
        return 0.0
    # Reward being close to the all-time low relative to the average band.
    band = max(hist_avg - hist_low, 0.01)
    closeness = (hist_avg - current) / band      # 1.0 == at the low
    closeness = max(0.0, min(1.2, closeness))     # allow slight overshoot
    return min(30.0, closeness * 30.0)


def _saving_component(current: float, ref: Optional[float]) -> float:
    if not ref or ref <= current:
        return 0.0
    saving = ref - current
    # £10 -> ~3, £50 -> ~9, £150+ -> 15 (log-ish, capped)
    return min(15.0, (saving ** 0.5) * 1.2)


def score_deal(
    *,
    current_price: float,
    pct_off: Optional[float],
    ref_price: Optional[float],
    hist_low: Optional[float] = None,
    hist_avg: Optional[float] = None,
) -> int:
    """Return an integer 0-100."""
    has_history = hist_low is not None and hist_avg is not None

    score = _discount_component(pct_off)
    score += _history_component(current_price, hist_low, hist_avg)
    score += _saving_component(current_price, ref_price)

    # Cap unproven deals (no real history yet) so they can't max out.
    if not has_history:
        score = min(score, 72.0)

    return int(max(0, min(100, round(score))))
