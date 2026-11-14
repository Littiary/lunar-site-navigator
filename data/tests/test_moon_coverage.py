"""Whole-Moon coverage: cylindrical reader, tiled mosaics, MoonTerrain and its product choice.

Synthetic data only (lsn_data.synthetic and lsn_data.synthetic_cyl, NOT LOLA data); the real-data checks of the new
products are in data/checkpoints (moon_report.json) and in test_moon_real.py.
"""

import numpy as np
import pytest

from lsn_data import pyramid, synthetic_cyl as sc
from lsn_data.cylindrical import CylDEM, CylGrid, CylMosaic
from lsn_data.dem import PolarDEM, Terrain
from lsn_data.moon import MoonTerrain
from lsn_data.pdslabel import parse_label


# -- cylindrical grid: values derived by hand from DSMAP.CAT ---------------------------------------
def _ldem16_grid():
    # LDEM_16 label: 2880 x 5760, 16 pix/deg, CENTER_LONGITUDE 180, LINE/SAMPLE_PROJECTION_OFFSET 1439.5 / 2879.5
    return CylGrid(2880, 5760, 16.0, 180.0, 0.0, 1439.5, 2879.5, 1_737_400.0)


@pytest.mark.parametrize(
    "lon, lat, row, col",
    [
        (0.03125, 89.96875, 0.0, 0.0),            # centre of the upper-left pixel: 90 - 1/32, 0 + 1/32
        (180.0, 0.0, 1439.5, 2879.5),             # the projection origin is a pixel corner
        (359.96875, -89.96875, 2879.0, 5759.0),   # centre of the lower-right pixel
        (-0.03125, 0.03125, 1439.0, 5759.0),      # negative longitude wraps to 359.96875
        (90.0, -45.0, 2159.5, 1439.5),
    ],
)
def test_cylindrical_grid_by_hand(lon, lat, row, col):
    g = _ldem16_grid()
    r, c = g.lonlat_to_rowcol(lon, lat)
    assert abs(float(r) - row) < 1e-9 and abs(float(c) - col) < 1e-9
    lon2, lat2 = g.rowcol_to_lonlat(row, col)
    assert abs(float(lat2) - lat) < 1e-9 and abs(((float(lon2) - lon + 180) % 360) - 180) < 1e-9


def test_cylindrical_tile_extent_and_origin_by_hand():
    # SLDEM2015_256_60S_0S_000_120 label: 15360 x 30720, 256 ppd, LINE_PROJECTION_OFFSET -0.5, SAMPLE 46079.5
    g = CylGrid(15360, 30720, 256.0, 180.0, 0.0, -0.5, 46079.5, 1_737_400.0)
    assert (g.west_lon, g.east_lon, g.north_lat, g.south_lat) == (0.0, 120.0, 0.0, -60.0)
    assert g.global_origin == (90 * 256, 0)
    assert abs(g.pixel_m - 118.4505876) < 1e-6  # the label's MAP_SCALE, 0.1184505876 km
    d = g.decimated(4)
    assert (d.west_lon, d.north_lat, d.res_ppd) == (0.0, 0.0, 64.0)


# -- mosaics of synthetic tiles ------------------------------------------------------------------
@pytest.fixture()
def tiles(tmp_path):
    a = sc.write_tile(tmp_path / "a", "SYN_T_W", 4.0, -60, 0, 0, 180)
    b = sc.write_tile(tmp_path / "b", "SYN_T_E", 4.0, -60, 0, 180, 360)
    c = sc.write_tile(tmp_path / "c", "SYN_T_N", 4.0, 0, 60, 0, 360, dtype="<i2")
    return [CylDEM(p) for p in (a, b, c)]


def test_tile_values_and_units(tiles):
    t = tiles[0]
    assert t.scale == 1000.0 and t.reference_radius_m == 1_737_400.0
    m = CylMosaic([t])
    lon, lat = np.array([10.125, 100.375]), np.array([-30.125, -5.375])
    assert np.allclose(m.height_m(lon, lat), sc.height_m(lon, lat), atol=1e-3)


def test_bilinear_is_exact_across_tile_seams(tiles):
    m = CylMosaic(tiles, product_id="SYN")
    # across the 180 deg seam (two tiles), across the equator (float and int16 tiles), and inside tiles
    lon = np.array([179.9, 180.0, 180.1, 45.0, 300.0, 200.0])
    lat = np.array([-10.0, -20.0, -30.0, 0.0, 0.05, -0.05])
    assert np.allclose(m.height_m(lon, lat), sc.height_m(lon, lat), atol=0.3)  # int16 tile is quantised to 0.5 m


