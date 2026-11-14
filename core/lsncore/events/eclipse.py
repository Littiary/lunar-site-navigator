"""Eclipses of the Sun by the Earth seen from a lunar site, and the eclipse-aware power line.

What observers on the Earth call a lunar eclipse is, at a site on the Moon, an eclipse of
the Sun by the Earth. For a few hours the Earth's disc (about 0.9 degree in radius) covers
part or all of the Sun's disc (about 0.27 degree), and solar power drops or stops even
though the Sun is high above the terrain.

Model
-----
* The Earth is an opaque disc of its equatorial radius. No atmosphere: in reality the air
  refracts some red light into the shadow, so totality is dim, not black, and the edge of
  the shadow is soft over about a minute.
* The Sun is a uniform disc (no limb darkening).
* All angles are those seen from the site (parallax included).

Contacts: C1 and C4 are the instants at which the two discs touch from outside
(separation = Earth radius + Sun radius); C2 and C3 those at which the Sun's disc touches
the Earth's limb from inside (separation = Earth radius - Sun radius).

The power line is the fraction of the Sun's disc that is lit at the site: above the
terrain horizon and not hidden by the Earth. It is integrated over the same vertical
strips as the visible fraction of the event finder, so the terrain and the Earth are
never counted twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from ..ephem import directions as d
from . import finder

DEFAULT_SCAN_STEP_S = 60.0
DEFAULT_TOL_S = 0.5
_COARSE_STEP_S = 3600.0
_COARSE_MARGIN_DEG = 1.0  # the Sun moves about 0.5 deg per hour relative to the Earth

Geometry = Callable[[np.ndarray], tuple]


# --------------------------------------------------------------------------- two discs


def covered_fraction(separation_deg, sun_radius_deg, earth_radius_deg):
    """Fraction of the Sun's disc area that the Earth's disc covers (0 to 1).

    Closed form for the overlap of two circles. Scalars or arrays.
    """
    sep = np.asarray(separation_deg, dtype=np.float64)
    rs = np.broadcast_to(np.asarray(sun_radius_deg, dtype=np.float64), sep.shape)
    re = np.broadcast_to(np.asarray(earth_radius_deg, dtype=np.float64), sep.shape)
    out = np.zeros(sep.shape)
    inside = sep <= np.abs(re - rs)  # one disc entirely inside the other
    out[inside] = np.minimum(1.0, (re[inside] / rs[inside]) ** 2)
    lens = (~inside) & (sep < re + rs)
    if np.any(lens):
        s, a, b = sep[lens], rs[lens], re[lens]
        alpha = np.arccos(np.clip((s * s + a * a - b * b) / (2.0 * s * a), -1.0, 1.0))
        beta = np.arccos(np.clip((s * s + b * b - a * a) / (2.0 * s * b), -1.0, 1.0))
        area = a * a * (alpha - np.sin(alpha) * np.cos(alpha)) + b * b * (beta - np.sin(beta) * np.cos(beta))
        out[lens] = area / (np.pi * a * a)
    return float(out) if out.ndim == 0 else out


def _strips(az, el, radius, horizon: finder.Horizon, n_strips: int):
    """Vertical strips of the Sun's disc: offsets, half heights, tops, bottoms cut by the horizon, weights."""
    theta = np.arange(1, n_strips + 1) * np.pi / (n_strips + 1)
    weights = 2.0 / (n_strips + 1) * np.sin(theta) ** 2
    stretch = np.minimum(1.0 / np.maximum(np.cos(np.radians(el)), 1e-12), 1.0 / np.cos(np.radians(80.0)))
    x = radius[:, None] * np.cos(theta)[None, :]  # horizontal offset of each strip on the sky
    half = radius[:, None] * np.sin(theta)[None, :]
    top = el[:, None] + half
    bottom = np.maximum(el[:, None] - half, horizon.elevation_at(az[:, None] + x * stretch[:, None]))
    return x, half, top, bottom, weights, stretch


