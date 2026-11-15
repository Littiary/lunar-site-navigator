"""What a package says where the computed time range ends (contract 0.12).

A third review round (15 November 2026) looked at short and oddly placed time windows and
found four places where a value was cut by the start or the end of the range, or could not
be judged at all, and the package did not say so:

1. the earliest and latest time of an event under the stated horizon error;
2. two custom sites a few metres apart, or one custom site computed for two windows,
   under one default site id;
3. landing windows in a time window shorter than the mission: "0.0 feasible" where the
   truth is "cannot be judged";
4. the longest interval without a body, when that interval runs into an end of the range.

Expected values were written before the fixes; every test here failed first.
"""

import json

import numpy as np
import pytest

from lsncore.contract import validate_document, validate_package
from lsncore.dem import AnalyticTerrain
from lsncore.pipeline import run_scenario
from lsncore.scenario import custom_site_scenario, single_site_scenario
from lsncore.timeline import IntervalSet

from test_calendar import DAY, HOUR, _Table, _Timeline, _standard
from test_pinned_lines import R, WINDOW, _horizon, _ramps, _ridge, _timeline, table  # noqa: F401  (table is a fixture)


# -- 1. bounds of an event that the range cuts -------------------------------------------------

def _ridge_package(tmp_path, table, window, name):  # noqa: F811
    scenario = single_site_scenario("ridge-site", "Analytic ridge site", -86.0, 20.0, dem_set_id="any", synthetic=False, heights_m=[2.0], azimuth_step_deg=1.0, max_range_m=50_000.0)
    scenario["time_window"] = window
    scenario["uncertainty"] = {"horizon_error_deg": 0.3}
    paths = run_scenario(scenario, tmp_path / name, AnalyticTerrain(_ridge, R, ceiling_height_m=800.0, dem_set_id="ANALYTIC-ridges"), direction_table=table)
    return validate_package(paths[-1])


def test_event_bounds_cut_by_the_range_say_so(tmp_path, table):  # noqa: F811
    """An event (of the Sun or the Earth) whose band lies well inside ten days; then a window
    that begins and ends inside that band. In the short window the earliest and latest time can only be its two
    ends, and the event must say that they are cut."""
    from lsncore.ephem import directions as d

    long = _ridge_package(tmp_path, table, WINDOW, "long")
    start, end = d.utc_to_et(WINDOW["start_utc"]), d.utc_to_et(WINDOW["end_utc"])
    inner = [e for e in long["timeline"]["events"] if e["earliest_et_s"] > start + 6 * HOUR and e["latest_et_s"] < end - 6 * HOUR
             and e["et_s"] - e["earliest_et_s"] > 2 * HOUR and e["latest_et_s"] - e["et_s"] > 2 * HOUR]
    assert inner, "no event with a band of some hours inside the ten days"
    event = inner[0]
    assert event["earliest_clipped"] is False and event["latest_clipped"] is False
    for other in long["timeline"]["events"]:
        if "earliest_et_s" in other:
            assert other["earliest_clipped"] == (other["earliest_et_s"] <= start + 1e-6) and other["latest_clipped"] == (other["latest_et_s"] >= end - 1e-6)

    cut_start = 0.5 * (event["earliest_et_s"] + event["et_s"])
    cut_end = 0.5 * (event["et_s"] + event["latest_et_s"])
    short_window = {"start_utc": d.et_to_utc_z(cut_start), "end_utc": d.et_to_utc_z(cut_end), "step_s": 600.0}
    short = _ridge_package(tmp_path, table, short_window, "short")
    (same,) = [e for e in short["timeline"]["events"] if e["body"] == event["body"] and abs(e["et_s"] - event["et_s"]) < 2.0]
    grid = short["timeline"]["time"]
    assert same["earliest_et_s"] == pytest.approx(grid["start_et_s"], abs=1e-6) and same["earliest_clipped"] is True
    assert same["latest_et_s"] == pytest.approx(grid["start_et_s"] + grid["step_s"] * (grid["count"] - 1), abs=1e-6) and same["latest_clipped"] is True
    # the truth, known from the longer run, lies outside the short window on both sides
    assert event["earliest_et_s"] < same["earliest_et_s"] and event["latest_et_s"] > same["latest_et_s"]


