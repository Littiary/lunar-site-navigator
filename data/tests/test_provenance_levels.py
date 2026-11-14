"""Provenance of the files read, and direct access to pyramid levels (requests from the core stream)."""

import numpy as np
import pytest

from lsn_data import open_terrain, pyramid
from lsn_data.dem import PolarDEM, Terrain
from lsn_data.georef import xy_to_lonlat


@pytest.fixture()
def synth_with_pyramid(tmp_path, synth_label):
    pyramid.build(PolarDEM(synth_label), tmp_path, levels=4, log=lambda *_: None)
    return PolarDEM(synth_label, pyramid_dir=tmp_path)


def test_provenance_lists_every_file_with_sha256(synth_with_pyramid):
    t = Terrain([synth_with_pyramid])
    p = t.provenance()[0]
    assert p["product_id"] == "SYNTH_S90_100M" and p["product_version"] == "SYNTHETIC-1"
    names = {f["name"] for f in p["files"]}
    assert {"synth_s90_100m.dat", "synth_s90_100m.lbl", "pyramid.json", "mean_L1.npy", "max_L4.npy"} <= names
    for f in p["files"]:
        assert len(f["sha256"]) == 64 and f["size_bytes"] > 0
        assert f["role"] in ("data", "label", "pyramid", "pyramid_meta")
        assert "source_url" in f and "read" in f
    # nothing has been read through a level yet except the label and the base array opened at construction
    assert not any(f["read"] for f in p["files"] if f["name"].startswith("mean_L"))
    t.height_m(*xy_to_lonlat(np.array([1000.0]), np.array([2000.0])), max_pixel_m=400.0)
    read = {f["name"] for f in t.provenance()[0]["files"] if f["read"]}
    assert "mean_L2.npy" in read and "mean_L3.npy" not in read


def test_provenance_old_keys_kept(synth_with_pyramid):
    p = Terrain([synth_with_pyramid]).provenance()[0]
    for k in ("product_id", "product_version", "data_set_id", "pixel_m", "reference_radius_m", "file"):
        assert k in p


def test_level_view_is_zero_copy_dn(synth_with_pyramid):
    d = synth_with_pyramid
    v = d.level_view(2, "max")
    assert v.dn.dtype == np.dtype("<i2") and v.dn.shape == (100, 100)
    assert v.grid == d.grid(2) and v.scale == 0.5 and v.level == 2 and v.statistic == "max"
    assert not v.dn.flags.writeable
    h = v.heights_m()
    assert h.dtype == np.float32 and np.array_equal(h, v.dn * np.float32(0.5))


def test_level_window_whole_and_part(synth_with_pyramid):
    d = synth_with_pyramid
    whole = d.level_window(1)
    assert whole.heights_m.shape == (200, 200) and whole.grid == d.grid(1) and whole.level == 1
    part = d.level_window(1, rows=(10, 30), cols=(50, 90))
    assert part.heights_m.shape == (20, 40)
    assert np.array_equal(part.heights_m, whole.heights_m[10:30, 50:90])
    # georeferencing of the part: pixel centres match the whole level's
    x, y = part.grid.rowcol_to_xy(0, 0)
    x2, y2 = whole.grid.rowcol_to_xy(10, 50)
    assert (x, y) == (x2, y2) and part.grid.pixel_m == 200.0
    # level-0 mean equals the raw array in metres
    w0 = d.level_window(0)
    assert w0.heights_m.shape == (400, 400)
    assert np.array_equal(w0.heights_m, np.asarray(d._array(0, "mean")).astype(np.float32) * np.float32(0.5))


def test_level_window_bad_input(synth_with_pyramid):
    with pytest.raises(KeyError):
        synth_with_pyramid.level_window(9)
    with pytest.raises(ValueError):
        synth_with_pyramid.level_window(1, rows=(0, 500))


def test_window_radius_helper(synth_with_pyramid):
    w = synth_with_pyramid.level_window(3)
    assert np.allclose(w.radius_m(), w.heights_m.astype(np.float64) + 1_737_400.0)


def test_terrain_levels_and_window_selection(tmp_path, synth_label, synth_with_pyramid):
    lbl, _ = __import__("lsn_data.synthetic", fromlist=["write"]).write(tmp_path / "c", n=200, pixel_m=400.0, product_id="SYNTH_S90_400M")
    t = Terrain([synth_with_pyramid, PolarDEM(lbl)])
    info = t.levels()
    assert {"product_id": "SYNTH_S90_100M", "level": 0, "statistic": "mean", "pixel_m": 100.0} .items() <= info[0].items()
    assert any(i["product_id"] == "SYNTH_S90_400M" for i in info)
    assert t.product("SYNTH_S90_400M").grid0.pixel_m == 400.0
    w = t.window_around(90.0, -89.8, 5000.0, max_pixel_m=800.0)
    assert w.grid.pixel_m <= 800.0 and w.grid.pixel_m >= 400.0
    w_fine = t.window_around(90.0, -89.8, 5000.0)
    assert w_fine.grid.pixel_m == 100.0 and w_fine.product_id == "SYNTH_S90_100M"


@pytest.mark.needs_data
def test_real_provenance_matches_manifest():
    from lsn_data import manifest as mf
    from lsn_data.paths import manifest_path

    t = open_terrain()
    m = mf.load(manifest_path())["files"]
    t.height_m(0.0, -85.0, max_pixel_m=1300.0)
    for p in t.provenance():
        data = [f for f in p["files"] if f["role"] == "data"][0]
        rec = m[data["manifest_path"]]
        assert data["sha256"] == rec["sha256"] and data["source_url"] == rec["source_url"]
        assert p["product_version"] == rec["product_version"] == "V2.0"
        lab = [f for f in p["files"] if f["role"] == "label"][0]
        assert lab["sha256"] == m[lab["manifest_path"]]["sha256"]
        pm = [f for f in p["files"] if f["role"] == "pyramid_meta"][0]
        assert pm["base_sha256"] == rec["sha256"]