def test_wrap_at_zero_meridian_blends_both_sides(tiles):
    m = CylMosaic(tiles)
    h = m.height_m(359.999, -30.125)
    # neighbours are col 1439 (lon 359.875) and col 0 (lon 0.125) of the global grid
    w = (359.999 - 359.875) * 4.0
    expect = (1 - w) * sc.height_m(359.875, -30.125) + w * sc.height_m(0.125, -30.125)
    assert abs(float(h) - expect) < 1e-3


def test_outside_tiles_is_nan_and_edge_does_not_vanish(tiles):
    m = CylMosaic(tiles[:2])  # 60S..0 only
    assert np.isnan(m.height_m(10.0, 10.0))
    assert np.isnan(m.height_m(10.0, -61.0))
    v = m.height_m(10.0, -59.95)  # inside the outermost half pixel: nearest row, not NaN
    assert np.isfinite(v)


def test_cylindrical_pyramid_float(tmp_path, tiles):
    t = tiles[0]
    meta = pyramid.build(t, tmp_path / "pyr", levels=3)
    assert meta["levels"] == [1, 2, 3] and meta["dtype"] == "<f4"
    t2 = CylDEM(t.label_path, pyramid_dir=tmp_path / "pyr")
    m = CylMosaic([t2])
    assert m.levels == [0, 1, 2, 3] and m.has_level(2, "max")
    # level 2: 4 x 4 blocks; the mean of a linear surface over a block equals its value at the block centre
    assert abs(float(m.height_m(90.0, -30.0, level=2)) - float(sc.height_m(90.0, -30.0))) < 1e-2
    assert float(m.height_m(90.0, -30.0, level=2, statistic="max")) >= float(m.height_m(90.0, -30.0, level=2))


# -- MoonTerrain -----------------------------------------------------------------------------------
@pytest.fixture()
def moon(tmp_path, synth_label, tiles):
    south = Terrain([PolarDEM(synth_label)])
    north = Terrain([PolarDEM(sc.write_north_polar(tmp_path / "n"))])
    return MoonTerrain([south, north], [CylMosaic(tiles, product_id="SYN_CYL")])


def test_moon_uses_polar_where_it_covers_and_same_values(moon, synth_label):
    lon, lat = np.array([90.0, 10.0, 200.0]), np.array([-89.8, -89.9, -89.95])
    ref = Terrain([PolarDEM(synth_label)]).height_m(lon, lat)
    assert np.array_equal(moon.height_m(lon, lat), ref)
    ids, levels = moon.source(lon, lat)
    assert list(ids) == ["SYNTH_S90_100M"] * 3 and list(levels) == [0, 0, 0]


def test_moon_north_and_cylindrical_and_nothing(moon):
    ids, _ = moon.source(np.array([90.0, 45.0, 45.0, 45.0]), np.array([89.9, 30.0, -30.0, -75.0]))
    assert list(ids) == ["SYNTH_N90_100M", "SYN_CYL", "SYN_CYL", ""]
    h = moon.height_m(np.array([45.0, 45.0]), np.array([-30.0, -75.0]))
    assert abs(h[0] - sc.height_m(45.0, -30.0)) < 1e-3 and np.isnan(h[1])


def test_moon_radius_and_provenance(moon):
    assert moon.reference_radius_m == 1_737_400.0
    r = moon.radius_m(45.0, -30.0)
    assert abs(float(r) - 1_737_400.0 - float(sc.height_m(45.0, -30.0))) < 1e-3
    prov = moon.provenance()
    assert {p["product_id"] for p in prov} == {"SYNTH_S90_100M", "SYNTH_N90_100M", "SYN_CYL"}
    assert any(f["role"] == "data" for f in prov[-1]["files"])


def test_moon_rejects_different_reference_radii(tmp_path, synth_label):
    lbl = sc.write_tile(tmp_path / "x", "SYN_BAD", 4.0, -60, 0, 0, 180)
    lbl.write_text(lbl.read_text().replace("OFFSET                = 1737.4", "OFFSET                = 1738.0").replace("A_AXIS_RADIUS                = 1737.4", "A_AXIS_RADIUS                = 1738.0").replace("B_AXIS_RADIUS                = 1737.4", "B_AXIS_RADIUS                = 1738.0").replace("C_AXIS_RADIUS                = 1737.4", "C_AXIS_RADIUS                = 1738.0"))
    with pytest.raises(ValueError):
        MoonTerrain([Terrain([PolarDEM(synth_label)])], [CylMosaic([CylDEM(lbl)])])


def test_open_terrain_default_is_unchanged(synth_label):
    import lsn_data

    t = lsn_data.open_terrain(label_paths=[synth_label])
    assert isinstance(t, Terrain)
    assert lsn_data.DEFAULT_PRODUCTS == ("LDEM_80S_20M", "LDEM_60S_60M")