# -- 2. default identity of a custom site ---------------------------------------------------------

def test_default_custom_site_id_tells_apart_what_the_package_tells_apart():
    a = custom_site_scenario(-89.80531, 205.76891, "2026-12-09")["sites"][0]
    b = custom_site_scenario(-89.80534, 205.76891, "2026-12-09")["sites"][0]  # 3.3 m away
    assert a["site_id"] != b["site_id"] and a["name"] != b["name"]
    assert a["site_id"] == "custom-89-8053100s-154-2310900w"
    # the id follows the canonical coordinates (1e-7 deg): what rounds to the same place is the same site
    c = custom_site_scenario(-89.80531004, 205.76891, "2027-01-01", days=3)["sites"][0]
    assert c["site_id"] == a["site_id"]
    validate_document(custom_site_scenario(12.3456789, -0.0000001, "2026-12-09"))


def test_two_packages_of_one_site_are_told_apart_by_package_id_in_the_index(tmp_path):
    """One place computed for two time windows: one site id, two packages. The index lists
    both, each with its window, and package_id is what identifies an entry."""
    terrain = AnalyticTerrain(_ridge, R, ceiling_height_m=800.0, dem_set_id="ANALYTIC-ridges")
    for start in ("2026-11-14T00:00:00.000Z", "2026-12-01T00:00:00.000Z"):
        scenario = single_site_scenario("same-place", "Same place", -86.0, 20.0, dem_set_id="SYNTHETIC-v1", synthetic=True, heights_m=[2.0])
        from lsncore.synthetic import SYNTHETIC_DEM_SET_ID

        scenario["data"]["dem_set_id"] = SYNTHETIC_DEM_SET_ID
        scenario["time_window"] = {"start_utc": start, "end_utc": start.replace("T00", "T12"), "step_s": 3600.0}
        run_scenario(scenario, tmp_path)
    del terrain
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    validate_document(index)
    sites = [entry for entry in index["packages"] if entry["kind"] == "site"]
    assert len(sites) == 2 and {entry["site_id"] for entry in sites} == {"same-place"}
    assert len({entry["package_id"] for entry in sites}) == 2
    assert sorted(entry["start_utc"] for entry in sites) == ["2026-11-14T00:00:00.000Z", "2026-12-01T00:00:00.000Z"]
    assert all(entry["end_utc"] > entry["start_utc"] for entry in sites)


# -- 3. a window shorter than the mission -----------------------------------------------------------

def _opportunity_and_notes(sun, earth, requirement, days, planned_day=None):
    from lsncore.calendar import add_calendar_to_timeline

    time = {"start_et_s": 0.0, "step_s": HOUR, "count": int(days * 24) + 1}
    domain = (0.0, days * DAY)
    windows = {"sun_visible": IntervalSet([(a * DAY, b * DAY) for a, b in sun], domain), "earth_visible": IntervalSet([(a * DAY, b * DAY) for a, b in earth], domain)}
    timeline = _Timeline(time, windows)
    notes = add_calendar_to_timeline(timeline, _Table(time), 1, [requirement], None if planned_day is None else planned_day * DAY, lambda et: f"day {et / DAY:.6f}")
    (record,) = timeline.opportunities
    return record, notes


def test_a_window_shorter_than_the_mission_cannot_be_judged_and_says_so():
    """Three days, a mission of ten: no landing time can be judged. That is not "0.0 of the
    time is feasible"."""
    record, notes = _opportunity_and_notes([(0, 3)], [(0, 3)], _standard(), days=3.0, planned_day=1.0)
    assert record["landing_windows_et_s"] == [] and record["window_count"] == 0
    assert record["feasible_fraction"] is None
    assert record["latest_landing_et_s"] is None and record["latest_landing_utc"] is None
    assert record["clipped_end"] is False and record["planned_landing"] is None
    (note,) = notes
    assert "shorter than the mission duration" in note and "like-example-standard" in note