def lit_fraction(
    az_deg,
    el_deg,
    radius_deg,
    earth_az_deg,
    earth_el_deg,
    earth_radius_deg,
    horizon: finder.Horizon,
    n_strips: int = finder.DEFAULT_STRIPS,
    n_earth_strips: int = 511,
) -> np.ndarray:
    """Fraction of the Sun's disc that is above the horizon and not hidden by the Earth.

    Arrays of equal length. The part above the horizon is the visible fraction of the
    event finder (same strips, same numbers). From it the part hidden by the Earth is
    subtracted: in each strip, the overlap of the Earth's disc with what the horizon left
    visible. The Earth's limb is steep where it crosses the Sun, so that second term is
    integrated on a finer set of strips (measured error with 511 strips: 0.0002 of the
    disc; with the finder's 63 strips it would be 0.004).
    """
    az = np.atleast_1d(np.asarray(az_deg, dtype=np.float64))
    el = np.atleast_1d(np.asarray(el_deg, dtype=np.float64))
    radius = np.atleast_1d(np.asarray(radius_deg, dtype=np.float64))
    e_az = np.atleast_1d(np.asarray(earth_az_deg, dtype=np.float64))
    e_el = np.atleast_1d(np.asarray(earth_el_deg, dtype=np.float64))
    e_radius = np.atleast_1d(np.asarray(earth_radius_deg, dtype=np.float64))

    _, half, top, bottom, weights, _ = _strips(az, el, radius, horizon, n_strips)
    lit = (np.maximum(top - bottom, 0.0) / (2.0 * half)) @ weights

    separation = d.angular_separation_deg(az, el, e_az, e_el)
    touching = separation < radius + e_radius
    if np.any(touching):
        a, e, r = az[touching], el[touching], radius[touching]
        x, half, top, bottom, weights, stretch = _strips(a, e, r, horizon, n_earth_strips)
        visible = np.maximum(top - bottom, 0.0)
        # Earth's disc in the same flat patch of sky centred on the Sun.
        dx = ((e_az[touching] - a + 180.0) % 360.0 - 180.0) / stretch
        chord_sq = e_radius[touching][:, None] ** 2 - (x - dx[:, None]) ** 2
        reach = np.sqrt(np.maximum(chord_sq, 0.0))
        centre = e_el[touching][:, None]
        hidden = np.minimum(top, centre + reach) - np.maximum(bottom, centre - reach)
        hidden = np.where(chord_sq > 0.0, np.clip(hidden, 0.0, None), 0.0)
        hidden = np.minimum(hidden, visible)
        lit = lit.copy()
        lit[touching] = np.clip(lit[touching] - (hidden / (2.0 * half)) @ weights, 0.0, 1.0)
    return lit


# --------------------------------------------------------------------------- contacts


@dataclass(frozen=True)
class Eclipse:
    """One eclipse of the Sun by the Earth at a site. Times are TDB seconds past J2000."""

    partial_start_et_s: float  # C1, or the start of the range if clipped_start
    total_start_et_s: float | None  # C2; None if the eclipse is not total at the site
    total_end_et_s: float | None  # C3
    partial_end_et_s: float  # C4, or the end of the range if clipped_end
    max_covered_fraction: float
    minimum_separation_deg: float
    minimum_separation_et_s: float
    clipped_start: bool
    clipped_end: bool


def _refine(condition: Callable[[np.ndarray], np.ndarray], low: np.ndarray, high: np.ndarray, state_high: np.ndarray, tol_s: float) -> np.ndarray:
    """Bisection of brackets [low, high] in which a boolean condition changes once."""
    low, high = low.copy(), high.copy()
    while low.size and np.max(high - low) > tol_s:
        middle = 0.5 * (low + high)
        same = condition(middle) == state_high
        high = np.where(same, middle, high)
        low = np.where(same, low, middle)
    return 0.5 * (low + high)


def _intervals(condition: Callable[[np.ndarray], np.ndarray], grid: np.ndarray, tol_s: float) -> list:
    """Intervals of a time grid in which a condition holds, with refined ends.

    Returns [(start, end, clipped_start, clipped_end)].
    """
    state = condition(grid)
    index = np.nonzero(state[1:] != state[:-1])[0]
    times = _refine(condition, grid[index], grid[index + 1], state[index + 1], tol_s)
    out, opened, clipped = [], (grid[0] if state[0] else None), bool(state[0])
    for time, rising in zip(times, state[index + 1]):
        if rising:
            opened, clipped = float(time), False
        elif opened is not None:
            out.append((float(opened), float(time), clipped, False))
            opened = None
    if opened is not None:
        out.append((float(opened), float(grid[-1]), clipped, True))
    return out


