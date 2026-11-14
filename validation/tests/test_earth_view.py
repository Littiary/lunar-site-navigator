"""The orientation of the Earth against JPL Horizons, as a test: green means every query is
inside the thresholds fixed beforehand.

Runs offline from the stored raw responses; it never contacts Horizons.
"""

import hashlib
import json

import pytest

from validation.earth_view import compare
from validation.earth_view.compare import HERE, RAW
from validation.horizons.fetch import iter_cases, load_cases


@pytest.fixture(scope="module")
def station_kernels():
    from lsncore.ephem import kernels

    try:
        if not kernels.stations_available():
            pytest.skip("the Earth orientation kernels are not installed: python -m lsncore.ephem.fetch_kernels")
        kernels.load_stations()
    except FileNotFoundError as missing:
        pytest.skip(f"kernels are not on this machine: {missing}")


def test_raw_responses_are_complete_and_unmodified():
    case_ids = [case_id for case_id, *_ in iter_cases(load_cases(HERE))]
    assert len(case_ids) == 4
    for case_id in case_ids:
        meta = json.loads((RAW / f"{case_id}.meta.json").read_text(encoding="utf-8"))
        payload = (RAW / f"{case_id}.json").read_bytes()
        assert hashlib.sha256(payload).hexdigest() == meta["sha256"], case_id
        assert len(payload) == meta["bytes"], case_id


def test_earth_view_agrees_with_horizons_within_fixed_thresholds(station_kernels):
    limits = {key: item["value"] for key, item in json.loads((HERE / "thresholds.json").read_text(encoding="utf-8"))["thresholds"].items()}
    assert limits == {"sub_lunar_latitude_deg_max": 0.05, "sub_lunar_longitude_deg_max": 0.05, "north_pole_angle_deg_max": 0.1}  # this file does not define them
    report = compare.run()
    assert len(report["cases"]) == 4 and report["rows"] >= 2 * 169 + 2 * 100
    for row in report["cases"]:
        assert row["status"] == "PASS", row["case_id"]
    assert report["worst"]["sub_lunar_latitude_deg"] < limits["sub_lunar_latitude_deg_max"]
    assert report["worst"]["sub_lunar_longitude_deg"] < limits["sub_lunar_longitude_deg_max"]
    assert report["worst"]["north_pole_angle_deg"] < limits["north_pole_angle_deg_max"]
