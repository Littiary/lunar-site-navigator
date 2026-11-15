"""Lines that were right but that no test held in place.

A review changed single lines of the core on purpose (a mutation test, 15 November 2026)
and found that for the lines below a wrong version passed every test. The code was not
changed; these tests exist so that it cannot go wrong unnoticed. Each one was run once
against the wrong version it is named after and failed there (the commit message lists
them). Expected values and tolerances were written before the first run.

Needs the SPICE kernels for everything that has a Sun or an Earth in it.
"""

import json
import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from lsncore.contract import read_package, validate_package
from lsncore.dem import AnalyticTerrain
from lsncore.pipeline import run_scenario
from lsncore.results import HorizonResult
from lsncore.scenario import single_site_scenario
from lsncore.timeline import IntervalSet, TimeGrid

R = 1_737_400.0
DAY = 86400.0
TOL_EDGE_S = 1.0  # two event searches of the same crossing agree to twice the finder's 0.5 s
WINDOW = {"start_utc": "2026-11-14T00:00:00.000Z", "end_utc": "2026-11-24T00:00:00.000Z", "step_s": 3600.0}
SITE = {"site_id": "pinned", "name": "Pinned lines site", "lat_deg": -86.0, "lon_deg": 20.0}


def _flat(lon, lat):
    return np.zeros(np.broadcast(lon, lat).shape)


def _ridge(lon, lat):
    return 800.0 * np.sin(np.radians(lon) * 3.0) * np.cos(np.radians(lat) * 40.0)


@pytest.fixture(scope="module")
def table(tmp_path_factory):
    """A direction table for the ten days of WINDOW (kernels needed)."""
    pytest.importorskip("spiceypy")
    from lsncore.ephem import kernels
    from lsncore.ephem import table as ephem_table

    try:
        kernels.load()
    except FileNotFoundError as missing:
        pytest.skip(f"kernels are not on this machine: {missing}")
    return ephem_table.write_direction_table(tmp_path_factory.mktemp("table"), WINDOW["start_utc"], WINDOW["end_utc"])


def _horizon(profile_deg, heights=(2.0,), surface_height_m=0.0, step_deg=0.25):
    """A horizon given as a profile, the same for every observer height."""
    profile = np.asarray(profile_deg, dtype=np.float64)
    n = len(heights)
    return HorizonResult(
        azimuth_step_deg=step_deg, observer_heights_m=list(heights), max_range_m=300_000.0, reference_radius_m=R, surface_height_m=float(surface_height_m),
        elevation_deg=np.tile(profile, (n, 1)), distance_m=np.full((n, profile.size), 1000.0),
    )


def _timeline(horizon, table, thresholds=None):
    from lsncore.events import timeline as timeline_mod

    return timeline_mod.compute_timeline(SITE, horizon, table, WINDOW, ["SUN", "EARTH"], thresholds)


def _edges(interval_set):
    return np.array([edge for interval in interval_set.intervals for edge in interval])


# -- 1. the smooth sphere has a dip ---------------------------------------------------------
# Wrong version: dip = 0.0 in pipeline._smooth_sphere_windows. At 2 m that moved the smooth
# total of a published site by 138 h, and with it every "lost to terrain" figure.

def test_smooth_sphere_windows_are_those_of_a_sphere_seen_from_the_observer_height(table):
    from lsncore.ephem import directions as d
    from lsncore.ephem import table as ephem_table
    from lsncore.events import finder
    from lsncore.events.timeline import DEFAULT_THRESHOLDS
    from lsncore.pipeline import _smooth_sphere_windows

    heights = (2.0, 20.0, 100.0)
    horizon = _horizon(np.full(1440, -0.5), heights)
    timeline = _timeline(horizon, table)
    found = _smooth_sphere_windows(SITE, horizon, table, timeline, DEFAULT_THRESHOLDS)
    grid = TimeGrid.from_contract(timeline.time)
    loaded = ephem_table.load_table(table)
    ground = d.Site(SITE["lon_deg"], SITE["lat_deg"], 0.0)
    compared = 0
    for body in ("SUN", "EARTH"):
        direction = finder.site_direction(ground, loaded, body)
        rule = {"visible": finder.threshold_from_contract(DEFAULT_THRESHOLDS[body], "visible")}
        for h, m in enumerate(heights):
            result = finder.find_events(direction, finder.Horizon.smooth_sphere(m), grid.start_et_s, grid.end_et_s, thresholds=rule)
            expected = _edges(IntervalSet(finder.windows(result, "visible").intervals_et_s, (grid.start_et_s, grid.end_et_s)))
            got = _edges(found[(body, h)])
            assert got.size == expected.size and np.abs(got - expected).max() <= TOL_EDGE_S, (body, m)
            compared += got.size
    assert compared >= 12  # the window has rises and sets to compare


