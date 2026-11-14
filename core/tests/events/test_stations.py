"""Acceptance tests for ground-station geometry and direct-to-Earth windows (stream B).

Written before the implementation. The comparison with JPL Horizons lives in
``validation/stations``; here the fast path is checked against direct SPICE calls and the
window logic against cases with a known answer.
"""

import numpy as np
import pytest

from lsncore import events as ev
from lsncore.ephem import directions as d
from lsncore.ephem import kernels
from lsncore.ephem import stations as st
from lsncore.events import links

TOL_MOON_END_ARCSEC = 1.0  # station seen from the lunar site: fast path against exact path
TOL_EARTH_END_DEG = 0.012  # lunar site seen from the station: fast path against exact path (light time ignored)
TOL_EVENT_S = 1.0

pytestmark = pytest.mark.skipif(not kernels.stations_available(), reason="station kernels not downloaded (python -m lsncore.ephem.fetch_kernels)")


@pytest.fixture(scope="module")
def table():
    kernels.load_stations()
    start = d.utc_to_et("2026-11-14T00:00:00")
    return st.station_table(start, start + 6 * 86400.0)


SITES = [d.Site(0.0, 0.0, 0.0), d.Site(205.76891, -89.80531, 1.7011), d.Site(-60.0, 40.0, 0.0)]


def test_station_catalogue_is_the_three_dsn_complexes():
    assert [s.name for s in st.DSN_STATIONS] == ["DSS-14", "DSS-43", "DSS-63"]
    assert [s.window_id for s in st.DSN_STATIONS] == ["goldstone", "canberra", "madrid"]
    assert st.RECEIVE_MASK_DEG == 6.0 and st.TRANSMIT_MASK_DEG == 10.0


def test_table_grid_and_content(table):
    assert table.step_s == 600.0 and table.position_km.shape == (3, table.et.size, 3) and table.zenith.shape == (3, table.et.size, 3)
    assert np.allclose(np.linalg.norm(table.zenith, axis=2), 1.0, atol=1e-12)
    # A station is one Earth radius from the Earth's centre: its distance from the Moon differs
    # from the Earth's by less than that.
    earth = d.direction_table(table.et).earth_km
    assert np.all(np.linalg.norm(table.position_km - earth[None], axis=2) < 6379.5)
    assert np.all(np.linalg.norm(table.position_km - earth[None], axis=2) > 6356.0)


def test_fast_path_matches_exact_spice_at_both_ends(table):
    rng = np.random.default_rng(5)
    et = np.sort(rng.uniform(table.et[1], table.et[-2], 400))
    for site in SITES:
        fast = st.link_geometry(site, table, et)
        for k, station in enumerate(st.DSN_STATIONS):
            az, el = st.station_from_site_exact(site, station.name, et)
            sep = d.angular_separation_deg(fast.station_az_deg[k], fast.station_el_deg[k], az, el) * 3600.0
            assert sep.max() < TOL_MOON_END_ARCSEC, (station.name, sep.max())
            _, el_at_station = st.site_from_station_exact(site, station.name, et)
            assert np.abs(fast.site_el_at_station_deg[k] - el_at_station).max() < TOL_EARTH_END_DEG, station.name


def test_station_is_inside_the_earth_disc_seen_from_the_moon(table):
    et = table.et[::20]
    site = SITES[0]
    geometry = st.link_geometry(site, table, et)
    earth = d.topocentric_from_table(site, d.direction_table(et))["EARTH"]
    for k in range(3):
        sep = d.angular_separation_deg(geometry.station_az_deg[k], geometry.station_el_deg[k], earth.az_deg, earth.el_deg)
        assert np.all(sep < earth.angular_radius_deg + 1e-3)
    # A station that sees the Moon above its horizon is on the half of the Earth that faces the Moon.
    up = geometry.site_el_at_station_deg > 0.0
    assert up.any() and (~up).any()


# ------------------------------------------------------------------ window logic with a known answer


def synthetic_geometry(period_s=86400.0):
    """Three stations 120 degrees apart whose elevation of the Moon is a sine of 24 h period;
    the stations stay 5 degrees above the lunar horizontal, at azimuth 10 degrees."""

    def geometry(et):
        et = np.asarray(et, dtype=float)
        phase = 2.0 * np.pi * et / period_s
        site_el = np.stack([60.0 * np.sin(phase + shift) for shift in (0.0, 2.0 * np.pi / 3.0, 4.0 * np.pi / 3.0)])
        return links.LinkGeometry(et, np.full((3, et.size), 10.0), np.full((3, et.size), 5.0), site_el)

    return geometry


