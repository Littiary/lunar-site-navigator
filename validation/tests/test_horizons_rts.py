"""Event finder versus Horizons rise/set rows, as a test. Runs offline from the stored responses."""

import json

from validation.horizons_rts import compare


def test_sun_rise_and_set_agree_with_horizons_within_fixed_threshold():
    limits = {key: item["value"] for key, item in json.loads((compare.HERE / "thresholds.json").read_text(encoding="utf-8"))["thresholds"].items()}
    assert limits == {"event_time_seconds_max": 120.0, "unmatched_events_max": 0}  # as committed before the data was fetched
    report = compare.run()
    assert len(report["cases"]) == 4
    total = 0
    for case in report["cases"]:
        assert case["status"] == "PASS", case["case_id"]
        assert case["unmatched"] == 0
        for pair in case["events"]:
            assert abs(pair["horizons_minus_core_s"]) < limits["event_time_seconds_max"]
            total += 1
    assert total == 16