def test_a_window_as_long_as_the_mission_or_longer_is_judged_as_before():
    exact, notes = _opportunity_and_notes([(0, 12)], [(0, 12)], _standard(), days=12.0)
    assert notes == [] and exact["latest_landing_et_s"] == 2 * DAY and exact["feasible_fraction"] == pytest.approx(1.0)
    none, notes = _opportunity_and_notes([(0, 3), (20, 22)], [(0, 30)], _standard(), days=30.0)
    assert notes == [] and none["feasible_fraction"] == 0.0 and none["latest_landing_et_s"] == 20 * DAY  # judged, and truly never feasible


def test_a_package_with_a_short_window_is_valid_and_carries_the_warning(tmp_path):
    from lsncore.contract import contract_dir
    from lsncore.scenario import load_scenario
    from lsncore.synthetic import run_synthetic_scenario

    scenario = load_scenario(contract_dir() / "sample" / "SYNTHETIC_scenario.json")
    scenario["sites"] = scenario["sites"][:1]
    scenario["sites"][0].pop("landing_utc", None)
    scenario["time_window"] = {"start_utc": "2026-12-08T00:00:00.000Z", "end_utc": "2026-12-11T00:00:00.000Z", "step_s": 3600.0}
    durations = {r["id"]: r.get("mission_duration_s", 0.0) for r in scenario["requirements"]}
    assert max(durations.values()) > 3 * DAY
    paths = run_synthetic_scenario(scenario, tmp_path)
    manifest = validate_package(next(p for p in paths if p.name.startswith("site-")))
    for record in manifest["timeline"]["opportunities"]:
        if durations[record["requirement_id"]] > 3 * DAY:
            assert record["feasible_fraction"] is None and record["latest_landing_utc"] is None and record["landing_windows_utc"] == []
    assert any("shorter than the mission duration" in w for w in manifest["warnings"])


def test_the_published_24_month_requirements_are_not_touched(tmp_path):
    """Every example requirement in a window of two years keeps a number for its feasible
    share and a latest landing time."""
    from lsncore.scenario import requirement_presets

    for requirement in requirement_presets().values():
        record, notes = _opportunity_and_notes([(5, 700)], [(0, 731)], requirement, days=731.0)
        assert notes == [] and isinstance(record["feasible_fraction"], float) and record["feasible_fraction"] > 0.0
        assert record["latest_landing_et_s"] == 731 * DAY - requirement["mission_duration_s"]


# -- 4. the longest outage is a lower bound when the range cuts it ------------------------------------

@pytest.mark.parametrize("profile, expected", [(np.full(1440, 20.0), 1.0), (np.full(1440, -5.0), 0.0), (None, None)], ids=["always hidden", "always visible", "ramps"])
def test_longest_outage_says_when_the_range_cuts_it(table, profile, expected):  # noqa: F811
    timeline = _timeline(_horizon(_ramps(np.arange(1440) * 0.25) if profile is None else profile), table)
    metrics = {m["id"]: m["value"] for m in timeline.metrics if m["height_index"] == 0}
    grid = timeline.time
    start, end = grid["start_et_s"], grid["start_et_s"] + grid["step_s"] * (grid["count"] - 1)
    for body in ("sun", "earth"):
        outages = timeline.window(f"{body}_visible", 0).complement().intervals
        longest = max(outages, key=lambda iv: iv[1] - iv[0], default=None)
        cut = longest is not None and (longest[0] <= start + 1e-6 or longest[1] >= end - 1e-6)
        assert metrics[f"{body}_longest_outage_is_lower_bound"] == (1.0 if cut else 0.0), body
    if expected is not None:
        assert metrics["sun_longest_outage_is_lower_bound"] == expected
