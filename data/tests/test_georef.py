import numpy as np
import pytest

from lsn_data.georef import PolarGrid, lonlat_to_xy, xy_to_lonlat
from lsn_data.pdslabel import parse_label

R = 1_737_400.0


def test_south_pole_origin_and_axes():
    x, y = lonlat_to_xy(0.0, -90.0)
    assert abs(x) < 1e-9 and abs(y) < 1e-9
    # 0 deg east points to +y, 90 deg east to +x (south polar stereographic, central meridian 0).
    x0, y0 = lonlat_to_xy(0.0, -89.0)
    x1, y1 = lonlat_to_xy(90.0, -89.0)
    assert abs(x0) < 1e-6 and y0 > 0
    assert x1 > 0 and abs(y1) < 1e-6
    x2, y2 = lonlat_to_xy(180.0, -89.0)
    assert y2 < 0


def test_true_at_pole_scale_and_80s_edge():
    # rho = 2 R tan(colat/2); at 80S the distance is 304.0 km (the edge of the 20 m product).
    x, y = lonlat_to_xy(0.0, -80.0)
    assert np.isclose(y, 2 * R * np.tan(np.radians(5.0)), atol=1e-6)
    assert abs(y - 304_000.0) < 10.0
    # near the pole one degree of latitude is R*pi/180 metres
    _, y = lonlat_to_xy(0.0, -89.999)
    assert np.isclose(y / 0.001, R * np.pi / 180, rtol=1e-6)


@pytest.mark.parametrize("pole", [-1, 1])
def test_roundtrip(pole):
    rng = np.random.default_rng(1)
    lon = rng.uniform(0, 360, 1000)
    lat = pole * rng.uniform(60, 90, 1000)
    x, y = lonlat_to_xy(lon, lat, R, pole)
    lon2, lat2 = xy_to_lonlat(x, y, R, pole)
    assert np.allclose(lat, lat2, atol=1e-9)
    dl = (lon - lon2 + 180) % 360 - 180
    assert np.all(np.abs(dl) < 1e-8)


def test_grid_from_synthetic_label(synth_label):
    g = PolarGrid.from_label(parse_label(synth_label))
    assert (g.n_rows, g.n_cols, g.pixel_m) == (400, 400, 100.0)
    assert (g.x_ul_m, g.y_ul_m) == (-20000.0, 20000.0)
    # the pole is a pixel corner: the four pixels around it are rows/cols 199 and 200
    r, c = g.xy_to_rowcol(0.0, 0.0)
    assert (r, c) == (199.5, 199.5)
    x, y = g.rowcol_to_xy(0, 0)
    assert (x, y) == (-19950.0, 19950.0)
    assert g.covers_xy(0, 0) and not g.covers_xy(20001, 0)


def test_decimated_grid_keeps_corner():
    g = PolarGrid(400, 400, 100.0, -20000.0, 20000.0)
    d = g.decimated(4)
    assert (d.n_rows, d.pixel_m, d.x_ul_m, d.y_ul_m) == (100, 400.0, -20000.0, 20000.0)
    with pytest.raises(ValueError):
        PolarGrid(10, 10, 1.0, 0, 0).decimated(4)
