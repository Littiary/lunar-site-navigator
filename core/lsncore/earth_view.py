"""The orientation of the Earth as seen from the Moon: what a viewer needs to turn a
textured Earth the right way.

Three angles per record of the direction table:

sub_lunar_lat_deg, sub_lunar_lon_deg
    The point of the Earth's surface at the centre of the disc seen from the centre of the
    Moon: latitude as on a map (perpendicular to the reference ellipsoid) and east
    longitude in (-180, 180].
north_pole_angle_deg
    Position angle of the Earth's north pole in the sky of that observer, measured from
    the Moon's north pole (+Z of the body-fixed frame of the table, projected on the
    plane of the sky) counter-clockwise, that is towards the east of the sky,
    east = +Z x (direction to the Earth).

Together with the direction to the Earth, which the table already holds, the three
angles fix the orientation of the Earth completely; SPEC section 6 gives the recipe.
"""

from __future__ import annotations

import numpy as np

from . import packaging as pk

DEG = np.pi / 180.0
EARTH_FRAME = "ITRF93"


def _unit(v: np.ndarray) -> np.ndarray:
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def view_angles(to_earth, pole, prime_meridian, flattening: float = 0.0, reference_north=(0.0, 0.0, 1.0)):
    """Sub-observer latitude, longitude and north-pole position angle, in degrees.

    All vectors in one frame, arrays [..., 3]: to_earth from the observer to the centre of
    the Earth; pole and prime_meridian the unit +Z and +X axes of the Earth-fixed frame;
    reference_north the direction the position angle is counted from. Pure geometry.
    """
    g = _unit(np.asarray(to_earth, dtype=np.float64))
    p = np.asarray(pole, dtype=np.float64)
    x = np.asarray(prime_meridian, dtype=np.float64)
    y = np.cross(p, x)
    back = -g  # from the Earth to the observer
    sine = np.clip(np.sum(back * p, axis=-1), -1.0, 1.0)
    cosine = np.sqrt(1.0 - sine * sine)
    # geocentric latitude of the direction, then the latitude of the surface point the
    # line to the centre passes through, perpendicular to the ellipsoid
    lat = np.arctan2(sine, cosine * (1.0 - flattening) ** 2)
    lon = np.arctan2(np.sum(back * y, axis=-1), np.sum(back * x, axis=-1))
    east = _unit(np.cross(np.asarray(reference_north, dtype=np.float64), g))
    north = np.cross(g, east)
    angle = np.arctan2(np.sum(p * east, axis=-1), np.sum(p * north, axis=-1))
    return lat / DEG, lon / DEG, angle / DEG


def earth_view(et) -> dict:
    """The three angles at TDB epochs, with SPICE.

    The Earth is taken as it appears from the centre of the Moon at the epoch: its
    direction with the aberration correction of the direction table, its orientation at
    the epoch minus the light time. The Earth's orientation comes from the binary
    orientation kernels of the optional kernel group (frame ITRF93).
    """
    import spiceypy as spice

    from .ephem import directions as d
    from .ephem import kernels

    kernels.load_stations()
    epochs = np.atleast_1d(np.asarray(et, dtype=np.float64))
    radii = spice.bodvrd("EARTH", "RADII", 3)[1]
    flattening = float((radii[0] - radii[2]) / radii[0])
    to_earth = np.empty((epochs.size, 3))
    pole = np.empty((epochs.size, 3))
    prime = np.empty((epochs.size, 3))
    for k, t in enumerate(epochs):
        position, light_time = spice.spkpos("EARTH", float(t), d.FRAME, d.ABCORR, "MOON")
        rotation = np.asarray(spice.pxfrm2(EARTH_FRAME, d.FRAME, float(t) - light_time, float(t)))
        to_earth[k], pole[k], prime[k] = position, rotation[:, 2], rotation[:, 0]
    lat, lon, angle = view_angles(to_earth, pole, prime, flattening)
    lon = np.where(lon <= -180.0, lon + 360.0, lon)
    return {
        "sub_lunar_lat_deg": lat,
        "sub_lunar_lon_deg": lon,
        "north_pole_angle_deg": angle,
        "flattening": flattening,
        "earth_frame": EARTH_FRAME,
    }


