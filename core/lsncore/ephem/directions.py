"""Directions and angular sizes of the Sun and the Earth seen from the Moon.

Conventions (see ``core/lsncore/ephem/README.md`` for the reasons):

* Body-fixed frame: ``MOON_ME_DE440_ME421`` -- the lunar mean-Earth/polar-axis
  frame realised from the DE440 principal-axis orientation and aligned with the
  DE421 mean-Earth frame, which is the frame of the LOLA elevation products.
* Site coordinates: planetocentric latitude, east-positive longitude, height
  above the 1737.4 km reference sphere.
* Local frame: East, North, Up with Up = the outward normal of that sphere.
  Azimuth is measured from north through east; elevation from the local
  horizontal plane (not from the visible horizon).
* Aberration correction: ``LT+S`` (one-way light time and stellar aberration,
  reception case): the direction in which the body is seen.
* Time: computation in TDB seconds past J2000 (SPICE "ET"); UTC only at the
  interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import spiceypy as spice

from . import kernels

MOON_RADIUS_KM = 1737.4
FRAME = "MOON_ME_DE440_ME421"
ABCORR = "LT+S"
BODIES = ("SUN", "EARTH")

# Radius used for the apparent angular radius of each disc, km.
# Sun: IAU nominal value as in pck00011. Earth: equatorial radius, i.e. the
# largest half-width of the slightly flattened disc (polar radius is 21.4 km
# less, about 0.3 % of the angular radius).
_RADIUS_INDEX = {"SUN": 0, "EARTH": 0}


def body_radius_km(body: str) -> float:
    kernels.load()
    return float(spice.bodvrd(body, "RADII", 3)[1][_RADIUS_INDEX[body]])


# --------------------------------------------------------------------------- time


def utc_to_et(utc):
    """UTC calendar string(s) (ISO 8601, with or without a trailing Z) -> TDB seconds past J2000."""
    kernels.load()
    if isinstance(utc, str):
        return float(spice.str2et(utc.rstrip("Zz")))
    return np.array([spice.str2et(item.rstrip("Zz")) for item in utc], dtype=np.float64)


def et_to_utc(et, precision: int = 3):
    """TDB seconds past J2000 -> UTC ISO 8601 string(s)."""
    kernels.load()
    if np.ndim(et) == 0:
        return spice.et2utc(float(et), "ISOC", precision)
    return [spice.et2utc(float(item), "ISOC", precision) for item in np.asarray(et)]


def et_to_utc_z(et: float) -> str:
    """TDB seconds past J2000 -> the contract's display form, 2026-11-14T09:00:00.000Z.

    SPICE rounds to the millisecond. A grid that is uniform in TDB is uniform in UTC only
    to about a millisecond, because TDB - UTC has a periodic term of up to 1.7 ms: a
    sample that is nominally on a whole UTC second can print as ...59.999 or ...00.001.
    """
    return et_to_utc(float(et), 3) + "Z"


def leap_seconds_between(et_start: float, et_end: float) -> int:
    """Number of leap seconds inserted between two epochs (0 for any range after 2017 with naif0012)."""
    kernels.load()
    return int(round(spice.deltet(float(et_end), "ET") - spice.deltet(float(et_start), "ET")))


# --------------------------------------------------------------------------- site


@dataclass(frozen=True)
class Site:
    """A point on or above the lunar reference sphere, in the mean-Earth frame."""

    lon_deg: float  # east positive; any of -180..180 or 0..360
    lat_deg: float  # planetocentric
    height_km: float = 0.0  # above the 1737.4 km sphere

    def enu(self):
        """Unit vectors East, North, Up expressed in the body-fixed frame."""
        lon, lat = np.radians(self.lon_deg), np.radians(self.lat_deg)
        up = np.array([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])
        east = np.array([-np.sin(lon), np.cos(lon), 0.0])
        north = np.cross(up, east)
        return east, north, up

    @property
    def position_km(self) -> np.ndarray:
        return (MOON_RADIUS_KM + self.height_km) * self.enu()[2]


# --------------------------------------------------------------------------- results


@dataclass(frozen=True)
class Topocentric:
    """Apparent direction of one body from one site, per epoch."""

    et: np.ndarray
    az_deg: np.ndarray  # 0..360, north = 0, east = 90
    el_deg: np.ndarray  # above the local horizontal plane of the reference sphere
    range_km: np.ndarray
    angular_radius_deg: np.ndarray


@dataclass(frozen=True)
class DirectionTable:
    """Site-independent apparent positions of the Sun and the Earth.

    Vectors are from the Moon's centre, in the body-fixed frame, corrected for
    light time and stellar aberration for an observer at the Moon's centre.
    A site direction is obtained by subtracting the site position vector
    (``topocentric_from_table``); the cost of using the centre instead of the
    site for the corrections is measured in the tests and in the validation.
    """

    et: np.ndarray  # TDB seconds past J2000, float64
    sun_km: np.ndarray  # (N, 3)
    earth_km: np.ndarray  # (N, 3)
    frame: str = FRAME
    abcorr: str = ABCORR
    observer: str = "MOON"
    time_scale: str = "TDB seconds past J2000"
    kernel_set_id: str = ""
    radii_km: dict = field(default_factory=dict)

    def vectors(self, body: str) -> np.ndarray:
        return {"SUN": self.sun_km, "EARTH": self.earth_km}[body]


def _as_array(et) -> np.ndarray:
    return np.atleast_1d(np.asarray(et, dtype=np.float64))


def _project(site: Site, vectors_km: np.ndarray, et: np.ndarray, radius_km: float) -> Topocentric:
    east, north, up = site.enu()
    e, n, u = vectors_km @ east, vectors_km @ north, vectors_km @ up
    rng = np.sqrt(e * e + n * n + u * u)
    el = np.degrees(np.arctan2(u, np.hypot(e, n)))
    az = np.degrees(np.arctan2(e, n)) % 360.0
    return Topocentric(et, az, el, rng, np.degrees(np.arcsin(radius_km / rng)))


# --------------------------------------------------------------------------- computations


def direction_table(et) -> DirectionTable:
    """Apparent Moon-centre -> Sun and Moon-centre -> Earth vectors for every epoch."""
    kernels.load()
    et = _as_array(et)
    sun, _ = spice.spkpos("SUN", et, FRAME, ABCORR, "MOON")
    earth, _ = spice.spkpos("EARTH", et, FRAME, ABCORR, "MOON")
    return DirectionTable(
        et=et,
        sun_km=np.asarray(sun, dtype=np.float64).reshape(-1, 3),
        earth_km=np.asarray(earth, dtype=np.float64).reshape(-1, 3),
        kernel_set_id=kernels.kernel_set_id(),
        radii_km={body: body_radius_km(body) for body in BODIES},
    )


def topocentric_from_table(site: Site, table: DirectionTable) -> dict[str, Topocentric]:
    """Azimuth, elevation, range and angular radius of both bodies from a site, using the table."""
    position = site.position_km
    return {
        body: _project(site, table.vectors(body) - position, table.et, table.radii_km[body])
        for body in BODIES
    }


def topocentric_exact(site: Site, et, body: str) -> Topocentric:
    """Reference computation: observer at the site itself (SPICE ``spkcpo``, LT+S).

    Slower than the table path (one SPICE call per epoch); used for validation
    and wherever the last 0.1 arcsecond matters.
    """
    kernels.load()
    et = _as_array(et)
    position = site.position_km
    vectors = np.empty((et.size, 3))
    for i, epoch in enumerate(et):
        state, _ = spice.spkcpo(body, float(epoch), FRAME, "OBSERVER", ABCORR, position, "MOON", FRAME)
        vectors[i] = state[:3]
    return _project(site, vectors, et, body_radius_km(body))


def topocentric_azlcpo(site: Site, et, body: str):
    """Independent check through the SPICE routine ``azlcpo`` (not used in production).

    Returns azimuth (deg, clockwise from north), elevation (deg) and range (km).
    ``azlcpo`` builds its own local frame from the ellipsoid normal, so it does
    not share our East-North-Up code.
    """
    kernels.load()
    et = _as_array(et)
    position = site.position_km
    az, el, rng = np.empty(et.size), np.empty(et.size), np.empty(et.size)
    for i, epoch in enumerate(et):
        azlsta, _ = spice.azlcpo("ELLIPSOID", body, float(epoch), ABCORR, False, True, position, "MOON", FRAME)
        rng[i], az[i], el[i] = azlsta[0], np.degrees(azlsta[1]) % 360.0, np.degrees(azlsta[2])
    return az, el, rng


def angular_separation_deg(az1_deg, el1_deg, az2_deg, el2_deg) -> np.ndarray:
    """Great-circle angle between two directions given as azimuth and elevation (deg)."""
    az1, el1, az2, el2 = (np.radians(np.asarray(x, dtype=np.float64)) for x in (az1_deg, el1_deg, az2_deg, el2_deg))
    # Haversine form: accurate for very small separations.
    h = np.sin((el2 - el1) / 2.0) ** 2 + np.cos(el1) * np.cos(el2) * np.sin((az2 - az1) / 2.0) ** 2
    return np.degrees(2.0 * np.arcsin(np.sqrt(np.clip(h, 0.0, 1.0))))


# --------------------------------------------------------------------------- interpolation


def interpolate_table(table: DirectionTable, et) -> DirectionTable:
    """Direction table at arbitrary epochs by 4-point (cubic) Lagrange interpolation of the vectors.

    The table must be on a uniform time grid. Vectors are interpolated, never
    angles, so there is no wrap-around problem. The interpolation error for an
    hourly table is measured in the tests (below 0.01 arcsec).
    """
    et = _as_array(et)
    grid = table.et
    count = grid.size
    if count < 4:
        raise ValueError("interpolation needs at least 4 table epochs")
    step = (grid[-1] - grid[0]) / (count - 1)
    if not np.allclose(np.diff(grid), step, rtol=0.0, atol=1e-6):
        raise ValueError("direction table is not on a uniform time grid")
    if et.min() < grid[0] - 1e-6 or et.max() > grid[-1] + 1e-6:
        raise ValueError("requested epoch outside the direction table")
    x = (et - grid[0]) / step
    i = np.clip(np.floor(x).astype(np.int64), 1, count - 3)  # stencil i-1 .. i+2
    u = (x - i)[:, None]
    w_m1 = -u * (u - 1.0) * (u - 2.0) / 6.0
    w_0 = (u + 1.0) * (u - 1.0) * (u - 2.0) / 2.0
    w_p1 = -(u + 1.0) * u * (u - 2.0) / 2.0
    w_p2 = (u + 1.0) * u * (u - 1.0) / 6.0

    def interpolate(vectors):
        return w_m1 * vectors[i - 1] + w_0 * vectors[i] + w_p1 * vectors[i + 1] + w_p2 * vectors[i + 2]

    return DirectionTable(
        et=et,
        sun_km=interpolate(table.sun_km),
        earth_km=interpolate(table.earth_km),
        frame=table.frame,
        abcorr=table.abcorr,
        observer=table.observer,
        time_scale=table.time_scale,
        kernel_set_id=table.kernel_set_id,
        radii_km=table.radii_km,
    )
