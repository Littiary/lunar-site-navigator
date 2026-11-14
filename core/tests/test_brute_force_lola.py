"""Independent recomputation straight from the elevation data, on LOLA terrain.

Nothing of the horizon core is used for the expected values: rays are walked on the
finest data with the classic great-circle formulas and the unrearranged triangle formula,
with no stored profile and no obstacle grouping. The Sun's direction comes from the
ephemeris modules, which are validated separately.

These tests need the LOLA products, the site records of the data stream and the SPICE
kernels; they are skipped where any of them is missing.

Thresholds were fixed before the first run (CONTRIBUTING.md, rule 5).
"""

import json
import math
from pathlib import Path

import numpy as np
import pytest

from lsncore.contract import contract_header, read_package
from lsncore.horizon import compute_horizon
from lsncore.uncertainty import ellipse_points, visibility_window

# --------------------------------------------------------------------------------------
# THRESHOLDS (fixed before measuring)
# --------------------------------------------------------------------------------------
TOL_BELOW_DEG = 0.002     # the core may not be lower than the brute force on the same ray by more
TOL_ABOVE_DEG = 0.02      # nor higher by more (the brute force walks 0.1 m steps near the observer)
TOL_DISTANCE_REL = 0.10   # distance of the limiting terrain point: 10 % ...
TOL_DISTANCE_M = 50.0     # ... or 50 m, whichever is larger
TOL_LIMIT_AZIMUTH_DEG = 0.25  # limiting azimuth under the Sun: one step of the stored profile
TOL_TIE_DEG = 0.05        # two candidates count as equally limiting within this
TOL_VISIBLE_HOURS = 2.0   # Sun-visible time: hourly brute-force count against the core's windows
# --------------------------------------------------------------------------------------

REPO = Path(__file__).resolve().parents[2]
START, END = "2026-11-14T00:00:00.000Z", "2026-12-14T00:00:00.000Z"
OBSERVER_M = 2.0
RANGE_M = np.concatenate(
    [np.arange(20.0, 200.0, 0.1), np.arange(200.0, 2000.0, 0.5), np.arange(2000.0, 20000.0, 5.0), np.arange(20000.0, 300000.0 + 1.0, 20.0)]
)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    lsn_data = pytest.importorskip("lsn_data")
    pytest.importorskip("lsncore.events.finder")
    from lsncore.dem import LolaTerrain
    from lsncore.ephem import directions as d
    from lsncore.ephem import table as ephem_table

    records = REPO / "data" / "sites" / "sites.json"
    if not records.exists():
        pytest.skip("site records of the data stream not found")
    try:
        reader = lsn_data.open_terrain()
        table_dir = ephem_table.write_direction_table(tmp_path_factory.mktemp("table"), START, END)
    except FileNotFoundError as missing:
        pytest.skip(f"LOLA products or kernels are not on this machine: {missing}")
    sites = {s["site_id"]: s for s in json.loads(records.read_text(encoding="utf-8"))["sites"]}
    et = float(d.utc_to_et(START)) + 3600.0 * np.arange(721)
    return {"reader": reader, "terrain": LolaTerrain(reader), "table": ephem_table.load_table(table_dir), "sites": sites, "et": et}


def great_circle(lat1, lon1, azimuth_deg, gamma):
    p1, l1, az = math.radians(lat1), math.radians(lon1), np.radians(azimuth_deg)
    lat2 = np.arcsin(np.sin(p1) * np.cos(gamma) + np.cos(p1) * np.sin(gamma) * np.cos(az))
    lon2 = l1 + np.arctan2(np.sin(az) * np.sin(gamma) * np.cos(p1), np.cos(gamma) - np.sin(p1) * np.sin(lat2))
    return np.degrees(lat2), np.degrees(lon2)


