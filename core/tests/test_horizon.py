"""Acceptance tests of the horizon core.

The thresholds in the block below were written before the implementation existed and
before anything was measured. They are not to be edited to make a test pass
(CONTRIBUTING.md, rule 5). If a threshold turns out to be wrong, the change needs a
human decision and a note in docs/method/horizon.md.

Expected values are computed inside this file from closed-form geometry, written
independently of lsncore/horizon.py (a different algebraic form of the elevation
formula, classic spherical trigonometry for great circles).
"""

import math
import time

import numpy as np
import pytest

from lsncore.dem import AnalyticTerrain
from lsncore.horizon import compute_horizon

# --------------------------------------------------------------------------------------
# THRESHOLDS (fixed before measuring)
# --------------------------------------------------------------------------------------
# Design target: the algorithm's own contribution (formula, range sampling, refinement)
# stays below 0.01 deg, so that data errors dominate. The analytic cases have no data
# error, so they are held to a tenth of that or better.
TOL_SPHERE_DEG = 0.0005        # smooth sphere: horizon depression for a given observer height
TOL_RIM_DEG = 0.001            # crater rim at a known distance and height
TOL_RIM_DISTANCE_M = 10.0      # reported distance to the rim crest (rim at 20 km)
TOL_RIM_HEIGHT_M = 1.0         # reported height of the obstacle
TOL_HILL_DEG = 0.002           # smooth hill off-axis, against an independent 1-D solution
TOL_OBSTACLE_POSITION_M = 1.0  # obstacle lat/lon against azimuth + distance
TOL_HEIGHTS_ONE_PASS_DEG = 1e-9  # several heights in one pass vs one height per run
MAX_RUNTIME_S = 5.0            # one site, default settings (0.25 deg, 300 km, 6 heights)
TOL_FIXTURE_DEG = 0.02         # gridded 100 m test DEM of the data stream, smooth part
# --------------------------------------------------------------------------------------

# Sphere radius for the analytic cases. Any sphere would do; this is the reference radius
# the data stream reads from the LOLA product labels.
R = 1_737_400.0

SITES = [
    pytest.param(-85.0, 30.0, id="lat-85"),
    pytest.param(-90.0, 0.0, id="south-pole"),
    pytest.param(-89.999, 179.9999, id="near-pole-at-seam"),
    pytest.param(-80.0, -179.5, id="seam"),
    pytest.param(12.0, -75.0, id="low-latitude"),
    pytest.param(88.0, 10.0, id="north"),
]


# -- independent geometry used for expected values ----------------------------------------

def exact_elevation_deg(r_observer, r_target, gamma):
    """Elevation of a target at central angle gamma, straight from the triangle."""
    return np.degrees(np.arctan2(r_target * np.cos(gamma) - r_observer, r_target * np.sin(gamma)))


