"""Contract 0.10: the 5 m near-field layer and an uncertainty band fed by stated product errors.

The data stream can add 5 m site rasters inside the 20 m product. The horizon search must
stay complete across the edge of the finer raster, and its speed must not collapse
because the finer raster has no overview levels. The uncertainty band takes the height
error of the terrain point that sets the horizon from a stated model: the error map of
the product where it has one, a flat figure or a slope class elsewhere.

Thresholds were fixed before the first run (CONTRIBUTING.md, rule 5). The first two are
those of core/tests/test_horizon.py.
"""

import json
import math
from pathlib import Path

import numpy as np
import pytest

from lsncore.contract import contract_dir, read_package, validate_package
from lsncore.dem import AnalyticTerrain
from lsncore.geometry import destination
from lsncore.horizon import compute_horizon
from lsncore.pipeline import run_scenario
from lsncore.scenario import single_site_scenario
from lsncore.uncertainty import height_error_for_points, terrain_slope_deg

from test_horizon import _assert_complete, _best_of_three

# --------------------------------------------------------------------------------------
# THRESHOLDS (fixed before measuring)
# --------------------------------------------------------------------------------------
TOL_BOUND_M = 1e-6            # a neighbourhood bound may not lie below any sampled point of the neighbourhood
TOL_SAME_SURFACE_M = 1e-9     # the adapter's surface against the data reader's
MAX_RUNTIME_NEAR_FIELD_S = 15.0  # one site with the 5 m near field: three times the 5 s of the 20 m data (the lattice is four times finer).
#                                  It is the time of one site on a machine that is doing nothing else, taken as the best of three runs.
TOL_SLOPE_DEG = 0.1           # slope of a tilted plane from the terrain
TOL_PATCH_NODE_M = 0.05       # a node of a terrain patch against the level of the 5 m raster it was read from (as for the 20 m product)
# --------------------------------------------------------------------------------------