def test_flat_terrain_loses_and_gains_nothing_against_the_smooth_sphere(table, tmp_path):
    """On a sphere without relief the terrain horizon is the dip, so terrain and smooth
    sphere must agree. Tolerance: the horizon of a sphere is found to 0.0005 deg; at the
    slowest rate of the Sun's elevation here that is 90 s per edge, a few edges per body."""
    scenario = single_site_scenario("flat-site", "Flat site", -86.0, 20.0, dem_set_id="any", synthetic=False, heights_m=[2.0, 20.0], azimuth_step_deg=1.0, max_range_m=60_000.0)
    scenario["time_window"] = WINDOW
    paths = run_scenario(scenario, tmp_path, AnalyticTerrain(_flat, R, ceiling_height_m=0.0, dem_set_id="ANALYTIC-flat"), direction_table=table)
    manifest = validate_package(paths[-1])
    metrics = {(m["id"], m["height_index"]): m["value"] for m in manifest["timeline"]["metrics"]}
    for body in ("sun", "earth"):
        for h in (0, 1):
            assert metrics[(f"{body}_lost_to_terrain_s", h)] <= 600.0 and metrics[(f"{body}_gained_from_terrain_s", h)] <= 600.0, (body, h)
    assert not [b for b in manifest["timeline"]["blockers"] if b["lost_s"] > 600.0]


# -- 2. the band and the ellipse belong to the default observer height ------------------------
# Wrong version: hd = 0 where the uncertainty is prepared.

def test_band_and_ellipse_are_computed_at_the_default_observer_height(table, tmp_path):
    scenario = single_site_scenario("ridge-site", "Analytic ridge site", -86.0, 20.0, dem_set_id="any", synthetic=False, heights_m=[0.0, 2.0, 10.0], azimuth_step_deg=1.0, max_range_m=50_000.0)
    scenario["time_window"] = WINDOW
    scenario["default_height_m"] = 2.0
    scenario["uncertainty"] = {"dem_height_error_m": 5.0, "landing_ellipse": {"semi_major_m": 3000.0, "semi_minor_m": 2000.0, "azimuth_deg": 20.0, "points": 3}}
    paths = run_scenario(scenario, tmp_path, AnalyticTerrain(_ridge, R, ceiling_height_m=800.0, dem_set_id="ANALYTIC-ridges"), direction_table=table)
    manifest = validate_package(paths[-1])
    package = read_package(paths[-1])
    hd = manifest["horizon"]["default_height_index"]
    assert hd == 1
    uncertainty = manifest["timeline"]["uncertainty"]
    assert uncertainty["landing_ellipse"]["height_index"] == hd
    distance = package.array(manifest["horizon"]["distance_m"]).astype(np.float64)
    profile = lambda h: np.degrees(np.arctan(5.0 / distance[h]))  # noqa: E731
    applied = uncertainty["horizon_error"]["applied_error_deg"]
    stats = lambda values: (float(values.min()), float(np.median(values)), float(values.max()))  # noqa: E731
    assert (applied["min"], applied["median"], applied["max"]) == pytest.approx(stats(profile(hd)), rel=1e-5)
    assert stats(profile(0))[1] != pytest.approx(applied["median"], rel=1e-3)  # the rows differ, so the comparison means something


# -- 3. the products behind the horizon are counted at the default observer height ------------
# Wrong version: default_index = 0 for horizon.terrain_source. The shares the published
# README quotes would have become those of the 0 m observer.

class _TwoProducts(AnalyticTerrain):
    """A low wall 50 m from the site on one product, mountains 20 km away on another. From
    the ground the wall is the horizon everywhere; from 2 m up the mountains are."""

    def __init__(self, lat, lon):
        self._site = (math.radians(lat), math.radians(lon))
        super().__init__(self._surface, R, ceiling_height_m=600.0, dem_set_id="ANALYTIC-two-products")

    def _arc_m(self, lon, lat):
        p1, l1 = self._site
        p2, l2 = np.radians(np.asarray(lat, dtype=np.float64)), np.radians(np.asarray(lon, dtype=np.float64))
        a = np.sin((p2 - p1) / 2.0) ** 2 + math.cos(p1) * np.cos(p2) * np.sin((l2 - l1) / 2.0) ** 2
        return 2.0 * R * np.arcsin(np.sqrt(a))

    def _surface(self, lon, lat):
        s = self._arc_m(lon, lat)
        return 1.5 * np.exp(-(((s - 50.0) / 8.0) ** 2)) + 500.0 * np.exp(-(((s - 20_000.0) / 1500.0) ** 2))

    def source_at(self, lon_deg, lat_deg):
        near = self._arc_m(lon_deg, lat_deg) < 1000.0
        ids = np.where(near, "WALL_PRODUCT", "MOUNTAIN_PRODUCT").astype(object)
        info = {name: {"pixel_m": 20.0, "projection": "analytic function, no grid"} for name in ("WALL_PRODUCT", "MOUNTAIN_PRODUCT")}
        return ids, info


