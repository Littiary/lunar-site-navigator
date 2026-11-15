"""Opportunity calendar and slip tolerance.

Everything here is arithmetic on visibility windows (lsncore.timeline.IntervalSet) that
were computed elsewhere; no new geometry.

* ``lunar_day_periods``: the time axis cut into lunar days. A lunar day begins when the
  Sun crosses the 180 degree meridian of the body-fixed frame (the middle of the far
  side), which is close to new Moon. The definition does not depend on the site, so the
  rows of two sites can be compared directly.
* ``calendar_totals``: visible time per lunar day for any set of windows.
* ``landing_windows``: the set of landing times for which a stated requirement holds.
  It is computed exactly from the window edges, not by trying dates.
* ``slip_report``: how far a planned landing can slip before the requirement fails.
"""

from __future__ import annotations

import numpy as np

from . import packaging as pk
from .results import TimelineResult
from .timeline import IntervalSet, TimeGrid

CONDITION_KINDS = ("visible_at_landing", "continuous_from_landing", "total_in_mission")
_EPS = 1e-9
_LIMIT_TOL_S = 1e-6  # two instants closer than this are the same edge of a window


def lunar_day_periods(et_s, sun_km, domain=None) -> list[dict]:
    """Lunar days inside the time span of a direction table (or inside ``domain``).

    et_s: [N] times of the table records; sun_km: [N, 3] Sun position relative to the
    centre of the Moon in the body-fixed frame. Returns a list of periods
    {"index", "start_et_s", "end_et_s", "complete"}; the first and the last are cut by
    the ends of the span and are marked incomplete.
    """
    et = np.asarray(et_s, dtype=np.float64)
    x, y = np.asarray(sun_km)[:, 0], np.asarray(sun_km)[:, 1]
    start, end = (float(et[0]), float(et[-1])) if domain is None else (float(domain[0]), float(domain[1]))
    # subsolar longitude = 180 deg  <=>  y = 0 with x < 0
    cross = np.flatnonzero((np.sign(y[:-1]) != np.sign(y[1:])) & (x[:-1] < 0) & (x[1:] < 0))
    times = et[cross] + (et[cross + 1] - et[cross]) * (y[cross] / (y[cross] - y[cross + 1]))
    inner = [float(t) for t in times if start < t < end]
    edges = [start] + inner + [end]
    periods = []
    for k in range(len(edges) - 1):
        periods.append(
            {
                "index": k,
                "start_et_s": edges[k],
                "end_et_s": edges[k + 1],
                "complete": 0 < k < len(edges) - 2,
            }
        )
    return periods


def _clip(window: IntervalSet, a: float, b: float) -> list[tuple[float, float]]:
    return [(max(s, a), min(e, b)) for s, e in window.intervals if min(e, b) > max(s, a)]


def calendar_totals(periods: list[dict], windows: dict, longest_outage: bool = False) -> dict:
    """Seconds of each window inside each period: {name: [value per period]}.

    With longest_outage=True the value is instead the longest stretch of the period in
    which the window's condition does not hold (cut at the period boundaries).
    """
    out = {}
    for name, window in windows.items():
        values = []
        for period in periods:
            a, b = period["start_et_s"], period["end_et_s"]
            pieces = _clip(window, a, b)
            if not longest_outage:
                values.append(float(sum(e - s for s, e in pieces)))
                continue
            longest, position = 0.0, a
            for s, e in pieces:
                longest = max(longest, s - position)
                position = e
            values.append(float(max(longest, b - position)))
        out[name] = values
    return out


def _measure_up_to(window: IntervalSet):
    """Function x -> measure(window up to x), piecewise linear."""
    starts = np.array([s for s, _ in window.intervals], dtype=np.float64)
    ends = np.array([e for _, e in window.intervals], dtype=np.float64)

    def measure(x):
        x = np.asarray(x, dtype=np.float64)[..., None]
        return np.sum(np.clip(np.minimum(x, ends) - starts, 0.0, None), axis=-1) if starts.size else np.zeros(x.shape[:-1])

    return measure


def _total_in_mission(window: IntervalSet, duration: float, need: float, first: float, latest: float) -> list[tuple[float, float]]:
    """Landing times t in [first, latest] with measure(window in [t, t + duration]) >= need."""
    if latest <= first:
        return []
    measure = _measure_up_to(window)
    points = {first, latest}
    for s, e in window.intervals:
        for p in (s, e, s - duration, e - duration):
            if first < p < latest:
                points.add(p)
    t = np.array(sorted(points))
    f = measure(t + duration) - measure(t) - need  # linear between consecutive points
    ok = f >= -_EPS * max(1.0, need)
    out = []
    for k in range(t.size - 1):
        a, b, fa, fb = t[k], t[k + 1], f[k], f[k + 1]
        if ok[k] and ok[k + 1]:
            out.append((a, b))
        elif ok[k] or ok[k + 1]:
            zero = a + (b - a) * (fa / (fa - fb))
            out.append((a, zero) if ok[k] else (zero, b))
    return out


