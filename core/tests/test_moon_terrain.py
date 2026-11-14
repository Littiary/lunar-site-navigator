"""Contract 0.9: a site anywhere on the Moon.

Near the poles the polar elevation products serve a site as before. Elsewhere the data
stream's simple-cylindrical products do (LDEM_128 at 237 m, or finer mosaics where they
are installed), and the package says which product and which resolution class served it.

The thresholds are those of the horizon tests (core/tests/test_horizon.py): nothing may be
missed by more than 0.002 degrees against an exhaustive scan in 1 m steps, the reported
obstacle must be a point of the surface to 1e-5 degrees, and one site must finish within
5 s. They were fixed before this file was run for the first time.
"""

import json
import math
from pathlib import Path

import numpy as np
import pytest

from lsncore.contract import read_package, validate_package
from lsncore.geometry import destination
from lsncore.horizon import compute_horizon
from lsncore.pipeline import run_scenario
from lsncore.scenario import single_site_scenario

from test_horizon import MAX_RUNTIME_S, _assert_complete, _best_of_three

# --------------------------------------------------------------------------------------
# THRESHOLDS (fixed before measuring; the first three are the ones of test_horizon.py)
# --------------------------------------------------------------------------------------
TOL_BOUND_M = 1e-6  # a neighbourhood bound may not lie below any sampled point of the neighbourhood
# --------------------------------------------------------------------------------------

REPO = Path(__file__).resolve().parents[2]
R = 1_737_400.0


def _rough(lon, lat):
    lon, lat = np.radians(np.asarray(lon, dtype=np.float64)), np.radians(np.asarray(lat, dtype=np.float64))
    return 1800.0 * np.sin(23.0 * lon) * np.cos(31.0 * lat) + 500.0 * np.sin(140.0 * lon + 90.0 * lat) + 120.0 * np.sin(700.0 * lon) * np.sin(900.0 * lat)


@pytest.fixture(scope="module")
def cylindrical(tmp_path_factory):
    """A rough synthetic tile in the format of the LOLA cylindrical products, with overviews:
    16 pixels per degree (1.9 km), latitude 30 to 90 north, all longitudes, relief with
    single-pixel spikes. Not lunar data."""
    pytest.importorskip("lsn_data")
    from lsn_data import pyramid
    from lsn_data import synthetic_cyl as sc
    from lsn_data.cylindrical import CylDEM, CylMosaic
    from lsn_data.moon import MoonTerrain

    out = tmp_path_factory.mktemp("cyl")
    original = sc.height_m
    sc.height_m = _rough
    try:
        label = sc.write_tile(out, "SYNTH_CYL_16", 16.0, 30, 90, 0, 360, dtype="<i2")
    finally:
        sc.height_m = original
    image = label.with_suffix(".img")
    data = np.fromfile(image, dtype="<i2").reshape(960, 5760)
    rng = np.random.default_rng(20261114)
    spikes = np.column_stack([rng.integers(0, 960, 3000), rng.integers(0, 5760, 3000)])
    data[spikes[:, 0], spikes[:, 1]] += rng.integers(400, 3000, 3000).astype("<i2")  # 200 to 1500 m, half-metre units
    image.write_bytes(data.tobytes())
    pyramid.build(CylDEM(label), out / "pyr", levels=6, log=lambda *a: None)
    return MoonTerrain([], [CylMosaic([CylDEM(label, pyramid_dir=out / "pyr")])])


