"""Acceptance tests for the eclipse of the Sun by the Earth (stream B).

Written before the implementation. The comparison with the published eclipse of
14 March 2025 lives in ``validation/eclipse``; here every expected value is either a
closed form or an independent numerical integration.
"""

import numpy as np
import pytest

from lsncore import events as ev
from lsncore.ephem import directions as d
from lsncore.ephem import kernels
from lsncore.events import eclipse as ec

TOL_COVERED = 0.002  # covered fraction: closed form against pixel counting
TOL_LIT = 0.003  # lit fraction (terrain and Earth together): strips against pixel counting
TOL_CONTACT_S = 1.0  # contact times in an analytic pass


def pixel_fraction(sun_radius, horizon_fn=None, occulter=None, n=1601):
    """Independent estimate: share of a fine pixel grid over the Sun's disc that is lit.

    The Sun's centre is at (0, 0) in a flat patch of sky (degrees). ``horizon_fn(x)`` gives
    the horizon height at horizontal offset x; ``occulter`` is (x, y, radius) of the Earth.
    """
    axis = np.linspace(-sun_radius, sun_radius, n)
    x, y = np.meshgrid(axis, axis)
    inside = x * x + y * y <= sun_radius * sun_radius
    lit = inside.copy()
    if horizon_fn is not None:
        lit &= y > horizon_fn(x)
    if occulter is not None:
        ox, oy, radius = occulter
        lit &= (x - ox) ** 2 + (y - oy) ** 2 > radius * radius
    return lit.sum() / inside.sum()


# ------------------------------------------------------------------ covered fraction of two discs


def test_covered_fraction_limits():
    rs, re = 0.266, 0.912
    assert ec.covered_fraction(re + rs, rs, re) == 0.0
    assert ec.covered_fraction(re + rs + 0.5, rs, re) == 0.0
    assert ec.covered_fraction(re - rs, rs, re) == 1.0
    assert ec.covered_fraction(0.0, rs, re) == 1.0
    # An occulter smaller than the Sun, centred on it, hides the ratio of the areas.
    assert ec.covered_fraction(0.0, 0.5, 0.2) == pytest.approx(0.16, abs=1e-12)
    # Equal discs whose edges pass through each other's centres: 2/3 - sqrt(3)/(2 pi).
    assert ec.covered_fraction(1.0, 1.0, 1.0) == pytest.approx(2.0 / 3.0 - np.sqrt(3.0) / (2.0 * np.pi), abs=1e-12)


def test_covered_fraction_matches_pixel_counting_and_is_monotonic():
    rs, re = 0.266, 0.912
    separations = np.linspace(re - rs, re + rs, 21)
    covered = ec.covered_fraction(separations, np.full(21, rs), np.full(21, re))
    assert np.all(np.diff(covered) < 0.0)
    for sep, value in zip(separations[1:-1:3], covered[1:-1:3]):
        reference = 1.0 - pixel_fraction(rs, occulter=(sep, 0.0, re))
        assert abs(value - reference) < TOL_COVERED, (sep, value, reference)


# ------------------------------------------------------------------ lit fraction: terrain and Earth together


def flat(elevation=-5.0):
    return ev.Horizon(0.0, 0.25, np.full(1440, elevation))


def test_lit_fraction_reduces_to_the_two_single_cases():
    rs, re = 0.266, 0.912
    az, el = np.array([100.0]), np.array([10.0])
    far = (np.array([200.0]), np.array([40.0]), np.array([re]))
    # Nothing in the way.
    assert ec.lit_fraction(az, el, np.array([rs]), *far, flat()) == pytest.approx(1.0, abs=1e-12)
    # Earth only: one minus the covered fraction.
    for sep in (0.70, 0.90, 1.10):
        occulter = (az + sep / np.cos(np.radians(el)), el, np.array([re]))
        lit = ec.lit_fraction(az, el, np.array([rs]), *occulter, flat())
        assert lit[0] == pytest.approx(1.0 - ec.covered_fraction(sep, rs, re), abs=TOL_COVERED)
    # Terrain only: the visible fraction of the event finder, strip for strip.
    rough = ev.Horizon(0.0, 0.25, 10.0 + 0.2 * np.sin(np.radians(np.arange(1440) * 0.25 * 40.0)))
    only_terrain = ec.lit_fraction(az, el, np.array([rs]), *far, rough)
    assert only_terrain[0] == pytest.approx(ev.disc_signals(az, el, np.array([rs]), rough).visible_fraction[0], abs=1e-12)


