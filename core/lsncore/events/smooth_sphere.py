"""Terrain-free horizon: the edge of the reference sphere seen from a height above it.

Used for analytic tests and as the stand-in until a terrain horizon is available.
A package built from it must say so (status "partial" and a warning).
"""

from __future__ import annotations

import numpy as np

from ..results import HorizonResult

REFERENCE_RADIUS_M = 1737400.0


def smooth_sphere_horizon(
    observer_heights_m,
    azimuth_step_deg: float = 0.25,
    max_range_m: float = 300000.0,
    reference_radius_m: float = REFERENCE_RADIUS_M,
) -> HorizonResult:
    """Horizon of a smooth sphere for several observer heights.

    For an observer h above the sphere of radius R the horizon lies below the local
    horizontal plane by the dip angle arccos(R / (R + h)); the horizon point is at arc
    length R * dip from the site.
    """
    heights = [float(h) for h in observer_heights_m]
    count = int(round(360.0 / azimuth_step_deg))
    dip_rad = np.arccos(reference_radius_m / (reference_radius_m + np.asarray(heights)))
    elevation = np.repeat(-np.degrees(dip_rad)[:, None], count, axis=1)
    distance = np.repeat((reference_radius_m * dip_rad)[:, None], count, axis=1)
    return HorizonResult(
        azimuth_step_deg=360.0 / count,
        observer_heights_m=heights,
        max_range_m=float(max_range_m),
        reference_radius_m=float(reference_radius_m),
        surface_height_m=0.0,
        elevation_deg=elevation,
        distance_m=distance,
        warnings=["No terrain: the horizon is the edge of a smooth sphere of the reference radius."],
    )
