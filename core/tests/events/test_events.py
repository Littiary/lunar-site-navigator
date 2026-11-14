"""Acceptance tests for the event finder (stream B, step 3).

Written before the implementation. The analytic cases need no kernels; the
last group checks the finder against direct SPICE evaluation on a smooth sphere.

Stated accuracy under test: every reported event time is within 1 second of
the true crossing of the stated signal; two crossings closer together than the
scan step (60 s by default) may be missed.
"""

import numpy as np
import pytest

from lsncore import events as ev
from lsncore.ephem import directions as d
from lsncore.ephem import kernels

TOL_EVENT_S = 1.0  # event time accuracy on analytic cases
TOL_FRACTION = 0.002  # strip quadrature versus the closed form for a flat horizon


def flat_horizon(elevation_deg=0.0, step_deg=1.0):
    count = int(round(360.0 / step_deg))
    return ev.Horizon(0.0, step_deg, np.full(count, elevation_deg))


def linear_body(az_deg, el0_deg, el_rate_deg_per_s, radius_deg, az_rate_deg_per_s=0.0):
    """A body whose azimuth and elevation change linearly with time."""

    def direction(et):
        et = np.asarray(et, dtype=float)
        return (az_deg + az_rate_deg_per_s * et) % 360.0, el0_deg + el_rate_deg_per_s * et, np.full(et.shape, radius_deg)

    return direction


def by_threshold(result, threshold):
    return [event for event in result.events if event.threshold == threshold]


# ------------------------------------------------------------------ horizon and disc signals


def test_horizon_interpolation_is_linear_and_periodic():
    horizon = ev.Horizon(0.0, 90.0, np.array([0.0, 4.0, 8.0, 4.0]))
    assert np.allclose(horizon.elevation_at([0.0, 45.0, 90.0, 180.0, 315.0, 360.0, -45.0, 720.0 + 45.0]), [0, 2, 4, 8, 2, 0, 2, 2])
    shifted = ev.Horizon(10.0, 90.0, np.array([0.0, 4.0, 8.0, 4.0]))
    assert np.allclose(shifted.elevation_at([10.0, 55.0, 5.0]), [0.0, 2.0, 4.0 * (5.0 / 90.0)])


def test_smooth_sphere_horizon_dip():
    assert np.allclose(ev.Horizon.smooth_sphere(0.0).elevation_deg, 0.0)
    for height_m in (2.0, 100.0, 1000.0):
        expected = -np.degrees(np.arccos(1737400.0 / (1737400.0 + height_m)))
        assert np.allclose(ev.Horizon.smooth_sphere(height_m).elevation_deg, expected, rtol=0, atol=1e-12)


def test_visible_fraction_matches_closed_form_on_flat_horizon():
    radius = 0.266
    x = np.linspace(-1.2, 1.2, 481)  # (centre elevation - horizon) / radius
    signals = ev.disc_signals(np.full(x.shape, 123.0), x * radius, np.full(x.shape, radius), flat_horizon(0.0))
    xc = np.clip(x, -1.0, 1.0)
    closed_form = (np.arccos(-xc) + xc * np.sqrt(1.0 - xc * xc)) / np.pi
    assert np.abs(signals.visible_fraction - closed_form).max() < TOL_FRACTION
    assert np.all(signals.visible_fraction[x <= -1.0] == 0.0)
    assert np.all(signals.visible_fraction[x >= 1.0] == 1.0)
    assert np.allclose(signals.center_margin_deg, x * radius)
    assert np.allclose(signals.upper_margin_deg, (x + 1.0) * radius, atol=1e-9)
    assert np.allclose(signals.lower_margin_deg, (x - 1.0) * radius, atol=1e-9)


def test_margins_are_ordered_on_a_rough_horizon():
    rng = np.random.default_rng(7)
    horizon = ev.Horizon(0.0, 0.25, rng.normal(0.0, 0.5, 1440))
    az = rng.uniform(0.0, 360.0, 500)
    el = rng.uniform(-1.5, 1.5, 500)
    signals = ev.disc_signals(az, el, np.full(500, 0.266), horizon)
    assert np.all(signals.lower_margin_deg <= signals.center_margin_deg + 1e-12)
    assert np.all(signals.center_margin_deg <= signals.upper_margin_deg + 1e-12)
    assert np.all((signals.visible_fraction > 0.0) <= (signals.upper_margin_deg > 0.0))
    assert np.all((signals.visible_fraction < 1.0) <= (signals.lower_margin_deg < 0.0))


# ------------------------------------------------------------------ analytic event cases


def test_linear_set_three_thresholds_and_half_disc():
    # Disc of radius 0.25 deg sinking at 0.5 deg/h through a flat horizon at 0 deg.
    radius, rate = 0.25, -0.5 / 3600.0
    el0 = 1.0
    result = ev.find_events(linear_body(200.0, el0, rate, radius), flat_horizon(), 0.0, 4 * 3600.0)
    expected = {
        "lower_limb": (el0 - radius) / -rate,  # full disc ends
        "center": el0 / -rate,
        "half_disc": el0 / -rate,
        "upper_limb": (el0 + radius) / -rate,  # last light
    }
    for threshold, time in expected.items():
        found = by_threshold(result, threshold)
        assert [event.type for event in found] == ["set"], threshold
        assert abs(found[0].et_s - time) < TOL_EVENT_S, (threshold, found[0].et_s, time)
    assert abs(by_threshold(result, "upper_limb")[0].azimuth_deg - 200.0) < 1e-6


