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


RECOMPUTED = ("ridge_or_rim_01", "plain_or_slope_03", "floor_01", "site_shackleton_rim_crest")


def test_stored_shares_are_what_the_current_code_gives_at_a_few_points():
    """Recomputes four of the hundred points, horizon and shares, with the code and the settings as they are now."""
    pytest.importorskip("lsn_data")
    from lsncore.ephem import kernels
    from lsncore.horizon import HorizonSettings
    from validation.pgda import compute

    try:
        terrains = compute.open_terrains()
    except FileNotFoundError as missing:
        pytest.skip(f"LOLA products are not on this machine: {missing}")
    kernels.load()
    stored = json.loads((compare.RESULTS / "our_shares.json").read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in stored["points"]}
    points = {p["id"]: p for p in json.loads((compare.HERE / "points.json").read_text(encoding="utf-8"))["points"]}
    assert stored["terrain"] == {run: terrain.describe()["dem_set_id"] for run, terrain in terrains.items()}
    table = compute.hourly_table(compute.PERIOD_START_UTC)
    differences = []
    for point_id in RECOMPUTED:
        fresh = compute.point_row(points[point_id], terrains, table, HorizonSettings())
        for run in terrains:
            old, new = rows[point_id][run], fresh[run]
            for key in ("surface_height_m", "horizon_min_deg", "horizon_max_deg"):
                if abs(old[key] - new[key]) > 1e-9:
                    differences.append((point_id, run, key, old[key], new[key]))
            for height, shares in new["shares"].items():
                for body, share in shares.items():
                    if abs(old["shares"][height][body] - share) > 1e-12:
                        differences.append((point_id, run, f"share {height} {body}", old["shares"][height][body], share))
    assert not differences, differences


def test_the_computation_records_what_the_horizon_depends_on():
    """From the next computation on, the result names its commit, its terrain layers and the settings of the search."""
    import inspect

    from validation.pgda import compute

    source = inspect.getsource(compute.main)
    for field in ('"code": code_state()', '"horizon_settings": dataclasses.asdict(settings)', '"terrain_layers"'):
        assert field in source
    state = compute.code_state()
    assert set(state) == {"git_commit", "uncommitted_changes"}
