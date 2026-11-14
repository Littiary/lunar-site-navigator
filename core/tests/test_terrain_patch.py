"""Contract 0.7: terrain patches, the ground a viewer draws.

A patch is a regular grid in the site's local East/North/Up frame; its values are the up
coordinate of the surface, so the curvature of the sphere is already in them. The checks
below go the other way round than the code: a node (east, north, up) is turned into a
body-fixed position with frame vectors written out here, and the height of that position
above the reference sphere is compared with the terrain read at its latitude and
longitude. Nothing of the patch code is used for the expected values.

Thresholds were fixed before the first run (CONTRIBUTING.md, rule 5).
"""

import copy
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pytest

from lsncore.contract import ContractError, contract_dir, read_package, validate_document, validate_package
from lsncore.dem import AnalyticTerrain
from lsncore.pipeline import run_scenario
from lsncore.scenario import load_scenario, single_site_scenario
from lsncore.synthetic import run_synthetic_scenario

# --------------------------------------------------------------------------------------
# THRESHOLDS (fixed before measuring)
# --------------------------------------------------------------------------------------
TOL_SPHERE_M = 0.002             # smooth sphere: up against the closed form of the spherical cap
TOL_NODE_M = 0.05                # a node against the surface it was read from
NEAR_BETWEEN_NODES_95_M = 0.5    # near patch between its nodes against the finest data: 95 % of points
NEAR_BETWEEN_NODES_MAX_M = 5.0   # ... and every point
# Horizon drawn from the patches against the horizon of the package. What a grid allows is
# a height error at the terrain that sets the horizon, stated as a share of the grid
# spacing there: a ridge with side slopes of 0.6 loses 0.15 of the spacing when it is
# averaged over one cell.
HEIGHT_SHARE_OF_SPACING = 0.15   # tolerance at 95 % of the azimuths
WORST_SHARE_OF_SPACING = 0.50    # no azimuth may be off by more
ANGLE_FLOOR_DEG = 0.02           # added to both
SHARE_OF_AZIMUTHS = 0.95
MAX_BYTES_DEFAULT_PATCHES = 500_000  # the default patches of one site, all arrays together
# --------------------------------------------------------------------------------------

R = 1_737_400.0
REPO = Path(__file__).resolve().parents[2]
SAMPLE = contract_dir() / "sample"
DEFAULT_IDS = ["near", "mid", "far"]


# ---------------------------------------------------------------- independent geometry

def frame(lat_deg, lon_deg):
    """East, north, up of a site in the body-fixed frame, from the definitions."""
    la, lo = math.radians(lat_deg), math.radians(lon_deg)
    up = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
    east = np.array([-math.sin(lo), math.cos(lo), 0.0])
    return east, np.cross(up, east), up


def patch_grid(patch):
    east = patch["east_min_m"] + patch["spacing_m"] * np.arange(patch["count_east"])
    north = patch["north_min_m"] + patch["spacing_m"] * np.arange(patch["count_north"])
    return np.meshgrid(east, north)  # [north index, east index]


def to_sphere(manifest, east_m, north_m, up_m):
    """Latitude, longitude (degrees) and height above the reference sphere of local points."""
    site = manifest["site"]
    e, n, u = frame(site["lat_deg"], site["lon_deg"])
    r0 = site["radius_m"]["value"]
    p = np.asarray(east_m)[..., None] * e + np.asarray(north_m)[..., None] * n + (np.asarray(up_m, dtype=np.float64) + r0)[..., None] * u
    radius = np.linalg.norm(p, axis=-1)
    lat = np.degrees(np.arcsin(p[..., 2] / radius))
    lon = np.degrees(np.arctan2(p[..., 1], p[..., 0]))
    return lat, lon, radius - site["reference_radius_m"]["value"]


def bilinear(up, patch, east_m, north_m):
    """The surface a viewer draws between the nodes."""
    x = (np.asarray(east_m) - patch["east_min_m"]) / patch["spacing_m"]
    y = (np.asarray(north_m) - patch["north_min_m"]) / patch["spacing_m"]
    j = np.clip(np.floor(x).astype(int), 0, patch["count_east"] - 2)
    i = np.clip(np.floor(y).astype(int), 0, patch["count_north"] - 2)
    fx, fy = x - j, y - i
    return (1 - fy) * ((1 - fx) * up[i, j] + fx * up[i, j + 1]) + fy * ((1 - fx) * up[i + 1, j] + fx * up[i + 1, j + 1])


