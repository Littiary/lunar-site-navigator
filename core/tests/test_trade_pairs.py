"""Acceptance tests of the mast-height trade and of complementary site pairs.

Thresholds were fixed before the implementation existed (CONTRIBUTING.md, rule 5).
"""

import math

import numpy as np
import pytest

from lsncore.dem import AnalyticTerrain
from lsncore.horizon import compute_horizon
from lsncore.pairs import pair_report
from lsncore.timeline import IntervalSet
from lsncore.trade import height_trade

# --------------------------------------------------------------------------------------
# THRESHOLDS (fixed before measuring)
# --------------------------------------------------------------------------------------
TOL_TRADE_S = 5.0        # visible time per observer height against the closed form
TOL_ALGEBRA_S = 1e-6     # identities of the pair arithmetic
# --------------------------------------------------------------------------------------

R = 1_737_400.0
HOUR = 3600.0


def central_angle(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin((np.radians(lon2) - np.radians(lon1)) / 2) ** 2
    return 2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def exact_elevation_deg(r_observer, r_target, gamma):
    return math.degrees(math.atan2(r_target * math.cos(gamma) - r_observer, r_target * math.sin(gamma)))


# -- mast-height trade ------------------------------------------------------------------------

def test_trade_table_from_windows():
    domain = (0.0, 100.0)
    windows = {
        "sun_visible": [IntervalSet([(0, 10), (60, 70)], domain), IntervalSet([(0, 30), (50, 70)], domain), IntervalSet([(0, 100)], domain)],
        "earth_visible": [IntervalSet([(0, 50)], domain)] * 3,
    }
    table = height_trade([0.0, 5.0, 20.0], windows)
    assert table["observer_heights_m"] == [0.0, 5.0, 20.0]
    by_id = {q["id"]: q for q in table["quantities"]}
    assert by_id["sun_visible_s"]["values"] == pytest.approx([20.0, 50.0, 100.0], abs=TOL_ALGEBRA_S)
    assert by_id["sun_visible_s"]["change_s"] == pytest.approx([0.0, 30.0, 80.0], abs=TOL_ALGEBRA_S)
    assert by_id["sun_longest_outage_s"]["values"] == pytest.approx([50.0, 30.0, 0.0], abs=TOL_ALGEBRA_S)
    assert by_id["sun_longest_outage_s"]["change_s"] == pytest.approx([0.0, -20.0, -50.0], abs=TOL_ALGEBRA_S)
    assert by_id["earth_visible_s"]["change_s"] == pytest.approx([0.0, 0.0, 0.0], abs=TOL_ALGEBRA_S)
    assert by_id["sun_visible_s"]["window"] == "sun_visible"


def test_mast_height_in_a_crater_against_the_closed_form():
    """An observer at the centre of a crater watches a body whose elevation swings like a
    sine. It is visible while it stands above the rim, and the rim sinks as the mast
    rises. Horizon from the real search, windows from the event finder, expected times
    from the closed form of the rim elevation."""
    finder = pytest.importorskip("lsncore.events.finder")
    lat, lon = -85.0, 30.0
    rim_m, floor_m = 2_000.0, -200.0

    def bowl(lo, la):
        s = R * central_angle(lat, lon, la, lo)
        return np.where(s < rim_m, floor_m + (0.0 - floor_m) * (s / rim_m) ** 2, 0.0)

    heights = [0.0, 2.0, 10.0, 20.0, 50.0]
    horizon = compute_horizon(AnalyticTerrain(bowl, R, max_slope=0.3), lat, lon, heights, azimuth_step_deg=5.0, max_range_m=30_000.0)

    amplitude, period = 7.0, 40.0 * HOUR  # the body swings +-7 deg about the horizontal
    domain = (0.0, 3.0 * period)

    def direction(et):
        et = np.asarray(et, dtype=np.float64)
        return np.full(et.shape, 77.0), amplitude * np.sin(2.0 * np.pi * et / period), np.full(et.shape, 0.25)

    rule = {"visible": finder.threshold_from_contract({"quantity": "margin_deg", "op": ">", "value": 0.0})}
    sets = []
    for h in range(len(heights)):
        profile = finder.Horizon(0.0, 5.0, horizon.elevation_deg[h])
        result = finder.find_events(direction, profile, domain[0], domain[1], thresholds=rule)
        sets.append(IntervalSet(finder.windows(result, "visible").intervals_et_s, domain))
    table = height_trade(heights, {"sun_visible": sets})
    values = {q["id"]: q for q in table["quantities"]}["sun_visible_s"]["values"]

    for m, value in zip(heights, values):
        rim_deg = exact_elevation_deg(R + floor_m + m, R + 0.0, rim_m / R)
        assert 0.0 < rim_deg < amplitude
        # sin above the level rim_deg / amplitude for (pi - 2 asin(level)) / (2 pi) of each period
        expected = 3.0 * period * (math.pi - 2.0 * math.asin(rim_deg / amplitude)) / (2.0 * math.pi)
        assert value == pytest.approx(expected, abs=TOL_TRADE_S)
    assert all(b > a for a, b in zip(values, values[1:]))  # a higher mast sees the body longer


# -- complementary pairs ------------------------------------------------------------------------

def test_pair_arithmetic():
    domain = (0.0, 100.0)
    a = IntervalSet([(0, 40)], domain)
    b = IntervalSet([(30, 60), (90, 100)], domain)
    report = pair_report(a, b)
    assert report["a_s"] == 40.0 and report["b_s"] == 40.0
    assert report["either_s"] == pytest.approx(70.0) and report["both_s"] == pytest.approx(10.0)
    assert report["neither_s"] == pytest.approx(30.0) and report["longest_neither_s"] == pytest.approx(30.0)
    assert report["gain_over_better_s"] == pytest.approx(30.0)            # 70 together against 40 for the better one
    assert report["covered_share_of_better_outage"] == pytest.approx(0.5)  # 30 of the 60 s the better one lacks
    assert report["either_fraction"] == pytest.approx(0.7)
    assert report["neither"].as_list() == [[60.0, 90.0]]


def test_pair_identities_hold_for_random_windows():
    rng = np.random.default_rng(5)
    domain = (0.0, 1000.0)
    for _ in range(50):
        a = IntervalSet(np.sort(rng.uniform(0, 1000, (5, 2)), axis=1), domain)
        b = IntervalSet(np.sort(rng.uniform(0, 1000, (5, 2)), axis=1), domain)
        r = pair_report(a, b)
        assert r["either_s"] + r["neither_s"] == pytest.approx(1000.0, abs=TOL_ALGEBRA_S)
        assert r["a_s"] + r["b_s"] == pytest.approx(r["either_s"] + r["both_s"], abs=TOL_ALGEBRA_S)
        assert max(r["a_s"], r["b_s"]) - TOL_ALGEBRA_S <= r["either_s"] <= r["a_s"] + r["b_s"] + TOL_ALGEBRA_S
        assert r["gain_over_better_s"] >= -TOL_ALGEBRA_S
        assert 0.0 <= r["covered_share_of_better_outage"] <= 1.0
        # symmetric in the two sites
        s = pair_report(b, a)
        assert s["either_s"] == pytest.approx(r["either_s"]) and s["gain_over_better_s"] == pytest.approx(r["gain_over_better_s"])


def test_a_site_that_is_never_dark_leaves_nothing_to_cover():
    domain = (0.0, 10.0)
    r = pair_report(IntervalSet.full(domain), IntervalSet([(2, 3)], domain))
    assert r["gain_over_better_s"] == 0.0 and r["covered_share_of_better_outage"] is None and r["neither_s"] == 0.0