def flat(elevation):
    return ev.Horizon(0.0, 1.0, np.full(360, float(elevation)))


def test_station_windows_follow_the_earth_end_when_the_moon_end_is_clear():
    period = 86400.0
    result = links.find_link_windows(synthetic_geometry(period), flat(0.0), 0.0, 3 * period, station_mask_deg=10.0)
    # Station 0: elevation 60 sin(phase) > 10 deg between phase asin(1/6) and pi - asin(1/6).
    a = np.arcsin(1.0 / 6.0) / (2.0 * np.pi) * period
    expected = [[n * period + a, n * period + period / 2.0 - a] for n in range(3)]
    assert np.allclose(result.station_windows[0], expected, atol=TOL_EVENT_S)
    assert all(cause == ("earth_end", "earth_end") for cause in result.station_causes[0])
    # With three stations 120 degrees apart and a 10 degree mask the network has no gap.
    assert np.allclose(result.network_windows, [[0.0, 3 * period]], atol=TOL_EVENT_S)
    assert result.relay_need_level == 0 and result.terrain_outages.shape == (0, 2)


def test_terrain_at_the_lunar_end_blocks_every_station():
    result = links.find_link_windows(synthetic_geometry(), flat(6.0), 0.0, 3 * 86400.0, station_mask_deg=10.0)
    assert all(len(w) == 0 for w in result.station_windows) and len(result.network_windows) == 0
    assert result.relay_need_level == 3
    assert np.allclose(result.terrain_outages, [[0.0, 3 * 86400.0]])


def test_lunar_end_mask_is_applied_and_cause_is_reported():
    # The stations are 5 degrees above the lunar horizontal: a 4 degree lunar-end mask lets them
    # through, a 6 degree mask does not.
    clear = links.find_link_windows(synthetic_geometry(), flat(0.0), 0.0, 86400.0, station_mask_deg=10.0, moon_mask_deg=4.0)
    blocked = links.find_link_windows(synthetic_geometry(), flat(0.0), 0.0, 86400.0, station_mask_deg=10.0, moon_mask_deg=6.0)
    assert clear.relay_need_level == 0 and blocked.relay_need_level == 3


def test_relay_need_levels_distinguish_station_gaps_from_terrain_outages():
    period = 86400.0

    def one_station(et):
        g = synthetic_geometry(period)(et)
        return links.LinkGeometry(g.et, g.station_az_deg[:1], g.station_el_deg[:1], g.site_el_at_station_deg[:1])

    gaps = links.find_link_windows(one_station, flat(0.0), 0.0, 3 * period, station_mask_deg=10.0)
    assert gaps.relay_need_level == 1  # the only outages are those of the Earth end
    assert gaps.terrain_outages.shape == (0, 2) and len(gaps.network_windows) == 3

    def setting_earth(et):
        g = synthetic_geometry(period)(et)
        el = 5.0 - 10.0 * np.asarray(et, dtype=float) / (3 * period)  # the stations sink below the lunar horizon
        return links.LinkGeometry(g.et, g.station_az_deg, np.broadcast_to(el, g.station_el_deg.shape).copy(), g.site_el_at_station_deg)

    terrain = links.find_link_windows(setting_earth, flat(0.0), 0.0, 3 * period, station_mask_deg=10.0)
    assert terrain.relay_need_level == 2
    assert np.allclose(terrain.terrain_outages, [[1.5 * period, 3 * period]], atol=TOL_EVENT_S)
    assert terrain.network_windows[-1][1] == pytest.approx(1.5 * period, abs=TOL_EVENT_S)
    assert terrain.station_causes[0][-1][1] in ("moon_end", "earth_end")


# ------------------------------------------------------------------ real geometry


def test_real_windows_for_a_near_side_site(table):
    site = SITES[0]
    start, stop = table.et[1], table.et[-2]
    result = links.find_link_windows(st.site_link_geometry(site, table), flat(0.0), start, stop, station_mask_deg=st.TRANSMIT_MASK_DEG)
    # From the sub-Earth point every station passes once per Earth day.
    for windows in result.station_windows:
        assert 4 <= len(windows) <= 7
        durations = (windows[:, 1] - windows[:, 0]) / 3600.0
        assert np.all(durations[1:-1] > 5.0) and np.all(durations < 16.0)
    assert result.relay_need_level in (0, 1)
    assert (result.network_windows[:, 1] - result.network_windows[:, 0]).sum() > 0.95 * (stop - start)
