"""Acceptance tests: real direction-table package and per-site timeline in contract form.

Written before the implementation. Terrain is replaced by a smooth sphere here, so every
expected value can be recomputed directly with SPICE.
"""

import numpy as np
import pytest

from lsncore import events as ev
from lsncore.contract import read_package, validate_package
from lsncore.ephem import directions as d
from lsncore.ephem import kernels
from lsncore.ephem import table as tb
from lsncore.events import timeline as tl
from lsncore.events.smooth_sphere import smooth_sphere_horizon
from lsncore.packaging import build_site_package

TOL_EVENT_S = 1.0
TOL_INTERPOLATION_ARCSEC = 0.01

SITE = {"site_id": "test-low-latitude", "name": "Test point, low latitude", "lat_deg": 2.0, "lon_deg": -20.0}
WINDOW = {"start_utc": "2026-11-01T00:00:00.000Z", "end_utc": "2026-12-16T00:00:00.000Z", "step_s": 3600.0}
HEIGHTS = [0.0, 2.0, 10.0]
THRESHOLDS = {
    "SUN": {"quantity": "visible_fraction", "op": ">", "value": 0.0},
    "EARTH": {"quantity": "margin_deg", "op": ">", "value": 0.0},
}


@pytest.fixture(scope="module")
def table_dir(tmp_path_factory):
    kernels.load()
    root = tmp_path_factory.mktemp("packages")
    return tb.write_direction_table(root, WINDOW["start_utc"], WINDOW["end_utc"])


@pytest.fixture(scope="module")
def horizon():
    return smooth_sphere_horizon(HEIGHTS, azimuth_step_deg=0.25)


@pytest.fixture(scope="module")
def timeline(table_dir, horizon):
    return tl.compute_timeline(SITE, horizon, table_dir, WINDOW, ["SUN", "EARTH"], THRESHOLDS)


# ------------------------------------------------------------------ direction table package


def test_direction_table_package_is_valid_and_real(table_dir):
    manifest = validate_package(table_dir)
    assert manifest["synthetic"] is False and manifest["status"] == "ok"
    assert manifest["frame"] == "MOON_ME_DE440_ME421" and manifest["aberration_correction"] == "LT+S"
    assert manifest["bodies"] == ["SUN", "EARTH"]
    assert manifest["time"]["step_s"] == 3600.0 and manifest["time"]["leap_seconds_in_range"] == 0
    names = [k["name"] for k in manifest["inputs"]["kernels"]]
    assert names == ["naif0012.tls", "pck00011.tpc", "de440s.bsp", "moon_pa_de440_200625.bpc", "moon_de440_250416.tf"]
    assert manifest["inputs"]["kernel_set_id"] == kernels.kernel_set_id()
    assert manifest["body_radii_km"]["SUN"]["value"] == 695700.0
    assert manifest["methods"]["dirtab.positions"]["validation"]["status"] == "externally-validated"
    # The grid starts on the requested UTC instant minus one record, so that every
    # interpolation stencil inside the requested window is centred.
    assert abs(d.utc_to_et(manifest["time"]["start_utc"]) - d.utc_to_et("2026-10-31T23:00:00.000Z")) < 0.002


def test_direction_table_records_equal_direct_spice(table_dir):
    package = read_package(table_dir)
    table = tb.load_table(table_dir)
    assert table.et.size == package.manifest["time"]["count"]
    direct = d.direction_table(table.et)
    assert np.array_equal(table.sun_km, direct.sun_km) and np.array_equal(table.earth_km, direct.earth_km)
    assert table.radii_km == {"SUN": 695700.0, "EARTH": 6378.1366}


def test_stated_interpolation_error_is_measured_and_small(table_dir):
    manifest = read_package(table_dir).manifest
    stated = manifest["interpolation"]["max_error_arcsec"]["value"]
    assert manifest["interpolation"]["recommended"] == "lagrange-4-point"
    assert stated is not None and 0.0 < stated < TOL_INTERPOLATION_ARCSEC
    # Independent re-measurement at other epochs must not exceed twice the stated value.
    table = tb.load_table(table_dir)
    rng = np.random.default_rng(99)
    query = np.sort(rng.uniform(table.et[0], table.et[-1], 3000))
    assert tb.interpolation_error(table, query)["max_error_arcsec"] < 2.0 * stated + 1e-6


