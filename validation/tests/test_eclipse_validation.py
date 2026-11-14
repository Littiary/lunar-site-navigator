"""The eclipse of 14 March 2025 against the published values, as a test (offline)."""

import json

from validation.eclipse import compare


def test_thresholds_are_the_committed_rules():
    _, rules = compare.load()
    assert rules["E1_contact_time_at_the_site"]["threshold_minutes"] == 2.0
    assert rules["E2_duration_of_totality"]["threshold_minutes"] == 3.5
    assert rules["E3_nesting_inside_whole_moon_contacts"]["allowance_minutes"] == 2.0


def test_every_registered_check_is_computed_and_passes():
    cases, _ = compare.load()
    report = compare.run()
    assert report["summary"] == {"pass_fail_checks": 8, "passed": 8, "failed": 0, "reported_without_verdict": 2}
    registered = {check["id"]: check["kind"] for check in cases["checks"]}
    assert registered == {row["id"]: row["kind"] for row in report["rows"]}
    stored = json.loads((compare.RESULTS / "validation_table.json").read_text(encoding="utf-8"))
    assert stored["contacts_utc"] == report["contacts_utc"]
