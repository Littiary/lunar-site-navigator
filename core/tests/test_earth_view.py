"""Contract 0.8: the orientation of the Earth as seen from the Moon, in the direction table.

Three angles per record let a viewer turn a textured Earth the right way: latitude and
longitude of the sub-lunar point, and the position angle of the Earth's north pole
relative to the Moon's north pole. The comparison with JPL Horizons is a separate test
(validation/tests/test_earth_view.py); here the geometry is checked against closed
forms and against SPICE's own routines.

Thresholds were fixed before the first run (CONTRIBUTING.md, rule 5).
"""

import copy
import json
import math
import shutil

import numpy as np
import pytest

from lsncore.contract import ContractError, contract_dir, read_package, validate_package
from lsncore.earth_view import view_angles

# --------------------------------------------------------------------------------------
# THRESHOLDS (fixed before measuring)
# --------------------------------------------------------------------------------------
TOL_CLOSED_FORM_DEG = 1e-9   # the pure geometry against closed forms
TOL_SPICE_DEG = 0.001        # against SPICE's own sub-observer routine
TOL_REBUILT_AXES_DEG = 0.01  # the Earth's axes rebuilt from the three stored angles against SPICE's rotation
TOL_BETWEEN_RECORDS_DEG = 0.05  # the three angles interpolated between hourly records against a direct computation
# --------------------------------------------------------------------------------------

SAMPLE = contract_dir() / "sample"
START, END = "2026-11-14T00:00:00.000Z", "2026-11-21T00:00:00.000Z"
X, Y, Z = np.eye(3)


def rot(axis, angle_deg):
    """Rotation matrix about a unit axis (Rodrigues)."""
    a = np.asarray(axis, dtype=float)
    c, s = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    k = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return c * np.eye(3) + s * k + (1 - c) * np.outer(a, a)


def test_closed_forms_of_the_three_angles():
    """Earth along +X of the Moon frame; its axes are turned one way at a time."""
    to_earth = 384_400.0 * X
    # 1. pole along the Moon's north, prime meridian facing the Moon
    lat, lon, angle = view_angles(to_earth, Z, -X)
    assert max(abs(lat), abs(lon), abs(angle)) <= TOL_CLOSED_FORM_DEG
    # 2. the Earth turned eastward by W about its pole: the Moon is over longitude -W
    for w in (10.0, 100.0, 179.0, -45.0):
        lat, lon, angle = view_angles(to_earth, Z, rot(Z, w) @ -X)
        assert lon == pytest.approx(-w, abs=TOL_CLOSED_FORM_DEG) and abs(lat) <= TOL_CLOSED_FORM_DEG and abs(angle) <= TOL_CLOSED_FORM_DEG
    # 3. the north pole tipped towards the Moon by t: the Moon stands over geocentric latitude t;
    #    on a flattened Earth the latitude on the map is atan(tan t / (1 - f)^2)
    for t, f in ((20.0, 0.0), (20.0, 1.0 / 298.257), (-28.0, 1.0 / 298.257)):
        tip = rot(Y, -t)  # turns Z towards -X, the direction from the Earth to the Moon
        lat, lon, angle = view_angles(to_earth, tip @ Z, tip @ -X, flattening=f)
        expected = math.degrees(math.atan(math.tan(math.radians(t)) / (1.0 - f) ** 2))
        assert lat == pytest.approx(expected, abs=TOL_CLOSED_FORM_DEG) and abs(lon) <= TOL_CLOSED_FORM_DEG
        assert abs(angle) <= TOL_CLOSED_FORM_DEG  # still straight up in the sky
    # 4. the north pole tipped sideways in the sky by a, towards the east of the sky
    #    (east = north x line of sight = Z x X = +Y): position angle a, counter-clockwise
    for a in (23.4, -23.4, 90.0):
        tip = rot(X, -a)  # turns Z towards +Y
        lat, lon, angle = view_angles(to_earth, tip @ Z, tip @ -X)
        assert angle == pytest.approx(a, abs=TOL_CLOSED_FORM_DEG) and abs(lat) <= TOL_CLOSED_FORM_DEG and abs(lon) <= TOL_CLOSED_FORM_DEG
    # arrays work the same
    lat, lon, angle = view_angles(np.tile(to_earth, (4, 1)), np.tile(Z, (4, 1)), np.array([rot(Z, w) @ -X for w in (0.0, 30.0, 60.0, 90.0)]))
    assert np.allclose(lon, [0.0, -30.0, -60.0, -90.0], atol=TOL_CLOSED_FORM_DEG)


