"""Which terrain limits the view of a body, and what it costs.

Three pieces, all independent of where the direction of the body comes from:

* ``blocker_azimuth_index``: for every instant, the horizon sample that limits the view
  of the disc. For a hidden disc under the "any part visible" convention this is where the
  disc is closest to showing: the place its first light will appear.
* ``attribute_time``: splitting a set of time intervals between labels given per sample.
* ``blocking_report``: time lost to terrain compared with a smooth sphere (and time gained
  where the terrain lies below the smooth horizon), split between the obstacles.

"Lost" is defined with the visibility windows, not with samples:
lost = visible over a smooth sphere AND NOT visible over the terrain. The windows come
from the event finder, so the totals have its accuracy. The split between obstacles uses
the sampled series: each sample stands for the half step before and after it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import packaging as pk
from .obstacles import ObstacleMap
from .results import HorizonResult, TimelineResult
from .timeline import IntervalSet, TimeGrid

LIMBS = ("upper_limb", "center", "lower_limb")
_MAX_STRETCH = 1.0 / math.cos(math.radians(80.0))


def limb_of_threshold(threshold: dict) -> str:
    """The part of the disc a contract threshold is decided on."""
    if threshold["quantity"] == "visible_fraction":
        if threshold["value"] <= 0.0:
            return "upper_limb"
        if threshold["value"] >= 1.0:
            return "lower_limb"
    return "center"


def blocker_azimuth_index(azimuth_deg, elevation_deg, angular_radius_deg, horizon_elevation_deg, step_deg: float, limb: str) -> np.ndarray:
    """Index of the horizon sample that limits the view of a disc; shape [H, N].

    center:      the sample nearest to the azimuth of the disc centre.
    upper_limb:  among the samples under the disc, the one where the upper edge of the disc
                 stands highest above the horizon (least hidden).
    lower_limb:  among the samples under the disc, the one where the horizon reaches
                 highest above the lower edge of the disc.
    """
    if limb not in LIMBS:
        raise ValueError(f"limb must be one of {LIMBS}")
    az = np.asarray(azimuth_deg, dtype=np.float64)
    el = np.asarray(elevation_deg, dtype=np.float64)
    r = np.asarray(angular_radius_deg, dtype=np.float64)
    hz = np.atleast_2d(np.asarray(horizon_elevation_deg, dtype=np.float64))
    n_h, n_az = hz.shape
    nearest = np.rint(az / step_deg).astype(np.int64)
    if limb == "center":
        return np.broadcast_to((nearest % n_az).astype(np.int32), (n_h, az.size)).copy()

    stretch = np.minimum(1.0 / np.maximum(np.cos(np.radians(el)), 1e-12), _MAX_STRETCH)
    n_side = int(math.ceil(float(np.max(r * stretch)) / step_deg)) + 1
    cand = nearest[:, None] + np.arange(-n_side, n_side + 1)[None, :]  # [N, C]
    x = (cand * step_deg - az[:, None]) / stretch[:, None]  # offset on the sky, degrees
    inside = np.abs(x) <= r[:, None]
    inside[:, n_side] = True  # the nearest sample always counts
    cap = np.sqrt(np.maximum(r[:, None] ** 2 - x * x, 0.0))
    profile = hz[:, cand % n_az]  # [H, N, C]
    with np.errstate(invalid="ignore"):
        if limb == "upper_limb":
            score = (el[:, None] + cap)[None] - profile
        else:
            score = profile - (el[:, None] - cap)[None]
    score = np.where(inside[None] & np.isfinite(score), score, -np.inf)
    best = np.argmax(score, axis=2)  # [H, N]
    return (np.take_along_axis(np.broadcast_to(cand, (n_h,) + cand.shape), best[..., None], axis=2)[..., 0] % n_az).astype(np.int32)


def attribute_time(grid: TimeGrid, intervals: IntervalSet, labels) -> dict:
    """Split time intervals between the labels of the samples they cover.

    Sample i stands for the time from half a step before it to half a step after it.
    Returns {label: {"seconds": float, "intervals": IntervalSet}}; the seconds add up to
    the total length of the intervals.
    """
    labels = np.asarray(labels)
    if labels.shape != (grid.count,):
        raise ValueError("labels must have one entry per grid sample")
    t0, step = grid.start_et_s, grid.step_s
    pieces: dict = {}
    for a, b in intervals.intervals:
        i = int(min(max(math.floor((a - t0) / step + 0.5), 0), grid.count - 1))
        start = a
        while True:
            edge = t0 + (i + 0.5) * step
            end = b if (edge >= b or i == grid.count - 1) else edge
            label = labels[i].item()
            runs = pieces.setdefault(label, [])
            if runs and runs[-1][1] == start:
                runs[-1][1] = end
            else:
                runs.append([start, end])
            if end >= b:
                break
            start, i = end, i + 1
    return {
        label: {"seconds": float(sum(e - s for s, e in runs)), "intervals": IntervalSet(runs, intervals.domain)}
        for label, runs in pieces.items()
    }


@dataclass
class BlockingReport:
    body: str
    height_index: int
    blocker_azimuth_index: np.ndarray  # [N] int32
    lost: IntervalSet  # visible over a smooth sphere, hidden by terrain
    gained: IntervalSet  # hidden over a smooth sphere, visible over the terrain
    blockers: list = field(default_factory=list)  # obstacles that cost time, largest first


def blocking_report(
    *,
    body: str,
    height_index: int,
    grid: TimeGrid,
    azimuth_deg,
    elevation_deg,
    angular_radius_deg,
    horizon: HorizonResult,
    obstacles: ObstacleMap,
    visible_terrain: IntervalSet,
    visible_smooth: IntervalSet,
    limb: str,
) -> BlockingReport:
    """Time lost to terrain for one body and one observer height, split between obstacles."""
    h = height_index
    index = blocker_azimuth_index(
        azimuth_deg, elevation_deg, angular_radius_deg, horizon.elevation_deg[h : h + 1], horizon.azimuth_step_deg, limb
    )[0]
    lost = visible_smooth.intersection(visible_terrain.complement())
    gained = visible_terrain.intersection(visible_smooth.complement())
    total = lost.total_s()
    blockers = []
    if total > 0.0:
        shares = attribute_time(grid, lost, obstacles.obstacle_id[h, index])
        for oid, share in sorted(shares.items(), key=lambda item: -item[1]["seconds"]):
            record = {
                "body": body,
                "height_index": h,
                "obstacle_id": int(oid),
                "lost_s": share["seconds"],
                "share_of_lost": share["seconds"] / total,
                "intervals_et_s": share["intervals"].as_list(),
            }
            if oid >= 0:
                source = obstacles.obstacles[oid]
                for key in (
                    "azimuth_start_deg", "azimuth_end_deg", "peak_azimuth_deg", "peak_elevation_deg",
                    "peak_distance_m", "peak_lat_deg", "peak_lon_deg", "peak_height_m", "near_field",
                ):
                    record[key] = source[key]
            blockers.append(record)
    return BlockingReport(body, h, index, lost, gained, blockers)


def add_blocking_to_timeline(timeline: TimelineResult, horizon: HorizonResult, visible_smooth: dict, et_to_utc) -> None:
    """Extend a site timeline with the comparison against a smooth sphere.

    visible_smooth maps (body, height index) to the visibility window of the body over a
    smooth sphere, for the same condition as the timeline's "<body>_visible" windows.
    Adds to the timeline: the blocker index of every sample, the smooth-sphere, lost and
    gained windows, their durations as metrics, and the list of blockers.
    """
    if horizon.obstacle_id is None or horizon.obstacles is None:
        raise ValueError("the horizon carries no obstacle grouping")
    obstacles = ObstacleMap(horizon.obstacle_id, horizon.obstacles)
    grid = TimeGrid.from_contract(timeline.time)
    domain = (grid.start_et_s, grid.end_et_s)
    n_h = len(horizon.observer_heights_m)

    def window(wid, subject, h, definition, intervals, method, threshold=None):
        record = {
            "id": wid,
            "subject": subject,
            "height_index": h,
            "definition": definition,
            "intervals_et_s": intervals.as_list(),
            "intervals_utc": [[et_to_utc(a), et_to_utc(b)] for a, b in intervals.intervals],
            "clipped_start": bool(intervals.clipped_start),
            "clipped_end": bool(intervals.clipped_end),
            "method": method,
        }
        if threshold is not None:
            record["threshold"] = threshold
        return record

    def metric(mid, label, value, h, method):
        return {"id": mid, "label": label, "value": float(value), "unit": "s", "height_index": h, "method": method}

    blockers = []
    for body in timeline.bodies:
        series = timeline.series[body]
        threshold = timeline.thresholds[body]
        limb = limb_of_threshold(threshold)
        tag = body.lower()
        index = np.empty((n_h, grid.count), dtype=np.int32)
        for h in range(n_h):
            record = next(w for w in timeline.windows if w["id"] == f"{tag}_visible" and w["height_index"] == h)
            terrain = IntervalSet(record["intervals_et_s"], domain)
            smooth = visible_smooth[(body, h)]
            report = blocking_report(
                body=body, height_index=h, grid=grid, azimuth_deg=series.azimuth_deg, elevation_deg=series.elevation_deg,
                angular_radius_deg=series.angular_radius_deg if series.angular_radius_deg is not None else np.zeros(grid.count),
                horizon=horizon, obstacles=obstacles, visible_terrain=terrain, visible_smooth=smooth, limb=limb,
            )
            index[h] = report.blocker_azimuth_index
            timeline.windows.append(window(f"{tag}_visible_smooth_sphere", body, h, f"{body} visible if the Moon were a smooth sphere through the site (no terrain), same condition", smooth, pk.M_SMOOTH_SPHERE, threshold))
            timeline.windows.append(window(f"{tag}_lost_to_terrain", body, h, f"{body} hidden by terrain while a smooth sphere would show it", report.lost, pk.M_BLOCKING))
            timeline.windows.append(window(f"{tag}_gained_from_terrain", body, h, f"{body} visible over the terrain while a smooth sphere would hide it", report.gained, pk.M_BLOCKING))
            timeline.metrics.append(metric(f"{tag}_visible_s", f"Total time with {body} visible", terrain.total_s(), h, pk.M_METRICS))
            timeline.metrics.append(metric(f"{tag}_visible_smooth_sphere_s", f"Total time with {body} visible over a smooth sphere", smooth.total_s(), h, pk.M_SMOOTH_SPHERE))
            timeline.metrics.append(metric(f"{tag}_lost_to_terrain_s", f"Time of {body} visibility lost to terrain, compared with a smooth sphere", report.lost.total_s(), h, pk.M_BLOCKING))
            timeline.metrics.append(metric(f"{tag}_gained_from_terrain_s", f"Time of {body} visibility gained from terrain lying below the smooth horizon", report.gained.total_s(), h, pk.M_BLOCKING))
            for blocker in report.blockers:
                blocker["intervals_utc"] = [[et_to_utc(a), et_to_utc(b)] for a, b in blocker["intervals_et_s"]]
                blocker["method"] = pk.M_BLOCKING
                blockers.append(blocker)
        series.blocker_azimuth_index = index
    timeline.blockers = blockers
