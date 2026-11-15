"""Acceptance tests of the opportunity calendar and of the slip tolerance of a landing date.

Thresholds were fixed before the implementation existed (CONTRIBUTING.md, rule 5).
"""

import math

import numpy as np
import pytest

from lsncore.calendar import (
    calendar_totals,
    landing_windows,
    lunar_day_periods,
    slip_report,
)
from lsncore.timeline import IntervalSet

# --------------------------------------------------------------------------------------
# THRESHOLDS (fixed before measuring)
# --------------------------------------------------------------------------------------
TOL_PERIOD_BOUNDARY_S = 5.0   # boundary of a lunar day against the closed-form instant
TOL_ALGEBRA_S = 1e-6          # sums and window edges that follow from interval algebra
TOL_BRUTE_FORCE_S = 2.0       # exact landing windows against a 1 s brute-force scan
# --------------------------------------------------------------------------------------

DAY = 86400.0
HOUR = 3600.0


# -- lunar days from the direction table ----------------------------------------------------

def _circling_sun(et, period_s, phase_deg=40.0, tilt_deg=1.5):
    """Sun going round the body-fixed frame westwards once per period."""
    lon = np.radians(phase_deg) - 2.0 * np.pi * et / period_s
    lat = np.radians(tilt_deg) * np.sin(2.0 * np.pi * et / (12.4 * period_s))
    return 1.5e8 * np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], axis=-1)


def test_lunar_days_begin_when_the_sun_crosses_the_far_side_meridian():
    period = 29.53 * DAY
    et = 1.0e8 + np.arange(0, int(200 * 24)) * HOUR  # 200 days, hourly
    periods = lunar_day_periods(et, _circling_sun(et, period))
    # subsolar longitude = 40 deg - 360 deg * t / period reaches 180 deg (mod 360) at
    # t = period * (40 - 180 + 360 k) / 360
    crossings = [period * (40.0 - 180.0 + 360.0 * k) / 360.0 for k in range(-20, 400)]
    expected = [c for c in crossings if et[0] < c < et[-1]]
    inner = [p["start_et_s"] for p in periods[1:]]
    # 200 days hold six or seven crossings depending on the phase; the count comes from the
    # closed form. (The first version of this test had the literal 6, a miscount: there are 7.)
    assert len(inner) == len(expected) >= 6
    assert np.abs(np.array(inner) - np.array(expected)).max() <= TOL_PERIOD_BOUNDARY_S
    # the periods tile the table; the first and the last are cut by its ends
    assert periods[0]["start_et_s"] == et[0] and periods[-1]["end_et_s"] == et[-1]
    assert all(a["end_et_s"] == b["start_et_s"] for a, b in zip(periods, periods[1:]))
    assert [p["complete"] for p in periods] == [False] + [True] * (len(expected) - 1) + [False]
    assert [p["index"] for p in periods] == list(range(len(expected) + 1))
    for p in periods[1:-1]:
        assert p["end_et_s"] - p["start_et_s"] == pytest.approx(period, abs=2 * TOL_PERIOD_BOUNDARY_S)


def test_periods_can_be_cut_to_a_window():
    period = 30.0 * DAY
    et = np.arange(0, int(100 * 24)) * HOUR
    periods = lunar_day_periods(et, _circling_sun(et, period), domain=(10 * DAY, 70 * DAY))
    assert periods[0]["start_et_s"] == 10 * DAY and periods[-1]["end_et_s"] == 70 * DAY
    assert not periods[0]["complete"] and not periods[-1]["complete"]


# -- hours per lunar day ---------------------------------------------------------------------

