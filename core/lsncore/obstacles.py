"""Grouping a horizon profile into obstacles.

The horizon stores, for every azimuth, the terrain point that sets it. Neighbouring
azimuths usually see the same piece of terrain (a ridge, a crater rim, a boulder field
next to the lander), and at some azimuths the limiting point jumps to another piece,
nearer or farther. An *obstacle* is a run of neighbouring azimuths between two such jumps.

Rule: two neighbouring azimuths belong to the same obstacle if the distances of their
limiting points differ by no more than 10 % of the smaller one, or by no more than 50 m.
The rule looks at distance only; it does not know names or geology.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .results import HorizonResult

REL_TOL = 0.10
ABS_TOL_M = 50.0
NEAR_FIELD_M = 1000.0


@dataclass
class ObstacleMap:
    obstacle_id: np.ndarray  # [H, A] int32; index into obstacles, -1 where the horizon has no data
    obstacles: list  # one record per obstacle, in the form the package contract defines


def _pick(values: np.ndarray | None, h: int, j: int):
    if values is None:
        return None
    value = float(values[h, j])
    return value if np.isfinite(value) else None


def segment_obstacles(
    horizon: HorizonResult,
    rel_tol: float = REL_TOL,
    abs_tol_m: float = ABS_TOL_M,
    near_field_m: float = NEAR_FIELD_M,
) -> ObstacleMap:
    """Split the horizon of every observer height into obstacles."""
    elevation = np.asarray(horizon.elevation_deg, dtype=np.float64)
    distance = np.asarray(horizon.distance_m, dtype=np.float64)
    n_h, n_az = elevation.shape
    step = float(horizon.azimuth_step_deg)
    ids = np.full((n_h, n_az), -1, dtype=np.int32)
    records: list[dict] = []

    for h in range(n_h):
        d, e = distance[h], elevation[h]
        valid = np.isfinite(d) & np.isfinite(e)
        if not valid.any():
            continue
        nxt = np.roll(d, -1)
        with np.errstate(invalid="ignore"):
            joined = valid & np.roll(valid, -1) & (np.abs(nxt - d) <= np.maximum(abs_tol_m, rel_tol * np.minimum(d, nxt)))
        # joined[j]: azimuth j and j + 1 (cyclically) see the same obstacle
        starts = np.flatnonzero(valid & ~np.roll(joined, 1))
        if starts.size == 0:  # one obstacle all the way round
            starts = np.array([0])
            counts = [n_az]
        else:
            counts = []
            for s in starts:
                n = 1
                while n < n_az and joined[(s + n - 1) % n_az]:
                    n += 1
                counts.append(n)
        for s, n in zip(starts, counts):
            idx = (int(s) + np.arange(n)) % n_az
            oid = len(records)
            ids[h, idx] = oid
            peak = int(idx[int(np.argmax(e[idx]))])
            records.append(
                {
                    "id": oid,
                    "height_index": h,
                    "azimuth_start_index": int(s),
                    "azimuth_count": int(n),
                    "azimuth_start_deg": float(s * step),
                    "azimuth_end_deg": float(idx[-1] * step),
                    "peak_azimuth_deg": float(peak * step),
                    "peak_elevation_deg": float(e[peak]),
                    "peak_distance_m": float(d[peak]),
                    "peak_lat_deg": _pick(horizon.obstacle_lat_deg, h, peak),
                    "peak_lon_deg": _pick(horizon.obstacle_lon_deg, h, peak),
                    "peak_height_m": _pick(horizon.obstacle_height_m, h, peak),
                    "distance_min_m": float(d[idx].min()),
                    "distance_max_m": float(d[idx].max()),
                    "near_field": bool(d[peak] < near_field_m),
                }
            )
    return ObstacleMap(ids, records)
