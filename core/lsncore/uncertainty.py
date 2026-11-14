"""How the visibility windows move if the inputs are a little different.

Two separate questions, each with a stated assumption and nothing more:

* **Horizon error.** If the whole horizon profile may be too low or too high by a stated
  angle, which times are visible in either case (certain), in at least one case
  (possible), and in between (uncertain)? The assumption is one common shift of the
  profile, the same at every azimuth. That is the unfavourable case for an event time: a
  shift cannot average out along the limb.
* **Landing point.** If the lander may come down anywhere inside a stated ellipse, what do
  the windows look like at sample points of that ellipse? Each point gets its own
  horizon and its own local vertical. The points fill the ellipse evenly in area; they
  are a survey of the ellipse, not a probability statement, unless the reader supplies
  the distribution.

The two are not combined.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import packaging as pk
from .geometry import destination
from .results import TimelineResult
from .timeline import IntervalSet, TimeGrid

_GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))
_EVENT_SLACK_S = 1.0


def ellipse_points(lat_deg: float, lon_deg: float, semi_major_m: float, semi_minor_m: float, azimuth_deg: float, count: int, radius_m: float) -> np.ndarray:
    """Sample points of an ellipse on the sphere, as [count, 2] latitude and longitude.

    The first point is the centre. The others follow a sunflower pattern, which covers the
    ellipse evenly in area and puts the last point on the boundary. The major axis points
    along azimuth_deg (clockwise from north). The pattern is fixed: the same request
    always gives the same points.
    """
    if count < 1:
        raise ValueError("count must be at least 1")
    k = np.arange(count, dtype=np.float64)
    r = np.sqrt(k / max(count - 1, 1))
    theta = k * _GOLDEN_ANGLE
    u = semi_major_m * r * np.cos(theta)  # along the major axis
    v = semi_minor_m * r * np.sin(theta)  # across it, towards azimuth + 90 deg
    lat, lon = destination(lat_deg, lon_deg, azimuth_deg + np.degrees(np.arctan2(v, u)), np.hypot(u, v) / radius_m)
    points = np.stack([np.asarray(lat, dtype=np.float64), np.asarray(lon, dtype=np.float64)], axis=1)
    points[0] = (lat_deg, lon_deg)
    return points


@dataclass
class Band:
    """Visibility windows for a horizon that may be off by +-error_deg."""

    nominal: IntervalSet
    certain: IntervalSet  # visible even if the horizon is error_deg higher
    possible: IntervalSet  # visible if the horizon is error_deg lower
    uncertain: IntervalSet  # possible and not certain
    error_deg: float


def visibility_window(direction, elevation_deg, step_deg: float, domain, rule) -> IntervalSet:
    """Window of one visibility rule for a direction source over a horizon profile."""
    from .events import finder

    profile = finder.Horizon(0.0, float(step_deg), np.asarray(elevation_deg, dtype=np.float64))
    result = finder.find_events(direction, profile, float(domain[0]), float(domain[1]), thresholds={"visible": rule})
    return IntervalSet(finder.windows(result, "visible").intervals_et_s, (float(domain[0]), float(domain[1])))


def horizon_error_band(direction, elevation_deg, step_deg: float, domain, rule, error_deg: float, nominal: IntervalSet | None = None) -> Band:
    """Windows for the profile as given, raised by error_deg and lowered by error_deg."""
    elevation = np.asarray(elevation_deg, dtype=np.float64)
    if nominal is None:
        nominal = visibility_window(direction, elevation, step_deg, domain, rule)
    if error_deg <= 0.0:
        return Band(nominal, nominal, nominal, IntervalSet.empty(nominal.domain), 0.0)
    certain = visibility_window(direction, elevation + error_deg, step_deg, domain, rule)
    possible = visibility_window(direction, elevation - error_deg, step_deg, domain, rule)
    # Raising a horizon can only hide, lowering it can only reveal. Event times are located
    # to a fraction of a second, so the three sets are made consistent to that level.
    certain = certain.intersection(nominal)
    possible = possible.union(nominal)
    return Band(nominal, certain, possible, possible.intersection(certain.complement()), float(error_deg))


def event_time_bounds(event_times, band: Band) -> list[tuple[float, float]]:
    """Earliest and latest time of each event under the stated horizon error.

    An event of the nominal windows lies inside one interval of the uncertain set; that
    interval is its range. An event outside every such interval keeps its own time.
    """
    out = []
    for t in event_times:
        hit = next(((a, b) for a, b in band.uncertain.intervals if a - _EVENT_SLACK_S <= t <= b + _EVENT_SLACK_S), None)
        out.append(hit if hit is not None else (float(t), float(t)))
    return out


def windows_over_points(points, direction_for, horizon_for, domain, rule) -> list[IntervalSet]:
    """The visibility window at every sample point.

    direction_for(lat, lon) returns the direction source of the body seen from that
    point; horizon_for(lat, lon) returns (elevation profile, azimuth step) there.
    """
    sets = []
    for lat, lon in np.asarray(points, dtype=np.float64):
        elevation, step = horizon_for(float(lat), float(lon))
        sets.append(visibility_window(direction_for(float(lat), float(lon)), elevation, step, domain, rule))
    return sets


def ellipse_summary(sets: list[IntervalSet], grid: TimeGrid) -> dict:
    """What the windows of the sample points have in common and how they differ.

    all_points: times at which the condition holds at every point; any_point: at one point
    at least; share: at every sample of the grid, the share of the points at which it
    holds; totals_s and their minimum, median and maximum; centre_s is the first point.
    """
    all_points, any_point = sets[0], sets[0]
    for s in sets[1:]:
        all_points = all_points.intersection(s)
        any_point = any_point.union(s)
    t = grid.times()
    share = np.zeros(t.size)
    for s in sets:
        if len(s):
            starts = np.array([a for a, _ in s.intervals])
            ends = np.array([b for _, b in s.intervals])
            share += np.any((t[:, None] >= starts) & (t[:, None] <= ends), axis=1)
    totals = [s.total_s() for s in sets]
    return {
        "all_points": all_points,
        "any_point": any_point,
        "share": share / len(sets),
        "totals_s": totals,
        "centre_s": totals[0],
        "min_s": float(np.min(totals)),
        "median_s": float(np.median(totals)),
        "max_s": float(np.max(totals)),
    }


HORIZON_ERROR_ASSUMPTION = (
    "The whole horizon profile is shifted up or down by the stated angle, the same at every "
    "azimuth and for every observer height. 'Certain' holds even with the horizon that much "
    "higher than computed; 'possible' needs it that much lower. Other error sources (ephemeris, "
    "landing position, observer height) are not in this band."
)
ELLIPSE_ASSUMPTION = (
    "The landing point may be anywhere inside the stated ellipse on the reference sphere. The "
    "sample points fill the ellipse evenly in area (sunflower pattern, the centre first). Every "
    "point has its own terrain horizon and its own local vertical. The share of points is a "
    "survey of the ellipse, not a probability, and it is not combined with the horizon error."
)


def add_uncertainty_to_timeline(timeline: TimelineResult, error_deg: float | None, bands: dict | None, ellipse: dict | None, et_to_utc) -> None:
    """Write the band of a stated horizon error and the survey of a landing ellipse into a timeline.

    bands maps (body, height index) to a Band. ellipse is
    {"spec": the stated ellipse, "height_index": int, "points": [K, 2] latitude and longitude,
     "surface_height_m": [K], "sets": {body: [IntervalSet per point]}}.
    """
    grid = TimeGrid.from_contract(timeline.time)
    out = {}
    if bands:
        for (body, h), band in sorted(bands.items()):
            tag = body.lower()
            timeline.windows.append(pk.window_record(f"{tag}_visible_certain", body, h, f"{body} visible even if the terrain horizon is {error_deg:g} deg higher than computed", band.certain, et_to_utc, pk.M_HORIZON_ERROR))
            timeline.windows.append(pk.window_record(f"{tag}_visible_possible", body, h, f"{body} visible if the terrain horizon is {error_deg:g} deg lower than computed", band.possible, et_to_utc, pk.M_HORIZON_ERROR))
            timeline.windows.append(pk.window_record(f"{tag}_visible_uncertain", body, h, f"{body} visible or not, depending on a horizon error of up to {error_deg:g} deg", band.uncertain, et_to_utc, pk.M_HORIZON_ERROR))
            timeline.metrics.append(pk.metric_record(f"{tag}_visible_certain_s", f"Time with {body} visible even if the horizon is {error_deg:g} deg higher", band.certain.total_s(), "s", h, pk.M_HORIZON_ERROR))
            timeline.metrics.append(pk.metric_record(f"{tag}_visible_possible_s", f"Time with {body} visible if the horizon is {error_deg:g} deg lower", band.possible.total_s(), "s", h, pk.M_HORIZON_ERROR))
            timeline.metrics.append(pk.metric_record(f"{tag}_visible_uncertain_s", f"Time in which a horizon error of {error_deg:g} deg decides whether {body} is visible", band.uncertain.total_s(), "s", h, pk.M_HORIZON_ERROR))
            mine = [event for event in timeline.events if event["body"] == body and event["height_index"] == h]
            for event, (a, b) in zip(mine, event_time_bounds([event["et_s"] for event in mine], band)):
                a, b = min(a, event["et_s"]), max(b, event["et_s"])
                event.update(earliest_et_s=a, latest_et_s=b, earliest_utc=et_to_utc(a), latest_utc=et_to_utc(b))
        out["horizon_error"] = {"error_deg": float(error_deg), "assumption": HORIZON_ERROR_ASSUMPTION, "method": pk.M_HORIZON_ERROR}
    if ellipse:
        h = int(ellipse["height_index"])
        stats, per_point = {}, {}
        for body, sets in ellipse["sets"].items():
            tag = body.lower()
            kept = [s for s in sets if s is not None]
            summary = ellipse_summary(kept, grid)
            timeline.windows.append(pk.window_record(f"{tag}_visible_all_points", body, h, f"{body} visible at every sample point of the landing ellipse", summary["all_points"], et_to_utc, pk.M_ELLIPSE))
            timeline.windows.append(pk.window_record(f"{tag}_visible_any_point", body, h, f"{body} visible at one sample point of the landing ellipse at least", summary["any_point"], et_to_utc, pk.M_ELLIPSE))
            timeline.series[body].ellipse_visible_share = summary["share"]
            stats[body] = {key: float(summary[key]) for key in ("centre_s", "min_s", "median_s", "max_s")}
            per_point[body] = [None if s is None else s.total_s() for s in sets]
        spec = ellipse["spec"]
        out["landing_ellipse"] = {
            "semi_major_m": float(spec["semi_major_m"]),
            "semi_minor_m": float(spec["semi_minor_m"]),
            "azimuth_deg": float(spec["azimuth_deg"]),
            "height_index": h,
            "assumption": ELLIPSE_ASSUMPTION,
            "points": [
                {
                    "lat_deg": float(lat),
                    "lon_deg": float(lon),
                    "surface_height_m": None if height is None or not math.isfinite(height) else float(height),
                    "visible_s": {body: per_point[body][k] for body in per_point},
                }
                for k, ((lat, lon), height) in enumerate(zip(ellipse["points"], ellipse["surface_height_m"]))
            ],
            "visible_s": stats,
            "method": pk.M_ELLIPSE,
        }
    timeline.uncertainty = out or None