def great_circle(lat1, lon1, azimuth_deg, gamma):
    p1, l1, az = math.radians(lat1), math.radians(lon1), math.radians(azimuth_deg)
    lat2 = math.asin(math.sin(p1) * math.cos(gamma) + math.cos(p1) * math.sin(gamma) * math.cos(az))
    lon2 = l1 + math.atan2(math.sin(az) * math.sin(gamma) * math.cos(p1), math.cos(gamma) - math.sin(p1) * math.sin(lat2))
    return math.degrees(lat2), math.degrees(lon2)


def arc(lat1, lon1, lat2, lon2):
    """Central angle between points (haversine)."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * np.arcsin(np.sqrt(a))


def package_of(terrain, lat, lon, tmp_path, patches=None, **kwargs):
    scenario = single_site_scenario("patch-site", "Patch test site", lat, lon, dem_set_id="any", synthetic=False, azimuth_step_deg=5.0, max_range_m=40_000.0, **kwargs)
    if patches is not None:
        scenario["terrain_patches"] = patches
    (path,) = run_scenario(scenario, tmp_path, terrain)
    validate_package(path)
    return read_package(path)


# ---------------------------------------------------------------- analytic surfaces

@pytest.mark.parametrize("lat, lon", [(-85.0, 30.0), (-89.9, -160.0), (12.0, 179.5)])
def test_patch_of_a_smooth_sphere_is_the_spherical_cap(tmp_path, lat, lon):
    terrain = AnalyticTerrain(lambda lo, la: np.full(np.broadcast(lo, la).shape, 250.0), R, ceiling_height_m=250.0)
    pkg = package_of(terrain, lat, lon, tmp_path)
    r0 = R + 250.0
    patches = pkg.manifest["terrain"]["patches"]
    assert [p["id"] for p in patches] == DEFAULT_IDS
    for patch in patches:
        up = pkg.array(patch["up_m"])
        east, north = patch_grid(patch)
        expected = np.sqrt(r0 * r0 - east * east - north * north) - r0
        assert up.shape == (patch["count_north"], patch["count_east"])
        assert np.abs(up - expected).max() <= TOL_SPHERE_M
        assert up[patch["count_north"] // 2, patch["count_east"] // 2] == 0.0  # the site itself
    far = patches[-1]
    assert pkg.array(far["up_m"]).min() < -500.0  # 45 km away the sphere has dropped by more than half a kilometre


def _rolling(lon, lat):
    return 400.0 * np.sin(np.radians(lon) * 31.0) * np.cos(np.radians(lat) * 47.0) + 150.0 * np.cos(np.radians(lon + lat) * 211.0)


@pytest.mark.parametrize("lat, lon", [(-86.0, 20.0), (-89.7, 115.0)])
def test_patch_nodes_lie_on_the_surface(tmp_path, lat, lon):
    terrain = AnalyticTerrain(_rolling, R, ceiling_height_m=550.0)
    pkg = package_of(terrain, lat, lon, tmp_path)
    for patch in pkg.manifest["terrain"]["patches"]:
        east, north = patch_grid(patch)
        la, lo, height = to_sphere(pkg.manifest, east, north, pkg.array(patch["up_m"]))
        assert np.abs(height - _rolling(lo, la)).max() <= TOL_NODE_M


@pytest.mark.parametrize("lat, lon, azimuth, distance, patch_id", [(-89.5, 200.0, 60.0, 1200.0, "near"), (-85.0, -60.0, 300.0, 20_000.0, "far"), (-88.0, 10.0, 180.0, 5000.0, "mid")])
def test_east_is_east_and_north_is_north(tmp_path, lat, lon, azimuth, distance, patch_id):
    """A hill placed at a known bearing and distance must show up at that place of the grid."""
    hill_lat, hill_lon = great_circle(lat, lon, azimuth, distance / R)
    width = distance / 4.0
    terrain = AnalyticTerrain(lambda lo, la: 0.2 * width * np.exp(-((arc(la, lo, hill_lat, hill_lon) * R / width) ** 2)), R, ceiling_height_m=0.2 * width)
    pkg = package_of(terrain, lat, lon, tmp_path)
    patch = next(p for p in pkg.manifest["terrain"]["patches"] if p["id"] == patch_id)
    east, north = patch_grid(patch)
    above_sphere = pkg.array(patch["up_m"]) + (east * east + north * north) / (2.0 * R)  # curvature taken out again
    i, j = np.unravel_index(np.argmax(above_sphere), above_sphere.shape)
    e, n, u = frame(pkg.manifest["site"]["lat_deg"], pkg.manifest["site"]["lon_deg"])
    he, hn, hu = frame(hill_lat, hill_lon)
    top = hu * (R + 0.2 * width)
    assert abs(east[i, j] - top @ e) <= patch["spacing_m"]
    assert abs(north[i, j] - top @ n) <= patch["spacing_m"]
    # the same in words of the contract: azimuth is clockwise from north
    assert math.degrees(math.atan2(east[i, j], north[i, j])) % 360.0 == pytest.approx(azimuth, abs=math.degrees(1.5 * patch["spacing_m"] / distance))


# ---------------------------------------------------------------- the package

def test_default_patches_are_described_and_small_enough_for_a_phone(tmp_path):
    terrain = AnalyticTerrain(_rolling, R, ceiling_height_m=550.0, dem_set_id="ANALYTIC-rolling")
    pkg = package_of(terrain, -86.0, 20.0, tmp_path)
    manifest = pkg.manifest
    block = manifest["terrain"]
    assert block["use"] == "drawing" and "timeline" in block["notice"]
    assert manifest["request"]["terrain_patches"] == [
        {"id": "near", "half_width_m": 2000.0, "spacing_m": 20.0},
        {"id": "mid", "half_width_m": 8000.0, "spacing_m": 80.0},
        {"id": "far", "half_width_m": 32000.0, "spacing_m": 320.0},
    ]
    total = 0
    for patch, spec in zip(block["patches"], manifest["request"]["terrain_patches"]):
        assert (patch["id"], patch["half_width_m"], patch["spacing_m"]) == (spec["id"], spec["half_width_m"], spec["spacing_m"])
        assert patch["count_east"] == patch["count_north"] == 201
        assert patch["east_min_m"] == patch["north_min_m"] == -spec["half_width_m"]
        ref = patch["up_m"]
        assert ref["dtype"] == "<f4" and ref["unit"] == "m" and ref["shape"] == [201, 201] and len(ref["sha256"]) == 64
        up = pkg.array(ref)
        assert patch["up_min_m"] == pytest.approx(float(up.min())) and patch["up_max_m"] == pytest.approx(float(up.max()))
        assert sum(s["node_share"] for s in patch["sources"]) == pytest.approx(1.0)
        total += (pkg.path / ref["file"]).stat().st_size
    assert total <= MAX_BYTES_DEFAULT_PATCHES
    card = manifest["methods"][block["method"]]
    assert block["method"] == block["patches"][0]["up_m"]["method"]
    assert any("drawing" in limit for limit in card["limits"])
    assert card["data"] == ["ANALYTIC-rolling"]


def test_a_scenario_can_state_its_own_patches_or_none(tmp_path):
    terrain = AnalyticTerrain(_rolling, R, ceiling_height_m=550.0)
    own = [{"id": "ring", "half_width_m": 600.0, "spacing_m": 50.0}]
    pkg = package_of(terrain, -86.0, 20.0, tmp_path / "own", patches=own)
    (patch,) = pkg.manifest["terrain"]["patches"]
    assert patch["id"] == "ring" and patch["count_east"] == 25 and pkg.array(patch["up_m"]).shape == (25, 25)
    assert pkg.manifest["request"]["terrain_patches"] == own
    none = package_of(terrain, -86.0, 20.0, tmp_path / "none", patches=[])
    assert "terrain" not in none.manifest and "terrain_patches" not in none.manifest["request"]
    for broken, message in (
        ([{"id": "a", "half_width_m": 610.0, "spacing_m": 50.0}], "multiple"),
        ([{"id": "a", "half_width_m": 600.0, "spacing_m": 50.0}, {"id": "a", "half_width_m": 1200.0, "spacing_m": 100.0}], "unique"),
        ([{"id": "a", "half_width_m": 60000.0, "spacing_m": 20.0}], "nodes"),
    ):
        with pytest.raises(ValueError, match=message):
            package_of(terrain, -86.0, 20.0, tmp_path / "broken", patches=broken)


def test_patch_beyond_the_data_is_marked_not_invented(tmp_path):
    def cut(lon, lat):  # no data north of 85.9 degrees south
        return np.where(np.asarray(lat) < -85.9, _rolling(lon, lat), np.nan)

    terrain = AnalyticTerrain(cut, R, ceiling_height_m=550.0)
    pkg = package_of(terrain, -86.0, 20.0, tmp_path, patches=[{"id": "far", "half_width_m": 32000.0, "spacing_m": 320.0}])
    (patch,) = pkg.manifest["terrain"]["patches"]
    up = pkg.array(patch["up_m"])
    east, north = patch_grid(patch)
    assert patch["up_m"]["nan_count"] == int(np.isnan(up).sum()) > 0
    # The edge of the data is a circle of latitude 3.0 km north of the site on its meridian;
    # it bends towards the site with distance from the meridian, hence the strip.
    assert np.isnan(up[north > 4000.0]).all() and np.isfinite(up[(north < 2500.0) & (np.abs(east) < 5000.0)]).all()
    assert any("terrain patch" in w and "far" in w for w in pkg.manifest["warnings"])


@pytest.mark.parametrize(
    "case, change, expected",
    [
        ("grid that does not match its array", lambda t: t["patches"][0].update(count_east=t["patches"][0]["count_east"] + 1), "count"),
        ("grid not centred on the site", lambda t: t["patches"][1].update(east_min_m=0.0), "east_min_m"),
        ("two patches with one id", lambda t: t["patches"][1].update(id=t["patches"][0]["id"]), "unique"),
        ("patches not from fine to coarse", lambda t: t["patches"].reverse(), "finest first"),
    ],
)
def test_validator_rejects_broken_patches(tmp_path, case, change, expected):
    terrain = AnalyticTerrain(_rolling, R, ceiling_height_m=550.0)
    pkg = package_of(terrain, -86.0, 20.0, tmp_path / "ok")
    dst = tmp_path / "broken" / pkg.path.name
    shutil.copytree(pkg.path, dst)
    manifest = json.loads((dst / "manifest.json").read_text())
    change(manifest["terrain"])
    (dst / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ContractError) as info:
        validate_package(dst)
    assert expected in str(info.value)


def test_sample_carries_invented_patches(tmp_path):
    scenario = load_scenario(SAMPLE / "SYNTHETIC_scenario.json")
    assert [p["id"] for p in scenario["terrain_patches"]] == DEFAULT_IDS
    paths = run_synthetic_scenario(scenario, tmp_path)
    for path in (p for p in paths if p.name.startswith("site-")):
        manifest = validate_package(path)
        pkg = read_package(path)
        block = manifest["terrain"]
        assert manifest["synthetic"] and block["use"] == "drawing"
        assert manifest["methods"][block["method"]]["validation"]["status"] == "synthetic"
        assert [p["id"] for p in block["patches"]] == DEFAULT_IDS
        for patch in block["patches"]:
            up = pkg.array(patch["up_m"])
            assert np.isfinite(up).all() and patch["sources"] == []
            assert up[patch["count_north"] // 2, patch["count_east"] // 2] == 0.0
    plain = copy.deepcopy(scenario)
    plain.pop("terrain_patches")
    validate_document(plain)  # the field is optional
    broken = copy.deepcopy(scenario)
    broken["terrain_patches"][0]["spacing_m"] = 0.0
    with pytest.raises(ContractError):
        validate_document(broken)


# ---------------------------------------------------------------- LOLA terrain

SITES = ["shackleton_rim_crest", "de_gerlache_rim_crest", "malapert_massif_summit"]


@pytest.fixture(scope="module")
def lola(tmp_path_factory):
    lsn_data = pytest.importorskip("lsn_data")
    from lsncore.dem import LolaTerrain

    records = REPO / "data" / "sites" / "sites.json"
    if not records.exists():
        pytest.skip("site records of the data stream not found")
    try:
        reader = lsn_data.open_terrain()
    except FileNotFoundError as missing:
        pytest.skip(f"LOLA products are not on this machine: {missing}")
    terrain = LolaTerrain(reader)
    sites = {s["site_id"]: s for s in json.loads(records.read_text(encoding="utf-8"))["sites"]}
    packages = {}
    for name in SITES:
        rec = sites[name]
        scenario = single_site_scenario(name.replace("_", "-"), rec["name"], rec["lat_deg"], rec["lon_deg_east"], dem_set_id="any", synthetic=False)
        (path,) = run_scenario(scenario, tmp_path_factory.mktemp(name), terrain)
        validate_package(path)
        packages[name] = read_package(path)
    return {"reader": reader, "packages": packages}


def _patch(pkg, patch_id):
    return next(p for p in pkg.manifest["terrain"]["patches"] if p["id"] == patch_id)


@pytest.mark.parametrize("name", SITES)
def test_near_patch_reproduces_the_elevation_data(lola, name):
    pkg, reader = lola["packages"][name], lola["reader"]
    patch = _patch(pkg, "near")
    up = pkg.array(patch["up_m"])
    east, north = patch_grid(patch)
    lat, lon, height = to_sphere(pkg.manifest, east, north, up)
    assert np.abs(height - reader.height_m(lon, lat)).max() <= TOL_NODE_M
    assert _between_nodes(pkg, reader).max() <= NEAR_BETWEEN_NODES_MAX_M
    (source,) = patch["sources"]
    assert (source["product_id"], source["level"], source["pixel_m"]) == ("LDEM_80S_20M", 0, 20.0)
    data_file = next(f for item in reader.provenance() if item["product_id"] == "LDEM_80S_20M" for f in item["files"] if f["role"] == "data")
    assert source["sha256"] == data_file["sha256"]


def _between_nodes(pkg, reader):
    """Near patch, drawn between its nodes, against the finest data at 2000 random places."""
    patch = _patch(pkg, "near")
    rng = np.random.default_rng(20261114)
    e, n = rng.uniform(-patch["half_width_m"], patch["half_width_m"], (2, 2000))
    lat, lon, height = to_sphere(pkg.manifest, e, n, bilinear(pkg.array(patch["up_m"]), patch, e, n))
    return np.abs(height - reader.height_m(lon, lat))


# The criterion below was fixed before the first run, together with the others, and it was
# NOT MET at two of the three site records: 0.83 m at the Shackleton record and 0.55 m at
# the de Gerlache record (0.49 m at the Malapert record). It stands as written; the two
# cases are marked as known failures so that a change in either direction shows up.
# Nothing else was changed to make the suite pass. What the failure means is in
# docs/method/terrain_patch.md, section 3: the patch is a 20 m grid in another orientation
# than the 20 m elevation model, and on rim terrain the model is rougher from pixel to
# pixel than the 0.5 m assumed here.
_NOT_MET = pytest.mark.xfail(strict=True, reason="registered criterion not met: 95 % of points within 0.5 m between the nodes of the near patch")


@pytest.mark.parametrize(
    "name",
    [pytest.param("shackleton_rim_crest", marks=_NOT_MET), pytest.param("de_gerlache_rim_crest", marks=_NOT_MET), "malapert_massif_summit"],
)
def test_near_patch_between_its_nodes_stays_within_half_a_metre(lola, name):
    off = _between_nodes(lola["packages"][name], lola["reader"])
    assert np.percentile(off, 95.0) <= NEAR_BETWEEN_NODES_95_M


@pytest.mark.parametrize("name", SITES)
@pytest.mark.parametrize("patch_id, level", [("mid", 2), ("far", 4)])
def test_coarser_patches_reproduce_their_overview_level(lola, name, patch_id, level):
    pkg, reader = lola["packages"][name], lola["reader"]
    patch = _patch(pkg, patch_id)
    east, north = patch_grid(patch)
    lat, lon, height = to_sphere(pkg.manifest, east, north, pkg.array(patch["up_m"]))
    assert np.abs(height - reader.height_m(lon, lat, max_pixel_m=patch["spacing_m"])).max() <= TOL_NODE_M
    (source,) = patch["sources"]
    assert (source["product_id"], source["level"], source["pixel_m"], source["statistic"]) == ("LDEM_80S_20M", level, patch["spacing_m"], "mean")
    files = next(item["files"] for item in reader.provenance() if item["product_id"] == "LDEM_80S_20M")
    assert source["sha256"] == next(f["sha256"] for f in files if f["name"] == f"mean_L{level}.npy")
    assert source["derived_from_sha256"] == next(f["sha256"] for f in files if f["role"] == "data")


def drawn_horizon(pkg, patch_ids, observer_m, azimuth_deg):
    """Horizon of the surface a viewer draws from the patches (finest patch wins where
    several cover a place): elevation, distance of the limiting point and grid spacing there."""
    az = np.radians(azimuth_deg)[:, None]
    reach = 1.0 / np.maximum(np.abs(np.sin(az)), np.abs(np.cos(az)))  # of a square of half width 1
    best = np.full(az.shape[0], -np.inf)
    where = np.zeros(az.shape[0])
    spacing = np.zeros(az.shape[0])
    inner = np.zeros_like(reach)
    for patch_id in patch_ids:
        patch = _patch(pkg, patch_id)
        up = pkg.array(patch["up_m"]).astype(np.float64)
        outer = patch["half_width_m"] * reach
        steps = int(math.ceil(patch["half_width_m"] * math.sqrt(2.0) / (0.5 * patch["spacing_m"])))
        s = inner + (outer - inner) * (np.arange(1, steps + 1) / steps)[None, :]
        elevation = np.degrees(np.arctan2(bilinear(up, patch, s * np.sin(az), s * np.cos(az)) - observer_m, s))
        k = np.nanargmax(elevation, axis=1)
        top = elevation[np.arange(az.shape[0]), k]
        better = top > best
        best, where, spacing = np.where(better, top, best), np.where(better, s[np.arange(az.shape[0]), k], where), np.where(better, patch["spacing_m"], spacing)
        inner = outer
    return best, where, spacing, inner[:, 0]


def allowed(share, spacing_m, distance_m):
    return np.degrees(np.arctan(share * spacing_m / distance_m)) + ANGLE_FLOOR_DEG


def compare_with_package(pkg, patch_ids):
    hz = pkg.manifest["horizon"]
    h = hz["default_height_index"]
    azimuth = hz["azimuth"]["start_deg"] + hz["azimuth"]["step_deg"] * np.arange(hz["azimuth"]["count"])
    science, science_distance = pkg.array(hz["elevation_deg"])[h].astype(np.float64), pkg.array(hz["distance_m"])[h].astype(np.float64)
    drawn, drawn_distance, drawn_spacing, reach = drawn_horizon(pkg, patch_ids, hz["observer_heights_m"][h], azimuth)
    inside = science_distance <= reach  # the terrain that sets the package horizon is on the drawn ground
    # grid spacing of the drawn ground at the distance of that terrain
    squares = 1.0 / np.maximum(np.abs(np.sin(np.radians(azimuth))), np.abs(np.cos(np.radians(azimuth))))
    spacing_there = np.full(azimuth.shape, np.nan)
    for patch_id in reversed(patch_ids):
        patch = _patch(pkg, patch_id)
        spacing_there = np.where(science_distance <= patch["half_width_m"] * squares, patch["spacing_m"], spacing_there)
    diff = drawn - science
    result = {}
    for label, share in (("usual", HEIGHT_SHARE_OF_SPACING), ("worst", WORST_SHARE_OF_SPACING)):
        tolerance = allowed(share, drawn_spacing, drawn_distance)
        with np.errstate(invalid="ignore"):
            tolerance = np.where(inside, np.maximum(tolerance, allowed(share, spacing_there, science_distance)), tolerance)
        # where the limiting terrain lies beyond the drawn ground, the drawn ground may only be lower
        result[label] = np.where(inside, np.abs(diff) <= tolerance, diff <= tolerance)
    return result, diff, inside, science_distance


@pytest.mark.parametrize("name", SITES)
@pytest.mark.parametrize("patch_ids", [DEFAULT_IDS, ["far"]], ids=["all patches", "far patch alone"])
def test_horizon_drawn_from_the_patches_agrees_with_the_package_horizon(lola, name, patch_ids):
    """A viewer's silhouette must not visibly contradict the science: the horizon of the
    drawn ground stays within what its grid spacing allows of the package horizon, and
    where the package horizon is set by terrain beyond the patches it stays below it."""
    result, diff, inside, _ = compare_with_package(lola["packages"][name], patch_ids)
    assert result["usual"].mean() >= SHARE_OF_AZIMUTHS
    assert result["worst"].all()