# ------------------------------------------------------------------ smooth-sphere horizon


def test_smooth_sphere_horizon_result(horizon):
    assert horizon.elevation_deg.shape == (3, 1440) and horizon.distance_m.shape == (3, 1440)
    radius = 1737400.0
    for h, height in enumerate(HEIGHTS):
        dip = np.degrees(np.arccos(radius / (radius + height)))
        assert np.allclose(horizon.elevation_deg[h], -dip, atol=1e-12)
        assert np.allclose(horizon.distance_m[h], radius * np.radians(dip), atol=1e-6)
    assert horizon.reference_radius_m == radius and horizon.surface_height_m == 0.0


# ------------------------------------------------------------------ timeline


def test_series_shapes_and_ranges(timeline):
    n = timeline.time["count"]
    # The grid is uniform in TDB; TDB - UTC varies periodically by up to 1.7 ms, so the UTC
    # label of the last sample may differ from the requested end by a millisecond.
    assert timeline.time["start_utc"] == WINDOW["start_utc"]
    assert abs(d.utc_to_et(timeline.time["end_utc"]) - d.utc_to_et(WINDOW["end_utc"])) < 0.002
    for body in ("SUN", "EARTH"):
        series = timeline.series[body]
        assert series.azimuth_deg.shape == (n,) and series.elevation_deg.shape == (n,)
        assert series.margin_deg.shape == (3, n) and series.visible_fraction.shape == (3, n)
        assert np.all((series.visible_fraction >= 0.0) & (series.visible_fraction <= 1.0))
        # A higher observer sees a lower horizon: the margin grows with height.
        assert np.all(np.diff(series.margin_deg, axis=0) > 0.0)
    # From 20 W, 2 N the Earth is always high in the sky.
    assert timeline.series["EARTH"].elevation_deg.min() > 60.0


def test_series_match_exact_spice(timeline):
    site = d.Site(SITE["lon_deg"], SITE["lat_deg"], 0.0)
    et = timeline.time["start_et_s"] + timeline.time["step_s"] * np.arange(timeline.time["count"])
    for body in ("SUN", "EARTH"):
        exact = d.topocentric_exact(site, et, body)
        sep = d.angular_separation_deg(timeline.series[body].azimuth_deg, timeline.series[body].elevation_deg, exact.az_deg, exact.el_deg)
        assert sep.max() * 3600.0 < 0.2, body  # the direction-table shortcut, measured at 0.1 arcsec


def test_sun_events_match_direct_spice_crossings(timeline):
    site = d.Site(SITE["lon_deg"], SITE["lat_deg"], 0.0)
    sun = [event for event in timeline.events if event["body"] == "SUN"]
    assert len(sun) >= 2 * len(HEIGHTS)
    for event in sun:
        assert event["threshold"] == THRESHOLDS["SUN"]
        height = HEIGHTS[event["height_index"]]
        dip = np.degrees(np.arccos(1737400.0 / (1737400.0 + height)))
        et = event["et_s"] + np.arange(-5.0, 6.0)
        exact = d.topocentric_exact(site, et, "SUN")
        signal = exact.el_deg + exact.angular_radius_deg + dip  # upper limb above the dipped horizon
        assert abs(et[np.argmin(np.abs(signal))] - event["et_s"]) <= TOL_EVENT_S
        assert (np.diff(signal) > 0).all() == (event["type"] == "rise")
        assert event["utc"] == d.et_to_utc_z(event["et_s"])
        assert abs(event["horizon_elevation_deg"] + dip) < 1e-9
        assert event["closing_rate_deg_per_h"] is not None and 0.3 < abs(event["closing_rate_deg_per_h"]) < 0.7
    # A higher observer sees the Sun rise earlier and set later.
    rises = sorted((e["height_index"], e["et_s"]) for e in sun if e["type"] == "rise")
    first = {h: t for h, t in reversed(rises)}
    assert first[0] > first[1] > first[2]


