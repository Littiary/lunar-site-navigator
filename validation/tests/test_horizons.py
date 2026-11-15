"""The Horizons comparison as a test: green means every case is inside the fixed thresholds.

Runs offline from the stored raw responses; it never contacts Horizons.
"""

import hashlib
import json

from validation.horizons import compare
from validation.horizons.fetch import HERE, RAW, iter_cases, load_cases


def test_raw_responses_are_complete_and_unmodified():
    case_ids = [case_id for case_id, *_ in iter_cases(load_cases())]
    assert len(case_ids) == 28
    for case_id in case_ids:
        meta = json.loads((RAW / f"{case_id}.meta.json").read_text(encoding="utf-8"))
        payload = (RAW / f"{case_id}.json").read_bytes()
        assert hashlib.sha256(payload).hexdigest() == meta["sha256"], case_id
        assert len(payload) == meta["bytes"], case_id


def test_core_agrees_with_horizons_within_fixed_thresholds():
    limits = {key: item["value"] for key, item in json.loads((HERE / "thresholds.json").read_text(encoding="utf-8"))["thresholds"].items()}
    assert limits["direction_arcsec_max"] == 1.0  # the stated target; this file does not define it
    report = compare.run()
    assert len(report["cases"]) == 28
    for row in report["cases"]:
        assert row["status"] == "PASS", row["case_id"]
        assert row["rows"] >= 289
        for path in ("exact", "table"):
            assert row[path]["direction_arcsec_max"] < limits["direction_arcsec_max"]
        assert row["exact"]["angular_diameter_arcsec_max_abs"] < limits["angular_diameter_arcsec_max"]
        assert row["exact"]["range_km_max_abs"] < limits["range_km_max"]
        assert row["tdb_minus_ut_seconds_max_abs"] < limits["tdb_minus_ut_seconds_max"]


def test_the_time_row_sees_an_error_of_the_core_conversion(monkeypatch):
    """Row 5 of the card compares the core's own UTC to TDB conversion with Horizons, not only the leap-second kernel:
    with the conversion shifted by one second the difference is one second, while the kernel alone still agrees."""
    from lsncore.ephem import kernels

    kernels.load()
    limit = json.loads((HERE / "thresholds.json").read_text(encoding="utf-8"))["thresholds"]["tdb_minus_ut_seconds_max"]["value"]
    case_id, site_def, body, _span, _params = next(iter_cases(load_cases()))
    ref = compare.parse_response(RAW / f"{case_id}.json")
    result = compare.compare_case(site_def, body, ref)
    assert result["tdb_minus_ut_seconds_max_abs"] < limit and result["leap_second_kernel_tdb_minus_ut_seconds_max_abs"] < limit
    true_conversion = compare.d.utc_to_et
    monkeypatch.setattr(compare.d, "utc_to_et", lambda utc: true_conversion(utc) + 1.0)
    shifted = compare.compare_case(site_def, body, ref)
    assert abs(shifted["tdb_minus_ut_seconds_max_abs"] - 1.0) < 0.001 and shifted["tdb_minus_ut_seconds_max_abs"] > limit
    assert shifted["leap_second_kernel_tdb_minus_ut_seconds_max_abs"] < limit
