"""Ground-station geometry versus Horizons, as a test. Runs offline from the stored responses."""

import hashlib
import json

import pytest

from lsncore.ephem import kernels

pytestmark = pytest.mark.skipif(not kernels.stations_available(), reason="station kernels not downloaded")


def test_station_geometry_agrees_with_horizons_within_fixed_thresholds():
    from validation.horizons.fetch import iter_cases, load_cases
    from validation.stations import compare

    cases = load_cases(compare.HERE)
    for case_id, *_ in iter_cases(cases):
        meta = json.loads((compare.RAW / f"{case_id}.meta.json").read_text(encoding="utf-8"))
        assert hashlib.sha256((compare.RAW / f"{case_id}.json").read_bytes()).hexdigest() == meta["sha256"], case_id
    report = compare.run()
    limits = report["thresholds"]
    assert limits == {"earth_end_direction_arcsec_max": 1.0, "moon_end_direction_arcsec_max": 1.0, "fast_path_earth_end_deg_max": 0.012, "fast_path_moon_end_arcsec_max": 1.0}
    assert report["summary"]["cases"] == 12 and report["summary"]["passed"] == 12
    for row in report["cases"]:
        assert row["status"] == "PASS" and row["rows"] == 289, row["case_id"]
