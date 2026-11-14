"""Acceptance tests of "show the obstacle": which terrain feature limits the view of a
body, and how much visible time it costs compared with a smooth sphere.

Thresholds were fixed before the implementation existed (CONTRIBUTING.md, rule 5).
"""

import math

import numpy as np
import pytest

from lsncore.blocking import attribute_time, blocker_azimuth_index, blocking_report
from lsncore.dem import AnalyticTerrain
from lsncore.horizon import compute_horizon
from lsncore.obstacles import segment_obstacles
from lsncore.results import HorizonResult
from lsncore.timeline import IntervalSet, TimeGrid

# --------------------------------------------------------------------------------------
# THRESHOLDS (fixed before measuring)
# --------------------------------------------------------------------------------------
TOL_ATTRIBUTION_SUM_S = 1e-6   # time given to obstacles must add up to the lost time
TOL_LOST_TIME_S = 5.0          # lost time against the closed-form value (analytic case)
TOL_PEAK_DISTANCE = 0.02       # relative error of the distance of an obstacle's peak
# --------------------------------------------------------------------------------------

R = 1_737_400.0


def central_angle(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin((np.radians(lon2) - np.radians(lon1)) / 2) ** 2
    return 2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def gc_point(lat1, lon1, azimuth_deg, gamma):
    p1, l1, az = math.radians(lat1), math.radians(lon1), math.radians(azimuth_deg)
    lat2 = math.asin(math.sin(p1) * math.cos(gamma) + math.cos(p1) * math.sin(gamma) * math.cos(az))
    lon2 = l1 + math.atan2(math.sin(az) * math.sin(gamma) * math.cos(p1), math.cos(gamma) - math.sin(p1) * math.sin(lat2))
    return math.degrees(lat2), math.degrees(lon2)


def hill_terrain(lat, lon, bearing, dist_m, peak_m=3000.0, sigma_m=3000.0):
    hlat, hlon = gc_point(lat, lon, bearing, dist_m / R)

    def height(lo, la):
        s = R * central_angle(hlat, hlon, la, lo)
        return peak_m * np.exp(-0.5 * (s / sigma_m) ** 2)

    return AnalyticTerrain(height, R, max_slope=0.7)


# -- horizon -> obstacles -------------------------------------------------------------------

@pytest.mark.parametrize("bearing", [120.0, 0.0, 359.0])
def test_a_hill_on_a_plain_is_one_obstacle_and_the_plain_is_the_other(bearing):
    lat, lon = -85.0, 30.0
    horizon = compute_horizon(hill_terrain(lat, lon, bearing, 30_000.0), lat, lon, [2.0, 20.0], azimuth_step_deg=1.0, max_range_m=100_000.0)
    omap = segment_obstacles(horizon)
    assert omap.obstacle_id.shape == (2, 360) and omap.obstacle_id.dtype == np.int32
    for h in range(2):
        mine = [o for o in omap.obstacles if o["height_index"] == h]
        assert len(mine) == 2  # also when the hill straddles azimuth 0
        hill = max(mine, key=lambda o: o["peak_elevation_deg"])
        plain = min(mine, key=lambda o: o["peak_elevation_deg"])
        assert hill["peak_azimuth_deg"] == bearing
        # the line of sight touches the hill slightly in front of its summit
        assert 25_000.0 < hill["peak_distance_m"] < 30_000.0
        j = int(round(bearing))
        assert omap.obstacle_id[h, j] == hill["id"]
        assert hill["peak_distance_m"] == pytest.approx(horizon.distance_m[h, j], rel=TOL_PEAK_DISTANCE)
        assert hill["peak_lat_deg"] == pytest.approx(horizon.obstacle_lat_deg[h, j], abs=1e-9)
        assert hill["peak_height_m"] == pytest.approx(horizon.obstacle_height_m[h, j], abs=1e-6)
        # every azimuth belongs to exactly one obstacle, and the index form reproduces the array
        assert hill["azimuth_count"] + plain["azimuth_count"] == 360
        for o in mine:
            idx = (o["azimuth_start_index"] + np.arange(o["azimuth_count"])) % 360
            assert np.all(omap.obstacle_id[h, idx] == o["id"])
            assert o["azimuth_start_deg"] == o["azimuth_start_index"] * 1.0
            assert o["azimuth_end_deg"] == float((o["azimuth_start_index"] + o["azimuth_count"] - 1) % 360)
        # the plain is the observer's own smooth horizon: a few kilometres away
        assert plain["distance_max_m"] < 10_000.0 and not hill["near_field"]
    assert len({o["id"] for o in omap.obstacles}) == len(omap.obstacles)


def test_uniform_horizon_is_a_single_obstacle_and_missing_data_has_none():
    count = 72
    elevation = np.full((1, count), -0.1)
    distance = np.full((1, count), 2600.0)
    elevation[0, 10:13] = np.nan
    distance[0, 10:13] = np.nan
    horizon = HorizonResult(5.0, [2.0], 100_000.0, R, 0.0, elevation, distance)
    omap = segment_obstacles(horizon)
    assert np.all(omap.obstacle_id[0, 10:13] == -1)
    assert len(omap.obstacles) == 1 and omap.obstacles[0]["azimuth_count"] == count - 3
    assert omap.obstacles[0]["azimuth_start_index"] == 13  # the run starts after the gap and wraps


# -- which horizon sample limits a disc -----------------------------------------------------

def test_limiting_azimuth_on_a_sloping_horizon():
    """Hidden disc behind a horizon that falls towards larger azimuth: the first light
    appears where the upper edge of the disc is closest to the horizon, at the offset
    x = -r s / sqrt(1 + s^2) from the centre for a horizon slope s (here s < 0)."""
    step = 0.05
    az_grid = np.arange(int(round(360 / step))) * step
    slope = -0.5  # degrees of elevation per degree of azimuth
    elevation = (5.0 + slope * (az_grid - 100.0))[None, :]
    az0, el0, r = 100.0, 3.0, 0.5
    idx = blocker_azimuth_index(np.array([az0]), np.array([el0]), np.array([r]), elevation, step, "upper_limb")
    x = -r * slope / math.sqrt(1.0 + slope * slope)
    expected_az = az0 + x / math.cos(math.radians(el0))
    assert abs(idx[0, 0] * step - expected_az) <= step
    # centre convention: the terrain straight below (or above) the disc centre
    idx_c = blocker_azimuth_index(np.array([az0 + 0.02]), np.array([el0]), np.array([r]), elevation, step, "center")
    assert idx_c[0, 0] == int(round(az0 / step))
    # wrap-around
    idx_w = blocker_azimuth_index(np.array([359.99]), np.array([el0]), np.array([r]), np.full((1, 7200), 9.0), step, "center")
    assert idx_w[0, 0] == 0


# -- lost time and its attribution ----------------------------------------------------------

def test_lost_time_is_split_between_obstacles_without_loss():
    hour = 3600.0
    grid = TimeGrid(0.0, hour, 101)  # samples at 0, 1, ..., 100 h
    domain = (0.0, 100.0 * hour)
    lost = IntervalSet([(10.2 * hour, 30.7 * hour), (50.0 * hour, 50.4 * hour)], domain)
    blocker = np.where(np.arange(101) <= 20, 7, 9)  # obstacle 7 up to sample 20, then obstacle 9
    shares = attribute_time(grid, lost, blocker)
    assert set(shares) == {7, 9}
    # a sample stands for the half step before and after it
    assert shares[7]["seconds"] == pytest.approx((20.5 - 10.2) * hour, abs=1e-6)
    assert shares[9]["seconds"] == pytest.approx((30.7 - 20.5 + 0.4) * hour, abs=1e-6)
    assert abs(sum(s["seconds"] for s in shares.values()) - lost.total_s()) <= TOL_ATTRIBUTION_SUM_S
    assert shares[7]["intervals"].as_list() == [[10.2 * hour, 20.5 * hour]]
    assert shares[9]["intervals"].as_list() == [[20.5 * hour, 30.7 * hour], [50.0 * hour, 50.4 * hour]]


def _bump_horizon(step, base, amplitude, centre, width, distance_plain=2600.0, distance_bump=30_000.0):
    az = np.arange(int(round(360 / step))) * step
    bump = amplitude * np.exp(-(((az - centre) / width) ** 2))
    elevation = (base + bump)[None, :]
    distance = np.where(bump > 0.02, distance_bump, distance_plain)[None, :]
    lat = np.full_like(elevation, -85.0)
    return HorizonResult(step, [2.0], 300_000.0, R, 0.0, elevation, distance, obstacle_height_m=np.zeros_like(elevation), obstacle_lat_deg=lat, obstacle_lon_deg=lat * 0 + az)


def test_hours_lost_to_a_ridge_against_the_closed_form():
    """A body circles at constant elevation and constant azimuth rate. A smooth ridge in the
    horizon hides its centre for a time that follows from the ridge shape."""
    finder = pytest.importorskip("lsncore.events.finder")
    step, base, amplitude, centre, width = 0.05, -0.0869, 4.0, 115.0, 10.0
    horizon = _bump_horizon(step, base, amplitude, centre, width)
    omap = segment_obstacles(horizon)
    el0, radius, rate = 1.0, 0.27, 0.5 / 3600.0  # deg, deg, deg per second
    hour = 3600.0
    grid = TimeGrid(0.0, 600.0, int(400 * hour / 600.0) + 1)  # 400 h: from azimuth 0 to 200
    domain = (0.0, grid.end_et_s)

    def direction(et):
        et = np.asarray(et, dtype=np.float64)
        return rate * et, np.full(et.shape, el0), np.full(et.shape, radius)

    rule = {"visible": finder.threshold_from_contract({"quantity": "margin_deg", "op": ">", "value": 0.0})}

    def window(profile):
        result = finder.find_events(direction, profile, domain[0], domain[1], thresholds=rule)
        return IntervalSet(finder.windows(result, "visible").intervals_et_s, domain)

    terrain = window(finder.Horizon(0.0, step, horizon.elevation_deg[0], horizon.distance_m[0]))
    smooth = window(finder.Horizon(0.0, step, np.full(horizon.elevation_deg.shape[1], base)))
    az, el, rad = direction(grid.times())
    report = blocking_report(
        body="SUN", height_index=0, grid=grid, azimuth_deg=az, elevation_deg=el, angular_radius_deg=rad,
        horizon=horizon, obstacles=omap, visible_terrain=terrain, visible_smooth=smooth, limb="center",
    )

    half_width = width * math.sqrt(math.log(amplitude / (el0 - base)))  # where the ridge is above the body
    expected_s = 2.0 * half_width / rate
    assert abs(report.lost.total_s() - expected_s) <= TOL_LOST_TIME_S
    assert report.gained.total_s() == 0.0
    # one blocker, the ridge, with all of the lost time
    assert len(report.blockers) == 1
    ridge = report.blockers[0]
    assert ridge["peak_azimuth_deg"] == pytest.approx(centre, abs=step)
    assert ridge["peak_distance_m"] == 30_000.0
    assert ridge["share_of_lost"] == pytest.approx(1.0, abs=1e-9)
    assert abs(ridge["lost_s"] - report.lost.total_s()) <= TOL_ATTRIBUTION_SUM_S
    assert ridge["obstacle_id"] == omap.obstacle_id[0, int(round(centre / step))]
    assert ridge["intervals_et_s"] == report.lost.as_list()
    # per sample: while the body is behind the ridge its blocker index points into the ridge
    behind = np.abs(az - centre) < half_width - 0.5
    assert np.all(omap.obstacle_id[0, report.blocker_azimuth_index[behind]] == ridge["obstacle_id"])


def test_terrain_below_the_smooth_horizon_gains_time():
    """A site that looks down on its surroundings sees a body the smooth sphere would hide."""
    grid = TimeGrid(0.0, 3600.0, 11)
    domain = (0.0, 36000.0)
    horizon = _bump_horizon(1.0, -2.0, 0.0, 0.0, 1.0)
    omap = segment_obstacles(horizon)
    report = blocking_report(
        body="EARTH", height_index=0, grid=grid, azimuth_deg=np.linspace(10, 20, 11), elevation_deg=np.full(11, -1.0),
        angular_radius_deg=np.full(11, 0.95), horizon=horizon, obstacles=omap,
        visible_terrain=IntervalSet.full(domain), visible_smooth=IntervalSet.empty(domain), limb="center",
    )
    assert report.lost.total_s() == 0.0 and report.gained.total_s() == 36000.0
    assert report.blockers == []