def rebuilt_axes(to_earth, lat_deg, lon_deg, angle_deg, flattening):
    """The recipe of SPEC section 6 for a viewer, written out independently of the core:
    north pole and prime-meridian axis of the Earth in the frame of the table."""
    g = np.asarray(to_earth, dtype=float)
    g = g / np.linalg.norm(g)
    east = np.cross(Z, g)
    east /= np.linalg.norm(east)
    north = np.cross(g, east)
    centric = math.atan(math.tan(math.radians(lat_deg)) * (1.0 - flattening) ** 2)
    a = math.radians(angle_deg)
    pole = math.sin(centric) * -g + math.cos(centric) * (math.cos(a) * north + math.sin(a) * east)
    meridian = -g - math.sin(centric) * pole  # the half-plane of the pole that holds the Moon
    meridian /= np.linalg.norm(meridian)
    lam = math.radians(lon_deg)
    return pole, math.cos(lam) * meridian - math.sin(lam) * np.cross(pole, meridian)


@pytest.fixture(scope="module")
def spice_world():
    spice = pytest.importorskip("spiceypy")
    from lsncore.ephem import directions as d
    from lsncore.ephem import kernels

    try:
        if not kernels.stations_available():
            pytest.skip("the Earth orientation kernels are not installed: python -m lsncore.ephem.fetch_kernels")
        kernels.load_stations()
    except FileNotFoundError as missing:
        pytest.skip(f"kernels are not on this machine: {missing}")
    return spice, d


def separation_deg(a, b):
    return math.degrees(math.atan2(np.linalg.norm(np.cross(a, b)), float(np.dot(a, b))))


def test_against_the_sub_observer_routine_and_the_rotation_of_spice(spice_world):
    from lsncore.earth_view import earth_view

    spice, d = spice_world
    rng = np.random.default_rng(20261114)
    et = np.sort(rng.uniform(float(d.utc_to_et("2026-11-14T00:00:00")), float(d.utc_to_et("2028-11-14T00:00:00")), 300))
    view = earth_view(et)
    radii = spice.bodvrd("EARTH", "RADII", 3)[1]
    flattening = (radii[0] - radii[2]) / radii[0]
    assert view["flattening"] == pytest.approx(flattening, abs=1e-12)
    worst_point, worst_axes = 0.0, 0.0
    for k, t in enumerate(et):
        point, epoch, _ = spice.subpnt("INTERCEPT/ELLIPSOID", "EARTH", float(t), "ITRF93", d.ABCORR, "MOON")
        lon, lat, _ = spice.recgeo(point, radii[0], flattening)
        worst_point = max(worst_point, abs(view["sub_lunar_lat_deg"][k] - math.degrees(lat)), abs((view["sub_lunar_lon_deg"][k] - math.degrees(lon) + 180.0) % 360.0 - 180.0))
        # the axes a viewer rebuilds from the three numbers as the package stores them (float32)
        to_earth, light_time = spice.spkpos("EARTH", float(t), d.FRAME, d.ABCORR, "MOON")
        pole, prime = rebuilt_axes(to_earth, np.float32(view["sub_lunar_lat_deg"][k]), np.float32(view["sub_lunar_lon_deg"][k]), np.float32(view["north_pole_angle_deg"][k]), flattening)
        rotation = np.array(spice.pxfrm2("ITRF93", d.FRAME, float(t) - light_time, float(t)))
        worst_axes = max(worst_axes, separation_deg(pole, rotation[:, 2]), separation_deg(prime, rotation[:, 0]))
    assert worst_point <= TOL_SPICE_DEG
    assert worst_axes <= TOL_REBUILT_AXES_DEG
    # plausibility: the Moon never stands farther from the Earth's equator than 28.7 degrees,
    # and the two north poles are never more than 23.44 + 1.54 + 6.7 degrees apart in the sky
    assert np.abs(view["sub_lunar_lat_deg"]).max() < 29.0 and np.abs(view["north_pole_angle_deg"]).max() < 32.0
    assert view["sub_lunar_lon_deg"].min() > -180.0 - 1e-9 and view["sub_lunar_lon_deg"].max() <= 180.0


@pytest.fixture(scope="module")
def table(spice_world, tmp_path_factory):
    from lsncore.ephem import table as ephem_table

    path = ephem_table.write_direction_table(tmp_path_factory.mktemp("table"), START, END)
    validate_package(path)
    return read_package(path)