def test_calendar_totals_add_up_to_the_window_totals():
    domain = (0.0, 100.0 * DAY)
    periods = [
        {"index": k, "start_et_s": a * DAY, "end_et_s": b * DAY, "complete": c}
        for k, (a, b, c) in enumerate([(0, 12, False), (12, 41.5, True), (41.5, 71, True), (71, 100, False)])
    ]
    rng = np.random.default_rng(3)
    sun = IntervalSet(np.sort(rng.uniform(0, 100 * DAY, (12, 2)), axis=1), domain)
    earth = IntervalSet(np.sort(rng.uniform(0, 100 * DAY, (9, 2)), axis=1), domain)
    totals = calendar_totals(periods, {"sun_visible_s": sun, "earth_visible_s": earth, "sun_and_earth_visible_s": sun.intersection(earth)})
    for name, window in (("sun_visible_s", sun), ("earth_visible_s", earth)):
        values = totals[name]
        assert len(values) == 4
        assert abs(sum(values) - window.total_s()) <= TOL_ALGEBRA_S
        assert all(0.0 <= v <= p["end_et_s"] - p["start_et_s"] + 1e-9 for v, p in zip(values, periods))
    # a window that covers one period exactly
    one = calendar_totals(periods, {"x": IntervalSet([(12 * DAY, 41.5 * DAY)], domain)})["x"]
    assert one == pytest.approx([0.0, 29.5 * DAY, 0.0, 0.0], abs=TOL_ALGEBRA_S)
    # longest outage inside each period: the complement, cut at the period boundaries
    gaps = calendar_totals(periods, {"x": IntervalSet([(0, 10 * DAY), (20 * DAY, 100 * DAY)], domain)}, longest_outage=True)["x"]
    assert gaps == pytest.approx([2 * DAY, 8 * DAY, 0.0, 0.0], abs=TOL_ALGEBRA_S)


# -- landing windows for a stated requirement ------------------------------------------------

DOMAIN = (0.0, 1000.0)


def test_continuous_visibility_from_landing():
    sun = IntervalSet([(0, 100), (150, 160), (300, 1000)], DOMAIN)
    req = {"id": "r", "conditions": [{"window": "sun_visible", "kind": "continuous_from_landing", "min_s": 20.0}]}
    feasible, _ = landing_windows(req, {"sun_visible": sun}, DOMAIN)
    # an interval of visibility [a, b] admits landings in [a, b - 20]; the last one is cut by the
    # end of the computed range, where visibility beyond is unknown
    assert feasible.as_list() == [[0.0, 80.0], [300.0, 980.0]]


def test_visible_at_landing_and_combination():
    sun = IntervalSet([(0, 100), (300, 1000)], DOMAIN)
    earth = IntervalSet([(50, 400)], DOMAIN)
    req = {
        "id": "r",
        "conditions": [
            {"window": "earth_visible", "kind": "visible_at_landing"},
            {"window": "sun_visible", "kind": "continuous_from_landing", "min_s": 30.0},
        ],
    }
    feasible, _ = landing_windows(req, {"sun_visible": sun, "earth_visible": earth}, DOMAIN)
    assert feasible.as_list() == [[50.0, 70.0], [300.0, 400.0]]


def test_total_visibility_within_the_mission():
    w = IntervalSet([(0, 10), (20, 30)], (0.0, 100.0))
    req = {"id": "r", "mission_duration_s": 25.0, "conditions": [{"window": "sun_visible", "kind": "total_in_mission", "min_s": 15.0}]}
    feasible, info = landing_windows(req, {"sun_visible": w}, (0.0, 100.0))
    # landing at t in [0, 5]: (10 - t) seconds of the first interval + (t + 5) of the second = 15
    assert len(feasible) == 1
    assert feasible.as_list()[0] == pytest.approx([0.0, 5.0], abs=TOL_ALGEBRA_S)
    assert info["latest_landing_et_s"] == 75.0  # the mission must end inside the computed range


