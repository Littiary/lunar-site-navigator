"""Acceptance tests of the reader and pyramids on the synthetic DEM (exact analytic truth)."""

import numpy as np
import pytest

from lsn_data import pyramid, synthetic
from lsn_data.dem import PolarDEM, Terrain
from lsn_data.georef import lonlat_to_xy, xy_to_lonlat

# Thresholds written before measuring:
# quantisation of DN to 0.5 m gives <= 0.25 m; bilinear on 100 m pixels over the smooth ring and
# bowl adds < 1.5 m in total (curvature 8e-4 /m * (100 m)^2 / 8).
TOL_SMOOTH_M = 1.5


def test_fixture_is_the_generator_output(tmp_path, synth_label):
    lbl, dat = synthetic.write(tmp_path)
    assert lbl.read_bytes() == synth_label.read_bytes()
    assert dat.read_bytes() == synth_label.with_suffix(".dat").read_bytes()


def test_open_reads_label_values(synth_label):
    d = PolarDEM(synth_label)
    assert d.product_id == "SYNTH_S90_100M"
    assert d.reference_radius_m == 1_737_400.0 and d.scale == 0.5
    assert d.grid0.pixel_m == 100.0 and d.grid0.pole == -1


def test_pixel_centres_equal_dn_times_scale(synth_label):
    d = PolarDEM(synth_label)
    raw = np.fromfile(synth_label.with_suffix(".dat"), dtype="<i2").reshape(400, 400)
    rng = np.random.default_rng(0)
    rows, cols = rng.integers(0, 400, 500), rng.integers(0, 400, 500)
    x, y = d.grid0.rowcol_to_xy(rows, cols)
    got = d.height_xy(x, y)
    assert np.array_equal(got, raw[rows, cols] * 0.5)


def test_bilinear_at_pixel_corner_is_mean_of_four(synth_label):
    d = PolarDEM(synth_label)
    raw = np.fromfile(synth_label.with_suffix(".dat"), dtype="<i2").reshape(400, 400).astype(float) * 0.5
    # the pole is the corner between pixels (199..200, 199..200)
    got = float(d.height_xy(0.0, 0.0))
    assert got == pytest.approx(raw[199:201, 199:201].mean(), abs=1e-9)


def test_matches_analytic_surface_away_from_cone_apex(synth_label):
    d = PolarDEM(synth_label)
    rng = np.random.default_rng(2)
    x = rng.uniform(-18000, 18000, 4000)
    y = rng.uniform(-18000, 18000, 4000)
    keep = np.hypot(x - synthetic.CONE_X, y - synthetic.CONE_Y) > 1500  # the apex kink is not smooth
    keep &= np.abs(np.hypot(x - synthetic.CONE_X, y - synthetic.CONE_Y) - synthetic.CONE_R) > 300  # nor is the cone foot
    x, y = x[keep], y[keep]
    err = d.height_xy(x, y) - synthetic.height_m(x, y)
    assert np.abs(err).max() < TOL_SMOOTH_M


def test_lonlat_and_xy_paths_agree(synth_label):
    d = PolarDEM(synth_label)
    rng = np.random.default_rng(3)
    x = rng.uniform(-15000, 15000, 300)
    y = rng.uniform(-15000, 15000, 300)
    lon, lat = xy_to_lonlat(x, y)
    assert np.allclose(d.height_m(lon, lat), d.height_xy(x, y), atol=1e-6)
    assert np.allclose(lonlat_to_xy(lon, lat)[0], x, atol=1e-6)


def test_outside_is_nan_and_cone_is_where_the_label_says(synth_label):
    d = PolarDEM(synth_label)
    assert np.isnan(d.height_xy(25000.0, 0.0))
    assert np.isnan(d.height_xy(0.0, -20001.0))
    # the cone apex is 8 km from the pole towards +x, i.e. longitude 90 deg east
    lon = 90.0
    _, lat = xy_to_lonlat(8000.0, 0.0)
    h = float(d.height_m(lon, lat))
    assert 1250 < h < 1400
    # and the same distance towards -x (270 deg) is at ring-flat ~ bowl height
    assert float(d.height_m(270.0, lat)) < 0