def find_eclipses(geometry: Geometry, start_et_s: float, stop_et_s: float, scan_step_s: float = DEFAULT_SCAN_STEP_S, tol_s: float = DEFAULT_TOL_S) -> list:
    """Every eclipse of the Sun by the Earth between two epochs.

    ``geometry(et)`` returns (separation_deg, sun_radius_deg, earth_radius_deg) as seen
    from the site. The range is first sampled hourly; only stretches in which the two
    discs come within one degree of touching are scanned at ``scan_step_s``. Contacts are
    then located by bisection to ``tol_s``; the reported time is the middle of the last
    bracket.
    """
    if stop_et_s <= start_et_s:
        raise ValueError("stop must be after start")
    coarse = np.append(np.arange(start_et_s, stop_et_s, _COARSE_STEP_S), stop_et_s)
    sep, rs, re = geometry(coarse)
    near = sep < re + rs + _COARSE_MARGIN_DEG
    eclipses: list[Eclipse] = []
    edges = np.nonzero(np.diff(np.concatenate(([False], near, [False])).astype(int)))[0]
    for first, last in zip(edges[::2], edges[1::2]):
        t0 = coarse[max(first - 1, 0)]
        t1 = coarse[min(last, coarse.size - 1)]
        count = int(np.ceil((t1 - t0) / scan_step_s)) + 1
        grid = np.linspace(t0, t1, max(count, 2))

        def partial(et):
            s, a, b = geometry(et)
            return s < b + a

        def total(et):
            s, a, b = geometry(et)
            return s < b - a

        totals = _intervals(total, grid, tol_s)
        for begin, end, clipped_start, clipped_end in _intervals(partial, grid, tol_s):
            inside = [t for t in totals if t[0] >= begin - tol_s and t[1] <= end + tol_s]
            sample = np.linspace(begin, end, max(int((end - begin) / scan_step_s) + 2, 3))
            s, a, b = geometry(sample)
            i = int(np.argmin(s))
            # Refine the minimum separation with a parabola through the three nearest samples.
            t_min, s_min = float(sample[i]), float(s[i])
            if 0 < i < sample.size - 1:
                y0, y1, y2 = s[i - 1], s[i], s[i + 1]
                denom = y0 - 2.0 * y1 + y2
                if denom > 0.0:
                    shift = 0.5 * (y0 - y2) / denom
                    t_min = float(sample[i] + shift * (sample[1] - sample[0]))
                    s_min = float(geometry(np.array([t_min]))[0][0])
            a_min, b_min = (float(v[0]) for v in geometry(np.array([t_min]))[1:])
            eclipses.append(
                Eclipse(
                    partial_start_et_s=begin,
                    total_start_et_s=inside[0][0] if inside else None,
                    total_end_et_s=inside[-1][1] if inside else None,
                    partial_end_et_s=end,
                    max_covered_fraction=float(covered_fraction(s_min, a_min, b_min)),
                    minimum_separation_deg=s_min,
                    minimum_separation_et_s=t_min,
                    clipped_start=bool(clipped_start and begin <= start_et_s + tol_s),
                    clipped_end=bool(clipped_end and end >= stop_et_s - tol_s),
                )
            )
    return eclipses


# --------------------------------------------------------------------------- site geometry


def _directions(site: d.Site, table: d.DirectionTable, et: np.ndarray) -> dict:
    return d.topocentric_from_table(site, d.interpolate_table(table, et))


def site_geometry(site: d.Site, table: d.DirectionTable) -> Geometry:
    """Separation of the Sun and the Earth and their angular radii at a site, from the table."""

    def geometry(et):
        topo = _directions(site, table, np.atleast_1d(np.asarray(et, dtype=np.float64)))
        sun, earth = topo["SUN"], topo["EARTH"]
        separation = d.angular_separation_deg(sun.az_deg, sun.el_deg, earth.az_deg, earth.el_deg)
        return separation, sun.angular_radius_deg, earth.angular_radius_deg

    return geometry


def power_line(site: d.Site, table: d.DirectionTable, horizon: finder.Horizon, et, n_strips: int = finder.DEFAULT_STRIPS) -> np.ndarray:
    """Fraction of the Sun's disc lit at the site for every epoch: terrain and Earth together."""
    topo = _directions(site, table, np.atleast_1d(np.asarray(et, dtype=np.float64)))
    sun, earth = topo["SUN"], topo["EARTH"]
    return lit_fraction(sun.az_deg, sun.el_deg, sun.angular_radius_deg, earth.az_deg, earth.el_deg, earth.angular_radius_deg, horizon, n_strips)
