"""Acceptance tests of the uncertainty band (stated horizon error) and of the
landing-ellipse sampling.

Thresholds were fixed before the implementation existed (CONTRIBUTING.md, rule 5).
"""

import math

import numpy as np
import pytest

from lsncore.geometry import site_frame
from lsncore.timeline import IntervalSet, TimeGrid
from lsncore.uncertainty import (
    ellipse_points,
    ellipse_summary,
    event_time_bounds,
    horizon_error_band,
    windows_over_points,
)

# --------------------------------------------------------------------------------------
# THRESHOLDS (fixed before measuring)
# --------------------------------------------------------------------------------------
TOL_ELLIPSE_M = 0.5          # sample points against the ellipse, on the sphere
TOL_BAND_EDGE_S = 2.0        # edges of the band against the closed form delta / rate
TOL_POINT_WINDOW_S = 2.0     # window edges of a displaced point against a brute-force scan
TOL_ALGEBRA_S = 1e-6
# --------------------------------------------------------------------------------------

R = 1_737_400.0
HOUR = 3600.0


def central_angle(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin((np.radians(lon2) - np.radians(lon1)) / 2) ** 2
    return 2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def bearing(lat1, lon1, lat2, lon2):
    p1, p2, dl = np.radians(lat1), np.radians(lat2), np.radians(lon2 - lon1)
    return np.degrees(np.arctan2(np.sin(dl) * np.cos(p2), np.cos(p1) * np.sin(p2) - np.sin(p1) * np.cos(p2) * np.cos(dl)))


# -- sample points of a landing ellipse ------------------------------------------------------

@pytest.mark.parametrize("lat, lon", [(-85.0, 30.0), (-89.9, 179.99), (10.0, -120.0)])
def test_ellipse_points_fill_the_ellipse_evenly(lat, lon):
    a, b, azimuth, n = 2000.0, 500.0, 35.0, 200
    pts = ellipse_points(lat, lon, a, b, azimuth, n, R)
    assert pts.shape == (n, 2)
    assert pts[0, 0] == pytest.approx(lat, abs=1e-12) and pts[0, 1] == pytest.approx(lon, abs=1e-9)  # the centre comes first
    dist = R * central_angle(lat, lon, pts[1:, 0], pts[1:, 1])
    ang = np.radians(bearing(lat, lon, pts[1:, 0], pts[1:, 1]) - azimuth)
    u, v = dist * np.cos(ang), dist * np.sin(ang)  # along the major axis, across it
    rho = np.hypot(u / a, v / b)
    assert rho.max() <= 1.0 + TOL_ELLIPSE_M / b
    assert rho.max() >= 0.99                         # the outermost point is on the boundary
    assert np.abs(u).max() > 0.9 * a and np.abs(v).max() > 0.9 * b
    # even in area: a quarter of the points lie inside the half-size ellipse
    assert abs(np.mean(rho <= 0.5) - 0.25) <= 0.02
    assert abs(u.mean()) <= 0.05 * a and abs(v.mean()) <= 0.05 * b
    # the same request gives the same points
    assert np.array_equal(pts, ellipse_points(lat, lon, a, b, azimuth, n, R))


def test_a_single_point_is_the_centre():
    pts = ellipse_points(-85.0, 30.0, 1000.0, 1000.0, 0.0, 1, R)
    assert pts.shape == (1, 2) and pts[0, 0] == pytest.approx(-85.0) and pts[0, 1] == pytest.approx(30.0)


# -- band for a stated horizon error ---------------------------------------------------------

def test_band_of_a_rising_body_against_the_closed_form():
    """A body rises at a constant rate over a flat horizon. If the horizon may be off by
    +-delta, the rise may be early or late by delta / rate."""
    finder = pytest.importorskip("lsncore.events.finder")
    rate = 0.05 / HOUR  # degrees per second
    e0, horizon_deg, delta = -1.0, 0.3, 0.05
    domain = (0.0, 60.0 * HOUR)

    def direction(et):
        et = np.asarray(et, dtype=np.float64)
        return np.full(et.shape, 120.0), e0 + rate * et, np.full(et.shape, 0.27)

    rule = finder.threshold_from_contract({"quantity": "margin_deg", "op": ">", "value": 0.0})
    band = horizon_error_band(direction, np.full(360, horizon_deg), 1.0, domain, rule, delta)
    t0 = (horizon_deg - e0) / rate
    shift = delta / rate
    assert band.nominal.as_list()[0][0] == pytest.approx(t0, abs=TOL_BAND_EDGE_S)
    assert band.possible.as_list()[0][0] == pytest.approx(t0 - shift, abs=TOL_BAND_EDGE_S)   # horizon lower: earlier
    assert band.certain.as_list()[0][0] == pytest.approx(t0 + shift, abs=TOL_BAND_EDGE_S)    # horizon higher: later
    assert band.uncertain.total_s() == pytest.approx(2.0 * shift, abs=2 * TOL_BAND_EDGE_S)
    # certain is inside nominal is inside possible
    assert band.certain.intersection(band.nominal) == band.certain
    assert band.nominal.intersection(band.possible) == band.nominal
    assert band.uncertain == band.possible.intersection(band.certain.complement())
    # the nominal event lies in the band, and the band gives its earliest and latest time
    (bounds,) = event_time_bounds([band.nominal.as_list()[0][0]], band)
    assert bounds[0] == pytest.approx(t0 - shift, abs=TOL_BAND_EDGE_S)
    assert bounds[1] == pytest.approx(t0 + shift, abs=TOL_BAND_EDGE_S)


def test_event_bounds_fall_back_to_the_event_itself_outside_the_band():
    domain = (0.0, 1000.0)
    nominal = IntervalSet([(100, 500)], domain)
    from lsncore.uncertainty import Band

    band = Band(nominal, IntervalSet([(120, 470)], domain), IntervalSet([(90, 540)], domain), IntervalSet([(90, 120), (470, 540)], domain), 0.05)
    assert event_time_bounds([100.0, 500.0, 700.0], band) == [(90.0, 120.0), (470.0, 540.0), (700.0, 700.0)]


def test_zero_error_gives_an_empty_band():
    finder = pytest.importorskip("lsncore.events.finder")

    def direction(et):
        et = np.asarray(et, dtype=np.float64)
        return np.full(et.shape, 10.0), -1.0 + et / 36000.0, np.full(et.shape, 0.27)

    rule = finder.threshold_from_contract({"quantity": "visible_fraction", "op": ">", "value": 0.0})
    band = horizon_error_band(direction, np.zeros(360), 1.0, (0.0, 72000.0), rule, 0.0)
    assert band.uncertain.total_s() == 0.0 and band.certain == band.nominal == band.possible


# -- many landing points ---------------------------------------------------------------------

def test_summary_over_points_is_plain_set_arithmetic():
    domain = (0.0, 100.0)
    grid = TimeGrid(0.0, 10.0, 11)
    sets = [IntervalSet([(0, 50)], domain), IntervalSet([(20, 70)], domain), IntervalSet([(40, 100)], domain), IntervalSet([(45, 48)], domain)]
    summary = ellipse_summary(sets, grid)
    assert summary["all_points"].as_list() == [[45.0, 48.0]]
    assert summary["any_point"].as_list() == [[0.0, 100.0]]
    assert summary["totals_s"] == pytest.approx([50.0, 50.0, 60.0, 3.0], abs=TOL_ALGEBRA_S)
    # share of the points at which the condition holds, at every sample of the grid
    assert summary["share"].tolist() == pytest.approx([0.25, 0.25, 0.5, 0.5, 0.75, 0.75, 0.5, 0.5, 0.25, 0.25, 0.25])
    assert summary["min_s"] == 3.0 and summary["max_s"] == 60.0 and summary["median_s"] == 50.0
    assert summary["centre_s"] == 50.0  # the first point is the nominal site


def test_window_of_a_displaced_point_follows_from_its_own_local_frame():
    """A distant body circles the pole. Moving the site changes its local vertical, hence
    the elevation of the body and the times at which it clears a smooth horizon. The
    runner must use each point's own frame; the expected windows come from a brute-force
    scan written here."""
    finder = pytest.importorskip("lsncore.events.finder")
    omega = 2.0 * math.pi / (29.5 * 86400.0)  # the body goes round once per lunar day
    beta = math.radians(-0.8)                 # 0.8 deg south of the equator plane
    domain = (0.0, 40.0 * 86400.0)
    observer_m = 2.0
    dip = math.degrees(math.acos(R / (R + observer_m)))

    def body(et):
        lon = -omega * np.asarray(et, dtype=np.float64)
        return np.stack([math.cos(beta) * np.cos(lon), math.cos(beta) * np.sin(lon), np.full(lon.shape, math.sin(beta))], axis=-1)

    def direction_for(lat, lon):
        east, north, up = site_frame(lat, lon)

        def direction(et):
            s = body(et)
            az = np.degrees(np.arctan2(s @ east, s @ north)) % 360.0
            el = np.degrees(np.arcsin(np.clip(s @ up, -1.0, 1.0)))
            return az, el, np.full(np.shape(et), 0.25)

        return direction

    def horizon_for(lat, lon):
        return np.full(360, -dip), 1.0  # smooth sphere: elevation profile and azimuth step

    centre = (-88.5, 40.0)
    points = ellipse_points(centre[0], centre[1], 15_000.0, 5_000.0, 70.0, 9, R)
    rule = finder.threshold_from_contract({"quantity": "margin_deg", "op": ">", "value": 0.0})
    sets = windows_over_points(points, direction_for, horizon_for, domain, rule)
    assert len(sets) == 9

    t = np.arange(domain[0], domain[1] + 1.0, 1.0)
    for (lat, lon), found in zip(points, sets):
        _, _, up = site_frame(lat, lon)
        above = np.degrees(np.arcsin(np.clip(body(t) @ up, -1.0, 1.0))) + dip > 0.0
        edges = t[1:][above[1:] != above[:-1]]
        mine = np.array([e for iv in found.intervals for e in iv if domain[0] < e < domain[1]])
        assert mine.size == edges.size and mine.size >= 2
        assert np.abs(np.sort(mine) - edges).max() <= TOL_POINT_WINDOW_S
    # the points differ: the displacement moves the window edges by more than the tolerance
    starts = [s.as_list()[0][0] if not s.clipped_start else s.as_list()[1][0] for s in sets]
    assert max(starts) - min(starts) > 600.0
