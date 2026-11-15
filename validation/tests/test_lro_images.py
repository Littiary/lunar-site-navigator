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
                   "Two causes fit the one-sided disagreement, the single brightness threshold of the image rule or a terrain horizon that is too low, and the data do not decide. "
                   "Rule and criterion are unchanged.")
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


def test_the_failed_check_is_described_with_two_candidate_causes():
    stored = _stored()
    extra = stored["exploratory_after_the_result"]
    table = (compare.RESULTS / "validation_table.md").read_text(encoding="utf-8")
    assert "Two causes fit this pattern, and these data do not decide between them." in table
    assert "likely" not in table
    scan = extra["one_threshold_on_the_point_brightness"]
    assert scan["best_agreement"] < 1.0  # no single threshold makes every point agree
    low, high = scan["thresholds_with_agreement_of_at_least_0.9"]
    assert low < scan["best_threshold"] < high < stored["image"]["threshold"]
    near = extra["agreed_shadow_with_our_sun_centre_less_than_1_deg_below_the_horizon"]
    disputed = extra["image_shadow_ours_sunlit"]
    assert near["image_brightness_min_max"][1] > disputed["image_brightness_min_median_max"][0]  # the two brightness ranges overlap
    assert abs(extra["rank_correlation_of_brightness_with_our_centre_margin_at_the_disputed_points"]) < 0.5


def test_ground_inside_the_first_sample_of_the_horizon_search_explains_one_disputed_point():
    """A limit of the core that this strip shows. The horizon search starts one pixel from the point (at most 20 m),
    so ground that rises inside that distance is not in the horizon of an observer at 0 m. Here the interpolated
    ground is sampled along the Sun's azimuth between 0.5 m and 19.5 m at every strip point, and the state is judged
    against the higher of that and the stored horizon. The stored result is not changed by this."""
    import numpy as np

    pytest.importorskip("lsn_data")
    from lsncore.dem import open_lola

    try:
        terrain = open_lola()
    except FileNotFoundError as missing:
        pytest.skip(f"LOLA products are not on this machine: {missing}")
    radius = 1737400.0
    steps = np.array([0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 13.0, 16.0, 19.5])
    rows, changed = _stored()["strip_points"], []
    agree = judged = 0
    for row in rows:
        lat, lon, azimuth, gamma = np.radians(row["lat_deg"]), np.radians(row["lon_deg"]), np.radians(row["sun_azimuth_deg"]), steps / radius
        lat2 = np.arcsin(np.sin(lat) * np.cos(gamma) + np.cos(lat) * np.sin(gamma) * np.cos(azimuth))
        lon2 = lon + np.arctan2(np.sin(azimuth) * np.sin(gamma) * np.cos(lat), np.cos(gamma) - np.sin(lat) * np.sin(lat2))
        ground = float(np.asarray(terrain.height_m(np.array([row["lon_deg"]]), np.array([row["lat_deg"]])))[0])
        height = np.asarray(terrain.height_m(np.degrees(lon2) % 360.0, np.degrees(lat2)), dtype=np.float64)
        near = float(np.degrees(np.arctan2((radius + height) * np.cos(gamma) - (radius + ground), (radius + height) * np.sin(gamma))).max())
        state = "sunlit" if row["sun_elevation_deg"] - max(near, row["horizon_elevation_at_sun_azimuth_deg"]) > 0.0 else "shadow"
        if state != row["state"]:
            changed.append((row["id"], row["state"], state, near))
        if row["image_state"] in ("sunlit", "shadow"):
            judged += 1
            agree += state == row["image_state"]
    assert [item[:3] for item in changed] == [("row+700_along11500", "sunlit", "shadow")]
    point = next(row for row in rows if row["id"] == "row+700_along11500")
    assert point["image_state"] == "shadow" and point["visible_fraction"] > 0.999 and point["obstacle_distance_m"] == 20.0
    upper_limb = point["horizon_elevation_at_sun_azimuth_deg"] + point["upper_limb_margin_deg"]
    assert changed[0][3] > upper_limb > point["sun_elevation_deg"]  # the near ground hides the whole disc
    assert (agree, judged) == (267, 298)  # one point more than the registered result; still below 90 %