def test_products_behind_the_horizon_are_counted_at_the_default_observer_height(tmp_path):
    terrain = _TwoProducts(-86.0, 20.0)
    scenario = single_site_scenario("two-products", "Two products site", -86.0, 20.0, dem_set_id="any", synthetic=False, heights_m=[0.0, 2.0], azimuth_step_deg=5.0, max_range_m=40_000.0)
    scenario["default_height_m"] = 2.0
    (path,) = run_scenario(scenario, tmp_path, terrain)
    manifest = validate_package(path)
    package = read_package(path)
    hd = manifest["horizon"]["default_height_index"]
    distance = package.array(manifest["horizon"]["distance_m"])
    assert hd == 1 and distance[0].max() < 100.0 and distance[1].min() > 10_000.0  # the two heights have different horizons
    shares = {p["product_id"]: p["azimuth_share"] for p in manifest["horizon"]["terrain_source"]["products"]}
    assert shares == {"MOUNTAIN_PRODUCT": 1.0}


# -- 4. the least sunlit lunar day is the least --------------------------------------------------
# Wrong version: max instead of min in trade.py.

def test_least_sunlit_lunar_day_is_the_smallest_of_the_complete_periods(tmp_path):
    pytest.importorskip("spiceypy")
    from lsncore.ephem import kernels

    try:
        kernels.load()
    except FileNotFoundError as missing:
        pytest.skip(f"kernels are not on this machine: {missing}")
    scenario = single_site_scenario("ridge-site", "Analytic ridge site", -86.0, 20.0, dem_set_id="any", synthetic=False, heights_m=[2.0, 10.0], azimuth_step_deg=1.0, max_range_m=50_000.0)
    scenario["time_window"] = {"start_utc": "2026-11-14T00:00:00.000Z", "end_utc": "2027-03-14T00:00:00.000Z", "step_s": 3600.0}
    paths = run_scenario(scenario, tmp_path, AnalyticTerrain(_ridge, R, ceiling_height_m=800.0, dem_set_id="ANALYTIC-ridges"))
    timeline = validate_package(paths[-1])["timeline"]
    complete = [p["index"] for p in timeline["calendar"]["periods"] if p["complete"]]
    assert len(complete) >= 3
    per_period = next(q["values"] for q in timeline["calendar"]["quantities"] if q["id"] == "sun_visible_s")
    least = next(q["values"] for q in timeline["height_trade"]["quantities"] if q["id"] == "sun_least_lunar_day_s")
    for h, row in enumerate(per_period):
        values = [row[i] for i in complete]
        assert least[h] == min(values)
        assert max(values) - min(values) > 3600.0  # the lunar days differ, so least and most are not the same number


# -- 5. the site stands on the ground, not on the reference sphere --------------------------------
# Wrong version: the direction of the bodies taken from a site at height 0. At the published
# sites that moved Earth rise and set by 14 s (Shackleton) to 90 s (Malapert).

def test_direction_of_the_earth_is_taken_from_the_ground_of_the_site(table):
    from lsncore.contract import read_package as read

    low = _timeline(_horizon(np.full(1440, -5.0), surface_height_m=0.0), table).series["EARTH"]
    high = _timeline(_horizon(np.full(1440, -5.0), surface_height_m=5000.0), table).series["EARTH"]
    earth_radius_km = read(table).manifest["body_radii_km"]["EARTH"]["value"]
    distance_km = earth_radius_km / np.sin(np.radians(low.angular_radius_deg))
    # an observer 5 km higher along the local vertical sees the Earth lower by 5 km / distance * cos(elevation)
    expected = -np.degrees(5.0 / distance_km * np.cos(np.radians(low.elevation_deg)))
    measured = high.elevation_deg - low.elevation_deg
    assert np.abs(expected).min() > 6e-4  # about 0.0007 deg: 2.6 arcseconds
    assert np.abs(measured - expected).max() <= 0.02 * np.abs(expected).max()


# -- 6. single lines ---------------------------------------------------------------------------------

def _ramps(azimuth_deg):
    """A horizon of straight ramps, one degree of elevation per degree of azimuth, up and down."""
    return np.abs((np.asarray(azimuth_deg) % 20.0) - 10.0) - 3.0


