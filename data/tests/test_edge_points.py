"""_square_edge_points: points on the edge of any raster, also one whose x and y ranges differ (the 5 m site DEMs)."""

from types import SimpleNamespace

import numpy as np
import pytest

from lsn_data.moon_check import _square_edge_points


@pytest.mark.parametrize("x0,x1,y0,y1", [(-9000, 7000, -15000, 1000), (-45000, -29000, 7000, 23000),
                                         (-11000, 10000, 111000, 132000), (-304000, 304000, -304000, 304000)])
def test_points_lie_on_the_edge_and_half_a_metre_inside_is_inside(x0, x1, y0, y1):
    dem = SimpleNamespace(grid0=SimpleNamespace(x_ul_m=x0, x_lr_m=x1, y_ul_m=y1, y_lr_m=y0))
    x, y, nx, ny = _square_edge_points(dem, 4000)
    on_lr = (np.isclose(x, x0) | np.isclose(x, x1)) & (y >= y0) & (y <= y1)
    on_tb = (np.isclose(y, y0) | np.isclose(y, y1)) & (x >= x0) & (x <= x1)
    assert np.all(on_lr | on_tb)
    xi, yi = x - 0.5 * nx, y - 0.5 * ny
    assert np.all((xi > x0) & (xi < x1) & (yi > y0) & (yi < y1))
    xo, yo = x + 0.5 * nx, y + 0.5 * ny
    assert not np.any((xo > x0) & (xo < x1) & (yo > y0) & (yo < y1))
    for s in range(4):  # all four sides are sampled along their whole length
        assert np.sum((nx, nx, ny, ny)[s] == (1, -1, 1, -1)[s]) > 800
