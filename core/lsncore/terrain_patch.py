"""Terrain patches: the ground around a site on regular grids, for drawing.

A patch is a square grid in the site's local East/North/Up frame, centred on the site.
Its values are the up coordinate of the surface at each (east, north) node, measured from
the ground point of the site. The curvature of the sphere is therefore already in the
values: a viewer places a vertex at (east, north, up) and is done.

Patches are for drawing only. Visibility, events and windows are computed on the finest
elevation data by the horizon code and are never derived from a patch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

from .geometry import site_frame

DEG = np.pi / 180.0

# Defaults chosen by the team: three nested grids of 201 x 201 nodes, each four times as
# wide and four times as coarse as the one before, 0.49 MB per site as float32.
DEFAULT_PATCHES = [
    {"id": "near", "half_width_m": 2000.0, "spacing_m": 20.0},
    {"id": "mid", "half_width_m": 8000.0, "spacing_m": 80.0},
    {"id": "far", "half_width_m": 32000.0, "spacing_m": 320.0},
]
MAX_NODES_PER_AXIS = 1025
MAX_PATCHES = 8
_ID = re.compile(r"^[a-z][a-z0-9_]{0,15}$")

NOTICE = (
    "For drawing only. Visibility, events and windows come from the timeline of this package, "
    "which was computed on the finest elevation data; never derive them from this surface."
)
FRAME = (
    "Local East/North/Up of the site (site.enu), origin at the ground point of the site "
    "(site.position_km), metres. Element [i][j] of up_m is the surface point with "
    "north = north_min_m + i * spacing_m and east = east_min_m + j * spacing_m. The curvature "
    "of the sphere is in the values. A direction with azimuth A and elevation E points to "
    "(sin A cos E, cos A cos E, sin E); an observer at height m stands at (0, 0, m)."
)


def canonical_patches(specs) -> list[dict]:
    """Patch requests in canonical form: rounded to the millimetre, finest first."""
    out = []
    for spec in specs:
        pid = str(spec["id"])
        if not _ID.match(pid):
            raise ValueError(f"terrain patch id '{pid}' must be lower case letters, digits and underscores, at most 16 characters")
        half, spacing = round(float(spec["half_width_m"]), 3), round(float(spec["spacing_m"]), 3)
        if spacing <= 0.0 or half <= 0.0:
            raise ValueError(f"terrain patch '{pid}': half_width_m and spacing_m must be positive")
        cells = half / spacing
        if abs(cells - round(cells)) > 1e-9:
            raise ValueError(f"terrain patch '{pid}': half_width_m must be a multiple of spacing_m")
        if 2 * int(round(cells)) + 1 > MAX_NODES_PER_AXIS:
            raise ValueError(f"terrain patch '{pid}': {2 * int(round(cells)) + 1} nodes per axis, at most {MAX_NODES_PER_AXIS} are written")
        out.append({"id": pid, "half_width_m": half, "spacing_m": spacing})
    if len({p["id"] for p in out}) != len(out):
        raise ValueError("terrain patch ids must be unique")
    if len(out) > MAX_PATCHES:
        raise ValueError(f"at most {MAX_PATCHES} terrain patches are written")
    return sorted(out, key=lambda p: (p["spacing_m"], p["half_width_m"]))


@dataclass
class TerrainPatch:
    """One patch: up coordinate [north index, east index] in metres, NaN without data."""

    id: str
    half_width_m: float
    spacing_m: float
    up_m: np.ndarray
    sources: list = field(default_factory=list)  # {product_id, level, pixel_m, statistic, sha256, node_share[, derived_from_sha256]}

    @property
    def count(self) -> int:
        return int(self.up_m.shape[0])


def patch_axis(half_width_m: float, spacing_m: float) -> np.ndarray:
    cells = int(round(half_width_m / spacing_m))
    return spacing_m * np.arange(-cells, cells + 1, dtype=np.float64)


def compute_patch(terrain, lat_deg: float, lon_deg: float, surface_height_m: float, spec: dict) -> TerrainPatch:
    """The surface around a site on one grid.

    For a node (east, north) the surface point is the one whose position, expressed in the
    site frame, has those two horizontal coordinates. Its distance from the centre of the
    Moon is the reference radius plus the terrain height at its latitude and longitude,
    which in turn depend on that distance; the few iterations below settle it (the place
    moves by the height change times the sine of the angle from the site, 0.026 at 45 km).

    The terrain is read at the coarsest stored level whose pixel is not larger than the
    grid spacing, so that a coarse patch shows averaged ground instead of single samples.
    """
    axis = patch_axis(spec["half_width_m"], spec["spacing_m"])
    east_m, north_m = np.meshgrid(axis, axis)  # [north index, east index]
    e_hat, n_hat, u_hat = site_frame(lat_deg, lon_deg)
    reference = float(terrain.reference_radius_m)
    r0 = reference + float(surface_height_m)
    rho2 = east_m * east_m + north_m * north_m

    radius = np.full(east_m.shape, r0)  # where to look; nodes without data keep their last value
    height, index, sources = None, None, []
    for _ in range(20):
        along_up = np.sqrt(np.maximum(radius * radius - rho2, 0.0))
        p = east_m[..., None] * e_hat + north_m[..., None] * n_hat + along_up[..., None] * u_hat
        lat = np.arctan2(p[..., 2], np.hypot(p[..., 0], p[..., 1])) / DEG
        lon = np.arctan2(p[..., 1], p[..., 0]) / DEG
        height, index, sources = terrain.height_at_pixel_m(lon, lat, spec["spacing_m"])
        new = np.where(np.isfinite(height), reference + height, radius)
        change = float(np.max(np.abs(new - radius)))
        radius = new
        if change < 1e-4:
            break
    up = np.sqrt(np.maximum(radius * radius - rho2, 0.0)) - r0
    up = np.where(np.isfinite(height), up, np.nan)

    used = []
    for k, source in enumerate(sources):
        share = float(np.mean(index == k))
        if share > 0.0:
            used.append({**source, "node_share": share / max(float(np.mean(index >= 0)), 1e-300)})
    return TerrainPatch(spec["id"], spec["half_width_m"], spec["spacing_m"], up.astype(np.float32), used)


def compute_patches(terrain, lat_deg: float, lon_deg: float, surface_height_m: float, specs) -> list[TerrainPatch]:
    return [compute_patch(terrain, lat_deg, lon_deg, surface_height_m, spec) for spec in canonical_patches(specs)]


def patch_warnings(patches: list[TerrainPatch]) -> list[str]:
    out = []
    for patch in patches:
        missing = float(np.mean(np.isnan(patch.up_m)))
        if missing > 0.0:
            out.append(f"terrain patch '{patch.id}': {100.0 * missing:.1f} % of the nodes lie outside the elevation data and are NaN")
    return out
