"""Acceptance tests for the ephemeris and time layer (stream B, step 1).

Thresholds in this file were written before the implementation was run.
The comparison against JPL Horizons lives in ``validation/horizons``.
"""

from datetime import datetime

import numpy as np
import pytest
import spiceypy as spice

from ephemeris import directions as d
from ephemeris import kernels

ARCSEC = 1.0 / 3600.0  # degrees

# Agreement required between our own topocentric formula and the SPICE routine
# azlcpo (independent code path inside SPICE, same kernels).
TOL_AZLCPO_DEG = 1.0e-6
# Agreement required between the site-independent table path (observer at the
# Moon's centre, site vector subtracted afterwards) and the exact path
# (observer at the site). Expected size from first principles: about 0.1 arcsec
# for the Earth, far less for the Sun.
TOL_TABLE_VS_EXACT_ARCSEC = 0.2

SITES = [
    d.Site(lon_deg=0.0, lat_deg=0.0, height_km=0.0),
    d.Site(lon_deg=23.47, lat_deg=0.67, height_km=0.0),
    d.Site(lon_deg=180.0, lat_deg=0.0, height_km=0.0),
    d.Site(lon_deg=-120.0, lat_deg=45.0, height_km=1.0),
    d.Site(lon_deg=30.0, lat_deg=88.0, height_km=0.0),
    d.Site(lon_deg=-135.0, lat_deg=-89.5, height_km=1.5),
    d.Site(lon_deg=45.0, lat_deg=-85.0, height_km=-2.0),
]


@pytest.fixture(scope="module", autouse=True)
def _kernels():
    kernels.load()


@pytest.fixture(scope="module")
def epochs():
    start = d.utc_to_et("2026-11-01T00:00:00")
    return start + np.arange(0, 60 * 86400.0, 5.5 * 3600.0)  # two lunar days, 5.5 h step


def test_reference_radius_matches_pck():
    radii = spice.bodvrd("MOON", "RADII", 3)[1]
    assert np.all(radii == d.MOON_RADIUS_KM)
    assert d.MOON_RADIUS_KM == 1737.4


def test_frame_is_mean_earth_aligned_with_de421():
    assert d.FRAME == "MOON_ME_DE440_ME421"
    # The generic alias must resolve to the same orientation with the loaded kernel set.
    rot = spice.pxform("MOON_ME", d.FRAME, d.utc_to_et("2026-11-14T00:00:00"))
    assert np.allclose(rot, np.eye(3), atol=1e-15)


def test_enu_triad_is_right_handed_and_orthonormal():
    for site in SITES:
        east, north, up = site.enu()
        triad = np.vstack([east, north, up])
        assert np.allclose(triad @ triad.T, np.eye(3), atol=1e-14)
        assert np.allclose(np.cross(east, north), up, atol=1e-14)
        assert np.allclose(site.position_km / np.linalg.norm(site.position_km), up, atol=1e-14)
        assert np.isclose(np.linalg.norm(site.position_km), d.MOON_RADIUS_KM + site.height_km)
    assert np.allclose(SITES[0].enu()[2], [1.0, 0.0, 0.0])


def test_time_scales():
    et = d.utc_to_et("2026-11-14T12:00:00")
    # TDB - UTC = 37 s (TAI-UTC since 2017) + 32.184 s (TT-TAI) + periodic term below 2 ms.
    # Calendar difference computed without SPICE (no leap seconds inside datetime).
    calendar_seconds = (datetime(2026, 11, 14, 12) - datetime(2000, 1, 1, 12)).total_seconds()
    assert abs((et - calendar_seconds) - 69.184) < 0.002
    assert d.et_to_utc(et) == "2026-11-14T12:00:00.000"
    many = d.utc_to_et(["2026-11-14T00:00:00", "2026-11-15T00:00:00"])
    assert many.shape == (2,) and abs((many[1] - many[0]) - 86400.0) < 1e-3