def landing_windows(requirement: dict, windows: dict, domain) -> tuple[IntervalSet, dict]:
    """Landing times for which every condition of a requirement holds.

    requirement: {"id", "mission_duration_s" (optional), "conditions": [...]}; a condition is
    {"window": name, "kind": ..., "min_s": seconds}:

    * visible_at_landing:      the window's condition holds at the landing time;
    * continuous_from_landing: it holds without interruption for min_s from landing;
    * total_in_mission:        it holds for at least min_s in total between landing and
                               landing + mission_duration_s.

    Nothing is assumed about the time after the computed range: a landing is feasible
    only if the requirement is proven inside the range. Returns the feasible set and
    {"mission_duration_s", "latest_landing_et_s", "knowledge_limits_et_s"}.

    latest_landing_et_s is the end of the range minus the mission duration: the mission
    must end inside the range, whatever the conditions are. knowledge_limits_et_s are the
    instants at which a landing window can end without an event ending it: latest_landing,
    and for every "continuous from landing" condition whose visibility is still going on
    when the range ends, the end of the range minus min_s. A window that ends at one of
    them is cut by what is known; the truth may extend further.
    """
    start, end = float(domain[0]), float(domain[1])
    duration = float(requirement.get("mission_duration_s", 0.0))
    latest = end - duration
    limits = {latest, end}
    feasible = IntervalSet.full((start, end))
    for condition in requirement["conditions"]:
        kind = condition["kind"]
        window = windows[condition["window"]]
        if kind == "visible_at_landing":
            part = window.intervals
        elif kind == "continuous_from_landing":
            need = float(condition["min_s"])
            # a stretch exactly as long as required admits a single instant, which has no length
            part = [(s, e - need) for s, e in window.intervals if e - s > need]
            if window.intervals and window.intervals[-1][1] >= end - _LIMIT_TOL_S:
                limits.add(end - need)  # visibility beyond the range is unknown
        elif kind == "total_in_mission":
            part = _total_in_mission(window, duration, float(condition["min_s"]), start, end - duration)
        else:
            raise ValueError(f"unknown condition kind {kind!r}; expected one of {CONDITION_KINDS}")
        feasible = feasible.intersection(IntervalSet(part, (start, end)))
    if latest < end:
        feasible = feasible.intersection(IntervalSet([(start, latest)], (start, end))) if latest > start else IntervalSet.empty((start, end))
    return feasible, {"mission_duration_s": duration, "latest_landing_et_s": latest, "knowledge_limits_et_s": sorted(limits)}


def is_knowledge_limit(t, limits) -> bool:
    """True if an instant is one of the knowledge limits of landing_windows."""
    return t is not None and any(abs(float(t) - limit) <= _LIMIT_TOL_S for limit in limits)


def slip_report(feasible: IntervalSet, planned_et_s: float) -> dict:
    """How far a planned landing time can move while the requirement keeps holding.

    slip_tolerance_s: the landing may be delayed by up to this much (0 if the planned
    time itself is not feasible). early_tolerance_s: or advanced by up to this much.
    If the feasible window is cut by the end of the computed range, the tolerance is a
    lower bound. Otherwise the wait for the next window is reported.
    """
    t = float(planned_et_s)
    current = next(((a, b) for a, b in feasible.intervals if a <= t <= b), None)
    later = [(a, b) for a, b in feasible.intervals if a > t]
    nxt = later[0] if later else None
    report = {
        "planned_et_s": t,
        "feasible": current is not None,
        "slip_tolerance_s": 0.0,
        "early_tolerance_s": 0.0,
        "slip_tolerance_is_lower_bound": False,
        "window_start_et_s": None,
        "window_end_et_s": None,
        "next_window_start_et_s": None if nxt is None else nxt[0],
        "next_window_length_s": None if nxt is None else nxt[1] - nxt[0],
        "wait_s": None,
        "wait_after_window_s": None,
    }
    if current is not None:
        report.update(
            slip_tolerance_s=current[1] - t,
            early_tolerance_s=t - current[0],
            slip_tolerance_is_lower_bound=bool(current[1] >= feasible.domain[1]),
            window_start_et_s=current[0],
            window_end_et_s=current[1],
            wait_s=0.0,
            wait_after_window_s=None if nxt is None else nxt[0] - current[1],
        )
    elif nxt is not None:
        report["wait_s"] = nxt[0] - t
    return report


CALENDAR_DEFINITION = (
    "A lunar day begins when the Sun crosses the 180 degree meridian of the body-fixed frame "
    "(the middle of the far side, close to new Moon). The periods do not depend on the site. "
    "The first and the last period are cut by the ends of the computed range."
)
_QUANTITIES = (
    ("sun_visible_s", "Time with the Sun visible", "sun_visible", False),
    ("sun_longest_outage_s", "Longest stretch without the Sun inside the lunar day", "sun_visible", True),
    ("sun_lit_s", "Time with the Sun visible and not totally eclipsed by the Earth", "sun_lit", False),
    ("earth_visible_s", "Time with the Earth visible", "earth_visible", False),
    ("earth_longest_outage_s", "Longest stretch without the Earth inside the lunar day", "earth_visible", True),
    ("sun_and_earth_visible_s", "Time with the Sun and the Earth visible together", "sun_and_earth_visible", False),
)