def central_angle(lat1, lon1, lat2, lon2):
    """Central angle (rad) between two points, haversine form; arrays broadcast."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dlat = p2 - p1
    dlon = np.radians(lon2) - np.radians(lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlon / 2) ** 2
    return 2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def gc_point(lat1, lon1, azimuth_deg, gamma):
    """Great-circle direct problem with the classic formulas (not valid at a pole)."""
    p1, l1, az = math.radians(lat1), math.radians(lon1), np.radians(azimuth_deg)
    lat2 = np.arcsin(np.sin(p1) * np.cos(gamma) + np.cos(p1) * np.sin(gamma) * np.cos(az))
    lon2 = l1 + np.arctan2(np.sin(az) * np.sin(gamma) * np.cos(p1), np.cos(gamma) - np.sin(p1) * np.sin(lat2))
    return np.degrees(lat2), np.degrees(lon2)


def flat(lon, lat):
    return np.zeros(np.broadcast(lon, lat).shape)


def bowl(site_lat, site_lon, rim_m, floor_m, rim_height_m):
    """Parabolic crater centred on the site; flat at rim_height_m beyond the rim."""

    def height(lon, lat):
        s = R * central_angle(site_lat, site_lon, lat, lon)
        inside = floor_m + (rim_height_m - floor_m) * (s / rim_m) ** 2
        return np.where(s < rim_m, inside, rim_height_m)

    return height


def hill(lat0, lon0, height_m, sigma_m):
    def height(lon, lat):
        s = R * central_angle(lat0, lon0, lat, lon)
        return height_m * np.exp(-0.5 * (s / sigma_m) ** 2)

    return height


# -- analytic case 1: smooth sphere -------------------------------------------------------

@pytest.mark.parametrize("lat, lon", SITES)
def test_smooth_sphere_horizon_depression(lat, lon):
    heights = [1.0, 2.0, 10.0, 100.0]
    res = compute_horizon(AnalyticTerrain(flat, R), lat, lon, heights, azimuth_step_deg=5.0, max_range_m=300_000.0)
    assert res.elevation_deg.shape == (4, 72)
    for i, h in enumerate(heights):
        expected = -math.degrees(math.acos(R / (R + h)))
        assert np.abs(res.elevation_deg[i] - expected).max() <= TOL_SPHERE_DEG
        # the horizon is where the line of sight is tangent to the sphere
        tangent_m = R * math.acos(R / (R + h))
        assert np.abs(res.distance_m[i] - tangent_m).max() <= 0.02 * tangent_m + 20.0
    assert res.coverage_complete and not res.truncated_at_data_edge and res.nodata_fraction == 0.0


def test_smooth_sphere_is_proven_complete_within_the_search_radius():
    """No terrain at or below the sphere beyond the range can change a negative horizon."""
    res = compute_horizon(AnalyticTerrain(flat, R, ceiling_height_m=0.0), -85.0, 30.0, [2.0], azimuth_step_deg=5.0, max_range_m=50_000.0)
    assert res.error_bounds["far_field_max_deg"][0] == 0.0


# -- analytic case 2: crater rim at a known distance and height ---------------------------

RIM_M, FLOOR_M, RIM_HEIGHT_M = 20_000.0, -1500.0, 0.0


@pytest.mark.parametrize("lat, lon", SITES)
def test_crater_rim_at_known_distance_and_height(lat, lon):
    heights = [0.0, 2.0, 20.0]
    terrain = AnalyticTerrain(bowl(lat, lon, RIM_M, FLOOR_M, RIM_HEIGHT_M), R)
    res = compute_horizon(terrain, lat, lon, heights, azimuth_step_deg=5.0, max_range_m=100_000.0)
    assert res.surface_height_m == pytest.approx(FLOOR_M, abs=1e-6)
    gamma = RIM_M / R
    for i, h in enumerate(heights):
        expected = exact_elevation_deg(R + FLOOR_M + h, R + RIM_HEIGHT_M, gamma)
        assert np.abs(res.elevation_deg[i] - expected).max() <= TOL_RIM_DEG
        assert np.abs(res.distance_m[i] - RIM_M).max() <= TOL_RIM_DISTANCE_M
        assert np.abs(res.obstacle_height_m[i] - RIM_HEIGHT_M).max() <= TOL_RIM_HEIGHT_M
        # the reported obstacle position is the point at that distance from the site
        arc = R * central_angle(lat, lon, res.obstacle_lat_deg[i], res.obstacle_lon_deg[i])
        assert np.abs(arc - res.distance_m[i]).max() <= TOL_OBSTACLE_POSITION_M


def test_higher_observer_sees_a_lower_rim():
    terrain = AnalyticTerrain(bowl(-85.0, 30.0, RIM_M, FLOOR_M, RIM_HEIGHT_M), R)
    res = compute_horizon(terrain, -85.0, 30.0, [0.0, 1.0, 2.0, 5.0, 10.0, 20.0], azimuth_step_deg=5.0, max_range_m=100_000.0)
    assert np.all(np.diff(res.elevation_deg, axis=0) < 0)


# -- direction conventions and an off-axis smooth hill ------------------------------------

def test_hill_appears_at_its_bearing_with_the_right_elevation():
    lat, lon, h = -85.0, 30.0, 2.0
    bearing, dist_m, peak_m, sigma_m = 37.5, 60_000.0, 3000.0, 3000.0
    hill_lat, hill_lon = gc_point(lat, lon, bearing, dist_m / R)
    terrain = AnalyticTerrain(hill(float(hill_lat), float(hill_lon), peak_m, sigma_m), R)
    res = compute_horizon(terrain, lat, lon, [h], azimuth_step_deg=0.25, max_range_m=300_000.0)
    az = np.arange(res.elevation_deg.shape[1]) * 0.25
    assert az[np.argmax(res.elevation_deg[0])] == bearing

    # independent solution along five great circles: dense sampling of the exact formula
    s = np.arange(100.0, 120_000.0, 1.0)
    for offset in (-3.0, -1.0, 0.0, 1.0, 3.0):
        plat, plon = gc_point(lat, lon, bearing + offset, s / R)
        profile = exact_elevation_deg(R + h, R + terrain.height_m(plon, plat), s / R)
        j = int(round((bearing + offset) / 0.25))
        assert abs(res.elevation_deg[0, j] - profile.max()) <= TOL_HILL_DEG
        assert abs(res.distance_m[0, j] - s[np.argmax(profile)]) <= 25.0


def test_azimuth_convention_at_the_south_pole():
    """At the pole with longitude 0 given, azimuth 0 looks along longitude 0 and azimuth 90
    along longitude 90 east."""
    terrain = AnalyticTerrain(hill(-89.0, 90.0, 2000.0, 2000.0), R)
    res = compute_horizon(terrain, -90.0, 0.0, [2.0], azimuth_step_deg=1.0, max_range_m=100_000.0)
    assert int(np.argmax(res.elevation_deg[0])) == 90
    j = 90
    assert res.obstacle_lon_deg[0, j] == pytest.approx(90.0, abs=1e-6)
    assert res.obstacle_lat_deg[0, j] == pytest.approx(-90.0 + math.degrees(res.distance_m[0, j] / R), abs=1e-9)


def test_east_is_ninety_degrees_at_low_latitude():
    terrain = AnalyticTerrain(hill(0.0, 1.0, 2000.0, 2000.0), R)  # hill one degree east of the site
    res = compute_horizon(terrain, 0.0, 0.0, [2.0], azimuth_step_deg=1.0, max_range_m=100_000.0)
    assert int(np.argmax(res.elevation_deg[0])) == 90


# -- several observer heights in one pass (contract decision 2) ---------------------------

def test_heights_in_one_pass_equal_separate_runs():
    lat, lon = -85.0, 30.0
    terrain = AnalyticTerrain(bowl(lat, lon, RIM_M, FLOOR_M, RIM_HEIGHT_M), R)
    heights = [0.0, 2.0, 10.0]
    together = compute_horizon(terrain, lat, lon, heights, azimuth_step_deg=5.0, max_range_m=100_000.0)
    for i, h in enumerate(heights):
        alone = compute_horizon(terrain, lat, lon, [h], azimuth_step_deg=5.0, max_range_m=100_000.0)
        assert np.abs(together.elevation_deg[i] - alone.elevation_deg[0]).max() <= TOL_HEIGHTS_ONE_PASS_DEG
        assert np.array_equal(together.distance_m[i], alone.distance_m[0])


# -- search radius and its error bound ----------------------------------------------------

def test_far_field_bound_covers_terrain_beyond_the_search_radius():
    """A mountain outside the search radius raises the true horizon; the stated bound must
    be at least as large as that rise in every azimuth and for every height."""
    lat, lon = -85.0, 30.0
    # Scenario note: the first version of this case (6000 m hill at 150 km) raised the
    # horizon by only 0.093 deg and failed the "not trivial" guard below. The mountain was
    # made higher and closer; the guard and the inequality under test were not changed.
    hill_lat, hill_lon = gc_point(lat, lon, 120.0, 130_000.0 / R)
    terrain = AnalyticTerrain(hill(float(hill_lat), float(hill_lon), 8000.0, 8000.0), R, ceiling_height_m=8000.0)
    heights = [2.0, 20.0]
    near = compute_horizon(terrain, lat, lon, heights, azimuth_step_deg=1.0, max_range_m=100_000.0)
    full = compute_horizon(terrain, lat, lon, heights, azimuth_step_deg=1.0, max_range_m=300_000.0)
    rise = full.elevation_deg - near.elevation_deg
    assert rise.max() > 0.1  # the case is not trivial
    bound = np.asarray(near.far_field_bound_deg)
    assert bound.shape == rise.shape
    assert np.all(bound >= rise - 1e-9)
    assert near.error_bounds["far_field_max_deg"][0] == pytest.approx(bound.max())
    # with the full radius the bound shrinks
    assert full.error_bounds["far_field_max_deg"][0] < near.error_bounds["far_field_max_deg"][0]


def test_missing_data_is_flagged_not_hidden():
    def partial(lon, lat):
        s = R * central_angle(-85.0, 30.0, lat, lon)
        return np.where(s < 40_000.0, 0.0, np.nan)

    res = compute_horizon(AnalyticTerrain(partial, R), -85.0, 30.0, [2.0], azimuth_step_deg=5.0, max_range_m=100_000.0)
    assert res.truncated_at_data_edge and not res.coverage_complete
    assert 0.0 < res.nodata_fraction < 1.0
    assert np.isfinite(res.elevation_deg).all()
    assert any("coverage" in w for w in res.warnings)


def test_site_without_data_is_an_error():
    nothing = lambda lon, lat: np.full(np.broadcast(lon, lat).shape, np.nan)  # noqa: E731
    with pytest.raises(ValueError):
        compute_horizon(AnalyticTerrain(nothing, R), -85.0, 30.0, [2.0], azimuth_step_deg=5.0, max_range_m=100_000.0)


# -- performance --------------------------------------------------------------------------

def _best_of_three(run) -> float:
    """Shortest wall time of three runs.

    Change of the test logic (not of the threshold), 14 November: a single timed run failed
    twice while other jobs loaded the laptop (the same call took 2.3 s and 7.5 s within a
    minute). The target is the runtime of the computation on this laptop, so the shortest
    of three runs is compared with the unchanged limit.
    """
    best = math.inf
    for _ in range(3):
        t0 = time.perf_counter()
        run()
        best = min(best, time.perf_counter() - t0)
    return best


def test_one_site_runs_within_the_time_budget():
    lat, lon = -85.0, 30.0
    a = hill(-84.0, 35.0, 4000.0, 9000.0)
    b = bowl(lat, lon, RIM_M, FLOOR_M, RIM_HEIGHT_M)
    terrain = AnalyticTerrain(lambda lo, la: a(lo, la) + b(lo, la), R)
    heights = [0.0, 1.0, 2.0, 5.0, 10.0, 20.0]
    compute_horizon(terrain, lat, lon, [2.0], azimuth_step_deg=5.0, max_range_m=10_000.0)  # warm-up
    elapsed = _best_of_three(lambda: compute_horizon(terrain, lat, lon, heights, azimuth_step_deg=0.25, max_range_m=300_000.0))
    assert elapsed <= MAX_RUNTIME_S, f"{elapsed:.2f} s"


# -- through the data stream's reader, on its gridded synthetic DEM -----------------------

def test_gridded_synthetic_dem_of_the_data_stream():
    """Observer at the south pole of the data stream's 100 m synthetic DEM: a bowl, a ring
    ridge 12 km away and a cone towards 90 deg east. Checks the whole path through the
    real reader: projection, pixel indexing, bilinear sampling, east/west orientation."""
    lsn_data = pytest.importorskip("lsn_data")
    from pathlib import Path

    from lsn_data import synthetic
    from lsn_data.georef import lonlat_to_xy

    from lsncore.dem import LolaTerrain

    label = Path(lsn_data.__file__).resolve().parents[1] / "fixtures" / "synth_s90_100m.lbl"
    if not label.exists():
        pytest.skip("synthetic DEM fixture of the data stream not found")
    terrain = LolaTerrain(lsn_data.open_terrain(label_paths=[label]))
    radius = terrain.reference_radius_m
    h = 2.0
    res = compute_horizon(terrain, -90.0, 0.0, [h], azimuth_step_deg=1.0, max_range_m=19_000.0)

    az = np.arange(360.0)
    s = np.arange(50.0, 19_000.0, 1.0)
    ground = float(synthetic.height_m(0.0, 0.0))
    expected = np.empty(360)
    for j, a in enumerate(az):
        # at the pole, azimuth a looks along longitude a (see the convention test above)
        x, y = lonlat_to_xy(a, -90.0 + np.degrees(s / radius), radius, -1)
        truth = synthetic.height_m(x, y)
        expected[j] = exact_elevation_deg(radius + ground + h, radius + truth, s / radius).max()

    cone = (az > 60.0) & (az < 120.0)  # the cone tip is a kink that a 100 m grid cannot hold
    assert np.abs(res.elevation_deg[0][~cone] - expected[~cone]).max() <= TOL_FIXTURE_DEG
    # orientation: the cone is towards 90 deg east and nowhere else
    assert abs(int(np.argmax(res.elevation_deg[0])) - 90) <= 1
    assert res.elevation_deg[0, 90] > res.elevation_deg[0, 270] + 3.0
    # the gridded cone is lower than the analytic one, never higher, and not by much
    assert -0.5 <= res.elevation_deg[0, 90] - expected[90] <= TOL_FIXTURE_DEG


# -- completeness on gridded terrain: nothing along a ray may be missed -------------------
#
# Added after the first runs on LOLA data showed that sparse sampling of far terrain can
# step over narrow crests. The threshold below was written before the new search was
# implemented and measured.
#
# The reference is an exhaustive walk along the ray on the finest data in 1 m steps with
# the unrearranged triangle formula. Both the core and the reference can only find
# elevations that exist on the surface, so "core >= reference - tolerance" means the core
# missed nothing the reference found.
#
# Change of the test logic (not of the threshold), 14 November: the first version also
# demanded |core - reference| <= tolerance for obstacles farther than 1 km, assuming that
# a 1 m step resolves the surface well below the tolerance there. That assumption is
# false where the surface has sharp peaks between the reference's steps: the core then
# reported HIGHER elevations than the reference (by 0.0022 deg on LOLA data, by 0.011 deg
# on the spiked raster below). A higher value is only acceptable if it is real, so the
# two-sided comparison was replaced by an independent check that the point the core
# reports exists on the surface and has the elevation the core states.
TOL_COMPLETENESS_DEG = 0.002
TOL_REPORTED_POINT_DEG = 1e-5  # reported obstacle, recomputed independently from the data


def _reference_profile(reader, radius, lat, lon, azimuth_deg, observer_m, max_range_m):
    s = np.arange(20.0, max_range_m, 1.0)
    g = s / radius
    if abs(lat) == 90.0:
        plat, plon = -90.0 + np.degrees(g), np.full_like(g, lon + azimuth_deg)
    else:
        plat, plon = gc_point(lat, lon, azimuth_deg, g)
    h = reader.height_m(plon, plat)
    ground = float(reader.height_m(lon, lat))
    e = exact_elevation_deg(radius + ground + observer_m, radius + h, g)
    k = int(np.nanargmax(e))
    return float(e[k]), float(s[k])


def _assert_complete(terrain, reader, lat, lon, max_range_m, azimuths, heights=(0.0, 2.0, 20.0)):
    res = compute_horizon(terrain, lat, lon, list(heights), azimuth_step_deg=0.25, max_range_m=max_range_m)
    for i, m in enumerate(heights):
        for az in azimuths:
            j = int(round(az / 0.25))
            ref_e, ref_s = _reference_profile(reader, terrain.reference_radius_m, lat, lon, az, m, max_range_m)
            assert res.elevation_deg[i, j] >= ref_e - TOL_COMPLETENESS_DEG, (lat, lon, az, m)
            # the reported obstacle is a real point of the surface with the stated elevation
            radius = terrain.reference_radius_m
            g = res.distance_m[i, j] / radius
            if abs(lat) == 90.0:
                plat, plon = -90.0 + math.degrees(g), lon + az
            else:
                plat, plon = gc_point(lat, lon, az, g)
            ground = float(reader.height_m(lon, lat))
            there = float(reader.height_m(plon, plat))
            recomputed = float(exact_elevation_deg(radius + ground + m, radius + there, g))
            assert abs(recomputed - res.elevation_deg[i, j]) <= TOL_REPORTED_POINT_DEG, (lat, lon, az, m)
            assert abs(there - res.obstacle_height_m[i, j]) <= 1e-3
    return res


@pytest.fixture(scope="module")
def rough_raster(tmp_path_factory):
    """A rough synthetic raster in the format of the LOLA polar products, with overviews:
    20 m pixels, 4096 x 4096, relief with sharp single-pixel spikes. Not lunar data."""
    lsn_data = pytest.importorskip("lsn_data")
    from lsn_data import pyramid, synthetic
    from lsn_data.dem import PolarDEM, Terrain

    out = tmp_path_factory.mktemp("rough")
    n, pixel = 4096, 20.0
    half = n * pixel / 2
    c = (np.arange(n) + 0.5) * pixel
    x, y = -half + c[None, :], half - c[:, None]
    h = (
        900.0 * np.sin(x / 5200.0) * np.cos(y / 4100.0)
        + 250.0 * np.sin(x / 700.0 + y / 450.0)
        + 60.0 * np.sin(x / 90.0) * np.sin(y / 70.0)
    )
    rng = np.random.default_rng(20261114)
    spikes = rng.integers(0, n, size=(4000, 2))
    h[spikes[:, 0], spikes[:, 1]] += rng.uniform(40.0, 200.0, size=4000)  # single-pixel peaks
    dn = np.rint(h / synthetic.SCALE).astype("<i2")
    (out / "rough_s90_20m.dat").write_bytes(dn.tobytes())
    (out / "rough_s90_20m.lbl").write_bytes(synthetic.label_text(dn, n, pixel, "ROUGH_S90_20M").encode("ascii"))
    base = PolarDEM(out / "rough_s90_20m.lbl")
    pyramid.build(base, out / "pyr", levels=6, log=lambda *a: None)
    return Terrain([PolarDEM(out / "rough_s90_20m.lbl", pyramid_dir=out / "pyr")])


@pytest.mark.parametrize("lat, lon", [(-90.0, 0.0), (-89.7, 40.0), (-89.4, -110.0)])
def test_nothing_is_missed_on_a_rough_gridded_surface(rough_raster, lat, lon):
    from lsncore.dem import LolaTerrain

    terrain = LolaTerrain(rough_raster)
    _assert_complete(terrain, rough_raster, lat, lon, 20_000.0, azimuths=np.arange(0.0, 360.0, 22.5))


def test_nothing_is_missed_on_lola_data():
    """The same check on the LOLA products, when they are present on this machine."""
    lsn_data = pytest.importorskip("lsn_data")
    from lsncore.dem import LolaTerrain

    try:
        reader = lsn_data.open_terrain()
    except FileNotFoundError:
        pytest.skip("LOLA products are not on this machine")
    terrain = LolaTerrain(reader)
    for lat, lon in [(-89.5, 137.0), (-85.3, 31.2), (-88.8, -68.5)]:  # arbitrary test points
        t0 = time.perf_counter()
        _assert_complete(terrain, reader, lat, lon, 300_000.0, azimuths=np.arange(0.0, 360.0, 30.0), heights=(2.0,))
    # runtime of the full default request on real data
    elapsed = _best_of_three(lambda: compute_horizon(terrain, -89.5, 137.0, [0.0, 1.0, 2.0, 5.0, 10.0, 20.0]))
    assert elapsed <= MAX_RUNTIME_S, f"{elapsed:.2f} s"


def test_site_far_from_the_pole_on_lola_data():
    """Rays that leave the 20 m product and run on over the 60 m product. Added after a
    measurement run failed there with larger pruning cells: points beyond the corner of
    the finer raster asked it for a neighbourhood it could not bound."""
    lsn_data = pytest.importorskip("lsn_data")
    from lsncore.dem import LolaTerrain

    try:
        reader = lsn_data.open_terrain()
    except FileNotFoundError:
        pytest.skip("LOLA products are not on this machine")
    terrain = LolaTerrain(reader)
    res = _assert_complete(terrain, reader, -82.0, -45.0, 300_000.0, azimuths=np.arange(0.0, 360.0, 45.0), heights=(2.0,))
    assert np.isfinite(res.elevation_deg).all() and res.coverage_complete