# The second site searches 300 km, far enough for stretches of ray to be skipped on the
# strength of the neighbourhood bound; the other two are walked completely.
# The fourth lies where the columns of the grid are narrower than a lattice step.
@pytest.mark.parametrize("lat, lon, reach_m", [(45.0, 359.7, 100_000.0), (52.0, 100.0, 300_000.0), (38.5, -0.2, 100_000.0), (84.0, 215.0, 100_000.0)])
def test_nothing_is_missed_on_a_rough_cylindrical_surface(cylindrical, lat, lon, reach_m):
    from lsncore.dem import MoonTerrainAdapter

    terrain = MoonTerrainAdapter(cylindrical).for_site(lat, lon, reach_m)
    assert type(terrain).__name__ == "MoonTerrainAdapter"
    # the lattice follows the east-west pixel, which shrinks with latitude
    assert 400.0 < terrain.finest_pixel_m <= 1895.3 * max(math.cos(math.radians(abs(lat))), math.cos(math.radians(75.0)))
    res = _assert_complete(terrain, cylindrical, lat, lon, reach_m, azimuths=np.arange(0.0, 360.0, 22.5))
    if abs(lat) < 75.0:
        assert (res.search_stats["cells_per_ray"] > 0) == (reach_m > 200_000.0)


def test_neighbourhood_bound_really_bounds(cylindrical):
    """At mid latitude, across the 0/360 meridian, close to the pole and over it."""
    from lsncore.dem import MoonTerrainAdapter

    terrain = MoonTerrainAdapter(cylindrical)
    rng = np.random.default_rng(5)
    cases = 0
    for lat_range, lon_range in (((40.0, 70.0), (0.0, 360.0)), ((40.0, 70.0), (-0.3, 0.3)), ((84.0, 89.95), (0.0, 360.0))):
        lat = rng.uniform(*lat_range, 60)
        lon = rng.uniform(*lon_range, 60)
        rad = 10.0 ** rng.uniform(2.0, 5.3, 60)  # 100 m to 200 km
        rad = np.minimum(rad, (lat - 30.5) * math.radians(1.0) * R)  # stay on the tile
        bound = terrain.cover_max_m(lon, lat, rad)
        for k in range(lat.size):
            az = rng.uniform(0.0, 360.0, 4000)
            arc = rad[k] / R * np.sqrt(rng.uniform(0.0, 1.0, 4000))
            plat, plon = destination(float(lat[k]), float(lon[k]), az, arc)
            inside = float(np.nanmax(cylindrical.height_m(np.append(plon, lon[k]), np.append(plat, lat[k]))))
            assert bound[k] >= inside - TOL_BOUND_M, (lat[k], lon[k], rad[k])
            cases += 1
    assert cases == 180
    # the bound is not just the highest terrain of the product: small neighbourhoods get less
    small = terrain.cover_max_m(rng.uniform(0.0, 360.0, 200), rng.uniform(40.0, 70.0, 200), 500.0)
    assert np.median(small) < terrain.ceiling_height_m - 500.0


def test_a_site_outside_the_polar_products_gets_a_package_that_says_so(cylindrical, tmp_path):
    from lsncore.dem import MoonTerrainAdapter

    scenario = single_site_scenario("mid-latitude", "Mid-latitude test site", 45.0, 0.3, dem_set_id="any", synthetic=False, max_range_m=100_000.0)
    (path,) = run_scenario(scenario, tmp_path, MoonTerrainAdapter(cylindrical), terrain_is_synthetic=True)
    manifest = validate_package(path)
    pkg = read_package(path)
    source = manifest["horizon"]["terrain_source"]
    assert source["at_site"]["product_id"] == "SYNTH_CYL_16" and source["at_site"]["pixel_m"] == pytest.approx(1895.21, abs=0.1)
    assert source["resolution_class"] == "coarse" and "simple cylindrical" in source["at_site"]["projection"]
    assert [p["product_id"] for p in source["products"]] == ["SYNTH_CYL_16"] and source["products"][0]["azimuth_share"] == pytest.approx(1.0)
    assert manifest["methods"][source["method"]]["title"]
    assert any("1895" in w or "1.9 km" in w for w in manifest["warnings"])  # the user is told what the pixel allows
    assert manifest["inputs"]["dem"]["layers"][0]["product_id"] == "SYNTH_CYL_16"
    # horizon and patches are complete, and the patches name the product they were read from
    assert np.isfinite(pkg.array(manifest["horizon"]["elevation_deg"])).all()
    for patch in manifest["terrain"]["patches"]:
        assert patch["up_m"]["nan_count"] == 0 and patch["sources"][0]["product_id"] == "SYNTH_CYL_16"