def test_direction_table_carries_the_earth_view(spice_world, table):
    from lsncore.earth_view import earth_view
    from lsncore.timeline import TimeGrid

    manifest = table.manifest
    block = manifest["earth_view"]
    count = manifest["time"]["count"]
    assert manifest["request"]["earth_view"] is True
    for name in ("sub_lunar_lat_deg", "sub_lunar_lon_deg", "north_pole_angle_deg"):
        ref = block[name]
        assert ref["shape"] == [count] and ref["dtype"] == "<f4" and ref["unit"] == "deg" and ref["method"] == block["method"]
    assert block["earth_frame"] == "ITRF93" and 0.0033 < block["flattening"] < 0.0034
    card = manifest["methods"][block["method"]]
    assert "Horizons" in " ".join(card["validation"]["evidence"])
    # the Earth's orientation is traceable: its kernels are inputs of the package, after the base set
    base, extra = manifest["inputs"]["kernels"], manifest["inputs"]["earth_orientation_kernels"]
    assert extra and all(k["name"].startswith("earth_") and k["name"].endswith(".bpc") and len(k["sha256"]) == 64 for k in extra)
    assert [k["load_order"] for k in base + extra] == list(range(len(base) + len(extra)))
    # the stored values are the computed ones
    et = TimeGrid.from_contract(manifest["time"]).times()
    direct = earth_view(et)
    for name in ("sub_lunar_lat_deg", "sub_lunar_lon_deg", "north_pole_angle_deg"):
        assert np.abs((table.array(block[name]) - direct[name] + 180.0) % 360.0 - 180.0).max() < 1e-4
    # the table still reads back for the event finder
    from lsncore.ephem import table as ephem_table

    assert ephem_table.load_table(table.path).et.size == count


def test_angles_between_hourly_records(spice_world, table):
    """What the contract tells a viewer to do between records: latitude and angle linearly,
    longitude linearly the short way round."""
    from lsncore.earth_view import earth_view
    from lsncore.timeline import TimeGrid

    manifest = table.manifest
    block = manifest["earth_view"]
    et = TimeGrid.from_contract(manifest["time"]).times()
    lat, lon, angle = (table.array(block[name]).astype(float) for name in ("sub_lunar_lat_deg", "sub_lunar_lon_deg", "north_pole_angle_deg"))
    rng = np.random.default_rng(7)
    u = rng.uniform(0.0, 1.0, et.size - 1)
    query = et[:-1] + u * (et[1:] - et[:-1])
    direct = earth_view(query)
    step = (lon[1:] - lon[:-1] + 180.0) % 360.0 - 180.0
    wrapped = lambda x: (x + 180.0) % 360.0 - 180.0  # noqa: E731
    assert np.abs(lat[:-1] + u * (lat[1:] - lat[:-1]) - direct["sub_lunar_lat_deg"]).max() <= TOL_BETWEEN_RECORDS_DEG
    assert np.abs(angle[:-1] + u * (angle[1:] - angle[:-1]) - direct["north_pole_angle_deg"]).max() <= TOL_BETWEEN_RECORDS_DEG
    assert np.abs(wrapped(lon[:-1] + u * step - direct["sub_lunar_lon_deg"])).max() <= TOL_BETWEEN_RECORDS_DEG


def test_validator_rejects_an_earth_view_of_the_wrong_length(spice_world, table, tmp_path):
    dst = tmp_path / table.path.name
    shutil.copytree(table.path, dst)
    manifest = json.loads((dst / "manifest.json").read_text())
    broken = copy.deepcopy(manifest)
    broken["earth_view"]["north_pole_angle_deg"]["shape"] = [manifest["time"]["count"] - 1]
    (dst / "manifest.json").write_text(json.dumps(broken))
    with pytest.raises(ContractError) as info:
        validate_package(dst)
    assert "earth_view" in str(info.value)


def test_sample_table_carries_an_invented_earth_view():
    (path,) = (SAMPLE / "packages" / "direction_table").iterdir()
    manifest = validate_package(path)
    pkg = read_package(path)
    block = manifest["earth_view"]
    assert manifest["synthetic"] and manifest["methods"][block["method"]]["validation"]["status"] == "synthetic"
    for name in ("sub_lunar_lat_deg", "sub_lunar_lon_deg", "north_pole_angle_deg"):
        values = pkg.array(block[name])
        assert values.shape == (manifest["time"]["count"],) and np.isfinite(values).all()
    assert np.abs(pkg.array(block["sub_lunar_lon_deg"])).max() <= 180.0
