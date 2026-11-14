"""Sunlit or shadowed state against dated LROC images, as a test.

The stored result is checked against the criteria of ``cases.json``. When the browse image
is present, the image is read again by the fixed rule and compared with the stored result;
our states are those of ``results/our_states.json`` (recomputing them needs the terrain).
"""

import json

import pytest

from validation.lro_images import compare


def _stored() -> dict:
    return json.loads((compare.RESULTS / "validation_table.json").read_text(encoding="utf-8"))


def test_cases_are_the_committed_ones():
    cases = compare.load()
    ids = [check["id"] for case in cases["cases"] for check in case["checks"]]
    assert ids == ["pole_2022_state", "pole_2022_sub_solar_point", "nadir_2010_agreement", "nadir_2010_sub_solar_point"]
    assert "at least 90 percent" in cases["cases"][1]["checks"][0]["criterion"]
    assert cases["our_state"]["definition"].count("visible fraction >= 0.5") == 1


def test_stored_result_follows_the_criteria():
    stored = _stored()
    checks = {check["id"]: check for check in stored["checks"]}
    assert set(checks) == {"pole_2022_state", "pole_2022_sub_solar_point", "nadir_2010_agreement", "nadir_2010_sub_solar_point"}
    pole = checks["pole_2022_state"]
    assert (pole["status"] == "PASS") == (pole["computed"] == "shadow")
    assert (pole["computed"] == "shadow") == (pole["detail"]["visible_fraction"] < 0.5)
    for key in ("pole_2022_sub_solar_point", "nadir_2010_sub_solar_point"):
        assert (checks[key]["status"] == "PASS") == all(abs(v) < 0.02 for v in checks[key]["difference_deg"])
    strip = checks["nadir_2010_agreement"]
    detail = strip["detail"]
    both = (detail["image_sunlit_ours_sunlit"] + detail["image_sunlit_ours_shadow"] > 0) and (detail["image_shadow_ours_sunlit"] + detail["image_shadow_ours_shadow"] > 0)
    if detail["judged"] >= 30 and both:
        assert strip["status"] == ("PASS" if strip["computed"] >= 0.90 else "FAIL")
    else:
        assert strip["status"] == "NOT DECIDED"
    judged = [row for row in stored["strip_points"] if row["image_state"] in ("sunlit", "shadow") and row["state"] is not None]
    assert len(judged) == detail["judged"]
    assert sum(1 for row in judged if row["image_state"] == row["state"]) == detail["agree"]


@pytest.mark.xfail(strict=True, reason="Registered check fails: 89.3 % of the judged points agree, the criterion fixed beforehand is 90 %. "
                   "One brightness threshold for the whole image reads dimly lit ground at grazing incidence as shadow. Rule and criterion are unchanged.")
def test_nadir_strip_meets_the_registered_criterion():
    strip = {check["id"]: check for check in _stored()["checks"]}["nadir_2010_agreement"]
    assert strip["status"] == "PASS"


def test_failed_agreement_is_reported_with_its_cause_and_not_turned_into_a_pass():
    stored = _stored()
    strip = {check["id"]: check for check in stored["checks"]}["nadir_2010_agreement"]
    table = (compare.RESULTS / "validation_table.md").read_text(encoding="utf-8")
    extra = stored["exploratory_after_the_result"]
    assert "not a pass criterion" in extra["note"]
    assert stored["summary"]["failed"] == sum(1 for check in stored["checks"] if check["status"] == "FAIL")
    if strip["status"] == "FAIL":
        assert "**FAIL**" in table
        assert "the registered check stays failed" in table


def test_recorded_browse_file_is_the_one_that_was_read():
    files = json.loads((compare.HERE / "files.json").read_text(encoding="utf-8"))["files"]
    assert [entry["name"] for entry in files] == [compare.BROWSE_NAME]
    assert files[0]["sha256"] == _stored()["image"]["browse_sha256"]
    case = next(case for case in compare.load()["cases"] if case["id"] == "nadir_strip_2010")
    assert files[0]["url"] == case["published"]["browse_url"]


def test_image_reading_repeats_from_the_downloaded_browse():
    if not (compare.cache_dir() / compare.BROWSE_NAME).exists():
        pytest.skip("browse image not downloaded (python -m validation.lro_images.fetch)")
    pytest.importorskip("PIL")
    pytest.importorskip("lsn_data")
    stored = _stored()
    fresh = compare.run(recompute=False)
    assert fresh["image"]["browse_sha256"] == stored["image"]["browse_sha256"]
    assert [row["image_state"] for row in fresh["strip_points"]] == [row["image_state"] for row in stored["strip_points"]]
    assert [check["status"] for check in fresh["checks"]] == [check["status"] for check in stored["checks"]]
