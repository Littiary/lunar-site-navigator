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
_RANGE_EDGE_S = 1e-6  # a time within this of an end of the computed range is that end
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


def horizon_error_profile(distance_m, common_deg: float | None = 0.0, dem_height_error_m: float | None = None) -> np.ndarray:
    """Horizon error per azimuth from the stated assumptions.

    common_deg is added at every azimuth. dem_height_error_m is a height error of the
    terrain point that sets the horizon: seen from the site it is atan(error / distance),
    large for near terrain and small for far terrain. Azimuths without a known limiting
    point get the common part only.
    """
    distance = np.asarray(distance_m, dtype=np.float64)
    error = np.full(distance.shape, float(common_deg or 0.0))
    if dem_height_error_m is not None and np.any(np.nan_to_num(np.asarray(dem_height_error_m, dtype=np.float64)) > 0.0):
        height = np.broadcast_to(np.nan_to_num(np.asarray(dem_height_error_m, dtype=np.float64)), distance.shape)  # one value, or one per azimuth
        with np.errstate(invalid="ignore", divide="ignore"):
            angle = np.degrees(np.arctan(height / distance))
        error = error + np.where(np.isfinite(distance) & (distance > 0.0), angle, 0.0)
    return error


def terrain_slope_deg(terrain, lon_deg, lat_deg, baseline_m) -> np.ndarray:
    """Slope of the terrain at points, in degrees: central differences over one baseline
    to the north and south and to the east and west of each point (the baseline is the
    pixel of the product the point is read from, as in the data stream's slope classes)."""
    lat = np.radians(np.atleast_1d(np.asarray(lat_deg, dtype=np.float64)))
    lon = np.radians(np.atleast_1d(np.asarray(lon_deg, dtype=np.float64)))
    base = np.broadcast_to(np.asarray(baseline_m, dtype=np.float64), lat.shape)
    arc = base / float(terrain.reference_radius_m)
    sl, cl, so, co = np.sin(lat), np.cos(lat), np.sin(lon), np.cos(lon)
    up = np.stack([cl * co, cl * so, sl], axis=-1)
    east = np.stack([-so, co, np.zeros_like(so)], axis=-1)
    north = np.stack([-sl * co, -sl * so, cl], axis=-1)

    def height(direction, sign):
        p = np.cos(arc)[:, None] * up + sign * np.sin(arc)[:, None] * direction
        return np.asarray(terrain.height_m(np.degrees(np.arctan2(p[:, 1], p[:, 0])), np.degrees(np.arctan2(p[:, 2], np.hypot(p[:, 0], p[:, 1])))), dtype=np.float64)

    span = 2.0 * float(terrain.reference_radius_m) * np.sin(arc)
    d_north = (height(north, 1.0) - height(north, -1.0)) / span
    d_east = (height(east, 1.0) - height(east, -1.0)) / span
    return np.degrees(np.arctan(np.hypot(d_north, d_east)))


def height_error_for_points(model: dict, product_ids, rms_error_m, slope_deg) -> tuple[np.ndarray, np.ndarray]:
    """Height error of terrain points after a stated model, and where each value came from.

    The model is either {"constant_m": x} or {"rules": {pattern: rule}}; a pattern is a
    product id with '*' as wildcard, the most specific pattern that fits a product applies.
    A rule is {"rms_map_factor": f, "flat_m": x} (f times the product's error map at the
    pixel, x where the map is empty) or {"slope_classes": [{"up_to_deg", "error_m"}, ...]}.
    Returns the errors in metres (NaN where there is no terrain point) and the sources:
    'rms_map', 'flat', 'slope_class' or 'constant'.
    """
    import fnmatch

    ids = np.asarray(product_ids, dtype=object)
    rms = np.broadcast_to(np.asarray(rms_error_m, dtype=np.float64), ids.shape)
    slope = np.broadcast_to(np.asarray(slope_deg, dtype=np.float64), ids.shape)
    error = np.full(ids.shape, np.nan)
    source = np.full(ids.shape, "", dtype=object)
    todo = ids != ""
    if "constant_m" in model:
        error[todo], source[todo] = float(model["constant_m"]), "constant"
        return error, source
    rules = model["rules"]
    for pattern in sorted(rules, key=lambda text: (text == "*", -len(text))):
        rule = rules[pattern]
        fits = {pid: fnmatch.fnmatchcase(str(pid), pattern) for pid in set(ids.ravel())}
        sel = todo & np.vectorize(fits.get, otypes=[bool])(ids)
        if not sel.any():
            continue
        if "rms_map_factor" in rule:
            mapped = sel & np.isfinite(rms)
            error[mapped], source[mapped] = float(rule["rms_map_factor"]) * rms[mapped], "rms_map"
            empty = sel & ~np.isfinite(rms)
            error[empty], source[empty] = float(rule["flat_m"]), "flat"
        else:
            classes = sorted(rule["slope_classes"], key=lambda c: c["up_to_deg"])
            value = np.full(ids.shape, float(classes[-1]["error_m"]))  # unknown slope: the steepest class
            for c in reversed(classes):
                value = np.where(slope <= c["up_to_deg"], float(c["error_m"]), value)
            error[sel], source[sel] = value[sel], "slope_class"
        todo &= ~sel
    return error, source