REPO = Path(__file__).resolve().parents[2]
R = 1_737_400.0
MODEL = json.loads((contract_dir() / "presets" / "terrain_height_error.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def nested(tmp_path_factory):
    """A rough synthetic 20 m raster with overviews and, inside it, a 5 m raster without
    any: 8 km square around the pole, other heights (finer relief, metres off the 20 m
    surface). Not lunar data."""
    pytest.importorskip("lsn_data")
    from lsn_data import pyramid, synthetic
    from lsn_data.dem import PolarDEM, Terrain

    out = tmp_path_factory.mktemp("nested")
    rng = np.random.default_rng(20261114)

    def surface(n, pixel, extra):
        half = n * pixel / 2
        c = (np.arange(n) + 0.5) * pixel
        x, y = -half + c[None, :], half - c[:, None]
        h = 900.0 * np.sin(x / 5200.0) * np.cos(y / 4100.0) + 250.0 * np.sin(x / 700.0 + y / 450.0) + 60.0 * np.sin(x / 90.0) * np.sin(y / 70.0)
        return h + extra(x, y)

    coarse = surface(4096, 20.0, lambda x, y: 0.0)
    spikes = rng.integers(0, 4096, size=(4000, 2))
    coarse[spikes[:, 0], spikes[:, 1]] += rng.uniform(40.0, 200.0, size=4000)
    fine = surface(1600, 5.0, lambda x, y: 4.0 * np.sin(x / 23.0) * np.cos(y / 17.0) + 3.0)
    spikes = rng.integers(0, 1600, size=(3000, 2))
    fine[spikes[:, 0], spikes[:, 1]] += rng.uniform(5.0, 60.0, size=3000)
    for name, h, n, pixel in (("rough_s90_20m", coarse, 4096, 20.0), ("fine_s90_5m", fine, 1600, 5.0)):
        dn = np.rint(h / synthetic.SCALE).astype("<i2")
        (out / f"{name}.dat").write_bytes(dn.tobytes())
        (out / f"{name}.lbl").write_bytes(synthetic.label_text(dn, n, pixel, name.upper()).encode("ascii"))
    pyramid.build(PolarDEM(out / "rough_s90_20m.lbl"), out / "pyr", levels=6, log=lambda *a: None)
    coarse_only = Terrain([PolarDEM(out / "rough_s90_20m.lbl", pyramid_dir=out / "pyr")])
    both = Terrain([PolarDEM(out / "fine_s90_5m.lbl"), PolarDEM(out / "rough_s90_20m.lbl", pyramid_dir=out / "pyr")])
    return coarse_only, both


def test_finer_raster_without_overviews_does_not_shrink_the_search_cells(nested):
    from lsncore.dem import LolaTerrain

    coarse_only, both = nested
    plain, refined = LolaTerrain(coarse_only), LolaTerrain(both)
    assert refined.finest_pixel_m == 5.0
    assert refined.max_cover_radius_m == plain.max_cover_radius_m  # set by the 20 m product, as before
    rng = np.random.default_rng(3)
    lat, lon = rng.uniform(-90.0, -89.6, 5000), rng.uniform(-180.0, 180.0, 5000)
    assert np.abs(refined.height_m(lon, lat) - both.height_m(lon, lat)).max() <= TOL_SAME_SURFACE_M
    ids, _ = both.source(lon, lat)
    assert {"FINE_S90_5M", "ROUGH_S90_20M"} == set(ids)  # the sample has points on both rasters


def test_neighbourhood_bound_holds_across_the_edge_of_the_finer_raster(nested):
    from lsncore.dem import LolaTerrain

    _, both = nested
    terrain = LolaTerrain(both)
    rng = np.random.default_rng(11)
    lat = rng.uniform(-90.0, -89.75, 150)  # the finer raster ends 4 km from the pole, 0.13 degrees
    lon = rng.uniform(-180.0, 180.0, 150)
    rad = np.minimum(10.0 ** rng.uniform(0.5, 3.2, 150), terrain.max_cover_radius_m)
    bound = terrain.cover_max_m(lon, lat, rad)
    for k in range(lat.size):
        plat, plon = destination(float(lat[k]), float(lon[k]), rng.uniform(0.0, 360.0, 3000), rad[k] / R * np.sqrt(rng.uniform(0.0, 1.0, 3000)))
        assert bound[k] >= float(np.nanmax(both.height_m(np.append(plon, lon[k]), np.append(plat, lat[k])))) - TOL_BOUND_M, (lat[k], lon[k], rad[k])


# Sites on the finer raster, at its edge and outside it; every ray crosses the edge.
@pytest.mark.parametrize("lat, lon", [(-90.0, 0.0), (-89.93, 40.0), (-89.869, 135.0), (-89.8, -110.0)])
def test_nothing_is_missed_across_the_transition(nested, lat, lon):
    from lsncore.dem import LolaTerrain

    coarse_only, both = nested
    adapter = LolaTerrain(both)
    # one search over both rasters, the finer lattice everywhere
    _assert_complete(adapter, both, lat, lon, 20_000.0, azimuths=np.arange(0.0, 360.0, 22.5))
    # the way a site is served: the finer raster and its lattice only out to the edge of that
    # raster, the 20 m lattice beyond; a site off the finer raster does not use it at all
    view = adapter.for_site(lat, lon, 20_000.0)
    on_fine = both.source(lon, lat)[0] == "FINE_S90_5M"
    assert (type(view).__name__ == "NearFieldTerrain") == bool(on_fine)
    res = _assert_complete(view, both if on_fine else coarse_only, lat, lon, 20_000.0, azimuths=np.arange(0.0, 360.0, 22.5))
    if on_fine:
        assert res.search_stats["zones"] == 2 and 4000.0 < view.switch_m < 10_000.0 and view.far_terrain.finest_pixel_m == 20.0


# ---------------------------------------------------------------- the stated height error

def test_slope_of_a_tilted_plane():
    # 12 degrees up towards the north-east at a mid-latitude point, read back from the surface
    lat0, lon0, tilt = -85.0, 30.0, math.tan(math.radians(12.0))

    def plane(lon, lat):
        north = np.radians(np.asarray(lat) - lat0) * R
        east = np.radians(np.asarray(lon) - lon0) * R * math.cos(math.radians(lat0))
        return tilt * (north + east) / math.sqrt(2.0)

    terrain = AnalyticTerrain(plane, R)
    slope = terrain_slope_deg(terrain, np.array([lon0, lon0 + 0.01]), np.array([lat0, lat0 + 0.002]), np.array([20.0, 60.0]))
    assert np.abs(slope - 12.0).max() <= TOL_SLOPE_DEG


def test_height_error_follows_the_stated_model():
    """Error map where the product has one, a flat figure where the map is empty, slope
    classes for the other products; each value says where it came from."""
    model = MODEL["models"][MODEL["default"]]
    products = np.array(["LOLA5MPP_SITE04", "LOLA5MPP_SITE04", "LDEM_80S_20M", "LDEM_80S_20M", "LDEM_60S_60M", ""], dtype=object)
    rms = np.array([0.3, np.nan, np.nan, np.nan, np.nan, np.nan])
    slope = np.array([5.0, 5.0, 10.0, 35.0, 31.0, 2.0])
    error, source = height_error_for_points(model, products, rms, slope)
    assert error[:5] == pytest.approx([0.6, 1.0, 5.0, 7.0, 7.0]) and math.isnan(error[5])
    assert list(source[:5]) == ["rms_map", "flat", "slope_class", "slope_class", "slope_class"] and source[5] == ""
    # a constant stated by the user is a model too
    error, source = height_error_for_points({"constant_m": 2.0}, products, rms, slope)
    assert error[:5] == pytest.approx([2.0] * 5) and set(source[:5]) == {"constant"}


def test_preset_names_its_source_and_keeps_the_earlier_values_selectable():
    assert MODEL["default"] in MODEL["models"]
    default = MODEL["models"][MODEL["default"]]
    assert "LOLA" in default["label"] and default["source"] and "two sigma" in default["label"].lower()
    assert default["rules"]["LOLA5MPP_*"] == {"rms_map_factor": 2.0, "flat_m": 1.0}
    assert default["rules"]["*"] == {"slope_classes": [{"up_to_deg": 30.0, "error_m": 5.0}, {"up_to_deg": 90.0, "error_m": 7.0}]}
    constants = sorted(m["constant_m"] for m in MODEL["models"].values() if "constant_m" in m)
    assert constants == [0.5, 1.0, 2.0] and all("no source" in m["label"] for m in MODEL["models"].values() if "constant_m" in m)


def _tilted(lon, lat):
    return 300.0 * np.sin(np.radians(lon) * 3.0) * np.cos(np.radians(lat) * 40.0)


def test_package_says_what_fed_the_band_of_every_event(tmp_path):
    pytest.importorskip("spiceypy")
    from lsncore.ephem import kernels

    try:
        kernels.load()
    except FileNotFoundError as missing:
        pytest.skip(f"kernels are not on this machine: {missing}")
    terrain = AnalyticTerrain(_tilted, R, ceiling_height_m=300.0, dem_set_id="ANALYTIC-tilted")
    scenario = single_site_scenario("tilted", "Analytic site", -86.0, 20.0, dem_set_id="any", synthetic=False, heights_m=[2.0], azimuth_step_deg=1.0, max_range_m=50_000.0)
    scenario["time_window"] = {"start_utc": "2026-11-14T00:00:00.000Z", "end_utc": "2026-12-14T00:00:00.000Z", "step_s": 3600.0}
    scenario["uncertainty"] = {"dem_height_error_model": MODEL["models"][MODEL["default"]]}
    paths = run_scenario(scenario, tmp_path, terrain)
    manifest = validate_package(paths[-1])
    pkg = read_package(paths[-1])
    block = manifest["timeline"]["uncertainty"]["horizon_error"]
    assert block["dem_height_error_model"]["id"] == MODEL["default"] and block["dem_height_error_model"]["label"] and block["dem_height_error_model"]["source"]
    assert block["applied_height_error_m"]["max"] in (5.0, 7.0) and block["sources"] == [{"source": "slope_class", "azimuth_share": 1.0}]
    hz = manifest["horizon"]
    error = pkg.array(hz["obstacle_height_error_m"])
    assert error.shape == (1, 360) and set(np.unique(error)) <= {5.0, 7.0}
    assert set(np.unique(pkg.array(hz["obstacle_constrained"]))) == {-1}  # an analytic surface has no laser returns
    events = manifest["timeline"]["events"]
    assert events and all(e["terrain_quality"]["band_source"] == "slope_class" and e["terrain_quality"]["height_error_m"] in (5.0, 7.0) for e in events)
    assert all(e["terrain_quality"]["limiting_pixel"] == "unknown" and e["terrain_quality"]["product_id"] == "ANALYTIC-tilted" for e in events)
    card = manifest["methods"][block["method"]]
    assert MODEL["models"][MODEL["default"]]["label"] in " ".join(card["limits"] + [card["algorithm"]])
    # a constant stays selectable, and the two are not mixed
    scenario["uncertainty"] = {"dem_height_error_m": 1.0}
    other = validate_package(run_scenario(scenario, tmp_path / "constant", terrain)[-1])
    assert other["timeline"]["uncertainty"]["horizon_error"]["sources"] == [{"source": "constant", "azimuth_share": 1.0}]


# ---------------------------------------------------------------- LOLA products with the 5 m site rasters

SITES = ["shackleton_rim_crest", "de_gerlache_rim_crest", "malapert_massif_summit"]


@pytest.fixture(scope="module")
def near_field():
    lsn_data = pytest.importorskip("lsn_data")
    from lsncore.dem import LolaTerrain

    records = REPO / "data" / "sites" / "sites.json"
    try:
        reader = lsn_data.open_terrain(near_field=True)
    except FileNotFoundError as missing:
        pytest.skip(f"LOLA products are not on this machine: {missing}")
    if not records.exists() or not any(p.grid0.pixel_m < 20.0 for p in reader.products):
        pytest.skip("the 5 m site rasters or the site records are not on this machine")
    sites = {s["site_id"]: s for s in json.loads(records.read_text(encoding="utf-8"))["sites"]}
    return reader, LolaTerrain(reader), sites


@pytest.mark.parametrize("name", SITES)
def test_site_records_on_the_5_m_near_field(near_field, name, tmp_path):
    """Nothing missed against a 1 m scan, the package names the 5 m raster, and the runtime.

    The runtime limit is for one site on an otherwise idle machine and is compared with the
    best of three runs. The best of three removes a short disturbance, not a loaded
    machine: in one run of the whole suite on 14 November, with the laptop slowed by the
    long run, two sites took 15.5 s and 18.1 s; alone, minutes later, 4.6 s and 9.7 s. A
    failure here while other work is running says nothing about the search; it is to be
    reported with the load, and the limit is not to be changed.
    """
    reader, adapter, sites = near_field
    lat, lon = sites[name]["lat_deg"], (sites[name]["lon_deg_east"] + 180.0) % 360.0 - 180.0
    terrain = adapter.for_site(lat, lon, 300_000.0)
    assert type(terrain).__name__ == "NearFieldTerrain" and terrain.switch_m < 25_000.0
    # the surface of the site: its own 5 m raster inside the 20 m and 60 m products; the 5 m
    # rasters of the other sites, tens of kilometres away, are not part of it
    own = str(reader.source(lon, lat)[0])
    surface = type(reader)([p for p in reader.products if p.product_id == own or p.grid0.pixel_m >= 20.0])
    _assert_complete(terrain, surface, lat, lon, 300_000.0, azimuths=np.arange(0.0, 360.0, 45.0), heights=(2.0,))
    elapsed = _best_of_three(lambda: compute_horizon(terrain, lat, lon, [0.0, 1.0, 2.0, 5.0, 10.0, 20.0]))
    assert elapsed <= MAX_RUNTIME_NEAR_FIELD_S, f"{elapsed:.2f} s, best of three (the limit holds on a machine that is doing nothing else)"
    scenario = single_site_scenario(name.replace("_", "-"), sites[name]["name"], lat, lon, dem_set_id="any", synthetic=False)
    (path,) = run_scenario(scenario, tmp_path, terrain)
    source = validate_package(path)["horizon"]["terrain_source"]
    assert source["at_site"]["product_id"].startswith("LOLA5MPP_SITE") and source["at_site"]["pixel_m"] == 5.0 and source["resolution_class"] == "fine"


@pytest.mark.parametrize("name", SITES)
def test_terrain_patches_are_read_from_the_5_m_raster_of_the_site(near_field, name, tmp_path):
    """With the near field on, the ground drawn around the site comes from the raster the
    science used: every node of the near patch that the 5 m raster covers is its 20 m
    block average (the level whose pixel equals the spacing of the patch), and the package
    names the raster and the level. A coarser patch uses the raster where the raster has
    a level with the pixel of that patch; where it has none (the Malapert raster stops at
    40 m), the patch shows the averaged ground of the 20 m product at its own spacing
    rather than finer samples of the raster. (The first version of this test expected
    the raster's 40 m level there; that was the test's mistake about the stated rule of
    height_at_pixel_m, not a change of the tolerance.)"""
    from lsn_data.georef import lonlat_to_xy
    from test_terrain_patch import patch_grid, to_sphere

    reader, adapter, sites = near_field
    lat, lon = sites[name]["lat_deg"], (sites[name]["lon_deg_east"] + 180.0) % 360.0 - 180.0
    terrain = adapter.for_site(lat, lon, 300_000.0)
    scenario = single_site_scenario(name.replace("_", "-"), sites[name]["name"], lat, lon, dem_set_id="any", synthetic=False, heights_m=[2.0], azimuth_step_deg=5.0)
    (path,) = run_scenario(scenario, tmp_path, terrain)
    manifest = validate_package(path)
    pkg = read_package(path)
    own = manifest["horizon"]["terrain_source"]["at_site"]["product_id"]
    assert own.startswith("LOLA5MPP_")
    raster = next(p for p in reader.products if str(p.product_id) == own)

    for patch in manifest["terrain"]["patches"]:
        levels = [k for k in raster.levels if raster.pixel_m(k) == patch["spacing_m"]]
        from_raster = [src for src in patch["sources"] if src["product_id"] == own]
        if not levels:
            assert not from_raster
            continue
        (level,) = levels  # the level whose pixel is the spacing of the patch
        up = pkg.array(patch["up_m"])
        east, north = patch_grid(patch)
        node_lat, node_lon, height = to_sphere(manifest, east, north, up)
        x, y = lonlat_to_xy(node_lon.ravel(), node_lat.ravel(), raster.grid0.radius_m, reader.pole)
        covered = raster.grid(level).covers_xy(x, y)
        expected = np.asarray(raster.height_xy(x[covered], y[covered], level, "mean"), dtype=np.float64)
        on_data = np.isfinite(expected)  # the raster has pixels without a value; other products serve those nodes
        assert np.abs(height.ravel()[covered][on_data] - expected[on_data]).max() <= TOL_PATCH_NODE_M, patch["id"]
        (source,) = from_raster
        assert (source["level"], source["pixel_m"]) == (level, raster.pixel_m(level))
        assert source["node_share"] == pytest.approx(on_data.sum() / np.isfinite(up).sum(), abs=1e-9)
        if patch["id"] == "near":
            assert level == 2 and source["pixel_m"] == 20.0 and source["node_share"] > 0.5