def test_earth_has_no_events_and_one_clipped_window(timeline):
    assert [event for event in timeline.events if event["body"] == "EARTH"] == []
    for window in timeline.windows:
        if window["id"] == "earth_visible":
            assert len(window["intervals_et_s"]) == 1 and window["clipped_start"] and window["clipped_end"]


def test_windows_follow_events_and_partial_phase_is_ordered(timeline):
    by_id = {(w["id"], w["height_index"]): w for w in timeline.windows}
    for h in range(len(HEIGHTS)):
        visible = by_id[("sun_visible", h)]
        any_part = by_id[("sun_any_part_visible", h)]
        full = by_id[("sun_full_disc_visible", h)]
        assert visible["intervals_et_s"] == any_part["intervals_et_s"]  # the scenario threshold is "any part"
        edges = sorted(t for a, b in visible["intervals_et_s"] for t in (a, b))
        event_times = sorted(e["et_s"] for e in timeline.events if e["body"] == "SUN" and e["height_index"] == h)
        inner = [t for t in edges if t not in (timeline.time["start_et_s"], visible_domain_end(timeline))]
        assert np.allclose(inner, event_times, atol=1e-6)
        # The full disc is visible only inside the "any part" window, later at rise and earlier at set.
        for (a, b), (c, e) in zip(any_part["intervals_et_s"], full["intervals_et_s"]):
            if a != timeline.time["start_et_s"]:
                assert 30 * 60 < c - a < 90 * 60  # the disc takes about an hour to clear the horizon here
            if b != visible_domain_end(timeline):
                assert 30 * 60 < b - e < 90 * 60
        both = by_id[("sun_and_earth_visible", h)]
        assert both["subject"] == "COMBINED" and both["intervals_et_s"] == visible["intervals_et_s"]


def visible_domain_end(timeline):
    return timeline.time["start_et_s"] + timeline.time["step_s"] * (timeline.time["count"] - 1)


def test_countdown_metrics(timeline):
    metrics = {(m["id"], m["height_index"]): m for m in timeline.metrics}
    start = timeline.time["start_et_s"]
    for h in range(len(HEIGHTS)):
        sun_sets = [e["et_s"] for e in timeline.events if e["body"] == "SUN" and e["height_index"] == h and e["type"] == "set"]
        to_set = metrics[("sun_time_to_set_s", h)]
        assert to_set["unit"] == "s" and abs(to_set["value"] - (sun_sets[0] - start)) < 1e-6
        assert metrics[("sun_time_to_set_is_lower_bound", h)]["value"] == 0.0
        # The Earth never sets from this site: the countdown is a lower bound equal to the rest of the range.
        earth = metrics[("earth_time_to_set_s", h)]
        assert abs(earth["value"] - (visible_domain_end(timeline) - start)) < 1e-6
        assert metrics[("earth_time_to_set_is_lower_bound", h)]["value"] == 1.0


def test_site_package_with_real_timeline_is_valid(tmp_path, table_dir, horizon, timeline):
    methods = {**tl.smooth_sphere_methods(), **tl.timeline_methods(table_dir, horizon_is_terrain=False)}
    request = {"start_utc": WINDOW["start_utc"], "end_utc": WINDOW["end_utc"], "step_s": WINDOW["step_s"], "bodies": ["SUN", "EARTH"], "thresholds": THRESHOLDS}
    out = build_site_package(
        tmp_path,
        site=SITE,
        frame_name=d.FRAME,
        dem_input={"dem_set_id": "none-smooth-sphere", "layers": []},
        horizon=horizon,
        methods=methods,
        synthetic=False,
        timeline=timeline,
        timeline_request=request,
        default_height_m=2.0,
        status="partial",
        warnings=["No terrain: the horizon is that of a smooth sphere."],
    )
    manifest = validate_package(out)
    assert manifest["synthetic"] is False and manifest["status"] == "partial"
    assert manifest["site"]["frame"] == "MOON_ME_DE440_ME421"
    assert manifest["methods"]["timeline.direction"]["validation"]["status"] == "externally-validated"
    assert manifest["methods"]["timeline.events"]["validation"]["status"] == "analytic-test-passed"