def horizon_error_band(direction, elevation_deg, step_deg: float, domain, rule, error_deg, nominal: IntervalSet | None = None) -> Band:
    """Windows for the profile as given, raised by error_deg and lowered by error_deg.

    error_deg is one number or one value per azimuth of the profile.
    """
    elevation = np.asarray(elevation_deg, dtype=np.float64)
    if nominal is None:
        nominal = visibility_window(direction, elevation, step_deg, domain, rule)
    error = np.asarray(error_deg, dtype=np.float64)
    if not np.any(error > 0.0):
        return Band(nominal, nominal, nominal, IntervalSet.empty(nominal.domain), 0.0)
    certain = visibility_window(direction, elevation + error, step_deg, domain, rule)
    possible = visibility_window(direction, elevation - error, step_deg, domain, rule)
    return band_from_windows(nominal, certain, possible, float(error.max()))


def band_from_windows(nominal: IntervalSet, raised: IntervalSet, lowered: IntervalSet, error_deg: float) -> Band:
    """The band from the windows over the raised and over the lowered horizon.

    Raising a horizon can only hide, lowering it can only reveal. Event times are located
    to a fraction of a second, so the three sets are made consistent to that level.
    """
    certain = raised.intersection(nominal)
    possible = lowered.union(nominal)
    return Band(nominal, certain, possible, possible.intersection(certain.complement()), float(error_deg))


_TABLES: dict = {}


def window_job(lon_deg: float, lat_deg: float, height_km: float, table_dir: str, body: str, profile, step_deg: float, domain, threshold: dict) -> list:
    """One visibility window, from plain arguments, so that it can run in another process.

    Returns the intervals; the caller builds the IntervalSet. The result does not depend
    on the process it runs in.
    """
    from .ephem import directions as d
    from .ephem import kernels
    from .ephem import table as ephem_table
    from .events import finder

    kernels.load()
    if table_dir not in _TABLES:
        _TABLES[table_dir] = ephem_table.load_table(table_dir)
    direction = finder.site_direction(d.Site(float(lon_deg), float(lat_deg), float(height_km)), _TABLES[table_dir], body)
    rule = finder.threshold_from_contract(threshold, "visible")
    return visibility_window(direction, np.asarray(profile, dtype=np.float64), step_deg, domain, rule).as_list()


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


COMMON_SHIFT_ASSUMPTION = (
    "The whole horizon profile is shifted up or down by the stated angle, the same at every "
    "azimuth and for every observer height."
)
HEIGHT_ERROR_ASSUMPTION = (
    "The terrain point that sets the horizon in each azimuth may be higher or lower than the "
    "elevation model says by the stated height; seen from the site that is atan(height error / "
    "distance), so near terrain gets a wide band and far terrain a narrow one. The same sign is "
    "assumed at every azimuth."
)
BAND_READING = (
    "'Certain' holds even with the horizon that much higher than computed; 'possible' needs it "
    "that much lower. Other error sources (ephemeris, landing position, observer height) are not "
    "in this band."
)


def horizon_error_assumption(stated: dict) -> str:
    parts = []
    if stated.get("horizon_error_deg"):
        parts.append(COMMON_SHIFT_ASSUMPTION)
    if stated.get("dem_height_error_model"):
        parts.append(HEIGHT_ERROR_ASSUMPTION + " The height is taken from the stated model: " + str(stated["dem_height_error_model"].get("label", "")) + ".")
    elif stated.get("dem_height_error_m"):
        parts.append(HEIGHT_ERROR_ASSUMPTION)
    if len(parts) == 2:
        parts.append("The two are added.")
    return " ".join(parts + [BAND_READING])


def _error_words(stated: dict) -> str:
    words = []
    if stated.get("horizon_error_deg"):
        words.append(f"a horizon error of {stated['horizon_error_deg']:g} deg")
    if stated.get("dem_height_error_model"):
        words.append(f"the terrain height error of the stated model ({stated['dem_height_error_model'].get('id', 'unnamed')})")
    elif stated.get("dem_height_error_m"):
        words.append(f"a terrain height error of {stated['dem_height_error_m']:g} m")
    return " and ".join(words)


ELLIPSE_ASSUMPTION = (
    "The landing point may be anywhere inside the stated ellipse on the reference sphere. The "
    "sample points fill the ellipse evenly in area (sunflower pattern, the centre first). Every "
    "point has its own terrain horizon and its own local vertical. The share of points is a "
    "survey of the ellipse, not a probability, and it is not combined with the horizon error."
)


