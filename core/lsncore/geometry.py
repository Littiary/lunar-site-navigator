"""Geometry on a sphere: site frame, great-circle steps, topocentric directions.

Conventions (docs/contract/SPEC.md, section 2):
- latitude and east-positive longitude in degrees, planetocentric, on a sphere;
- local frame East/North/Up, "up" being the outward radial direction;
- azimuth clockwise from north (north 0, east 90), elevation above the local horizontal.
"""

from __future__ import annotations

import numpy as np

DEG = np.pi / 180.0


def canonical_lon(lon_deg: float) -> float:
    """Wrap a longitude to the canonical range (-180, 180]."""
    lon = (float(lon_deg) + 180.0) % 360.0 - 180.0
    return 180.0 if lon == -180.0 else lon


def site_frame(lat_deg: float, lon_deg: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """East, north and up unit vectors of a site, in the body-fixed frame.

    At the poles east and north are not defined by the position alone; the formulas below
    are then evaluated with the longitude that was given, which fixes the azimuth zero
    along that meridian.
    """
    lat, lon = lat_deg * DEG, lon_deg * DEG
    sl, cl = np.sin(lat), np.cos(lat)
    so, co = np.sin(lon), np.cos(lon)
    east = np.array([-so, co, 0.0])
    north = np.array([-sl * co, -sl * so, cl])
    up = np.array([cl * co, cl * so, sl])
    return east, north, up


def destination(lat_deg: float, lon_deg: float, azimuth_deg, arc_rad):
    """Point reached from a site along a great circle.

    azimuth_deg and arc_rad (central angle) broadcast against each other. Built from unit
    vectors, so it stays well conditioned at the poles. Returns (lat_deg, lon_deg).
    """
    east, north, up = site_frame(lat_deg, lon_deg)
    az = np.asarray(azimuth_deg, dtype=np.float64) * DEG
    arc = np.asarray(arc_rad, dtype=np.float64)
    heading = np.sin(az)[..., None] * east + np.cos(az)[..., None] * north
    p = np.cos(arc)[..., None] * up + np.sin(arc)[..., None] * heading
    lat = np.arctan2(p[..., 2], np.hypot(p[..., 0], p[..., 1])) / DEG
    lon = np.arctan2(p[..., 1], p[..., 0]) / DEG
    return lat, lon


def topocentric_az_el(target_km: np.ndarray, site_position_km: np.ndarray, frame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Azimuth, elevation (degrees) and range (km) of body-fixed positions seen from a site.

    target_km has shape [..., 3] and is given relative to the centre of the Moon in the
    same body-fixed frame as the site position.
    """
    east, north, up = frame
    d = np.asarray(target_km, dtype=np.float64) - site_position_km
    rng = np.linalg.norm(d, axis=-1)
    e, n, u = d @ east, d @ north, d @ up
    az = np.mod(np.arctan2(e, n) / DEG, 360.0)
    el = np.arcsin(np.clip(u / rng, -1.0, 1.0)) / DEG
    return az, el, rng