def test_horizon_at_an_event_is_read_where_the_limb_touches_it(table):
    """Wrong version: read at the azimuth of the disc centre. On a ramp of slope 1 the upper
    limb touches the horizon r / sqrt(2) to the side of the centre, where the ramp is lower
    by r / sqrt(2) (r: angular radius of the Sun)."""
    timeline = _timeline(_horizon(_ramps(np.arange(1440) * 0.25)), table)
    radius = float(np.mean(timeline.series["SUN"].angular_radius_deg))
    drop = [float(_ramps(e["azimuth_deg"])) - e["horizon_elevation_deg"] for e in timeline.events if e["body"] == "SUN"]
    assert len(drop) >= 6 and np.median(drop) == pytest.approx(radius / math.sqrt(2.0), abs=0.01)


def test_obstacle_distance_is_that_of_the_nearest_azimuth_sample():
    """Wrong version: the sample below the azimuth, whatever the fraction."""
    pytest.importorskip("spiceypy")
    from lsncore.events import finder

    horizon = finder.Horizon(0.0, 1.0, np.zeros(360), np.arange(360.0))
    assert float(horizon.distance_at(10.7)) == 11.0 and float(horizon.distance_at(10.2)) == 10.0


def test_an_event_a_fraction_of_a_second_outside_the_band_still_gets_its_bounds():
    """Wrong version: without the second of slack. An event and the edge of the band are
    found by separate searches of the same crossing and can differ by the finder's tolerance."""
    from lsncore.uncertainty import Band, event_time_bounds

    domain = (0.0, 1000.0)
    empty = IntervalSet.empty(domain)
    band = Band(nominal=empty, certain=empty, possible=empty, uncertain=IntervalSet([(100.0, 200.0)], domain), error_deg=0.1)
    assert event_time_bounds([200.4, 99.6, 300.0], band) == [(100.0, 200.0), (100.0, 200.0), (300.0, 300.0)]


def test_sun_lit_counts_any_part_of_the_disc_whatever_the_threshold_of_visible(table):
    """Wrong version: sun_lit built from the scenario's own "visible". With a scenario that
    calls the Sun visible only when the whole disc is up, sun_lit must still begin when the
    first part of the disc appears."""
    whole_disc = {"SUN": {"quantity": "visible_fraction", "op": ">=", "value": 1.0}}
    timeline = _timeline(_horizon(_ramps(np.arange(1440) * 0.25)), table, whole_disc)
    lit, visible = timeline.window("sun_lit", 0), timeline.window("sun_visible", 0)
    assert visible.intersection(lit.complement()).total_s() <= TOL_EDGE_S * len(visible.intervals) * 2  # visible lies inside lit
    assert lit.total_s() - visible.total_s() > 3600.0  # and the partial phases belong to lit only


def test_a_slope_exactly_on_a_class_limit_belongs_to_the_class_below():
    """Wrong version: < instead of <=. The default model says "5 m up to 30 degrees"."""
    from lsncore.uncertainty import height_error_for_points

    model = {"rules": {"*": {"slope_classes": [{"up_to_deg": 30.0, "error_m": 5.0}, {"up_to_deg": 90.0, "error_m": 7.0}]}}}
    error, source = height_error_for_points(model, np.array(["A", "A", "A"], dtype=object), np.full(3, np.nan), np.array([29.999, 30.0, 30.001]))
    assert error.tolist() == [5.0, 5.0, 7.0] and set(source.tolist()) == {"slope_class"}


# -- 7. the far-field bound reaches out to the tangent point ---------------------------------------
# Wrong version: the bound evaluated at the end of the ray only (g_eval = g_end). It passed
# every test of the core and of the validation. For an observer above the ceiling, terrain
# of ceiling height beyond the end of the ray is seen highest at the tangent point, not at
# the end of the ray, so the wrong version said "proven complete" where it is not.

def test_far_field_bound_covers_the_sphere_beyond_a_short_ray_seen_from_above():
    """A sphere without relief, an observer 100 m up, a search of 5 km only. The horizon of
    the whole sphere is the dip, 0.615 deg below the horizontal, 18.6 km away; within 5 km
    the surface is seen 1.228 deg below it. What the search found plus the bound it states
    must reach the true horizon. Tolerance: that of the smooth-sphere test, 0.0005 deg."""
    from lsncore.horizon import compute_horizon

    terrain = AnalyticTerrain(_flat, R, ceiling_height_m=0.0, dem_set_id="ANALYTIC-flat")
    result = compute_horizon(terrain, -85.0, 30.0, [100.0], azimuth_step_deg=5.0, max_range_m=5_000.0)
    dip = math.degrees(math.acos(R / (R + 100.0)))
    found = result.elevation_deg[0]
    assert np.abs(found + 1.228).max() < 0.001  # the surface 5 km away, far below the true horizon
    assert np.abs(found + result.far_field_bound_deg[0] + dip).max() <= 0.0005
    assert result.error_bounds["far_field_max_deg"][0] == pytest.approx(1.228 - dip, abs=0.001)
