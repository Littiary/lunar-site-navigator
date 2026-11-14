"""Near-field layer: a polar stereographic GeoTIFF (as the PGDA 5 m site DEMs) read as a polar product.

Synthetic data only (NOT LOLA data). The GeoTIFF is written by the test: 25 m pixels, 4 km square at the cone of the
synthetic 100 m DEM, values = analytic surface + 1 m, with a NaN hole.
"""

import numpy as np
import pytest

from lsn_data import geotiff as gt, synthetic
from lsn_data.dem import PolarDEM, Terrain
from lsn_data.georef import xy_to_lonlat

X0, Y0, PX, N = 6000.0, 2000.0, 25.0, 160  # upper-left corner, pixel, size (4 km)


@pytest.fixture()
def tif(tmp_path):
    c = (np.arange(N) + 0.5) * PX
    x = X0 + c[None, :]
    y = Y0 - c[:, None]
    arr = (synthetic.height_m(x, y) + 1.0).astype("<f4")
    arr[60:70, 60:70] = np.nan  # a hole: must fall back to the coarser product
    p = tmp_path / "SYN_SITE_5MPP_surf.tif"
    gt.write_test_tiff(p, arr, X0, Y0, PX)
    return p


def test_header_and_geokeys(tif):
    info = gt.read_header(tif)
    assert (info.width, info.height, info.dtype, info.raster_type) == (N, N, "<f4", "PixelIsArea")
    assert info.geokeys[3075] == 15 and info.geokeys[3081] == -90.0 and info.geokeys[3092] == 1.0
    assert info.geokeys[2057] == 1737400.0 and info.contiguous


def test_from_geotiff_grid_and_values(tif):
    d = PolarDEM.from_geotiff(tif, product_id="SYN_SITE")
    g = d.grid0
    assert (g.n_rows, g.n_cols, g.pixel_m, g.x_ul_m, g.y_ul_m, g.pole) == (N, N, PX, X0, Y0, -1)
    x, y = g.rowcol_to_xy(10, 20)
    assert abs(float(d.height_xy(x, y)) - (synthetic.height_m(x, y) + 1.0)) < 1e-3


def test_from_geotiff_refuses_other_projections(tmp_path):
    p = tmp_path / "bad.tif"
    gt.write_test_tiff(p, np.zeros((8, 8)), 0.0, 0.0, 5.0, scale_at_origin=0.99)
    with pytest.raises(ValueError):
        PolarDEM.from_geotiff(p, product_id="BAD")
    gt.write_test_tiff(p, np.zeros((8, 8)), 0.0, 0.0, 5.0, radius_m=1737151.3)
    with pytest.raises(ValueError):
        PolarDEM.from_geotiff(p, product_id="BAD")


def test_terrain_uses_near_field_inside_and_falls_back(synth_label, tif):
    base = Terrain([PolarDEM(synth_label)])
    t = Terrain([PolarDEM(synth_label), PolarDEM.from_geotiff(tif, product_id="SYN_SITE")])
    # inside the near-field square, away from the hole
    x, y = np.array([6500.0, 9000.0]), np.array([1500.0, -1000.0])
    lon, lat = xy_to_lonlat(x, y)
    h = t.height_m(lon, lat)
    assert np.allclose(h, synthetic.height_m(x, y) + 1.0, atol=0.05)
    assert list(t.source(lon, lat)[0]) == ["SYN_SITE", "SYN_SITE"]
    # in the NaN hole: the 100 m product, exactly as without the near field
    xh, yh = X0 + 65 * PX, Y0 - 65 * PX
    lh, ah = xy_to_lonlat(xh, yh)
    assert float(t.height_m(lh, ah)) == float(base.height_m(lh, ah))
    assert t.source(lh, ah)[0].item() == "SYNTH_S90_100M"
    # outside: identical to the terrain without the near field
    lo, ao = xy_to_lonlat(np.array([-5000.0, 1000.0]), np.array([3000.0, -9000.0]))
    assert np.array_equal(t.height_m(lo, ao), base.height_m(lo, ao))
    # a coarse request is not served by the 25 m layer
    assert t.source(lon, lat, max_pixel_m=100.0)[0][0] == "SYNTH_S90_100M"


def test_open_terrain_near_field_is_opt_in(synth_label):
    import inspect

    import lsn_data

    sig = inspect.signature(lsn_data.open_terrain)
    assert sig.parameters["near_field"].default is False
