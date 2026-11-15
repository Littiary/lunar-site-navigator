"""Sun and Earth directions at the three site records against JPL Horizons, as a test.

An additional check outside the validation card. Runs offline from the stored raw
responses, with the thresholds of ``validation/horizons``.
"""

import hashlib
import json

from validation.horizons.fetch import iter_cases, load_cases
from validation.horizons_sites import compare


def test_raw_responses_are_complete_and_unmodified():
    case_ids = [case_id for case_id, *_ in iter_cases(load_cases(compare.HERE))]
    assert len(case_ids) == 12
    for case_id in case_ids:
        meta = json.loads((compare.RAW / f"{case_id}.meta.json").read_text(encoding="utf-8"))
        payload = (compare.RAW / f"{case_id}.json").read_bytes()
        assert hashlib.sha256(payload).hexdigest() == meta["sha256"], case_id


def test_core_agrees_with_horizons_at_the_site_records():
    report = compare.run()
    limits = report["thresholds"]
    assert limits["direction_arcsec_max"] == 1.0  # fixed in validation/horizons/thresholds.json; this test does not define it
    assert report["summary"]["cases"] == report["summary"]["passed"] == 12
    assert sorted({row["site"] for row in report["cases"]}) == ["de_gerlache_rim_crest", "malapert_massif_summit", "shackleton_rim_crest"]
    for row in report["cases"]:
        assert row["status"] == "PASS" and all(row["checks"].values()), row["case_id"]
        assert row["rows"] >= 289


def test_stored_table_is_what_the_comparison_gives():
    stored = json.loads((compare.RESULTS / "validation_table.json").read_text(encoding="utf-8"))
    fresh = compare.run()
    assert stored["summary"]["cases"] == 12 and stored["thresholds"] == fresh["thresholds"]
    for old, new in zip(stored["cases"], fresh["cases"]):
        assert old["case_id"] == new["case_id"] and old["status"] == new["status"] == "PASS"
        for path in ("exact", "table"):
            assert abs(old[path]["direction_arcsec_max"] - new[path]["direction_arcsec_max"]) < 1e-6, old["case_id"]
    text = (compare.RESULTS / "validation_table.md").read_text(encoding="utf-8")
    assert "not a row of the validation card" in text
    assert f"{stored['summary']['direction_exact_arcsec_max']:.4f} arcsec" in text