def test_window_is_georeferenced(synth_label):
    d = PolarDEM(synth_label)
    w = d.window_xy(-1000, -1000, 1000, 1000)
    assert w.heights_m.shape == (20, 20)
    assert w.grid.x_ul_m == -1000 and w.grid.y_ul_m == 1000 and w.grid.pixel_m == 100
    # window pixel centres reproduce point sampling exactly
    r, c = np.mgrid[0:20, 0:20]
    x, y = w.grid.rowcol_to_xy(r, c)
    assert np.array_equal(w.heights_m, d.height_xy(x, y, method="nearest").astype(np.float32))
    # a window hanging over the edge is padded with NaN
    w2 = d.window_xy(19000, -500, 21000, 500)
    assert np.isnan(w2.heights_m).any() and np.isfinite(w2.heights_m).any()


def test_pyramid_levels(tmp_path, synth_label):
    d0 = PolarDEM(synth_label)
    meta = pyramid.build(d0, tmp_path, levels=4, log=lambda *_: None)
    assert meta["levels"] == [1, 2, 3, 4]
    d = PolarDEM(synth_label, pyramid_dir=tmp_path)
    assert d.levels == [0, 1, 2, 3, 4]
    raw = np.fromfile(synth_label.with_suffix(".dat"), dtype="<i2").reshape(400, 400).astype(np.float64)
    for k in (1, 2, 4):
        b = 2**k
        blocks = raw.reshape(400 // b, b, 400 // b, b)
        assert np.array_equal(np.asarray(d._array(k, "mean")), np.rint(blocks.mean(axis=(1, 3))).astype(np.int16))
        assert np.array_equal(np.asarray(d._array(k, "max")), blocks.max(axis=(1, 3)).astype(np.int16))
        assert d.grid(k).pixel_m == 100.0 * b
    # a coarse level agrees with the base level within the block roughness, and never lies about location
    x, y = np.array([0.0, 5000.0, -9000.0]), np.array([0.0, 4000.0, 7000.0])
    assert np.abs(d.height_xy(x, y, level=2) - d.height_xy(x, y)).max() < 25
    assert (d.height_xy(x, y, level=2, statistic="max") >= d.height_xy(x, y, level=2) - 1e-9).all()
    assert d.level_for_pixel(None) == 0
    assert d.level_for_pixel(250.0) == 1
    assert d.level_for_pixel(1e9) == 4


def test_terrain_picks_resolution_and_falls_back(tmp_path, synth_label):
    fine = PolarDEM(synth_label)
    lbl, _ = synthetic.write(tmp_path, n=200, pixel_m=400.0, product_id="SYNTH_S90_400M")
    coarse = PolarDEM(lbl)  # 80 km wide
    t = Terrain([coarse, fine])
    assert [p.product_id for p in t.products] == ["SYNTH_S90_100M", "SYNTH_S90_400M"]
    # inside the fine product: identical to the fine product
    x, y = np.array([1000.0, -7000.0]), np.array([2000.0, 3000.0])
    lon, lat = xy_to_lonlat(x, y)
    assert np.allclose(t.height_m(lon, lat), fine.height_m(lon, lat))
    # outside the fine product (30 km out): served by the coarse one
    lon2, lat2 = xy_to_lonlat(np.array([30000.0]), np.array([0.0]))
    assert np.isnan(fine.height_m(lon2, lat2)).all()
    assert np.isfinite(t.height_m(lon2, lat2)).all()
    # requesting a coarse pixel inside the fine product reads the coarse product
    assert np.allclose(t.height_m(lon, lat, max_pixel_m=400.0), coarse.height_m(lon, lat))
    # far beyond both: NaN
    lon3, lat3 = xy_to_lonlat(np.array([50000.0]), np.array([0.0]))
    assert np.isnan(t.height_m(lon3, lat3)).all()
    # radius = height + reference radius
    assert np.allclose(t.radius_m(lon, lat), t.height_m(lon, lat) + 1_737_400.0)
    assert t.provenance()[0]["product_id"] == "SYNTH_S90_100M"