def brute_rays(reader, radius, lat, lon, azimuths_deg, observer_m):
    """Elevation profile along each ray, straight from the data: [rays, len(RANGE_M)] in degrees."""
    g = RANGE_M / radius
    r_o = radius + float(reader.height_m(lon, lat)) + observer_m
    rows = []
    azimuths = np.atleast_1d(np.asarray(azimuths_deg, dtype=np.float64))
    for start in range(0, azimuths.size, 120):
        plat, plon = great_circle(lat, lon, azimuths[start:start + 120, None], g[None, :])
        h = reader.height_m(plon, plat)
        rows.append(np.degrees(np.arctan2((radius + h) * np.cos(g) - r_o, (radius + h) * np.sin(g))))
    return np.concatenate(rows)


def close_enough(distance_m, reference_m):
    return abs(distance_m - reference_m) <= max(TOL_DISTANCE_M, TOL_DISTANCE_REL * reference_m)


def test_limiting_terrain_point_of_the_sun_against_brute_force(world, tmp_path):
    """For one site and 24 instants: which terrain point limits the Sun, recomputed from the
    data without the stored profile and without the obstacle grouping."""
    from lsncore.pipeline import run_scenario

    record = world["sites"]["shackleton_rim_crest"]
    lon = (record["lon_deg_east"] + 180.0) % 360.0 - 180.0
    scenario = {
        "contract": contract_header(),
        "kind": "scenario",
        "scenario_id": "brute-force-check",
        "title": "Brute-force check",
        "synthetic": False,
        "sites": [{"site_id": "shackleton-rim-crest", "name": record["name"], "lat_deg": record["lat_deg"], "lon_deg": lon}],
        "observer_heights_m": [OBSERVER_M],
        "default_height_m": OBSERVER_M,
        "horizon": {"azimuth_step_deg": 0.25, "max_range_m": 300000.0},
        "time_window": {"start_utc": START, "end_utc": END, "step_s": 3600.0},
        "bodies": ["SUN"],
        "data": {"dem_set_id": "any", "kernel_set_id": None},
    }
    paths = run_scenario(scenario, tmp_path, world["terrain"])
    pkg = read_package(next(p for p in paths if p.name.startswith("site-")))
    m = pkg.manifest
    lat, lon = m["site"]["lat_deg"], m["site"]["lon_deg"]
    radius = m["site"]["reference_radius_m"]["value"]
    hz, series = m["horizon"], m["timeline"]["series"]["SUN"]
    elevation = pkg.array(hz["elevation_deg"])[0]
    distance = pkg.array(hz["distance_m"])[0]
    sun_az, sun_el, sun_r = (pkg.array(series[k]) for k in ("azimuth_deg", "elevation_deg", "angular_radius_deg"))
    fraction = pkg.array(series["visible_fraction"])[0]
    blocker = pkg.array(series["blocker_azimuth_index"])[0]
    reader = world["reader"]

    hidden_seen = visible_seen = 0
    for i in range(0, 720, 30):
        az0, el0, r = float(sun_az[i]), float(sun_el[i]), float(sun_r[i])
        az_p = float(blocker[i]) * 0.25
        half = r / math.cos(math.radians(el0))
        under_disc = az0 + np.arange(-math.floor(half / 0.01), math.floor(half / 0.01) + 1) * 0.01
        profiles = brute_rays(reader, radius, lat, lon, np.append(under_disc, az_p), OBSERVER_M)
        best = np.argmax(profiles, axis=1)
        e_ray = profiles[np.arange(profiles.shape[0]), best]
        d_ray = RANGE_M[best]

        # 1. on the ray the package names: same horizon elevation, same limiting terrain point
        e_core, d_core = float(elevation[blocker[i]]), float(distance[blocker[i]])
        assert -TOL_BELOW_DEG <= e_core - e_ray[-1] <= TOL_ABOVE_DEG, (i, e_core, e_ray[-1])
        rivals = RANGE_M[profiles[-1] >= e_ray[-1] - TOL_TIE_DEG]  # terrain reaching the same elevation within the tie tolerance
        assert any(close_enough(d_core, float(x)) for x in rivals), (i, d_core, d_ray[-1])

        # 2. under the disc: the brute-force limiting azimuth (upper edge of the disc highest above the horizon)
        x = (under_disc - az0) * math.cos(math.radians(el0))
        gap = el0 + np.sqrt(np.maximum(r * r - x * x, 0.0)) - e_ray[:-1]
        k = int(np.argmax(gap))
        offset = (az_p - az0 + 180.0) % 360.0 - 180.0
        gap_at_package = el0 + math.sqrt(max(r * r - (offset * math.cos(math.radians(el0))) ** 2, 0.0)) - e_ray[-1]
        same_azimuth = abs((az_p - under_disc[k] + 180.0) % 360.0 - 180.0) <= TOL_LIMIT_AZIMUTH_DEG
        assert same_azimuth or gap_at_package >= gap[k] - TOL_TIE_DEG, (i, az_p, under_disc[k], gap_at_package, gap[k])

        # 3. hidden or not: the same answer, unless the limb is within the tie tolerance of the horizon
        if abs(gap[k]) > TOL_TIE_DEG:
            assert (gap[k] > 0.0) == (fraction[i] > 0.0), (i, gap[k], fraction[i])
            hidden_seen += gap[k] <= 0.0
            visible_seen += gap[k] > 0.0
    assert hidden_seen >= 1 and visible_seen >= 1  # the instants cover both cases