def test_exact_landing_windows_agree_with_a_brute_force_scan():
    rng = np.random.default_rng(11)
    domain = (0.0, 20000.0)
    t = np.arange(domain[0], domain[1] + 1.0, 1.0)
    for _ in range(25):
        sun = IntervalSet(np.sort(rng.uniform(0, 20000, (8, 2)), axis=1), domain)
        earth = IntervalSet(np.sort(rng.uniform(0, 20000, (6, 2)), axis=1), domain)
        duration = float(rng.uniform(500, 3000))
        need_total = float(rng.uniform(0.2, 0.8)) * duration
        need_cont = float(rng.uniform(50, 600))
        req = {
            "id": "r",
            "mission_duration_s": duration,
            "conditions": [
                {"window": "earth_visible", "kind": "visible_at_landing"},
                {"window": "sun_visible", "kind": "continuous_from_landing", "min_s": need_cont},
                {"window": "sun_visible", "kind": "total_in_mission", "min_s": need_total},
            ],
        }
        feasible, _ = landing_windows(req, {"sun_visible": sun, "earth_visible": earth}, domain)

        def measure(window, a, b):
            return IntervalSet(window.intervals, domain).intersection(IntervalSet([(a, b)], domain)).total_s() if b > a else 0.0

        brute = np.array([
            earth.contains(x)
            and x + duration <= domain[1]
            and measure(sun, x, x + need_cont) >= need_cont - 1e-9
            and measure(sun, x, x + duration) >= need_total - 1e-9
            for x in t
        ])
        exact = np.array([feasible.contains(x) for x in t])
        # they may differ only within the tolerance of an edge
        differ = t[brute != exact]
        edges = np.array([e for iv in feasible.intervals for e in iv] or [math.inf])
        assert all(np.abs(edges - x).min() <= TOL_BRUTE_FORCE_S for x in differ)


# -- slip tolerance --------------------------------------------------------------------------

def test_slip_tolerance_of_a_planned_landing():
    feasible = IntervalSet([(100, 180), (400, 520)], DOMAIN)
    inside = slip_report(feasible, 130.0)
    assert inside["feasible"] is True
    assert inside["slip_tolerance_s"] == pytest.approx(50.0, abs=TOL_ALGEBRA_S)   # may land up to 50 s late
    assert inside["early_tolerance_s"] == pytest.approx(30.0, abs=TOL_ALGEBRA_S)  # or up to 30 s early
    assert inside["next_window_start_et_s"] == 400.0 and inside["wait_after_window_s"] == pytest.approx(220.0)
    outside = slip_report(feasible, 250.0)
    assert outside["feasible"] is False and outside["slip_tolerance_s"] == 0.0
    assert outside["next_window_start_et_s"] == 400.0 and outside["wait_s"] == pytest.approx(150.0)
    assert outside["next_window_length_s"] == pytest.approx(120.0)
    never = slip_report(IntervalSet.empty(DOMAIN), 250.0)
    assert never["feasible"] is False and never["next_window_start_et_s"] is None and never["wait_s"] is None
    # a window cut by the end of the computed range gives a lower bound only
    open_end = slip_report(IntervalSet([(900, 1000)], DOMAIN), 950.0)
    assert open_end["slip_tolerance_s"] == pytest.approx(50.0) and open_end["slip_tolerance_is_lower_bound"] is True
    assert inside["slip_tolerance_is_lower_bound"] is False


# -- the end of what can be judged -----------------------------------------------------------
#
# SPEC 5.6: latest_landing is the end of the computed range minus the mission duration,
# for every requirement that states one, whatever its conditions. A landing window that
# ends there, or that ends where a visibility interval cut by the end of the range can no
# longer prove a "continuous from landing" condition, is cut by what is known, not by an
# event: it is marked clipped, and a slip tolerance inside it is a lower bound.
# Expected values fixed before the first run (case of the independent review, 15 November).

class _Table:
    """Stand-in for a direction-table package: a Sun circling the body-fixed frame."""

    def __init__(self, time):
        et = time["start_et_s"] + time["step_s"] * np.arange(time["count"])
        self.manifest = {"positions_km": "sun", "bodies": ["SUN"], "time": time}
        self._positions = _circling_sun(et, 29.53 * DAY)[:, None, :]

    def array(self, ref):
        return self._positions