def add_calendar_to_timeline(
    timeline: TimelineResult,
    table_package,
    n_heights: int,
    requirements: list | None,
    planned_landing_et_s: float | None,
    et_to_utc,
) -> None:
    """Add the lunar-day calendar and, for every stated requirement, the landing windows
    and the slip tolerance of the planned landing to a site timeline.

    Returns sentences for the warnings of the package: a planned landing that lies after
    what can be judged gets no slip report (it is neither feasible nor infeasible), and
    the package says so.
    """
    grid = TimeGrid.from_contract(timeline.time)
    domain = (grid.start_et_s, grid.end_et_s)
    table = table_package.manifest
    sun_km = table_package.array(table["positions_km"])[:, table["bodies"].index("SUN"), :]
    periods = lunar_day_periods(TimeGrid.from_contract(table["time"]).times(), sun_km, domain)

    quantities = []
    for qid, label, window_id, outage in _QUANTITIES:
        try:
            windows = [timeline.window(window_id, h) for h in range(n_heights)]
        except KeyError:
            continue
        quantities.append(
            {
                "id": qid,
                "label": label,
                "unit": "s",
                "window": window_id,
                "values": [calendar_totals(periods, {"w": w}, longest_outage=outage)["w"] for w in windows],
                "method": pk.M_CALENDAR,
            }
        )
    timeline.calendar = {
        "period": "lunar_day",
        "definition": CALENDAR_DEFINITION,
        "method": pk.M_CALENDAR,
        "periods": [
            {**period, "start_utc": et_to_utc(period["start_et_s"]), "end_utc": et_to_utc(period["end_et_s"])} for period in periods
        ],
        "quantities": quantities,
    }
    notes: list[str] = []
    if not requirements:
        return notes

    opportunities = []
    for requirement in requirements:
        names = {condition["window"] for condition in requirement["conditions"]}
        for h in range(n_heights):
            try:
                windows = {name: timeline.window(name, h) for name in names}
            except KeyError as err:
                raise ValueError(f"requirement {requirement['id']!r} names a window the timeline does not have: {err}") from None
            feasible, info = landing_windows(requirement, windows, domain)
            latest = info["latest_landing_et_s"]
            limits = info["knowledge_limits_et_s"]
            judged_until = min(limits)
            lengths = [b - a for a, b in feasible.intervals]
            planned = None
            if planned_landing_et_s is not None and judged_until + _LIMIT_TOL_S < planned_landing_et_s <= domain[1]:
                note = (
                    f"opportunities: the planned landing {et_to_utc(planned_landing_et_s)} lies after the last landing time that can be judged "
                    f"for requirement '{requirement['id']}' ({et_to_utc(judged_until)}); it gets no slip report, which says neither that it is feasible nor that it is not"
                )
                if note not in notes:
                    notes.append(note)
            elif planned_landing_et_s is not None and domain[0] <= planned_landing_et_s <= domain[1]:
                report = slip_report(feasible, planned_landing_et_s)
                cut = is_knowledge_limit(report["window_end_et_s"], limits)
                planned = {
                    "utc": et_to_utc(planned_landing_et_s),
                    "et_s": float(planned_landing_et_s),
                    "feasible": report["feasible"],
                    "slip_tolerance_s": report["slip_tolerance_s"],
                    "early_tolerance_s": report["early_tolerance_s"],
                    "slip_tolerance_is_lower_bound": bool(report["slip_tolerance_is_lower_bound"] or cut),
                    "wait_s": report["wait_s"],
                    "wait_after_window_s": report["wait_after_window_s"],
                    "next_window_start_utc": None if report["next_window_start_et_s"] is None else et_to_utc(report["next_window_start_et_s"]),
                    "next_window_length_s": report["next_window_length_s"],
                }
            opportunities.append(
                {
                    "requirement_id": requirement["id"],
                    "height_index": h,
                    "landing_windows_et_s": feasible.as_list(),
                    "landing_windows_utc": [[et_to_utc(a), et_to_utc(b)] for a, b in feasible.intervals],
                    "clipped_start": bool(feasible.clipped_start),
                    "clipped_end": bool(lengths and is_knowledge_limit(feasible.intervals[-1][1], limits)),
                    "latest_landing_et_s": float(latest),
                    "latest_landing_utc": et_to_utc(latest),
                    "feasible_fraction": float(feasible.total_s() / (latest - domain[0])) if latest > domain[0] else 0.0,
                    "window_count": len(lengths),
                    "longest_window_s": float(max(lengths, default=0.0)),
                    "median_window_s": float(np.median(lengths)) if lengths else None,
                    "feasible_s_per_period": calendar_totals(periods, {"f": feasible})["f"],
                    "planned_landing": planned,
                    "method": pk.M_OPPORTUNITY,
                }
            )
    timeline.opportunities = opportunities
    return notes