def test_lit_fraction_matches_the_closed_form_at_any_sun_elevation_and_position_angle():
    """The Earth is placed at a true angular distance and position angle from the Sun.

    Taking differences of azimuth and elevation as flat coordinates passes this near the
    horizon and fails it high in the sky (0.011 of the disc at 60 degrees elevation).
    """
    rs, re = 0.266, 0.912
    clear = ev.Horizon(0.0, 1.0, np.full(360, -5.0))
    for el in (1.0, 7.0, 30.0, 60.0, 85.0):
        for sep in (0.70, 0.90, 1.10):
            for angle in np.radians(np.arange(0.0, 360.0, 30.0)):
                s, e0 = np.radians(sep), np.radians(el)
                sin_el = np.sin(e0) * np.cos(s) + np.cos(e0) * np.sin(s) * np.cos(angle)
                d_az = np.arctan2(np.sin(angle) * np.sin(s) * np.cos(e0), np.cos(s) - np.sin(e0) * sin_el)
                lit = ec.lit_fraction(np.array([100.0]), np.array([el]), np.array([rs]), np.array([100.0 + np.degrees(d_az)]), np.array([np.degrees(np.arcsin(sin_el))]), np.array([re]), clear)
                assert lit[0] == pytest.approx(1.0 - ec.covered_fraction(sep, rs, re), abs=TOL_COVERED), (el, sep, np.degrees(angle))


def test_lit_fraction_with_terrain_and_earth_matches_pixel_counting():
    rs, re = 0.266, 0.912
    az0, el0 = 100.0, 0.05  # the Sun sits on a sloping horizon while the Earth covers part of it
    step = 0.05
    az_grid = np.arange(0.0, 360.0, step)
    profile = 0.0 + 0.4 * (az_grid - az0)  # slope 0.4 deg per deg of azimuth near the Sun
    horizon = ev.Horizon(0.0, step, np.where(np.abs(az_grid - az0) < 5.0, profile, 0.0))
    for dx, dy in ((0.75, 0.30), (-0.80, -0.20), (0.0, 0.95)):
        lit = ec.lit_fraction(np.array([az0]), np.array([el0]), np.array([rs]), np.array([az0 + dx / np.cos(np.radians(el0))]), np.array([el0 + dy]), np.array([re]), horizon)
        reference = pixel_fraction(rs, horizon_fn=lambda x: 0.4 * x / np.cos(np.radians(el0)) - el0, occulter=(dx, dy, re))
        assert abs(lit[0] - reference) < TOL_LIT, (dx, dy, lit[0], reference)


# ------------------------------------------------------------------ contacts in an analytic pass


def straight_pass(impact_deg, speed_deg_per_s, t_mid, rs=0.266, re=0.912):
    def geometry(et):
        et = np.asarray(et, dtype=float)
        separation = np.hypot(impact_deg, speed_deg_per_s * (et - t_mid))
        return separation, np.full(et.shape, rs), np.full(et.shape, re)

    return geometry


def test_contacts_of_a_central_pass():
    rs, re, speed, t_mid, impact = 0.266, 0.912, 0.5 / 3600.0, 40000.0, 0.37
    found = ec.find_eclipses(straight_pass(impact, speed, t_mid), 0.0, 80000.0)
    assert len(found) == 1
    e = found[0]
    outer = np.sqrt((re + rs) ** 2 - impact**2) / speed
    inner = np.sqrt((re - rs) ** 2 - impact**2) / speed
    assert abs(e.partial_start_et_s - (t_mid - outer)) < TOL_CONTACT_S
    assert abs(e.total_start_et_s - (t_mid - inner)) < TOL_CONTACT_S
    assert abs(e.total_end_et_s - (t_mid + inner)) < TOL_CONTACT_S
    assert abs(e.partial_end_et_s - (t_mid + outer)) < TOL_CONTACT_S
    assert e.max_covered_fraction == 1.0 and abs(e.minimum_separation_deg - impact) < 1e-6
    assert not e.clipped_start and not e.clipped_end


