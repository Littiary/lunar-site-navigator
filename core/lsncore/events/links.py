"""Direct-to-Earth link windows between a lunar site and ground stations.

A direct link with a station is geometrically possible when two conditions hold at once:

* Moon end: the station, a point on the Earth's disc, is above the terrain horizon of the
  lunar site by at least the lunar-end mask;
* Earth end: the lunar site is above the station's horizon by at least the station mask.

A station window is an interval in which both hold. The network window is the union over
the stations. This is geometry only: no link budget, no antenna pattern, no azimuth-
dependent station masks, no scheduling.

Relay need. The outages of the network are sorted by cause, because the remedy differs:
an Earth-end gap is closed by another station; a Moon-end outage (no station above the
lunar terrain) can only be closed by a relay or by waiting.

=====  ==========================================================================
level  meaning within the computed range
=====  ==========================================================================
0      a direct link is possible at all times
1      interrupted only because no station has the Moon above its mask
2      interrupted by lunar terrain for part of the time: relay or waiting needed
3      no station is ever above the lunar terrain: a relay is required
=====  ==========================================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from ..timeline import IntervalSet
from . import finder
from .eclipse import _intervals

DEFAULT_SCAN_STEP_S = 120.0
DEFAULT_TOL_S = 0.5

RELAY_NEED_LABELS = {
    0: "direct link possible at all times",
    1: "direct link interrupted only by station gaps on the Earth",
    2: "direct link interrupted by lunar terrain: relay or waiting needed during those outages",
    3: "no station is ever above the lunar terrain: relay required",
}


@dataclass(frozen=True)
class LinkGeometry:
    """Both ends of the link for S stations and N epochs."""

    et: np.ndarray  # [N]
    station_az_deg: np.ndarray  # [S, N] azimuth of the station in the sky of the lunar site
    station_el_deg: np.ndarray  # [S, N] elevation of the station above the site's horizontal plane
    site_el_at_station_deg: np.ndarray  # [S, N] elevation of the lunar site above the station's horizontal plane


Geometry = Callable[[np.ndarray], LinkGeometry]


@dataclass(frozen=True)
class LinkWindows:
    start_et_s: float
    stop_et_s: float
    station_windows: list  # per station: array [M, 2]
    station_causes: list  # per station: list of (cause at start, cause at end): "earth_end", "moon_end" or "range"
    network_windows: np.ndarray  # [M, 2] union over the stations
    terrain_outages: np.ndarray  # [M, 2] intervals in which no station is above the lunar terrain (and mask)
    relay_need_level: int
    station_mask_deg: float
    moon_mask_deg: float
    scan_step_s: float
    tol_s: float

    @property
    def relay_need_label(self) -> str:
        return RELAY_NEED_LABELS[self.relay_need_level]

    def network_share(self) -> float:
        return float((self.network_windows[:, 1] - self.network_windows[:, 0]).sum() / (self.stop_et_s - self.start_et_s)) if len(self.network_windows) else 0.0

    def longest_outage_s(self) -> float:
        return IntervalSet(self.network_windows, (self.start_et_s, self.stop_et_s)).complement().longest_s()

    def longest_terrain_outage_s(self) -> float:
        return float((self.terrain_outages[:, 1] - self.terrain_outages[:, 0]).max()) if len(self.terrain_outages) else 0.0


def _margins(geometry: LinkGeometry, horizon: finder.Horizon, station_mask_deg: float, moon_mask_deg: float):
    moon = geometry.station_el_deg - horizon.elevation_at(geometry.station_az_deg) - moon_mask_deg
    earth = geometry.site_el_at_station_deg - station_mask_deg
    return moon, earth


def _array(intervals) -> np.ndarray:
    return np.array([(a, b) for a, b, *_ in intervals], dtype=np.float64).reshape(-1, 2)


def find_link_windows(
    geometry: Geometry,
    horizon: finder.Horizon,
    start_et_s: float,
    stop_et_s: float,
    station_mask_deg: float,
    moon_mask_deg: float = 0.0,
    scan_step_s: float = DEFAULT_SCAN_STEP_S,
    tol_s: float = DEFAULT_TOL_S,
) -> LinkWindows:
    """Station windows, network window and relay need between two epochs.

    Conditions are sampled every ``scan_step_s``; every change is located by bisection to
    ``tol_s``. Two changes of the same condition closer together than the scan step can be
    missed (a station pass lasts hours, the lunar-end condition changes over hours or days).
    """
    if stop_et_s <= start_et_s:
        raise ValueError("stop must be after start")
    count = int(np.ceil((stop_et_s - start_et_s) / scan_step_s)) + 1
    grid = np.linspace(start_et_s, stop_et_s, max(count, 2))
    domain = (float(start_et_s), float(stop_et_s))
    n_stations = geometry(grid[:1]).station_el_deg.shape[0]

    def both(k):
        def condition(et):
            moon, earth = _margins(geometry(et), horizon, station_mask_deg, moon_mask_deg)
            return (moon[k] > 0.0) & (earth[k] > 0.0)

        return condition

    def any_above_terrain(et):
        moon, _ = _margins(geometry(et), horizon, station_mask_deg, moon_mask_deg)
        return np.any(moon > 0.0, axis=0)

    station_windows, station_causes = [], []
    for k in range(n_stations):
        found = _intervals(both(k), grid, tol_s)
        windows = _array(found)
        causes = []
        for begin, end, clipped_start, clipped_end in found:
            edge = []
            for time, clipped in ((begin, clipped_start), (end, clipped_end)):
                if clipped:
                    edge.append("range")
                    continue
                moon, earth = _margins(geometry(np.array([time])), horizon, station_mask_deg, moon_mask_deg)
                edge.append("moon_end" if abs(moon[k, 0]) < abs(earth[k, 0]) else "earth_end")
            causes.append(tuple(edge))
        station_windows.append(windows)
        station_causes.append(causes)

    network = IntervalSet([tuple(w) for windows in station_windows for w in windows], domain)
    visible = IntervalSet([(a, b) for a, b, *_ in _intervals(any_above_terrain, grid, tol_s)], domain)
    terrain_outages = np.array(visible.complement().as_list(), dtype=np.float64).reshape(-1, 2)

    span = domain[1] - domain[0]
    if visible.total_s() <= 0.0:
        level = 3
    elif len(terrain_outages):
        level = 2
    elif network.total_s() < span - 2.0 * tol_s:
        level = 1
    else:
        level = 0
    return LinkWindows(
        start_et_s=domain[0],
        stop_et_s=domain[1],
        station_windows=station_windows,
        station_causes=station_causes,
        network_windows=np.array(network.as_list(), dtype=np.float64).reshape(-1, 2),
        terrain_outages=terrain_outages,
        relay_need_level=level,
        station_mask_deg=float(station_mask_deg),
        moon_mask_deg=float(moon_mask_deg),
        scan_step_s=float(scan_step_s),
        tol_s=float(tol_s),
    )