def orientation_kernels() -> list[dict]:
    """The kernels that hold the Earth's orientation, as the kernel manifest records them."""
    from .ephem import kernels

    listed = {entry["name"]: entry for entry in kernels.read_manifest().get("station_kernels", [])}
    return [listed[k.name] for k in kernels.STATION_KERNEL_SET if k.kind == "binary PCK" and k.name in listed]


def _horizons_evidence() -> list[str]:
    """Evidence lines from the stored comparison with JPL Horizons, if its report is present."""
    import json

    from .ephem import kernels

    report = kernels.REPO_ROOT / "validation" / "earth_view" / "results" / "validation_table.json"
    lines = ["Test validation/tests/test_earth_view.py (comparison with JPL Horizons, thresholds fixed beforehand in validation/earth_view/thresholds.json)."]
    if report.exists():
        table = json.loads(report.read_text(encoding="utf-8"))
        worst = table["worst"]
        lines.append(
            f"{table['rows']} Horizons rows in {len(table['cases'])} queries: sub-lunar latitude within {worst['sub_lunar_latitude_deg']:.4f} deg, "
            f"longitude within {worst['sub_lunar_longitude_deg']:.4f} deg (threshold 0.05 deg each), position angle of the north pole within "
            f"{worst['north_pole_angle_deg']:.4f} deg (threshold 0.1 deg). Report: validation/earth_view/results/validation_table.md."
        )
    lines.append("core/tests/test_earth_view.py: closed forms of the geometry (1e-9 deg), SPICE's own sub-observer routine (0.001 deg), the Earth's axes rebuilt from the three stored angles (0.01 deg), interpolation between hourly records (0.05 deg).")
    return lines


def earth_view_methods(data: list[str], horizons_validated: bool) -> dict:
    """Method card of the Earth view."""
    return {
        pk.M_DIRTAB_EARTH_VIEW: pk.method_card(
            title="Orientation of the Earth as seen from the Moon",
            definition=(
                "sub_lunar_lat_deg, sub_lunar_lon_deg: latitude (perpendicular to the reference ellipsoid, as on a map) and east longitude of the point of the Earth's surface "
                "at the centre of the disc seen from the centre of the Moon. north_pole_angle_deg: position angle of the Earth's north pole in the sky of that observer, "
                "counted from the Moon's north pole (+Z of the body-fixed frame of the table, projected on the plane of the sky) counter-clockwise, towards east = +Z x (direction to the Earth). "
                "All three for the Earth as it appears at the record time: its direction corrected for light time and stellar aberration, its orientation taken one light time earlier."
            ),
            algorithm=(
                "SPICE spkpos for the apparent direction of the Earth and pxfrm2('ITRF93', table frame, record time - light time, record time) for the Earth's axes; "
                "the sub-lunar point is where the line from the Moon's centre to the Earth's centre meets the reference ellipsoid. "
                "Between records: latitude and position angle linearly, longitude linearly the short way round (it wraps at 180 degrees)."
            ),
            frame="Earth: ITRF93 (east longitude, latitude perpendicular to the ellipsoid of the planetary constants kernel). Position angle: body-fixed frame of the table.",
            time_scale="TDB",
            data=data,
            parameters={"earth_frame": EARTH_FRAME, "observer": "centre of the Moon"},
            status="externally-validated" if horizons_validated else "analytic-test-passed",
            evidence=_horizons_evidence(),
            limits=[
                "For drawing the Earth. The observer is the centre of the Moon: from a site on the surface the sub-observer point differs by up to 0.28 deg; that is not modelled.",
                "After the last measured Earth-orientation data the kernels hold a prediction, as Horizons does; the error of the prediction is not quantified here.",
                "No clouds, no day and night on the Earth: the lit part follows from the Sun's direction in the same table and is not computed here.",
            ],
        )
    }
