"""Terrain horizon of a point on a sphere.

For every azimuth the code walks along the great circle that leaves the site in that
direction, reads the terrain height at each sample and keeps the largest elevation angle
of the straight line from the observer to the terrain. Curvature needs no separate
correction: it is contained in the triangle observer - terrain point - centre of the Moon.

    tan(e) = (r_t cos(g) - r_o) / (r_t sin(g))

with r_o the observer's distance from the centre (reference radius + ground height +
observer height), r_t that of the terrain point and g the central angle between them. The
code evaluates the equivalent form

    tan(e) = ((H - h_ground - m) - 2 r_t sin^2(g / 2)) / (r_t sin(g))

which subtracts two small numbers (a height difference and the drop due to curvature)
instead of two radii of 1.7 million metres.

Sampling along the range: the first sample is one near-field pixel from the site, the step
is half a near-field pixel close to the site and grows in proportion to the distance
further out. Far samples are read from coarser overview levels of the terrain, never
coarser than the step. The best samples of each azimuth are then refined by nested
sampling between their neighbours, so the result does not depend on where the coarse
samples happened to fall. Method notes and measured accuracy: docs/method/horizon.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .dem import Terrain
from .geometry import DEG, site_frame
from .results import HorizonResult

M_FAR_FIELD = "horizon.far_field_bound"


@dataclass(frozen=True)
class HorizonSettings:
    """Numerical settings of the range sampling. The defaults are the validated ones."""

    first_sample_px: float = 1.0  # distance of the first sample, in near-field pixels
    near_step_px: float = 0.5  # range step close to the site, in near-field pixels
    range_growth: float = math.radians(0.25)  # relative growth of the step with distance
    refine_candidates: int = 3  # best local maxima per azimuth that are refined
    refine_rounds: int = 4
    refine_points: int = 9  # samples per refinement round; the bracket shrinks 4x per round


def range_table(near_pixel_m: float, max_range_m: float, settings: HorizonSettings) -> np.ndarray:
    """Distances of the samples along every ray, in metres along the reference sphere."""
    first = near_pixel_m * settings.first_sample_px
    if max_range_m <= first:
        raise ValueError("max_range_m must exceed the first sample distance")
    s = [first]
    while s[-1] < max_range_m:
        s.append(s[-1] + max(near_pixel_m * settings.near_step_px, settings.range_growth * s[-1]))
    s[-1] = max_range_m
    return np.asarray(s, dtype=np.float64)


def _points(up, heading, gamma):
    """Latitude and longitude (degrees) of points at central angles gamma along headings.

    heading has shape [..., 3]; gamma broadcasts against heading[..., 0].
    """
    cg, sg = np.cos(gamma), np.sin(gamma)
    x = cg * up[0] + sg * heading[..., 0]
    y = cg * up[1] + sg * heading[..., 1]
    z = cg * up[2] + sg * heading[..., 2]
    return np.arctan2(z, np.hypot(x, y)) / DEG, np.arctan2(y, x) / DEG


def _tan_elevation(height_m, gamma, radius_m, ground_m, observer_m):
    """tan of the elevation angle of terrain at central angle gamma (stable form)."""
    r_t = radius_m + height_m
    return ((height_m - ground_m - observer_m) - 2.0 * r_t * np.sin(0.5 * gamma) ** 2) / (r_t * np.sin(gamma))


def compute_horizon(
    terrain: Terrain,
    lat_deg: float,
    lon_deg: float,
    heights_m,
    azimuth_step_deg: float = 0.25,
    max_range_m: float = 300_000.0,
    settings: HorizonSettings = HorizonSettings(),
) -> HorizonResult:
    """Horizon elevation and obstacle location for every azimuth and observer height."""
    heights = np.asarray([float(h) for h in heights_m], dtype=np.float64)
    if heights.size == 0 or np.any(heights < 0) or np.any(np.diff(heights) <= 0):
        raise ValueError("observer heights must be non-negative and strictly increasing")
    n_az = int(round(360.0 / azimuth_step_deg))
    if abs(n_az * azimuth_step_deg - 360.0) > 1e-9:
        raise ValueError("azimuth_step_deg must divide 360")

    radius = float(terrain.reference_radius_m)
    ground = float(np.asarray(terrain.height_m(lon_deg, lat_deg)))
    if not math.isfinite(ground):
        raise ValueError(f"no terrain data at the site (lat {lat_deg}, lon {lon_deg})")

    east, north, up = site_frame(lat_deg, lon_deg)
    az = np.arange(n_az) * azimuth_step_deg * DEG
    heading = np.cos(az)[:, None] * north + np.sin(az)[:, None] * east  # [A, 3]

    s = range_table(terrain.finest_pixel_m, max_range_m, settings)  # [K]
    step = np.diff(s, prepend=0.0)
    gamma = s / radius
    lat, lon = _points(up, heading[:, None, :], gamma[None, :])  # [A, K]
    terrain_h = np.asarray(terrain.height_m(lon, lat, max_pixel_m=np.broadcast_to(step, lat.shape)), dtype=np.float64)
    valid = np.isfinite(terrain_h)

    n_h, n_k = heights.size, s.size
    elevation = np.full((n_h, n_az), np.nan)
    distance = np.full((n_h, n_az), np.nan)
    obstacle_h = np.full((n_h, n_az), np.nan)
    rows = np.arange(n_az)
    n_cand = min(settings.refine_candidates, n_k)

    with np.errstate(invalid="ignore"):
        base_tan = _tan_elevation(terrain_h, gamma[None, :], radius, ground, 0.0)
        r_t = radius + terrain_h
        per_metre = 1.0 / (r_t * np.sin(gamma)[None, :])  # d tan(e) / d(observer height), negated

    for i, m in enumerate(heights):
        t = np.where(valid, base_tan - m * per_metre, -np.inf)
        # local maxima along the range; the global maximum is always one of them
        left = np.concatenate([np.full((n_az, 1), -np.inf), t[:, :-1]], axis=1)
        right = np.concatenate([t[:, 1:], np.full((n_az, 1), -np.inf)], axis=1)
        peaks = np.where((t >= left) & (t >= right), t, -np.inf)
        if n_cand < n_k:
            cand = np.argpartition(-peaks, n_cand - 1, axis=1)[:, :n_cand]  # [A, C]
        else:
            cand = np.broadcast_to(np.arange(n_k), (n_az, n_k)).copy()
        best_t = np.take_along_axis(peaks, cand, axis=1)
        best_s = s[cand]
        best_h = np.take_along_axis(terrain_h, cand, axis=1)
        lo = s[np.maximum(cand - 1, 0)]
        hi = s[np.minimum(cand + 1, n_k - 1)]
        level = step[cand]  # refine on the same overview level the coarse sample was read from

        frac = np.linspace(0.0, 1.0, settings.refine_points)
        for _ in range(settings.refine_rounds):
            pts = lo[..., None] + (hi - lo)[..., None] * frac  # [A, C, P]
            g = pts / radius
            plat, plon = _points(up, heading[:, None, None, :], g)
            ph = np.asarray(terrain.height_m(plon, plat, max_pixel_m=np.broadcast_to(level[..., None], pts.shape)), dtype=np.float64)
            with np.errstate(invalid="ignore"):
                pt = _tan_elevation(ph, g, radius, ground, m)
            pt = np.where(np.isfinite(pt), pt, -np.inf)
            j = np.argmax(pt, axis=-1)[..., None]
            top = np.take_along_axis(pt, j, axis=-1)[..., 0]
            better = top > best_t
            best_t = np.where(better, top, best_t)
            best_s = np.where(better, np.take_along_axis(pts, j, axis=-1)[..., 0], best_s)
            best_h = np.where(better, np.take_along_axis(ph, j, axis=-1)[..., 0], best_h)
            lo = np.take_along_axis(pts, np.maximum(j - 1, 0), axis=-1)[..., 0]
            hi = np.take_along_axis(pts, np.minimum(j + 1, settings.refine_points - 1), axis=-1)[..., 0]

        pick = np.argmax(best_t, axis=1)
        tan_e = best_t[rows, pick]
        found = np.isfinite(tan_e)
        elevation[i] = np.where(found, np.arctan(np.where(found, tan_e, 0.0)) / DEG, np.nan)
        distance[i] = np.where(found, best_s[rows, pick], np.nan)
        obstacle_h[i] = np.where(found, best_h[rows, pick], np.nan)

    obstacle_lat, obstacle_lon = _points(up, heading[None, :, :], distance / radius)

    # -- coverage ---------------------------------------------------------------------------
    nodata_fraction = float(1.0 - valid.mean())
    last_valid = n_k - 1 - np.argmax(valid[:, ::-1], axis=1)
    reach = np.where(valid.any(axis=1), s[last_valid], 0.0)  # [A]
    truncated = bool(np.any(reach < max_range_m))
    warnings = []
    if truncated:
        warnings.append(
            f"coverage: terrain data ends before the search radius in {int((reach < max_range_m).sum())} of "
            f"{n_az} azimuths (shortest reach {reach.min() / 1000.0:.1f} km)"
        )
    if nodata_fraction > 0:
        warnings.append(f"coverage: {100.0 * nodata_fraction:.2f} % of the terrain samples have no data")

    # -- what terrain beyond the reach could still add --------------------------------------
    ceiling = terrain.ceiling_height_m
    ceiling_assumed = ceiling is None
    if ceiling_assumed:
        ceiling = float(max(np.nanmax(terrain_h), ground))
    r_c = radius + ceiling
    r_o = radius + ground + heights  # [H]
    # Terrain no higher than the ceiling, at central angle >= g_end, is seen at most at the
    # elevation of a point of ceiling height at g_end (or at the tangent point, if the
    # observer is above the ceiling and g_end is closer than the tangent point).
    g_end = np.maximum(reach / radius, 1e-12)[None, :]
    g_tangent = np.arccos(np.minimum(1.0, r_c / r_o))[:, None]
    g_eval = np.maximum(g_end, g_tangent)
    e_far = np.arctan2(r_c * np.cos(g_eval) - r_o[:, None], r_c * np.sin(g_eval)) / DEG
    far_bound = np.where(np.isfinite(elevation), np.maximum(0.0, e_far - elevation), np.nan)

    error_bounds = {
        "far_field_max_deg": (float(np.nanmax(far_bound)), "deg", M_FAR_FIELD),
        "far_field_open_azimuth_fraction": (float(np.mean(np.nanmax(far_bound, axis=0) > 0.0)), "1", M_FAR_FIELD),
        "ceiling_height_m": (float(ceiling), "m", M_FAR_FIELD),
        "shortest_reach_m": (float(reach.min()), "m", M_FAR_FIELD),
    }
    if ceiling_assumed:
        warnings.append(
            "far field: no terrain ceiling was supplied; the highest terrain found inside the search "
            "radius was used as the ceiling for the far-field bound"
        )

    return HorizonResult(
        azimuth_step_deg=float(azimuth_step_deg),
        observer_heights_m=[float(h) for h in heights],
        max_range_m=float(max_range_m),
        reference_radius_m=radius,
        surface_height_m=ground,
        elevation_deg=elevation,
        distance_m=distance,
        obstacle_height_m=obstacle_h,
        obstacle_lat_deg=obstacle_lat,
        obstacle_lon_deg=obstacle_lon,
        coverage_complete=nodata_fraction == 0.0,
        truncated_at_data_edge=truncated,
        nodata_fraction=nodata_fraction,
        error_bounds=error_bounds,
        far_field_bound_deg=far_bound,
        warnings=warnings,
    )
