"""Plain result objects passed from the computing modules to the package builder."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class HorizonResult:
    """Terrain horizon of one site for several observer heights.

    All arrays have shape [number of observer heights, number of azimuths].
    """

    azimuth_step_deg: float
    observer_heights_m: list[float]
    max_range_m: float
    reference_radius_m: float
    surface_height_m: float
    elevation_deg: np.ndarray
    distance_m: np.ndarray
    obstacle_height_m: np.ndarray | None = None
    obstacle_lat_deg: np.ndarray | None = None
    obstacle_lon_deg: np.ndarray | None = None
    coverage_complete: bool = True
    truncated_at_data_edge: bool = False
    nodata_fraction: float = 0.0
    # name -> (value, unit, method id)
    error_bounds: dict[str, tuple[float, str, str]] = field(default_factory=dict)
    # [H, A]: largest amount by which terrain beyond the reach of the data or of the search
    # radius could still raise the horizon in that azimuth
    far_field_bound_deg: np.ndarray | None = None
    dem_pixel: dict | None = None
    warnings: list[str] = field(default_factory=list)
    # how much of each ray was walked on the finest data and how much was proven irrelevant
    search_stats: dict = field(default_factory=dict)
    # grouping of the profile into obstacles (lsncore.obstacles): [H, A] ids and the records
    obstacle_id: np.ndarray | None = None
    obstacles: list | None = None


@dataclass
class BodySeries:
    """Sampled direction and visibility of one body from one site."""

    azimuth_deg: np.ndarray  # [N]
    elevation_deg: np.ndarray  # [N]
    margin_deg: np.ndarray  # [H, N]
    visible_fraction: np.ndarray  # [H, N]
    angular_radius_deg: np.ndarray | None = None  # [N]
    # [H, N] index of the horizon sample that limits the view of the disc (lsncore.blocking)
    blocker_azimuth_index: np.ndarray | None = None


@dataclass
class TimelineResult:
    """Time series, events, windows and metrics of one site.

    'time' is a contract time-grid object; events, windows and metrics are lists of
    objects already shaped as the contract defines them.
    """

    direction_table_id: str
    direction_table_sha256: str
    time: dict
    bodies: list[str]
    series: dict[str, BodySeries]
    events: list[dict]
    windows: list[dict]
    metrics: list[dict]
    thresholds: dict[str, dict] = field(default_factory=dict)
    # obstacles that cost visible time compared with a smooth sphere; None = not computed
    blockers: list | None = None
