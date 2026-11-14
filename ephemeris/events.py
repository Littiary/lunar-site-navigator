"""Rise and set events of a disc (the Sun or the Earth) against a horizon profile.

Inputs
------
* A direction source: a function ``et -> (azimuth_deg, elevation_deg, angular_radius_deg)``
  for the disc centre. ``site_direction`` builds one from the site-independent
  direction table; tests use analytic functions.
* A ``Horizon``: elevation of the terrain horizon on a uniform, periodic azimuth
  grid, linearly interpolated. ``Horizon.smooth_sphere`` is the terrain-free case.

The disc is not a point
-----------------------
The disc is cut into vertical strips. For each strip the part above the local
horizon is computed exactly, which gives four continuous signals:

* ``upper_margin``  largest height of any strip top above the horizon (deg);
  positive when **any part** of the disc is visible;
* ``center_margin`` height of the disc centre above the horizon (deg);
* ``lower_margin``  smallest height of any strip bottom above the horizon (deg);
  positive when the **whole** disc is visible;
* ``visible_fraction`` fraction of the disc area above the horizon, 0 to 1.

Each threshold has its own events and its own windows:

==============  =====================  ==========================================
threshold       signal > 0 means       rise / set
==============  =====================  ==========================================
``upper_limb``  any part is visible    first light / last light
``half_disc``   fraction above 0.5     half of the disc area appears / is lost
``center``      centre is visible      point-source convention
``lower_limb``  whole disc is visible  full disc reached / partial phase starts
==============  =====================  ==========================================

Between ``lower_limb`` set and ``upper_limb`` set the disc is partially
visible; ``visible_fraction`` says how much.

Time accuracy
-------------
Signals are sampled every ``scan_step_s`` (60 s by default). Every change of
sign between two consecutive samples is located by bisection until the bracket
is no wider than ``tol_s`` (0.5 s); the reported time is the middle of the
bracket, so it is within 0.25 s of the crossing of the sampled signal. Two
crossings of the same signal that both fall inside one scan interval are not
detected. This is numerical accuracy for the given inputs; the physical
accuracy of an event time is set by the horizon profile, not by this module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np

from . import directions as d

MOON_RADIUS_M = d.MOON_RADIUS_KM * 1000.0
THRESHOLDS = ("upper_limb", "half_disc", "center", "lower_limb")
DEFAULT_STRIPS = 63  # odd, so that one strip is the vertical diameter of the disc
DEFAULT_SCAN_STEP_S = 60.0
DEFAULT_TOL_S = 0.5

DirectionSource = Callable[[np.ndarray], tuple]


# --------------------------------------------------------------------------- horizon


@dataclass(frozen=True)
class Horizon:
    """Horizon elevation on a uniform azimuth grid covering 360 degrees, periodic."""

    start_deg: float
    step_deg: float
    elevation_deg: np.ndarray  # [count]; may be negative
    distance_m: np.ndarray | None = None  # [count]; distance to the obstacle, if known

    def __post_init__(self):
        count = np.asarray(self.elevation_deg).shape[0]
        if abs(count * self.step_deg - 360.0) > 1e-9:
            raise ValueError("horizon grid must cover exactly 360 degrees")
        if not np.all(np.isfinite(self.elevation_deg)):
            raise ValueError("horizon profile contains non-finite values")

    def _locate(self, az_deg):
        x = ((np.asarray(az_deg, dtype=np.float64) - self.start_deg) % 360.0) / self.step_deg
        base = np.floor(x)
        count = self.elevation_deg.shape[0]
        return base.astype(np.int64) % count, x - base, count

    def elevation_at(self, az_deg) -> np.ndarray:
        i, frac, count = self._locate(az_deg)
        return (1.0 - frac) * self.elevation_deg[i] + frac * self.elevation_deg[(i + 1) % count]

    def distance_at(self, az_deg):
        """Distance of the obstacle at the nearest azimuth sample (m), or NaN if not available."""
        if self.distance_m is None:
            return np.full(np.shape(az_deg), np.nan)
        i, frac, count = self._locate(az_deg)
        return self.distance_m[np.where(frac < 0.5, i, (i + 1) % count)]

    @classmethod
    def smooth_sphere(cls, observer_height_m: float = 0.0, step_deg: float = 1.0) -> "Horizon":
        """Horizon of a terrain-free sphere seen from ``observer_height_m`` above it.

        The horizon lies below the local horizontal plane by the dip angle
        arccos(R / (R + h)); the distance to it is sqrt(2 R h + h^2).
        """
        count = int(round(360.0 / step_deg))
        dip = math.degrees(math.acos(MOON_RADIUS_M / (MOON_RADIUS_M + observer_height_m)))
        distance = math.sqrt(2.0 * MOON_RADIUS_M * observer_height_m + observer_height_m**2)
        return cls(0.0, 360.0 / count, np.full(count, -dip), np.full(count, distance))


# --------------------------------------------------------------------------- disc signals


@dataclass(frozen=True)
class DiscSignals:
    center_margin_deg: np.ndarray
    upper_margin_deg: np.ndarray
    lower_margin_deg: np.ndarray
    visible_fraction: np.ndarray
    upper_azimuth_deg: np.ndarray  # azimuth of the strip that holds the upper margin
    lower_azimuth_deg: np.ndarray  # azimuth of the strip that holds the lower margin

    def signal(self, threshold: str) -> np.ndarray:
        if threshold == "upper_limb":
            return self.upper_margin_deg
        if threshold == "center":
            return self.center_margin_deg
        if threshold == "lower_limb":
            return self.lower_margin_deg
        if threshold == "half_disc":
            return self.visible_fraction - 0.5
        raise ValueError(f"unknown threshold {threshold!r}")


def disc_signals(az_deg, el_deg, radius_deg, horizon: Horizon, n_strips: int = DEFAULT_STRIPS) -> DiscSignals:
    """Margins and visible fraction of a disc for every epoch (arrays of equal length).

    Strip k has horizontal offset radius*cos(theta_k) from the centre and
    half-height radius*sin(theta_k), theta_k = k*pi/(K+1). The area weights
    2/(K+1)*sin(theta_k)^2 are those of Gauss-Chebyshev quadrature of the
    second kind, so a fully visible disc gives exactly 1.
    """
    if n_strips % 2 == 0:
        raise ValueError("n_strips must be odd")
    az = np.atleast_1d(np.asarray(az_deg, dtype=np.float64))
    el = np.atleast_1d(np.asarray(el_deg, dtype=np.float64))
    radius = np.atleast_1d(np.asarray(radius_deg, dtype=np.float64))
    theta = np.arange(1, n_strips + 1) * np.pi / (n_strips + 1)
    weights = 2.0 / (n_strips + 1) * np.sin(theta) ** 2
    # Azimuth offsets are stretched by 1/cos(elevation): a fixed angle on the sky
    # spans more azimuth away from the horizontal plane.
    stretch = 1.0 / np.maximum(np.cos(np.radians(el)), 1e-6)
    strip_az = az[:, None] + (radius * stretch)[:, None] * np.cos(theta)[None, :]
    half_height = radius[:, None] * np.sin(theta)[None, :]
    strip_horizon = horizon.elevation_at(strip_az)
    top = el[:, None] + half_height - strip_horizon
    bottom = el[:, None] - half_height - strip_horizon
    visible_part = np.clip(top / (2.0 * half_height), 0.0, 1.0)
    rows = np.arange(az.shape[0])
    i_top, i_bottom = np.argmax(top, axis=1), np.argmin(bottom, axis=1)
    return DiscSignals(
        center_margin_deg=el - horizon.elevation_at(az),
        upper_margin_deg=top[rows, i_top],
        lower_margin_deg=bottom[rows, i_bottom],
        visible_fraction=visible_part @ weights,
        upper_azimuth_deg=strip_az[rows, i_top] % 360.0,
        lower_azimuth_deg=strip_az[rows, i_bottom] % 360.0,
    )


# --------------------------------------------------------------------------- events


@dataclass(frozen=True)
class Event:
    type: str  # "rise" or "set"
    threshold: str  # one of THRESHOLDS
    et_s: float  # TDB seconds past J2000
    azimuth_deg: float  # where on the horizon it happens (limiting strip for limb events)
    center_azimuth_deg: float
    center_elevation_deg: float
    visible_fraction: float
    obstacle_distance_m: float  # NaN when the horizon carries no distances


@dataclass(frozen=True)
class EventResult:
    events: list  # sorted by time
    start_et_s: float
    stop_et_s: float
    initially_visible: dict  # threshold -> bool, state at start_et_s
    scan_step_s: float
    tol_s: float
    n_strips: int


def _signals(direction: DirectionSource, horizon: Horizon, et: np.ndarray, n_strips: int) -> DiscSignals:
    az, el, radius = direction(et)
    return disc_signals(az, el, radius, horizon, n_strips)


def find_events(
    direction: DirectionSource,
    horizon: Horizon,
    start_et_s: float,
    stop_et_s: float,
    scan_step_s: float = DEFAULT_SCAN_STEP_S,
    tol_s: float = DEFAULT_TOL_S,
    thresholds: tuple = THRESHOLDS,
    n_strips: int = DEFAULT_STRIPS,
    chunk: int = 20000,
) -> EventResult:
    """Find every rise and set of the disc between two epochs. See the module text for the accuracy."""
    if stop_et_s <= start_et_s:
        raise ValueError("stop must be after start")
    count = int(math.floor((stop_et_s - start_et_s) / scan_step_s)) + 1
    grid = start_et_s + scan_step_s * np.arange(count)
    if grid[-1] < stop_et_s:
        grid = np.append(grid, stop_et_s)

    sampled = {name: [] for name in thresholds}
    for begin in range(0, grid.size, chunk):
        signals = _signals(direction, horizon, grid[begin : begin + chunk], n_strips)
        for name in thresholds:
            sampled[name].append(signals.signal(name) > 0.0)
    visible = {name: np.concatenate(parts) for name, parts in sampled.items()}

    events: list[Event] = []
    for name in thresholds:
        state = visible[name]
        index = np.nonzero(state[1:] != state[:-1])[0]
        if index.size == 0:
            continue
        low, high = grid[index].copy(), grid[index + 1].copy()
        rising = state[index + 1]  # visible after the crossing
        while np.max(high - low) > tol_s:
            middle = 0.5 * (low + high)
            mid_visible = _signals(direction, horizon, middle, n_strips).signal(name) > 0.0
            same_as_high = mid_visible == rising
            high = np.where(same_as_high, middle, high)
            low = np.where(same_as_high, low, middle)
        times = 0.5 * (low + high)
        az, el, radius = direction(times)
        at_event = disc_signals(az, el, radius, horizon, n_strips)
        where = {"upper_limb": at_event.upper_azimuth_deg, "lower_limb": at_event.lower_azimuth_deg}.get(name, np.asarray(az) % 360.0)
        distance = horizon.distance_at(where)
        for k in range(times.size):
            events.append(
                Event(
                    type="rise" if rising[k] else "set",
                    threshold=name,
                    et_s=float(times[k]),
                    azimuth_deg=float(where[k]),
                    center_azimuth_deg=float(np.asarray(az)[k] % 360.0),
                    center_elevation_deg=float(np.asarray(el)[k]),
                    visible_fraction=float(at_event.visible_fraction[k]),
                    obstacle_distance_m=float(distance[k]),
                )
            )
    events.sort(key=lambda event: event.et_s)
    return EventResult(
        events=events,
        start_et_s=float(start_et_s),
        stop_et_s=float(stop_et_s),
        initially_visible={name: bool(visible[name][0]) for name in thresholds},
        scan_step_s=float(scan_step_s),
        tol_s=float(tol_s),
        n_strips=n_strips,
    )


# --------------------------------------------------------------------------- windows and countdown


@dataclass(frozen=True)
class Windows:
    threshold: str
    intervals_et_s: np.ndarray  # [M, 2]; sorted, disjoint
    open_start: bool  # first interval was already running at the start of the range
    open_end: bool  # last interval is cut by the end of the range: its true end is later

    @property
    def total_s(self) -> float:
        return float(np.sum(self.intervals_et_s[:, 1] - self.intervals_et_s[:, 0])) if self.intervals_et_s.size else 0.0


def windows(result: EventResult, threshold: str) -> Windows:
    """Visibility intervals for one threshold, from the event list."""
    visible = result.initially_visible[threshold]
    opened = result.start_et_s if visible else None
    intervals = []
    for event in result.events:
        if event.threshold != threshold:
            continue
        if event.type == "rise" and opened is None:
            opened = event.et_s
        elif event.type == "set" and opened is not None:
            intervals.append((opened, event.et_s))
            opened = None
    open_end = opened is not None
    if open_end:
        intervals.append((opened, result.stop_et_s))
    return Windows(threshold, np.array(intervals, dtype=np.float64).reshape(-1, 2), bool(visible), open_end)


@dataclass(frozen=True)
class Countdown:
    threshold: str
    visible_now: bool
    seconds: float  # time until the next change of state, or until the end of the range
    bound: str  # "exact", or "at_least" when no further event lies inside the computed range
    next_event_type: str | None  # "set" (visible now), "rise" (hidden now) or None
    next_event_et_s: float | None


def countdown(result: EventResult, threshold: str, now_et_s: float) -> Countdown:
    """Time from ``now_et_s`` until the body next sets (if visible) or rises (if hidden)."""
    if not result.start_et_s <= now_et_s <= result.stop_et_s:
        raise ValueError("the requested time is outside the computed range")
    visible = result.initially_visible[threshold]
    for event in result.events:
        if event.threshold != threshold:
            continue
        if event.et_s <= now_et_s:
            visible = event.type == "rise"
        else:
            return Countdown(threshold, bool(visible), event.et_s - now_et_s, "exact", event.type, event.et_s)
    return Countdown(threshold, bool(visible), result.stop_et_s - now_et_s, "at_least", None, None)


# --------------------------------------------------------------------------- direction sources


def site_direction(site: d.Site, table: d.DirectionTable, body: str) -> DirectionSource:
    """Direction source for one body at one site, from the (interpolated) direction table."""

    def direction(et):
        topo = d.topocentric_from_table(site, d.interpolate_table(table, et))[body]
        return topo.az_deg, topo.el_deg, topo.angular_radius_deg

    return direction
