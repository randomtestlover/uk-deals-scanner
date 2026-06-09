"""Detection-engine smoke tests. Run: python tests/test_detect.py (no deps beyond worker's)."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from worker.detect import evaluate  # noqa: E402
from worker.models import FareSnapshot  # noqa: E402


def snap(price: float) -> FareSnapshot:
    return FareSnapshot(
        origin="LHR", destination="BCN",
        depart_date=date(2026, 7, 10), return_date=date(2026, 7, 17),
        price_gbp=price, airline="VY", source="test",
    )


COMMON = dict(route_id=1, dest_name="Barcelona", band="short", tier="free")


def test_sale_fires_below_baseline():
    c = evaluate(snap(35), **COMMON, baseline_gbp=50, sample_count=10,
                 floor_gbp=20, min_samples=5, sale_discount=0.25)
    assert c is not None and c.trigger == "sale", c
    assert c.discount_pct == 30.0, c.discount_pct


def test_no_fire_above_threshold():
    c = evaluate(snap(40), **COMMON, baseline_gbp=50, sample_count=10,
                 floor_gbp=20, min_samples=5, sale_discount=0.25)
    assert c is None, c


def test_sale_needs_min_samples():
    c = evaluate(snap(30), **COMMON, baseline_gbp=50, sample_count=3,
                 floor_gbp=20, min_samples=5, sale_discount=0.25)
    assert c is None, "baseline with too few samples must not fire a sale"


def test_floor_fires_without_history():
    c = evaluate(snap(18), **COMMON, baseline_gbp=None, sample_count=0,
                 floor_gbp=20, min_samples=5, sale_discount=0.25)
    assert c is not None and c.trigger == "floor", c
    assert c.discount_pct is None


def test_floor_label_wins_when_both_fire():
    c = evaluate(snap(15), **COMMON, baseline_gbp=60, sample_count=10,
                 floor_gbp=20, min_samples=5, sale_discount=0.25)
    assert c is not None and c.trigger == "floor", c
    assert c.discount_pct == 75.0


def test_fare_hash_buckets_small_wobbles():
    a, b, c = snap(19.0), snap(21.0), snap(35.0)
    assert a.fare_hash(10) != b.fare_hash(10)  # different £10 buckets (1 vs 2)
    assert snap(22.0).fare_hash(10) == b.fare_hash(10)  # same bucket
    assert a.fare_hash(10) != c.fare_hash(10)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} tests passed")