def test_a_site_with_no_data_is_an_error_that_names_the_missing_products(cylindrical):
    from lsncore.dem import MoonTerrainAdapter

    with pytest.raises(ValueError, match="no elevation data"):
        MoonTerrainAdapter(cylindrical).for_site(-20.0, 10.0, 100_000.0)


# ---------------------------------------------------------------- LOLA products

@pytest.fixture(scope="module")
def moon():
    lsn_data = pytest.importorskip("lsn_data")
    from lsncore.dem import MoonTerrainAdapter

    try:
        reader = lsn_data.open_terrain(products="moon")
    except (FileNotFoundError, ValueError) as missing:
        pytest.skip(f"LOLA products are not on this machine: {missing}")
    return reader, MoonTerrainAdapter(reader)


def test_south_polar_sites_are_served_exactly_as_before(moon, tmp_path):
    """The whole-Moon terrain hands a polar site to the adapter of the polar products:
    same terrain description, same package."""
    lsn_data = pytest.importorskip("lsn_data")
    from lsncore.dem import LolaTerrain

    reader, adapter = moon
    if not any(t.pole < 0 for t in reader.polar):
        pytest.skip("south-polar products are not on this machine")
    plain = LolaTerrain(lsn_data.open_terrain())
    routed = adapter.for_site(-89.80531, -154.23109, 300_000.0)
    assert type(routed).__name__ == "LolaTerrain" and routed.describe() == plain.describe()
    scenario = single_site_scenario("shackleton-rim-crest", "Shackleton crater rim crest", -89.80531, 205.76891, dem_set_id="any", synthetic=False)
    (a,) = run_scenario(scenario, tmp_path / "moon", adapter)
    (b,) = run_scenario(scenario, tmp_path / "plain", plain)
    ma, mb = validate_package(a), validate_package(b)
    assert ma["package_id"] == mb["package_id"] and ma["content_sha256"] == mb["content_sha256"]
    source = ma["horizon"]["terrain_source"]
    assert source["at_site"]["product_id"] == "LDEM_80S_20M" and source["resolution_class"] == "fine"
    assert sum(p["azimuth_share"] for p in source["products"]) == pytest.approx(1.0)


def test_a_mid_latitude_site_on_the_global_product(moon, tmp_path):
    """A site far from the poles on LDEM_128: complete, within the time budget, and labelled."""
    reader, adapter = moon
    lat, lon = 26.1, 3.6
    ids, _ = reader.source(lon, lat)
    if str(ids) == "":
        pytest.skip(f"no cylindrical product on this machine; missing: {reader.missing}")
    try:
        terrain = adapter.for_site(lat, lon, 300_000.0)
        terrain.cover_max_m(lon, lat, 50_000.0)
    except ValueError as missing:
        pytest.skip(f"overview levels of the cylindrical product are not built: {missing}")
    _assert_complete(terrain, reader, lat, lon, 300_000.0, azimuths=np.arange(0.0, 360.0, 45.0), heights=(2.0,))
    elapsed = _best_of_three(lambda: compute_horizon(terrain, lat, lon, [0.0, 1.0, 2.0, 5.0, 10.0, 20.0]))
    assert elapsed <= MAX_RUNTIME_S, f"{elapsed:.2f} s"
    scenario = single_site_scenario("mid-latitude", "Mid-latitude test site", lat, lon, dem_set_id="any", synthetic=False)
    (path,) = run_scenario(scenario, tmp_path, adapter)
    manifest = validate_package(path)
    source = manifest["horizon"]["terrain_source"]
    assert source["at_site"]["product_id"] == str(ids) and source["resolution_class"] in ("medium", "coarse")
    assert manifest["status"] == "ok" and not manifest["synthetic"]
