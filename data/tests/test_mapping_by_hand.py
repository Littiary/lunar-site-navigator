"""Independent check of the polar stereographic mapping against values derived by hand.

The expected line and sample values below were NOT produced by lsn_data. They were derived from the equations
printed in the LOLA projection catalog DSMAP_POLAR.CAT (revision 2022-01-15, in the LOLA RDR bundle, fetched to
<data root>/raw/lola/_docs/dsmap_polar.cat) and the LDEM_80S_20M / LDEM_60S_60M labels:

    X = (I - N/2 - 0.5) * MAP_SCALE           I = sample, 1-based
    Y = (J - N/2 - 0.5) * MAP_SCALE * NS      J = line, 1-based; NS = -1 in the south
    LON = atan2(X, Y)                         (longitude 0 straight up, 90 E to the right, as the catalog text says)
    LAT = -90 + 2 atan(0.5 R / 1737400)       R = sqrt(X^2 + Y^2)

Solving these for I and J gives, with rho = 2 * 1737400 * tan((90 - |LAT|) / 2):

    I = rho sin(LON) / MAP_SCALE + N/2 + 0.5
    J = NS * rho cos(LON) / MAP_SCALE + N/2 + 0.5

Note on the catalog: its printed lat/lon -> line/sample equations multiply R by SIGN(LAT) and then use
X = R sin(LON) in both hemispheres. In the south this gives X = -rho sin(LON), i.e. 90 E to the LEFT, which
contradicts both the catalog's own inverse equations and its text ("Longitude 90 East extends to the right").
Two of the three statements agree, so the derivation follows them. The orientation is confirmed with data, not
only with the text, in data/checkpoints/cylindrical_report.json (comparison with the cylindrical LDEM_128 grid).

Pixel coordinates in the table are 0-based pixel CENTRES (row = J - 1, col = I - 1), the convention of
lsn_data.georef.PolarGrid: pixel (i, j) has its centre at (i, j), its outer edges at i +- 0.5.
Each row: (name, latitude deg, east longitude deg, row, col). Values rounded to 1e-4 pixel.
Hand checks of two of them:
  85 S, 0 E : rho = 3 474 800 * tan(2.5 deg) = 3 474 800 * 0.04366094 = 151 713.04 m;
              row = 15199.5 - 151713.04 / 20 = 7613.848, col = 15199.5.
  pole      : rho = 0, row = col = N/2 - 0.5 = 15199.5 (the pole is the corner shared by pixels 15199 and 15200).
"""

import math
from pathlib import Path

import numpy as np
import pytest

from lsn_data.georef import PolarGrid
from lsn_data.paths import data_root
from lsn_data.pdslabel import parse_label

TOL_PX = 1e-3  # a thousandth of a pixel (2 cm on the 20 m product); written before the first run

# LDEM_80S_20M: N = 30400, MAP_SCALE = 20 m, offsets 15199.5 (label)
EXPECTED_20M = [
    ("pole", -90.0, 0.0, 15199.5000, 15199.5000),
    ("85S 0E", -85.0, 0.0, 7613.8478, 15199.5000),
    ("85S 90E", -85.0, 90.0, 15199.5000, 22785.1522),
    ("85S 180E", -85.0, 180.0, 22785.1522, 15199.5000),
    ("85S 270E", -85.0, 270.0, 15199.5000, 7613.8478),
    ("80S 0E", -80.0, 0.0, -0.7804, 15199.5000),
    ("80S 90E", -80.0, 90.0, 15199.5000, 30399.7804),
    ("80S 180E", -80.0, 180.0, 30399.7804, 15199.5000),
    ("80S 270E", -80.0, 270.0, 15199.5000, -0.7804),
    ("87.5S 45E", -87.5, 45.0, 12518.8438, 17880.1562),
    ("shackleton_rim_crest", -89.80531, 205.76891, 15465.3284, 15071.1714),
    ("de_gerlache_rim_crest", -88.6641, 291.58956, 14454.1922, 13316.0647),
    ("malapert_massif_summit", -85.98795, 2.05767, 9117.9973, 15417.9997),
]

# LDEM_60S_60M: N = 31040, MAP_SCALE = 60 m, offsets 15519.5 (label)
EXPECTED_60M = [
    ("pole", -90.0, 0.0, 15519.5000, 15519.5000),
    ("70S 0E", -70.0, 0.0, 5307.8168, 15519.5000),
    ("70S 90E", -70.0, 90.0, 15519.5000, 25731.1832),
    ("62S 225E", -62.0, 225.0, 25729.7088, 5309.2912),
    ("80S 135E", -80.0, 135.0, 19102.2404, 19102.2404),
]

GRID_20M = PolarGrid(30400, 30400, 20.0, -304000.0, 304000.0, 1_737_400.0, -1)
GRID_60M = PolarGrid(31040, 31040, 60.0, -931200.0, 931200.0, 1_737_400.0, -1)


def _real_grid(pid: str) -> PolarGrid:
    lbl = data_root() / "raw" / "lola" / pid / f"{pid.lower()}.lbl"
    if not lbl.exists():
        pytest.skip(f"{pid} label not present under the data root")
    return PolarGrid.from_label(parse_label(lbl))


def _dlon(a, b):
    return (np.asarray(a) - np.asarray(b) + 180.0) % 360.0 - 180.0


def _check(grid: PolarGrid, table):
    for name, lat, lon, row, col in table:
        r, c = grid.lonlat_to_rowcol(lon, lat)
        assert abs(float(r) - row) <= TOL_PX and abs(float(c) - col) <= TOL_PX, (name, float(r), float(c), row, col)
        # inverse: line/sample -> lat/lon, compared as a ground distance in pixels
        lon2, lat2 = grid.rowcol_to_lonlat(row, col)
        colat = math.radians(90.0 + lat)
        d_north = math.radians(float(lat2) - lat) * grid.radius_m
        d_east = math.radians(float(_dlon(lon2, lon))) * grid.radius_m * math.sin(colat)
        assert math.hypot(d_north, d_east) / grid.pixel_m <= TOL_PX + 5e-5, (name, float(lat2), float(lon2))


def test_20m_by_hand_literal_grid():
    _check(GRID_20M, EXPECTED_20M)


def test_60m_by_hand_literal_grid():
    _check(GRID_60M, EXPECTED_60M)


def test_20m_by_hand_grid_from_real_label():
    g = _real_grid("LDEM_80S_20M")
    assert g == GRID_20M
    _check(g, EXPECTED_20M)


def test_60m_by_hand_grid_from_real_label():
    g = _real_grid("LDEM_60S_60M")
    assert g == GRID_60M
    _check(g, EXPECTED_60M)


def test_80s_edge_lies_just_outside_the_20m_square():
    # The label says MAXIMUM_LATITUDE = -80 "approximately": 80 S on the axes is 0.28 px beyond the outer pixel edge.
    for _, lat, lon, row, col in EXPECTED_20M[5:9]:
        x, y = GRID_20M.rowcol_to_xy(row, col)
        assert not GRID_20M.covers_xy(x, y)
        assert min(abs(row + 0.5), abs(col + 0.5), abs(row - 30399.5), abs(col - 30399.5)) == pytest.approx(0.2804, abs=1e-4)


def test_pole_is_a_pixel_corner():
    r, c = GRID_20M.lonlat_to_rowcol(123.0, -90.0)
    assert (float(r), float(c)) == (15199.5, 15199.5)