def test_diurnal_arc_rise_and_set_match_spherical_astronomy():
    # Observer at latitude phi, body at declination dec, hour angle advancing uniformly:
    # sin(el) = sin(phi) sin(dec) + cos(phi) cos(dec) cos(h). Centre rise/set at
    # cos(h0) = -tan(phi) tan(dec); upper limb at elevation -radius.
    phi, dec, radius = np.radians(40.0), np.radians(10.0), 0.3
    period = 86400.0
    omega = 2.0 * np.pi / period

    def direction(et):
        h = omega * (np.asarray(et, dtype=float) - period / 2.0)  # transit at mid-interval
        sin_el = np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.cos(h)
        el = np.arcsin(sin_el)
        az = np.arctan2(-np.cos(dec) * np.sin(h), np.sin(dec) * np.cos(phi) - np.cos(dec) * np.sin(phi) * np.cos(h))
        return np.degrees(az) % 360.0, np.degrees(el), np.full(h.shape, radius)

    result = ev.find_events(direction, flat_horizon(), 0.0, period)

    def hour_angle(elevation_deg):
        return np.arccos((np.sin(np.radians(elevation_deg)) - np.sin(phi) * np.sin(dec)) / (np.cos(phi) * np.cos(dec)))

    for threshold, elevation in (("center", 0.0), ("upper_limb", -radius), ("lower_limb", radius)):
        h0 = hour_angle(elevation)
        found = by_threshold(result, threshold)
        assert [event.type for event in found] == ["rise", "set"]
        assert abs(found[0].et_s - (period / 2.0 - h0 / omega)) < TOL_EVENT_S
        assert abs(found[1].et_s - (period / 2.0 + h0 / omega)) < TOL_EVENT_S
    rise = by_threshold(result, "center")[0]
    assert 0.0 < rise.azimuth_deg < 180.0  # rises in the east


def test_terrain_ramp_gives_analytic_centre_events():
    # Horizon: 0 deg everywhere except a ridge rising linearly from 0 deg at az 100 to 2 deg at az 110
    # and back to 0 deg at az 120. A point-like body at elevation 1 deg moves in azimuth at 1 deg/h.
    step = 0.5
    az_grid = np.arange(0.0, 360.0, step)
    profile = np.interp(az_grid, [0.0, 100.0, 110.0, 120.0, 360.0], [0.0, 0.0, 2.0, 0.0, 0.0])
    horizon = ev.Horizon(0.0, step, profile)
    rate = 1.0 / 3600.0
    result = ev.find_events(linear_body(90.0, 1.0, 0.0, 1e-4, az_rate_deg_per_s=rate), horizon, 0.0, 40 * 3600.0)
    found = by_threshold(result, "center")
    assert [event.type for event in found] == ["set", "rise"]
    assert abs(found[0].et_s - 15.0 * 3600.0) < TOL_EVENT_S  # reaches az 105 where the ridge is 1 deg high
    assert abs(found[1].et_s - 25.0 * 3600.0) < TOL_EVENT_S  # leaves at az 115
    assert abs(found[0].azimuth_deg - 105.0) < 1e-3 and abs(found[1].azimuth_deg - 115.0) < 1e-3


def test_short_occultation_longer_than_scan_step_is_found():
    # A narrow spike hides a point-like body for a few minutes; default scan step is 60 s.
    # With linear interpolation the spike has one-sample ramps: the horizon is above 1 deg
    # from az 49.992 to az 50.048, which the body crosses in 0.056 deg / (0.5 deg/h) = 403.2 s.
    step = 0.01
    az_grid = np.arange(0.0, 360.0, step)
    profile = np.where((az_grid >= 50.0) & (az_grid <= 50.04), 5.0, 0.0)
    horizon = ev.Horizon(0.0, step, profile)
    rate = 0.5 / 3600.0  # deg/s
    result = ev.find_events(linear_body(49.0, 1.0, 0.0, 1e-5, az_rate_deg_per_s=rate), horizon, 0.0, 6 * 3600.0)
    found = by_threshold(result, "center")
    assert [event.type for event in found] == ["set", "rise"]
    assert abs(found[0].et_s - 0.992 / rate) < TOL_EVENT_S
    assert abs(found[1].et_s - 1.048 / rate) < TOL_EVENT_S


def test_grazing_pass_without_crossing_gives_no_event():
    # Elevation peaks 0.01 deg below the point where the upper limb would appear.
    radius = 0.25

    def direction(et):
        et = np.asarray(et, dtype=float)
        el = -radius - 0.01 - 1e-9 * (et - 7200.0) ** 2
        return np.full(et.shape, 10.0), el, np.full(et.shape, radius)

    result = ev.find_events(direction, flat_horizon(), 0.0, 4 * 3600.0)
    assert result.events == []
    assert all(not visible for visible in result.initially_visible.values())


