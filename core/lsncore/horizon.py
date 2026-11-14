"""Terrain horizon of a point on a sphere.

For every azimuth the code looks along the great circle that leaves the site in that
direction and keeps the largest elevation angle of the straight line from the observer to
the terrain. Curvature needs no separate correction: it is contained in the triangle
observer - terrain point - centre of the Moon,

    tan(e) = (r_t cos(g) - r_o) / (r_t sin(g))

with r_o the observer's distance from the centre (reference radius + ground height +
observer height), r_t that of the terrain point and g the central angle between them. The
code evaluates the equivalent form

    tan(e) = ((H - h_ground - m) - 2 r_t sin^2(g / 2)) / (r_t sin(g))

which subtracts two small numbers (a height difference and the drop due to curvature)
instead of two radii of 1.7 million metres.

Search along a ray (details and measured accuracy in docs/method/horizon.md):

1. A lattice of points half a pixel apart covers the ray. Close to the site every lattice
   point is evaluated on the finest data.
2. Farther out the lattice is grouped into cells that grow with distance. For each cell
   the terrain source supplies an upper bound of the surface in the cell (from
   block-maximum overview levels). A cell is skipped only if that bound proves that
   nothing in it can reach the horizon already found; every other cell is walked point
   by point on the finest data. Nothing is skipped on the strength of a sparse sample.
3. Between two lattice points a gridded surface has creases where the ray crosses the
   lines through the pixel centres. The terrain source reports those crossings and they
   are evaluated as well, for every stretch of ray that was evaluated at all.
4. The leading points of each azimuth are refined by nested sampling.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .dem import Terrain
from .geometry import DEG, site_frame
from .obstacles import segment_obstacles
from .results import HorizonResult

M_FAR_FIELD = "horizon.far_field_bound"


@dataclass(frozen=True)
class HorizonSettings:
    """Numerical settings of the search along a ray. The defaults are the validated ones.

    Lengths are in units of the finest pixel of the terrain source.
    """

    first_sample_px: float = 1.0  # distance of the first point from the site ...
    first_sample_max_m: float = 20.0  # ... but never farther than this: on a coarse grid the ground next to the site counts too
    fine_step_px: float = 0.5  # lattice step
    inner_zone_px: float = 10.0  # extent of the denser lattice next to the site
    inner_step_px: float = 0.125  # its step: elevation angles are most sensitive there
    cell_growth: float = math.radians(0.5)  # cell length / distance
    max_cell_points: int = 256  # upper limit of lattice points per cell
    refine_candidates: int = 4  # best near-zone maxima per azimuth that are refined
    refine_rounds: int = 4
    refine_points: int = 9  # points per refinement round; the bracket shrinks 4x per round
    chunk_points: int = 3_000_000  # lattice points evaluated per batch (memory bound)
    walk_growth: int = 2  # cells walked per azimuth: one in the first round, this many times more in every following round


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


def _tan_upper(bound_m, g_a, g_b, radius_m, ground_m, observer_m):
    """Largest tan(elevation) of any point no higher than bound_m at central angle in [g_a, g_b].

    For a fixed height the elevation falls with distance, except below the observer, where
    it rises up to the tangent point; it always rises with height.
    """
    r_u = radius_m + bound_m
    r_o = radius_m + ground_m + observer_m
    g_tangent = np.arccos(np.minimum(1.0, r_u / r_o))
    g = np.clip(g_tangent, g_a, g_b)
    return _tan_elevation(bound_m, g, radius_m, ground_m, observer_m)


def _layout(terrain: Terrain, max_range_m: float, settings: HorizonSettings, start_m: float | None = None):
    """The lattice along every ray and its grouping into cells.

    Returns (first, fine, n_near, cell_first, cell_count): lattice point i is at
    first + i * fine; the first n_near points form the near zone; the following points are
    grouped into cells given by the index of their first point and their number of points.
    """
    p = terrain.finest_pixel_m
    first = float(start_m) if start_m is not None else min(p * settings.first_sample_px, settings.first_sample_max_m)
    fine = p * settings.fine_step_px
    if max_range_m <= first:
        raise ValueError("max_range_m must exceed the first sample distance")
    n_lattice = int(math.floor((max_range_m - first) / fine)) + 1
    cap = settings.max_cell_points
    if math.isfinite(terrain.max_cover_radius_m):
        cap = min(cap, int(math.floor(2.0 * terrain.max_cover_radius_m / fine)))
    cap = max(cap, 1)
    firsts, counts = [], []
    i = 0
    while i < n_lattice:
        s = first + i * fine
        n = int(min(cap, max(1, math.floor(settings.cell_growth * s / fine)), n_lattice - i))
        if i == 0:
            n = 1  # the first point is always evaluated on its own (it is, anyway, when the search starts at the site)
        firsts.append(i)
        counts.append(n)
        i += n
    firsts = np.asarray(firsts, dtype=np.int64)
    counts = np.asarray(counts, dtype=np.int64)
    n_near = int(np.argmax(counts > 1)) if np.any(counts > 1) else counts.size
    return first, fine, n_near, firsts[n_near:], counts[n_near:]


def _merge_zones(near: HorizonResult, far: HorizonResult, switch_m: float) -> HorizonResult:
    """One horizon from two searches of the same rays: out to switch_m on the terrain with
    the near-field refinement, from switch_m on without it. Per azimuth and height the
    higher of the two is the horizon, with the obstacle of the search that found it."""
    with np.errstate(invalid="ignore"):
        take_far = np.isfinite(far.elevation_deg) & ~(near.elevation_deg >= far.elevation_deg)
    pick = lambda a, b: np.where(take_far, b, a)  # noqa: E731
    elevation = pick(near.elevation_deg, far.elevation_deg)
    # What terrain beyond the reach could add was computed against the far search; restate it
    # against the merged horizon.
    with np.errstate(invalid="ignore"):
        beyond = np.maximum(0.0, far.elevation_deg + far.far_field_bound_deg - elevation)
    far_bound = np.where(np.isfinite(elevation), np.nan_to_num(beyond, nan=0.0), np.nan)
    bounds = dict(far.error_bounds)
    bounds["far_field_max_deg"] = (float(np.nanmax(far_bound)), "deg", M_FAR_FIELD)
    bounds["far_field_open_azimuth_fraction"] = (float(np.mean(np.nanmax(far_bound, axis=0) > 0.0)), "1", M_FAR_FIELD)
    share = switch_m / far.max_range_m
    nodata = share * near.nodata_fraction + (1.0 - share) * far.nodata_fraction
    result = HorizonResult(
        azimuth_step_deg=near.azimuth_step_deg,
        observer_heights_m=near.observer_heights_m,
        max_range_m=far.max_range_m,
        reference_radius_m=near.reference_radius_m,
        surface_height_m=near.surface_height_m,
        elevation_deg=elevation,
        distance_m=pick(near.distance_m, far.distance_m),
        obstacle_height_m=pick(near.obstacle_height_m, far.obstacle_height_m),
        obstacle_lat_deg=pick(near.obstacle_lat_deg, far.obstacle_lat_deg),
        obstacle_lon_deg=pick(near.obstacle_lon_deg, far.obstacle_lon_deg),
        coverage_complete=nodata == 0.0,
        truncated_at_data_edge=far.truncated_at_data_edge,
        nodata_fraction=float(nodata),
        error_bounds=bounds,
        far_field_bound_deg=far_bound,
        warnings=[w for w in near.warnings if not w.startswith(("coverage: terrain data ends", "far field:"))] + list(far.warnings),
        search_stats={
            "zones": 2,
            "switch_m": float(switch_m),
            "near_points_per_ray": near.search_stats["near_points_per_ray"],
            "cells_per_ray": near.search_stats["cells_per_ray"] + far.search_stats["cells_per_ray"],
            "lattice_points_beyond_near_zone": near.search_stats["lattice_points_beyond_near_zone"] + far.search_stats["lattice_points_beyond_near_zone"],
            "lattice_points_walked": near.search_stats["lattice_points_walked"] + far.search_stats["lattice_points_walked"],
            "walked_fraction": (near.search_stats["lattice_points_walked"] + far.search_stats["lattice_points_walked"])
            / max(1, near.search_stats["lattice_points_beyond_near_zone"] + far.search_stats["lattice_points_beyond_near_zone"]),
            "crease_points": near.search_stats["crease_points"] + far.search_stats["crease_points"],
        },
    )
    grouping = segment_obstacles(result)
    result.obstacle_id, result.obstacles = grouping.obstacle_id, grouping.obstacles
    return result


def compute_horizon(
    terrain: Terrain,
    lat_deg: float,
    lon_deg: float,
    heights_m,
    azimuth_step_deg: float = 0.25,
    max_range_m: float = 300_000.0,
    settings: HorizonSettings = HorizonSettings(),
    start_m: float | None = None,
    ground_m: float | None = None,
) -> HorizonResult:
    """Horizon elevation and obstacle location for every azimuth and observer height.

    A terrain with a near-field refinement around the site (it has far_terrain and
    switch_m) is searched in two zones: out to switch_m with the refinement and its finer
    lattice, beyond it on far_terrain with the lattice of the wide products. start_m and
    ground_m serve that second search: where the rays begin, and the terrain height at
    the site that the first search used.
    """
    far_terrain = getattr(terrain, "far_terrain", None)
    if far_terrain is not None and start_m is None and max_range_m > terrain.switch_m + 2.0 * far_terrain.finest_pixel_m:
        near = compute_horizon(terrain.near_terrain, lat_deg, lon_deg, heights_m, azimuth_step_deg, terrain.switch_m, settings)
        far = compute_horizon(far_terrain, lat_deg, lon_deg, heights_m, azimuth_step_deg, max_range_m, settings, start_m=terrain.switch_m, ground_m=near.surface_height_m)
        return _merge_zones(near, far, terrain.switch_m)
    heights = np.asarray([float(h) for h in heights_m], dtype=np.float64)
    if heights.size == 0 or np.any(heights < 0) or np.any(np.diff(heights) <= 0):
        raise ValueError("observer heights must be non-negative and strictly increasing")
    n_az = int(round(360.0 / azimuth_step_deg))
    if abs(n_az * azimuth_step_deg - 360.0) > 1e-9:
        raise ValueError("azimuth_step_deg must divide 360")

    radius = float(terrain.reference_radius_m)
    ground = float(ground_m) if ground_m is not None else float(np.asarray(terrain.height_m(lon_deg, lat_deg)))
    if not math.isfinite(ground):
        raise ValueError(f"no terrain data at the site (lat {lat_deg}, lon {lon_deg})")

    east, north, up = site_frame(lat_deg, lon_deg)
    az = np.arange(n_az) * azimuth_step_deg * DEG
    heading = np.cos(az)[:, None] * north + np.sin(az)[:, None] * east  # [A, 3]
    n_h = heights.size
    ref = n_h // 2  # observer height used to rank cells
    rows = np.arange(n_az)

    first, fine, n_lat_near, cell_first, cell_count = _layout(terrain, max_range_m, settings, start_m)
    n_cells = cell_first.size
    # Near zone: its lattice points and, as the last point, the boundary to the first cell.
    s_near = first + np.arange(n_lat_near) * fine
    s_near = np.append(s_near, min(s_near[-1] + 0.5 * fine, max_range_m) if n_cells else max_range_m)
    inner = first + np.arange(1, int(settings.inner_zone_px / settings.inner_step_px)) * (
        terrain.finest_pixel_m * settings.inner_step_px
    )
    s_near = np.unique(np.round(np.concatenate([s_near, inner[inner < s_near[-1]]]), 9))
    n_near = s_near.size

    def tan_all(h_terrain, gamma):
        """tan(elevation) for every observer height; the leading axis is the height."""
        with np.errstate(invalid="ignore", divide="ignore"):
            base = _tan_elevation(h_terrain, gamma, radius, ground, 0.0)
            per_metre = 1.0 / ((radius + h_terrain) * np.sin(gamma))
            t = base[None] - heights.reshape((n_h,) + (1,) * base.ndim) * per_metre[None]
        return np.where(np.isfinite(t), t, -np.inf)

    # Best point found so far for every observer height and azimuth. Every value in here is
    # the elevation of a point that exists on the surface, so it is a valid lower bound of
    # the horizon at all times.
    best_t = np.full((n_h, n_az), -np.inf)
    best_s = np.full((n_h, n_az), np.nan)
    best_h = np.full((n_h, n_az), np.nan)

    def offer(ray, s, h_terrain):
        """Offer points (flat arrays) to the best-point table."""
        t = tan_all(h_terrain, s / radius)
        for i in range(n_h):
            top = np.full(n_az, -np.inf)
            np.maximum.at(top, ray, t[i])
            better = top > best_t[i]
            if not better.any():
                continue
            hit = np.flatnonzero((t[i] == top[ray]) & better[ray])
            _, first_hit = np.unique(ray[hit], return_index=True)
            hit = hit[first_hit]
            best_t[i, ray[hit]] = t[i, hit]
            best_s[i, ray[hit]] = s[hit]
            best_h[i, ray[hit]] = h_terrain[hit]

    kink_points = 0

    def offer_creases(ray, s, lat, lon, same_stretch):
        """Evaluate the creases of the surface between consecutive points.

        ray, s, lat, lon are flat and ordered along the rays; same_stretch[i] says that
        points i and i + 1 are neighbours on the same ray.
        """
        nonlocal kink_points
        if s.size < 2:
            return
        tau = np.asarray(terrain.crease_fractions(lon, lat), dtype=np.float64)  # [P - 1, n]
        ok = np.isfinite(tau) & same_stretch[:, None]
        seg, _ = np.nonzero(ok)
        if seg.size == 0:
            return
        ks = s[seg] + tau[ok] * (s[seg + 1] - s[seg])
        kray = ray[seg]
        klat, klon = _points(up, heading[kray], ks / radius)
        offer(kray, ks, np.asarray(terrain.height_m(klon, klat), dtype=np.float64))
        kink_points += int(ks.size)

    # -- 1. near zone: every lattice point, finest data --------------------------------------
    g_near = s_near / radius
    near_lat, near_lon = _points(up, heading[:, None, :], g_near[None, :])  # [A, N]
    h_near = np.asarray(terrain.height_m(near_lon, near_lat), dtype=np.float64)
    near_valid = np.isfinite(h_near)
    t_near = tan_all(h_near, g_near[None, :])  # [H, A, N]
    k_best = np.argmax(t_near, axis=2)  # [H, A]
    best_t[:] = np.take_along_axis(t_near, k_best[..., None], axis=2)[..., 0]
    best_s[:] = s_near[k_best]
    best_h[:] = h_near[rows[None, :], k_best]
    if n_near > 1:
        stretch = np.ones((n_az, n_near), dtype=bool)
        stretch[:, -1] = False  # the last point of a ray has no successor on that ray
        offer_creases(
            np.repeat(rows, n_near), np.tile(s_near, n_az), near_lat.ravel(), near_lon.ravel(), stretch.ravel()[:-1]
        )

    # -- 2. cells beyond the near zone: bound, prune, walk ------------------------------------
    cell_has_data = np.zeros((n_az, n_cells), dtype=bool)
    walked_points = 0
    if n_cells:
        s_a = first + cell_first * fine - 0.5 * fine
        s_b = np.minimum(first + (cell_first + cell_count - 1) * fine + 0.5 * fine, max_range_m)
        s_c = 0.5 * (s_a + s_b)
        clat, clon = _points(up, heading[:, None, :], (s_c / radius)[None, :])  # [A, K]
        bound = np.asarray(terrain.cover_max_m(clon, clat, np.broadcast_to(0.5 * (s_b - s_a), clat.shape)), dtype=np.float64)
        cell_has_data = np.isfinite(bound)
        g_a, g_b = s_a / radius, s_b / radius
        # Upper bound of tan(elevation) in each cell for every observer height. With
        # tan(e) = t0(g) - m / (r sin g), t0 being the value for an observer on the ground,
        # the largest value over the cell is at most max t0 - m / (r sin g_b): one exact
        # bound for the ground observer, and a cheap valid one for the others.
        with np.errstate(invalid="ignore"):
            t_ground = _tan_upper(bound, g_a[None, :], g_b[None, :], radius, ground, 0.0)  # [A, K]
            per_metre = 1.0 / ((radius + bound) * np.sin(g_b)[None, :])
            t_bound = t_ground[None] - heights[:, None, None] * per_metre[None]  # [H, A, K]
        t_bound = np.where(np.isfinite(t_bound), t_bound, -np.inf)
        pending = cell_has_data.copy()
        # Cells are walked in rounds, the most promising of every azimuth first: what a round
        # finds raises the lower bound, and the next round skips every cell whose upper
        # bound no longer exceeds it. A cell is only ever skipped on that comparison, so
        # the order of the rounds changes how much is walked, not what is found.
        per_ray = 1

        while True:
            alive = pending & np.any(t_bound > best_t[:, :, None], axis=0)  # [A, K]
            if not alive.any():
                break
            if per_ray < n_cells:
                # walk the most promising cells first: they raise the lower bound the most
                score = np.where(alive, t_bound[ref], -np.inf)
                top = np.argpartition(-score, min(per_ray, n_cells) - 1, axis=1)[:, :per_ray]
                pick = np.zeros_like(alive)
                pick[rows[:, None], top] = True
                pick &= alive
                per_ray *= max(2, int(settings.walk_growth))
            else:
                pick = alive
            pending &= ~pick
            a_idx, k_idx = np.nonzero(pick)
            counts = cell_count[k_idx] + 2  # the lattice points of the cell and its two ends
            ends = np.cumsum(counts)
            start = 0
            while start < a_idx.size:  # batches bounded in memory
                stop = int(np.searchsorted(ends, (ends[start - 1] if start else 0) + settings.chunk_points, side="right"))
                stop = max(stop, start + 1)
                n = counts[start:stop]
                pair = np.repeat(np.arange(start, stop), n)
                within = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
                cell = k_idx[pair]
                s = first + (cell_first[cell] + within - 1) * fine
                s = np.where(within == 0, s_a[cell], np.where(within == counts[pair] - 1, s_b[cell], s))
                ray = a_idx[pair]
                plat, plon = _points(up, heading[ray], s / radius)
                offer(ray, s, np.asarray(terrain.height_m(plon, plat), dtype=np.float64))
                offer_creases(ray, s, plat, plon, pair[1:] == pair[:-1])
                walked_points += int(cell_count[k_idx[start:stop]].sum())
                start = stop

    # -- 3. refine the leading points ----------------------------------------------------------
    frac = np.linspace(0.0, 1.0, settings.refine_points)
    s_limit = (s_near[0], max_range_m)
    n_cand = min(settings.refine_candidates, n_near)
    for i, m in enumerate(heights):
        t = t_near[i]
        left = np.concatenate([np.full((n_az, 1), -np.inf), t[:, :-1]], axis=1)
        right = np.concatenate([t[:, 1:], np.full((n_az, 1), -np.inf)], axis=1)
        peaks = np.where((t >= left) & (t >= right), t, -np.inf)
        if n_cand < n_near:
            cand = np.argpartition(-peaks, n_cand - 1, axis=1)[:, :n_cand]
        else:
            cand = np.broadcast_to(np.arange(n_near), (n_az, n_near)).copy()
        # brackets: around the best near-zone maxima and around the best point so far
        s0 = np.nan_to_num(best_s[i], nan=s_near[0])
        lo = np.concatenate([s_near[np.maximum(cand - 1, 0)], (s0 - fine)[:, None]], axis=1)
        hi = np.concatenate([s_near[np.minimum(cand + 1, n_near - 1)], (s0 + fine)[:, None]], axis=1)
        lo, hi = np.clip(lo, *s_limit), np.clip(hi, *s_limit)
        for _ in range(settings.refine_rounds):
            pts = lo[..., None] + (hi - lo)[..., None] * frac  # [A, C, P]
            g = pts / radius
            plat, plon = _points(up, heading[:, None, None, :], g)
            ph = np.asarray(terrain.height_m(plon, plat), dtype=np.float64)
            with np.errstate(invalid="ignore"):
                pt = _tan_elevation(ph, g, radius, ground, m)
            pt = np.where(np.isfinite(pt), pt, -np.inf)
            j = np.argmax(pt, axis=-1)[..., None]
            top = np.take_along_axis(pt, j, axis=-1)[..., 0]  # [A, C]
            c = np.argmax(top, axis=1)
            better = top[rows, c] > best_t[i]
            best_t[i] = np.where(better, top[rows, c], best_t[i])
            best_s[i] = np.where(better, np.take_along_axis(pts, j, axis=-1)[..., 0][rows, c], best_s[i])
            best_h[i] = np.where(better, np.take_along_axis(ph, j, axis=-1)[..., 0][rows, c], best_h[i])
            lo = np.take_along_axis(pts, np.maximum(j - 1, 0), axis=-1)[..., 0]
            hi = np.take_along_axis(pts, np.minimum(j + 1, settings.refine_points - 1), axis=-1)[..., 0]

    found = np.isfinite(best_t)
    elevation = np.where(found, np.arctan(np.where(found, best_t, 0.0)) / DEG, np.nan)
    distance = np.where(found, best_s, np.nan)
    obstacle_h = np.where(found, best_h, np.nan)
    obstacle_lat, obstacle_lon = _points(up, heading[None, :, :], distance / radius)

    # -- coverage ---------------------------------------------------------------------------
    cell_len = cell_count * fine
    near_len = np.gradient(s_near) if n_near > 1 else np.full(1, fine)
    total_len = near_len.sum() + cell_len.sum()
    missing = (near_len[None, :] * ~near_valid).sum(axis=1) + (cell_len[None, :] * ~cell_has_data).sum(axis=1)
    nodata_fraction = float(missing.mean() / total_len)
    reach = np.where(near_valid.any(axis=1), s_near[n_near - 1 - np.argmax(near_valid[:, ::-1], axis=1)], 0.0)
    if n_cells:
        last_cell = n_cells - 1 - np.argmax(cell_has_data[:, ::-1], axis=1)
        reach = np.where(cell_has_data.any(axis=1), np.maximum(reach, s_b[last_cell]), reach)
    full_reach = max_range_m - fine
    truncated = bool(np.any(reach < full_reach))
    reach = np.where(reach >= full_reach, max_range_m, reach)
    warnings = []
    if truncated:
        warnings.append(
            f"coverage: terrain data ends before the search radius in {int((reach < max_range_m).sum())} of "
            f"{n_az} azimuths (shortest reach {reach.min() / 1000.0:.1f} km)"
        )
    if nodata_fraction > 0:
        warnings.append(f"coverage: {100.0 * nodata_fraction:.2f} % of the ray length has no terrain data")

    # -- what terrain beyond the reach could still add --------------------------------------
    ceiling = terrain.ceiling_height_m
    ceiling_assumed = ceiling is None
    if ceiling_assumed:
        ceiling = float(np.nanmax([np.nanmax(h_near), np.nanmax(obstacle_h), ground]))
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

    lattice_points = int(cell_count.sum()) * n_az
    result = HorizonResult(
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
        search_stats={
            "near_points_per_ray": int(n_near),
            "cells_per_ray": int(n_cells),
            "lattice_points_beyond_near_zone": lattice_points,
            "lattice_points_walked": int(walked_points),
            "walked_fraction": float(walked_points / lattice_points) if lattice_points else 0.0,
            "crease_points": int(kink_points),
        },
    )
    grouping = segment_obstacles(result)
    result.obstacle_id, result.obstacles = grouping.obstacle_id, grouping.obstacles
    return result
