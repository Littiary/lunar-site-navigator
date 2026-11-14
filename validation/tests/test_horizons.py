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
