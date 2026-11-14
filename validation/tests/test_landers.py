"""Published lander records versus the core, as a test.

The Apollo and Blue Ghost cases are recomputed on every run. The Chandrayaan-3 case
needs the LOLA terrain; without it the stored result is checked instead.
"""

import json

from validation.landers import compare


def test_thresholds_are_the_committed_rules():
    _, rules = compare.load()
    assert rules["R1_angle_same_inputs"]["threshold_deg"] == 0.05
    assert rules["R2_targeted_sun_angle"]["threshold_deg"] == 0.1
    assert rules["R4_one_sided_physical_bound"]["rounding_allowance_hours"] == 0.5


def test_every_registered_check_is_computed_and_passes():
    cases, _ = compare.load()
    report = compare.run()
    assert report["summary"] == {"pass_fail_checks": 20, "passed": 20, "failed": 0, "reported_without_verdict": 5}
    for case, result in zip(cases["cases"], report["cases"]):
        registered = {check["id"]: check["kind"] for check in case["checks"]}
        computed = {row["id"]: row["kind"] for row in result["rows"]}
        assert registered == computed, case["id"]
        for row in result["rows"]:
            assert (row["status"] == "PASS") == (row["kind"] == "pass_fail"), row["id"]


def test_committed_table_matches_a_fresh_run():
    stored = json.loads((compare.RESULTS / "validation_table.json").read_text(encoding="utf-8"))
    fresh = compare.run()
    old = {row["id"]: row for case in stored["cases"] for row in case["rows"]}
    new = {row["id"]: row for case in fresh["cases"] for row in case["rows"]}
    assert old.keys() == new.keys()
    for key in old:
        assert old[key]["status"] == new[key]["status"], key
        if isinstance(old[key]["difference"], float):
            assert abs(old[key]["difference"] - new[key]["difference"]) < 1e-3, key