def test_partial_pass_has_no_totality_and_a_miss_has_no_eclipse():
    rs, re, speed, t_mid = 0.266, 0.912, 0.5 / 3600.0, 40000.0
    (partial,) = ec.find_eclipses(straight_pass(0.90, speed, t_mid), 0.0, 80000.0)
    assert partial.total_start_et_s is None and partial.total_end_et_s is None
    assert partial.max_covered_fraction == pytest.approx(ec.covered_fraction(0.90, rs, re), abs=1e-4)
    assert 0.0 < partial.max_covered_fraction < 1.0
    assert ec.find_eclipses(straight_pass(re + rs + 0.05, speed, t_mid), 0.0, 80000.0) == []


def test_eclipse_cut_by_the_start_of_the_range_is_marked():
    speed, t_mid = 0.5 / 3600.0, 1000.0  # the eclipse is already in progress at t = 0
    (cut,) = ec.find_eclipses(straight_pass(0.2, speed, t_mid), 0.0, 40000.0)
    assert cut.clipped_start and not cut.clipped_end and cut.partial_start_et_s == 0.0


# ------------------------------------------------------------------ real geometry


@pytest.fixture(scope="module")
def march_2025():
    kernels.load()
    start = d.utc_to_et("2025-03-13T12:00:00")
    stop = d.utc_to_et("2025-03-15T00:00:00")
    table = d.direction_table(start - 3600.0 + 3600.0 * np.arange(40))
    return start, stop, table


def test_contacts_from_the_table_match_the_exact_spice_geometry(march_2025):
    # A near-side site; the reference is the separation of the two bodies computed with
    # the observer at the site (exact path), sampled around each contact.
    start, stop, table = march_2025
    site = d.Site(lon_deg=-20.0, lat_deg=10.0, height_km=0.0)
    (e,) = ec.find_eclipses(ec.site_geometry(site, table), start, stop)
    assert e.total_start_et_s is not None

    def exact_signal(et, sign):
        sun, earth = d.topocentric_exact(site, et, "SUN"), d.topocentric_exact(site, et, "EARTH")
        separation = d.angular_separation_deg(sun.az_deg, sun.el_deg, earth.az_deg, earth.el_deg)
        return separation - (earth.angular_radius_deg + sign * sun.angular_radius_deg)

    for time, sign in ((e.partial_start_et_s, 1.0), (e.total_start_et_s, -1.0), (e.total_end_et_s, -1.0), (e.partial_end_et_s, 1.0)):
        et = np.array([time - 2.0, time + 2.0])
        s = exact_signal(et, sign)
        crossing = et[0] - s[0] * (et[1] - et[0]) / (s[1] - s[0])
        assert abs(crossing - time) < TOL_CONTACT_S


def test_power_line_through_an_eclipse(march_2025):
    start, stop, table = march_2025
    site = d.Site(lon_deg=-20.0, lat_deg=10.0, height_km=0.0)
    (e,) = ec.find_eclipses(ec.site_geometry(site, table), start, stop)
    et = np.array([e.partial_start_et_s - 600.0, 0.5 * (e.partial_start_et_s + e.total_start_et_s), 0.5 * (e.total_start_et_s + e.total_end_et_s), e.partial_end_et_s + 600.0])
    lit = ec.power_line(site, table, ev.Horizon.smooth_sphere(2.0), et)
    assert lit[0] == pytest.approx(1.0, abs=1e-9) and lit[3] == pytest.approx(1.0, abs=1e-9)
    assert 0.05 < lit[1] < 0.95 and lit[2] == 0.0
    # Behind a ridge the Sun gives no light, eclipse or not.
    wall = ev.Horizon(0.0, 1.0, np.full(360, 89.0))
    assert np.all(ec.power_line(site, table, wall, et) == 0.0)