# ------------------------------------------------------------------ windows and countdown


def test_windows_and_countdown():
    radius, period, lead = 0.3, 86400.0, 1000.0
    omega = 2.0 * np.pi / period

    def direction(et):  # elevation is a sine that is already positive at t = 0
        et = np.asarray(et, dtype=float)
        return np.full(et.shape, 90.0), 30.0 * np.sin(omega * (et + lead)), np.full(et.shape, radius)

    t1 = 2.25 * period
    result = ev.find_events(direction, flat_horizon(), 0.0, t1)
    windows = ev.windows(result, "center")
    # Visible on (0, P/2 - lead), (P - lead, 3P/2 - lead), (2P - lead, end): the first interval was
    # already running at the start of the range, the last one is cut by its end.
    expected = [[0.0, period / 2 - lead], [period - lead, 1.5 * period - lead], [2 * period - lead, t1]]
    assert windows.intervals_et_s.shape == (3, 2)
    assert np.allclose(windows.intervals_et_s, expected, atol=TOL_EVENT_S)
    assert windows.open_start is True and windows.open_end is True
    assert abs(windows.total_s - sum(b - a for a, b in expected)) < 3 * TOL_EVENT_S

    count = ev.countdown(result, "center", 0.25 * period)
    assert count.visible_now is True and count.bound == "exact"
    assert abs(count.seconds - (0.25 * period - lead)) < TOL_EVENT_S and count.next_event_type == "set"

    count = ev.countdown(result, "center", 0.75 * period)
    assert count.visible_now is False and count.next_event_type == "rise"
    assert abs(count.seconds - (0.25 * period - lead)) < TOL_EVENT_S

    # After the last event the answer is a lower bound, never "infinite" and never empty.
    count = ev.countdown(result, "center", 2.1 * period)
    assert count.visible_now is True and count.bound == "at_least"
    assert abs(count.seconds - (t1 - 2.1 * period)) < 1e-6 and count.next_event_type is None


def test_upper_limb_window_contains_centre_window_contains_lower_limb_window():
    result = ev.find_events(linear_body(0.0, -1.0, 2.0 / 86400.0, 0.26), flat_horizon(), 0.0, 86400.0)
    upper, centre, lower = (ev.windows(result, name).intervals_et_s for name in ("upper_limb", "center", "lower_limb"))
    assert upper[0, 0] < centre[0, 0] < lower[0, 0]
    assert upper[0, 1] == centre[0, 1] == lower[0, 1] == 86400.0


# ------------------------------------------------------------------ table interpolation and real ephemeris


@pytest.fixture(scope="module")
def loaded():
    kernels.load()


TOL_INTERPOLATION_ARCSEC = 0.01  # interpolated table versus direct SPICE, hourly table


def test_table_interpolation_error_is_below_threshold(loaded):
    start = d.utc_to_et("2026-11-01T00:00:00")
    grid = start + 3600.0 * np.arange(0, 24 * 90 + 1)
    table = d.direction_table(grid)
    rng = np.random.default_rng(11)
    query = np.sort(rng.uniform(grid[0], grid[-1], 10000))
    direct = d.direction_table(query)
    interpolated = d.interpolate_table(table, query)
    for body in d.BODIES:
        a, b = interpolated.vectors(body), direct.vectors(body)
        cos_angle = np.sum(a * b, axis=1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1))
        cross = np.linalg.norm(np.cross(a, b), axis=1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1))
        angle_arcsec = np.degrees(np.arctan2(cross, cos_angle)) * 3600.0
        assert angle_arcsec.max() < TOL_INTERPOLATION_ARCSEC, (body, angle_arcsec.max())


def test_smooth_sphere_events_match_direct_spice_crossings(loaded):
    # Equatorial site, smooth sphere, observer 2 m above the surface. The finder works on the
    # interpolated direction table; the reference is the exact per-site SPICE computation,
    # sampled every second around each reported event.
    site = d.Site(lon_deg=15.0, lat_deg=2.0, height_km=0.0)
    start = d.utc_to_et("2026-11-01T00:00:00")
    stop = start + 45 * 86400.0
    table = d.direction_table(start + 3600.0 * np.arange(0, 45 * 24 + 1))
    horizon = ev.Horizon.smooth_sphere(observer_height_m=2.0)
    result = ev.find_events(ev.site_direction(site, table, "SUN"), horizon, start, stop)
    dip = horizon.elevation_deg[0]
    for threshold, sign in (("upper_limb", +1.0), ("center", 0.0), ("lower_limb", -1.0)):
        found = by_threshold(result, threshold)
        assert len(found) >= 2 and {event.type for event in found} == {"rise", "set"}
        for event in found:
            et = event.et_s + np.arange(-5.0, 6.0)
            exact = d.topocentric_exact(site, et, "SUN")
            signal = exact.el_deg + sign * exact.angular_radius_deg - dip
            crossing = et[np.argmin(np.abs(signal))]
            assert abs(crossing - event.et_s) <= TOL_EVENT_S, (threshold, event.type, crossing - event.et_s)
