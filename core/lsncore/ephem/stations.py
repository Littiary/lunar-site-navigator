"""Ground stations: where they are seen from a lunar site, and how high the site stands for them.

Stations are the three Deep Space Network complexes, represented by their 70 m antennas.
Their positions come from the NAIF station kernel (ITRF93), the orientation of the Earth
from the NAIF Earth orientation kernels, the local vertical of each station from the NAIF
topocentric frames (normal to the reference spheroid). These kernels are an optional
group: see ``kernels.STATION_KERNEL_SET``.

Two computation paths, as for the Sun and the Earth:

* fast path: positions and zenith directions of the stations, relative to the Moon's
  centre and in the Moon body-fixed frame, are tabulated every 10 minutes (the Earth turns
  2.5 degrees in that time) and interpolated. Both ends of the link are evaluated at the
  same instant, so the light time between them (about 1.3 s) is ignored: the elevation at
  the station can be off by up to 0.006 degree, a station rise or set by about 1.3 s;
* exact path: one SPICE call per epoch with the observer at the site or at the station;
  used for validation.

Elevation limits of the stations (DSN 810-005, module 301, Rev. N): 6.0 degrees to
receive, 10.0 degrees to transmit at low power. Azimuth-dependent masks are not modelled.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import spiceypy as spice

from ..events.links import LinkGeometry
from . import directions as d
from . import kernels

RECEIVE_MASK_DEG = 6.0
TRANSMIT_MASK_DEG = 10.0
MASK_SOURCE = "DSN Telecommunications Link Design Handbook 810-005, module 301 'Coverage and Geometry', Rev. N, 15 April 2022"
TABLE_STEP_S = 600.0


@dataclass(frozen=True)
class Station:
    name: str  # SPICE name in the station kernel
    window_id: str  # used in window and metric ids
    place: str


DSN_STATIONS = (
    Station("DSS-14", "goldstone", "Goldstone, California (70 m antenna DSS-14)"),
    Station("DSS-43", "canberra", "Canberra, Australia (70 m antenna DSS-43)"),
    Station("DSS-63", "madrid", "Madrid, Spain (70 m antenna DSS-63)"),
)


@dataclass(frozen=True)
class StationTable:
    """Site-independent station data on a uniform time grid."""

    et: np.ndarray  # [N] TDB seconds past J2000
    step_s: float
    stations: tuple
    position_km: np.ndarray  # [S, N, 3] station relative to the Moon's centre, Moon body-fixed frame, LT+S
    zenith: np.ndarray  # [S, N, 3] unit vector of the station's local vertical, Moon body-fixed frame
    frame: str = d.FRAME
    station_kernel_set_id: str = ""


def station_table(start_et_s: float, stop_et_s: float, stations: tuple = DSN_STATIONS, step_s: float = TABLE_STEP_S) -> StationTable:
    """Tabulate the stations from one step before ``start`` to at least one step after ``stop``."""
    kernels.load_stations()
    count = int(np.ceil((stop_et_s - start_et_s) / step_s)) + 4
    et = start_et_s - step_s + step_s * np.arange(count)
    position = np.empty((len(stations), count, 3))
    zenith = np.empty((len(stations), count, 3))
    for k, station in enumerate(stations):
        vectors, _ = spice.spkpos(station.name, et, d.FRAME, d.ABCORR, "MOON")
        position[k] = np.asarray(vectors).reshape(-1, 3)
        topo = f"{station.name}_TOPO"
        for i, epoch in enumerate(et):
            zenith[k, i] = spice.pxform(topo, d.FRAME, float(epoch))[:, 2]
    return StationTable(et, float(step_s), tuple(stations), position, zenith, station_kernel_set_id=kernels.station_kernel_set_id())


def _interpolate(table: StationTable, values: np.ndarray, et: np.ndarray) -> np.ndarray:
    """4-point Lagrange interpolation of values [S, N, 3] along the time axis."""
    count = table.et.size
    if et.min() < table.et[0] - 1e-6 or et.max() > table.et[-1] + 1e-6:
        raise ValueError("requested epoch outside the station table")
    x = (et - table.et[0]) / table.step_s
    i = np.clip(np.floor(x).astype(np.int64), 1, count - 3)
    u = (x - i)[None, :, None]
    w_m1 = -u * (u - 1.0) * (u - 2.0) / 6.0
    w_0 = (u + 1.0) * (u - 1.0) * (u - 2.0) / 2.0
    w_p1 = -(u + 1.0) * u * (u - 2.0) / 2.0
    w_p2 = (u + 1.0) * u * (u - 1.0) / 6.0
    return w_m1 * values[:, i - 1] + w_0 * values[:, i] + w_p1 * values[:, i + 1] + w_p2 * values[:, i + 2]


def link_geometry(site: d.Site, table: StationTable, et) -> LinkGeometry:
    """Fast path: both ends of the link for every station at the given epochs."""
    et = np.atleast_1d(np.asarray(et, dtype=np.float64))
    east, north, up = site.enu()
    to_station = _interpolate(table, table.position_km, et) - site.position_km  # [S, N, 3]
    zenith = _interpolate(table, table.zenith, et)
    zenith /= np.linalg.norm(zenith, axis=2, keepdims=True)
    distance = np.linalg.norm(to_station, axis=2)
    e, n, u = to_station @ east, to_station @ north, to_station @ up
    station_el = np.degrees(np.arctan2(u, np.hypot(e, n)))
    station_az = np.degrees(np.arctan2(e, n)) % 360.0
    site_el = np.degrees(np.arcsin(np.clip(-np.sum(to_station * zenith, axis=2) / distance, -1.0, 1.0)))
    return LinkGeometry(et, station_az, station_el, site_el)


def site_link_geometry(site: d.Site, table: StationTable):
    """Geometry function ``et -> LinkGeometry`` for one site."""

    def geometry(et):
        return link_geometry(site, table, et)

    return geometry


# --------------------------------------------------------------------------- exact path (validation)


def station_from_site_exact(site: d.Site, station_name: str, et):
    """Azimuth and elevation (deg) of a station seen from the lunar site, observer at the site."""
    kernels.load_stations()
    et = np.atleast_1d(np.asarray(et, dtype=np.float64))
    east, north, up = site.enu()
    position = site.position_km
    az, el = np.empty(et.size), np.empty(et.size)
    for i, epoch in enumerate(et):
        state, _ = spice.spkcpo(station_name, float(epoch), d.FRAME, "OBSERVER", d.ABCORR, position, "MOON", d.FRAME)
        vector = state[:3]
        az[i] = np.degrees(np.arctan2(vector @ east, vector @ north)) % 360.0
        el[i] = np.degrees(np.arctan2(vector @ up, np.hypot(vector @ east, vector @ north)))
    return az, el


def site_from_station_exact(site: d.Site, station_name: str, et):
    """Azimuth and elevation (deg) of the lunar site seen from a station, observer at the station.

    The station's topocentric frame has x north, y west, z up; azimuth is returned
    clockwise from north.
    """
    kernels.load_stations()
    et = np.atleast_1d(np.asarray(et, dtype=np.float64))
    position = site.position_km
    topo = f"{station_name}_TOPO"
    az, el = np.empty(et.size), np.empty(et.size)
    for i, epoch in enumerate(et):
        state, _ = spice.spkcpt(position, "MOON", d.FRAME, float(epoch), topo, "OBSERVER", d.ABCORR, station_name)
        x, y, z = state[:3]
        az[i] = np.degrees(np.arctan2(-y, x)) % 360.0
        el[i] = np.degrees(np.arctan2(z, np.hypot(x, y)))
    return az, el
