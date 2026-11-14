"""Long-term visibility versus the published LOLA illumination maps, as a test.

The stored result is always checked against the thresholds. The comparison itself is
repeated when the downloaded maps are present; the shares it compares are those of
``results/our_shares.json`` (recomputing them needs the LOLA terrain and takes minutes).
"""

import json

import pytest

from validation.pgda import compare
from validation.pgda.fetch import cache_dir


def test_thresholds_are_the_committed_ones():
    limits = json.loads((compare.HERE / "thresholds.json").read_text(encoding="utf-8"))["thresholds_run_A"]
    assert limits["sun"] == {"pearson_r_min": 0.90, "median_absolute_difference_max": 0.05, "median_signed_difference_abs_max": 0.02, "permanent_shadow_agreement_min": 0.95}
    assert limits["earth"] == {"pearson_r_min": 0.90, "median_absolute_difference_max": 0.05, "median_signed_difference_abs_max": 0.02}


def test_stored_result_passes_every_registered_check():
    stored = json.loads((compare.RESULTS / "validation_table.json").read_text(encoding="utf-8"))
    points = json.loads((compare.HERE / "points.json").read_text(encoding="utf-8"))["points"]
    assert [row["id"] for row in stored["points"]] == [p["id"] for p in points] and len(points) == 100
    assert stored["summary"] == {"checks": 7, "passed": 7, "failed": 0}
    assert all(check["status"] == "PASS" for check in stored["checks"])


def test_comparison_repeats_from_the_downloaded_maps():
    if not all((cache_dir() / f"{name}.IMG").exists() for name in compare.MAPS.values()):
        pytest.skip("published maps not downloaded (python -m validation.pgda.fetch)")
    pytest.importorskip("lsn_data")
    stored = json.loads((compare.RESULTS / "validation_table.json").read_text(encoding="utf-8"))
    fresh = compare.run()
    assert fresh["summary"] == stored["summary"]
    for old, new in zip(stored["checks"], fresh["checks"]):
        assert old["id"] == new["id"] and abs(old["measured"] - new["measured"]) < 1e-12