@pytest.mark.parametrize("point_index", [0, 8])
def test_extreme_points_of_the_de_gerlache_ellipse_against_brute_force(world, point_index):
    """The landing-ellipse survey around the de Gerlache record found a point with the Sun
    for the whole window (the record itself, index 0) and one with no Sun at all (index 8),
    82 m apart. Both are recomputed from the data: full horizon and Sun-visible hours."""
    from lsncore.ephem import directions as d
    from lsncore.events import finder

    record = world["sites"]["de_gerlache_rim_crest"]
    lat0, lon0 = round(record["lat_deg"], 7), round((record["lon_deg_east"] + 180.0) % 360.0 - 180.0, 7)
    reader, terrain = world["reader"], world["terrain"]
    radius = terrain.reference_radius_m
    points = ellipse_points(lat0, lon0, 100.0, 100.0, 0.0, 13, radius + float(reader.height_m(lon0, lat0)))
    lat, lon = float(points[point_index, 0]), float(points[point_index, 1])

    azimuths = np.arange(0.0, 360.0, 0.25)
    profiles = brute_rays(reader, radius, lat, lon, azimuths, OBSERVER_M)
    brute = profiles.max(axis=1)
    core = compute_horizon(terrain, lat, lon, [OBSERVER_M])
    difference = core.elevation_deg[0] - brute
    assert difference.min() >= -TOL_BELOW_DEG and difference.max() <= TOL_ABOVE_DEG, (difference.min(), difference.max())

    et = world["et"]
    direction = finder.site_direction(d.Site(lon, lat, core.surface_height_m / 1000.0), world["table"], "SUN")
    az, el, r = direction(et)
    visible = 0
    for a, e, rad in zip(az, el, r):
        half = rad / math.cos(math.radians(e))
        idx = np.arange(int(math.floor((a - half) / 0.25)), int(math.ceil((a + half) / 0.25)) + 1)
        x = (idx * 0.25 - a) * math.cos(math.radians(e))
        inside = np.abs(x) <= rad
        if not inside.any():
            idx, x, inside = np.array([int(round(a / 0.25))]), np.array([0.0]), np.array([True])
        gap = np.where(inside, e + np.sqrt(np.maximum(rad * rad - x * x, 0.0)) - brute[idx % 1440], -np.inf)
        visible += gap.max() > 0.0
    rule = finder.threshold_from_contract({"quantity": "visible_fraction", "op": ">", "value": 0.0})
    window = visibility_window(direction, core.elevation_deg[0], 0.25, (float(et[0]), float(et[-1])), rule)
    assert abs(window.total_s() / 3600.0 - (visible - 1)) <= TOL_VISIBLE_HOURS, (window.total_s() / 3600.0, visible)