def add_uncertainty_to_timeline(
    timeline: TimelineResult, stated: dict, bands: dict | None, ellipse: dict | None, et_to_utc, applied_error_deg: dict | None = None,
    quality: list | None = None, azimuth_step_deg: float | None = None, default_index: int = 0,
) -> None:
    """Write the band of a stated horizon error and the survey of a landing ellipse into a timeline.

    stated is the scenario's uncertainty object. bands maps (body, height index) to a Band.
    applied_error_deg gives the least, median and largest horizon error used at the default
    observer height. ellipse is
    {"spec": the stated ellipse, "height_index": int, "points": [K, 2] latitude and longitude,
     "surface_height_m": [K], "sets": {body: [IntervalSet per point]}}.
    """
    grid = TimeGrid.from_contract(timeline.time)
    out = {}
    if bands:
        what = _error_words(stated)
        for (body, h), band in sorted(bands.items()):
            tag = body.lower()
            timeline.windows.append(pk.window_record(f"{tag}_visible_certain", body, h, f"{body} visible even if the terrain horizon is higher than computed by {what}", band.certain, et_to_utc, pk.M_HORIZON_ERROR))
            timeline.windows.append(pk.window_record(f"{tag}_visible_possible", body, h, f"{body} visible if the terrain horizon is lower than computed by {what}", band.possible, et_to_utc, pk.M_HORIZON_ERROR))
            timeline.windows.append(pk.window_record(f"{tag}_visible_uncertain", body, h, f"{body} visible or not, depending on {what}", band.uncertain, et_to_utc, pk.M_HORIZON_ERROR))
            timeline.metrics.append(pk.metric_record(f"{tag}_visible_certain_s", f"Time with {body} visible even with the horizon higher by {what}", band.certain.total_s(), "s", h, pk.M_HORIZON_ERROR))
            timeline.metrics.append(pk.metric_record(f"{tag}_visible_possible_s", f"Time with {body} visible with the horizon lower by {what}", band.possible.total_s(), "s", h, pk.M_HORIZON_ERROR))
            timeline.metrics.append(pk.metric_record(f"{tag}_visible_uncertain_s", f"Time in which {what} decides whether {body} is visible", band.uncertain.total_s(), "s", h, pk.M_HORIZON_ERROR))
            mine = [event for event in timeline.events if event["body"] == body and event["height_index"] == h]
            for event, (a, b) in zip(mine, event_time_bounds([event["et_s"] for event in mine], band)):
                a, b = min(a, event["et_s"]), max(b, event["et_s"])
                # A bound that lies on an end of the computed range is not a bound of the event:
                # the band runs on beyond the range, and nothing is known there.
                event.update(
                    earliest_et_s=a, latest_et_s=b, earliest_utc=et_to_utc(a), latest_utc=et_to_utc(b),
                    earliest_clipped=bool(a <= grid.start_et_s + _RANGE_EDGE_S), latest_clipped=bool(b >= grid.end_et_s - _RANGE_EDGE_S),
                )
        block = {}
        if stated.get("horizon_error_deg"):
            block["error_deg"] = float(stated["horizon_error_deg"])
        if stated.get("dem_height_error_model"):
            model = stated["dem_height_error_model"]
            block["dem_height_error_model"] = {key: str(model.get(key, "")) for key in ("id", "label", "source")}
        elif stated.get("dem_height_error_m"):
            block["dem_height_error_m"] = float(stated["dem_height_error_m"])
        if quality is not None:
            # What fed the band: per event the limiting horizon sample at the event's azimuth,
            # and over the whole profile at the default height.
            pixel = {1: "constrained", 0: "interpolated"}
            for event in timeline.events:
                q = quality[event["height_index"]]
                j = int(round(event["azimuth_deg"] / azimuth_step_deg)) % q["error_m"].size
                value = float(q["error_m"][j])
                event["terrain_quality"] = {
                    "band_source": str(q["source"][j]) or "none",
                    "height_error_m": value if np.isfinite(value) else None,
                    "limiting_pixel": pixel.get(int(q["constrained"][j]), "unknown"),
                    "product_id": str(q["product_id"][j]),
                }
            q = quality[default_index]
            known = np.isfinite(q["error_m"])
            if known.any():
                block["applied_height_error_m"] = {"min": float(q["error_m"][known].min()), "median": float(np.median(q["error_m"][known])), "max": float(q["error_m"][known].max())}
                shares = [(float(np.mean(q["source"][known] == name)), str(name)) for name in sorted(set(q["source"][known]))]
                block["sources"] = [{"source": name, "azimuth_share": share} for share, name in sorted(shares, reverse=True)]
                counted = q["constrained"][known]
                block["limiting_pixels"] = {"constrained": float(np.mean(counted == 1)), "interpolated": float(np.mean(counted == 0)), "unknown": float(np.mean(counted < 0))}
        if applied_error_deg is not None:
            block["applied_error_deg"] = {key: float(applied_error_deg[key]) for key in ("min", "median", "max")}
        block["assumption"] = horizon_error_assumption(stated)
        block["method"] = pk.M_HORIZON_ERROR
        out["horizon_error"] = block
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