def test_exact_path_matches_azlcpo(epochs):
    for site in SITES:
        for body in ("SUN", "EARTH"):
            ours = d.topocentric_exact(site, epochs, body)
            ref_az, ref_el, ref_range = d.topocentric_azlcpo(site, epochs, body)
            sep = d.angular_separation_deg(ours.az_deg, ours.el_deg, ref_az, ref_el)
            assert sep.max() < TOL_AZLCPO_DEG, (site, body, sep.max())
            assert np.abs(ours.range_km - ref_range).max() < 1e-3


def test_table_path_matches_exact_path(epochs):
    table = d.direction_table(epochs)
    worst = 0.0
    for site in SITES:
        from_table = d.topocentric_from_table(site, table)
        for body in ("SUN", "EARTH"):
            exact = d.topocentric_exact(site, epochs, body)
            got = from_table[body]
            sep = d.angular_separation_deg(got.az_deg, got.el_deg, exact.az_deg, exact.el_deg)
            worst = max(worst, sep.max())
            assert sep.max() < TOL_TABLE_VS_EXACT_ARCSEC * ARCSEC, (site, body, sep.max() / ARCSEC)
            assert np.abs(got.angular_radius_deg - exact.angular_radius_deg).max() < 0.01 * ARCSEC
    print(f"table vs exact, worst case: {worst / ARCSEC:.4f} arcsec")


def test_table_is_site_independent(epochs):
    table = d.direction_table(epochs)
    assert table.observer == "MOON" and table.frame == d.FRAME and table.abcorr == "LT+S"
    assert table.sun_km.shape == (epochs.size, 3) and table.earth_km.shape == (epochs.size, 3)
    assert table.et.dtype == np.float64 and table.sun_km.dtype == np.float64
    assert table.kernel_set_id == kernels.kernel_set_id()


def test_earth_is_near_zenith_at_the_mean_sub_earth_point(epochs):
    # The +X axis of the mean-Earth frame points to the mean Earth direction;
    # optical librations move the Earth by at most about 8 degrees from it.
    earth = d.topocentric_exact(SITES[0], epochs, "EARTH")
    assert earth.el_deg.min() > 80.0
    # From the far side the Earth is never above the local horizontal plane.
    assert d.topocentric_exact(SITES[2], epochs, "EARTH").el_deg.max() < -80.0


def test_sun_rises_in_the_east_at_the_equator():
    start = d.utc_to_et("2026-11-01T00:00:00")
    et = start + np.arange(0, 60 * 86400.0, 600.0)
    sun = d.topocentric_exact(SITES[0], et, "SUN")
    rising = np.where((sun.el_deg[:-1] < 0) & (sun.el_deg[1:] >= 0))[0]
    setting = np.where((sun.el_deg[:-1] >= 0) & (sun.el_deg[1:] < 0))[0]
    assert rising.size >= 1 and setting.size >= 1
    # Lunar equator is inclined about 1.54 deg to the ecliptic: azimuth at rise is 90 +/- 2 deg.
    assert np.all(np.abs(sun.az_deg[rising] - 90.0) < 2.0)
    assert np.all(np.abs(sun.az_deg[setting] - 270.0) < 2.0)


def test_angular_sizes_are_physical(epochs):
    sun = d.topocentric_exact(SITES[1], epochs, "SUN")
    earth = d.topocentric_exact(SITES[1], epochs, "EARTH")
    assert 0.255 < sun.angular_radius_deg.min() and sun.angular_radius_deg.max() < 0.275
    assert 0.88 < earth.angular_radius_deg.min() and earth.angular_radius_deg.max() < 1.04


def test_principal_axis_frame_differs_by_the_known_offset():
    # Guard against mixing the two lunar body-fixed frames: they differ by a fixed
    # rotation of about 0.0289 deg (about 875 m on the surface).
    et = d.utc_to_et("2026-11-14T00:00:00")
    rot = spice.pxform("MOON_PA_DE440", d.FRAME, et)
    angle = np.degrees(np.arccos(np.clip((np.trace(rot) - 1.0) / 2.0, -1.0, 1.0)))
    assert 0.0285 < angle < 0.0292