class _Timeline:
    """Stand-in for a site timeline with given visibility windows (one observer height)."""

    def __init__(self, time, windows):
        self.time, self._windows, self.calendar, self.opportunities = time, windows, None, None

    def window(self, window_id, height_index):
        return self._windows[window_id]


def _opportunity(sun, earth, requirement, planned_day=None, days=30.0):
    from lsncore.calendar import add_calendar_to_timeline

    time = {"start_et_s": 0.0, "step_s": HOUR, "count": int(days * 24) + 1}
    domain = (0.0, days * DAY)
    windows = {"sun_visible": IntervalSet([(a * DAY, b * DAY) for a, b in sun], domain), "earth_visible": IntervalSet([(a * DAY, b * DAY) for a, b in earth], domain)}
    timeline = _Timeline(time, windows)
    add_calendar_to_timeline(timeline, _Table(time), 1, [requirement], None if planned_day is None else planned_day * DAY, lambda et: f"day {et / DAY:.6f}")
    (record,) = timeline.opportunities
    return record


def _standard(duration_days=10.0, continuous_days=10.0):
    requirement = {
        "id": "like-example-standard",
        "conditions": [
            {"window": "earth_visible", "kind": "visible_at_landing"},
            {"window": "sun_visible", "kind": "continuous_from_landing", "min_s": continuous_days * DAY},
        ],
    }
    if duration_days is not None:
        requirement["mission_duration_s"] = duration_days * DAY
    return requirement


def test_latest_landing_is_the_end_of_the_range_minus_the_mission_duration():
    """30 days, the Earth always in view, the Sun from day 5 to the end; 10 days of unbroken
    sunlight from landing, mission of 10 days, landing planned on day 12."""
    domain = (0.0, 30.0 * DAY)
    windows = {"sun_visible": IntervalSet([(5 * DAY, 30 * DAY)], domain), "earth_visible": IntervalSet([(0.0, 30 * DAY)], domain)}
    feasible, info = landing_windows(_standard(), windows, domain)
    assert feasible.as_list() == [[5 * DAY, 20 * DAY]]
    assert info["latest_landing_et_s"] == 20 * DAY

    record = _opportunity([(5, 30)], [(0, 30)], _standard(), planned_day=12)
    assert record["landing_windows_et_s"] == [[5 * DAY, 20 * DAY]]
    assert record["latest_landing_et_s"] == 20 * DAY
    assert record["feasible_fraction"] == pytest.approx(0.75, abs=1e-12)  # 15 of the 20 days that can be judged
    assert record["clipped_end"] is True  # the Sun is still up when the computed range ends
    planned = record["planned_landing"]
    assert planned["feasible"] is True and planned["slip_tolerance_s"] == pytest.approx(8 * DAY, abs=TOL_ALGEBRA_S)
    assert planned["slip_tolerance_is_lower_bound"] is True


def test_a_window_that_ends_at_an_event_is_not_marked_as_cut():
    record = _opportunity([(5, 22)], [(0, 30)], _standard(), planned_day=8)  # the Sun sets on day 22
    assert record["landing_windows_et_s"] == [[5 * DAY, 12 * DAY]]
    assert record["latest_landing_et_s"] == 20 * DAY and record["feasible_fraction"] == pytest.approx(7 / 20, abs=1e-12)
    assert record["clipped_end"] is False
    assert record["planned_landing"]["slip_tolerance_s"] == pytest.approx(4 * DAY, abs=TOL_ALGEBRA_S)
    assert record["planned_landing"]["slip_tolerance_is_lower_bound"] is False


@pytest.mark.parametrize(
    "duration_days, continuous_days, window_end_day, latest_day",
    [
        (10.0, 4.0, 20.0, 20.0),   # the mission must end inside the range: cut at latest_landing
        (3.0, 10.0, 20.0, 27.0),   # the sunlight cannot be proven beyond day 20: cut there, before latest_landing
        (None, 10.0, 20.0, 30.0),  # no mission duration stated: latest_landing is the end of the range
    ],
)
def test_a_window_cut_by_the_end_of_the_range_is_marked_whatever_cuts_it(duration_days, continuous_days, window_end_day, latest_day):
    record = _opportunity([(5, 30)], [(0, 30)], _standard(duration_days, continuous_days), planned_day=12)
    assert record["landing_windows_et_s"] == [[5 * DAY, window_end_day * DAY]]
    assert record["latest_landing_et_s"] == latest_day * DAY
    assert record["clipped_end"] is True
    assert record["planned_landing"]["slip_tolerance_is_lower_bound"] is True
    assert record["feasible_fraction"] == pytest.approx((window_end_day - 5.0) / latest_day, abs=1e-12)


def test_the_three_example_requirements_end_at_latest_landing_when_the_sun_stays_up():
    from lsncore.scenario import requirement_presets

    for requirement in requirement_presets().values():
        days = requirement["mission_duration_s"] / DAY
        record = _opportunity([(2, 40)], [(0, 40)], requirement, days=40.0)
        assert record["latest_landing_et_s"] == (40.0 - days) * DAY, requirement["id"]
        assert record["landing_windows_et_s"][-1][1] == pytest.approx((40.0 - days) * DAY, abs=TOL_ALGEBRA_S)
        assert record["clipped_end"] is True, requirement["id"]


def test_a_planned_landing_after_what_can_be_judged_gets_no_slip_report():
    """It is neither feasible nor infeasible: the mission would end after the computed
    range. The record carries no slip report, and a sentence for the warnings says why."""
    from lsncore.calendar import add_calendar_to_timeline

    time = {"start_et_s": 0.0, "step_s": HOUR, "count": 721}
    domain = (0.0, 30.0 * DAY)
    windows = {"sun_visible": IntervalSet([(5 * DAY, 30 * DAY)], domain), "earth_visible": IntervalSet([(0.0, 30 * DAY)], domain)}
    for planned_day, judged in ((25.0, False), (20.0, True), (12.0, True), (3.0, True)):
        timeline = _Timeline(time, windows)
        notes = add_calendar_to_timeline(timeline, _Table(time), 1, [_standard()], planned_day * DAY, lambda et: f"day {et / DAY:.6f}")
        (record,) = timeline.opportunities
        if judged:
            assert notes == [] and record["planned_landing"]["feasible"] is (planned_day >= 5.0)
        else:
            assert record["planned_landing"] is None
            (note,) = notes
            assert "day 25.000000" in note and "like-example-standard" in note and "day 20.000000" in note
    # the windows themselves do not depend on the planned landing
    assert record["landing_windows_et_s"] == [[5 * DAY, 20 * DAY]]


def test_a_package_says_when_its_planned_landing_cannot_be_judged(tmp_path):
    """The sentence reaches the warnings of the package, and the package stays valid."""
    from lsncore.contract import contract_dir, validate_package
    from lsncore.scenario import load_scenario
    from lsncore.synthetic import run_synthetic_scenario

    scenario = load_scenario(contract_dir() / "sample" / "SYNTHETIC_scenario.json")
    scenario["sites"] = scenario["sites"][:1]
    scenario["sites"][0]["landing_utc"] = "2026-12-13T12:00:00.000Z"  # half a day before the end of the range
    paths = run_synthetic_scenario(scenario, tmp_path)
    manifest = validate_package(next(p for p in paths if p.name.startswith("site-")))
    records = manifest["timeline"]["opportunities"]
    assert records and all(r["planned_landing"] is None for r in records)
    assert manifest["request"]["timeline"]["landing_utc"] == "2026-12-13T12:00:00.000Z"
    notes = [w for w in manifest["warnings"] if w.startswith("opportunities: the planned landing")]
    assert len(notes) == len({r["requirement_id"] for r in records}) and all("2026-12-13T12:00:00.000Z" in n for n in notes)
