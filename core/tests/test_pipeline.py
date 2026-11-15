"""The real horizon, end to end: scenario or command line in, valid package out."""

import json
from pathlib import Path

import numpy as np
import pytest

from lsncore import cli
from lsncore.contract import read_package, validate_package
from lsncore.dem import AnalyticTerrain
from lsncore.pipeline import BODY_FIXED_FRAME, run_scenario
from lsncore.scenario import single_site_scenario

R = 1_737_400.0


def _ridge(lon, lat):
    # a smooth east-west ridge system, enough relief for a non-trivial horizon
    return 800.0 * np.sin(np.radians(lon) * 3.0) * np.cos(np.radians(lat) * 40.0)


def test_scenario_with_real_horizon_writes_a_valid_package(tmp_path):
    terrain = AnalyticTerrain(_ridge, R, ceiling_height_m=800.0, dem_set_id="ANALYTIC-ridges")
    scenario = single_site_scenario(
        "ridge-site", "Analytic ridge site", -86.0, 20.0, dem_set_id="ANALYTIC-ridges", synthetic=False,
        azimuth_step_deg=1.0, max_range_m=150_000.0,
    )
    (path,) = run_scenario(scenario, tmp_path, terrain)
    manifest = validate_package(path)
    pkg = read_package(path)
    hz = manifest["horizon"]

    assert manifest["status"] == "ok" and manifest["synthetic"] is False
    assert manifest["site"]["frame"] == BODY_FIXED_FRAME
    assert manifest["site"]["reference_radius_m"]["value"] == R
    assert manifest["inputs"]["dem"]["dem_set_id"] == "ANALYTIC-ridges"
    assert hz["observer_heights_m"] == [0.0, 1.0, 2.0, 5.0, 10.0, 20.0]
    elevation = pkg.array(hz["elevation_deg"])
    assert elevation.shape == (6, 360) and np.isfinite(elevation).all()
    # every number has a card, and the horizon cards state how they were checked
    card = manifest["methods"][hz["elevation_deg"]["method"]]
    assert card["validation"]["status"] == "analytic-test-passed"
    assert card["parameters"]["max_range_m"] == 150_000.0
    assert card["data"] == ["ANALYTIC-ridges"]
    # search radius and its error bound are part of the package
    bounds = hz["error_bounds"]
    assert {"far_field_max_deg", "far_field_open_azimuth_fraction", "ceiling_height_m", "shortest_reach_m"} <= bounds.keys()
    assert bounds["shortest_reach_m"]["value"] == 150_000.0
    assert manifest["methods"][bounds["far_field_max_deg"]["method"]]["title"].startswith("Bound")
    # site position is the ground point on the radial through the site
    position = np.array(manifest["site"]["position_km"])
    assert np.linalg.norm(position) * 1000.0 == pytest.approx(manifest["site"]["radius_m"]["value"], abs=1e-6)
    assert np.allclose(position / np.linalg.norm(position), manifest["site"]["enu"]["up"], atol=1e-12)


def test_same_request_gives_the_same_package(tmp_path):
    terrain = AnalyticTerrain(_ridge, R, ceiling_height_m=800.0, dem_set_id="ANALYTIC-ridges")
    scenario = single_site_scenario(
        "ridge-site", "Analytic ridge site", -86.0, 20.0, dem_set_id="ANALYTIC-ridges", synthetic=False,
        azimuth_step_deg=5.0, max_range_m=50_000.0,
    )
    (a,) = run_scenario(scenario, tmp_path / "a", terrain)
    (b,) = run_scenario(scenario, tmp_path / "b", terrain)
    assert a.name == b.name
    assert read_package(a).manifest["content_sha256"] == read_package(b).manifest["content_sha256"]


def test_scenario_naming_other_data_gets_a_warning(tmp_path):
    terrain = AnalyticTerrain(_ridge, R, dem_set_id="ANALYTIC-ridges")
    scenario = single_site_scenario(
        "ridge-site", "Analytic ridge site", -86.0, 20.0, dem_set_id="something-else", synthetic=False,
        azimuth_step_deg=5.0, max_range_m=50_000.0,
    )
    (path,) = run_scenario(scenario, tmp_path, terrain)
    warnings = validate_package(path)["warnings"]
    assert any("something-else" in w for w in warnings)
    assert any("ceiling" in w for w in warnings)  # no ceiling supplied: the assumption is stated


def test_cli_site_on_the_data_streams_synthetic_dem(tmp_path):
    lsn_data = pytest.importorskip("lsn_data")
    label = Path(lsn_data.__file__).resolve().parents[1] / "fixtures" / "synth_s90_100m.lbl"
    if not label.exists():
        pytest.skip("synthetic DEM fixture of the data stream not found")
    code = cli.main([
        "site", "--lat", "-90", "--lon", "0", "--name", "Fixture pole", "--out", str(tmp_path),
        "--dem-label", str(label), "--max-range-km", "19", "--azimuth-step", "1",
    ])
    assert code == 0
    index = json.loads((tmp_path / "index.json").read_text())
    (entry,) = index["packages"]
    manifest = validate_package(tmp_path / entry["path"])
    # a test surface is not the Moon: the package must say so even though the algorithm is real
    assert manifest["synthetic"] is True and "SYNTHETIC TERRAIN" in manifest["synthetic_notice"]
    assert manifest["inputs"]["dem"]["layers"][0]["product_id"] == "SYNTH_S90_100M"
    pkg = read_package(tmp_path / entry["path"])
    elevation = pkg.array(manifest["horizon"]["elevation_deg"])
    h = manifest["horizon"]["default_height_index"]
    assert abs(int(np.argmax(elevation[h])) - 90) <= 1  # the cone lies towards 90 deg east


def test_scenario_command_builds_a_valid_scenario_from_site_records(tmp_path):
    from lsncore.contract import validate_document

    records = {
        "schema": "lunar-site-navigator site records v0",
        "sites": [
            {"site_id": "rim_crest_a", "name": "Rim crest A", "lon_deg_east": 205.5, "lat_deg": -89.8},
            {"site_id": "summit_b", "name": "Summit B", "lon_deg_east": 2.0, "lat_deg": -86.0},
        ],
    }
    (tmp_path / "sites.json").write_text(json.dumps(records))
    (tmp_path / "req.json").write_text(json.dumps([
        {"id": "stay", "label": "Example", "mission_duration_s": 86400.0,
         "conditions": [{"window": "sun_visible_certain", "kind": "continuous_from_landing", "min_s": 3600.0}]}
    ]))
    out = tmp_path / "scenario.json"
    code = cli.main([
        "scenario", "--sites", str(tmp_path / "sites.json"), "--id", "two-sites", "--start", "2026-11-14T00:00:00.000Z",
        "--end", "2027-11-14T00:00:00.000Z", "--step", "7200", "--landing-utc", "2027-01-10T00:00:00.000Z",
        "--requirements", str(tmp_path / "req.json"), "--horizon-error-deg", "0.05", "--ellipse", "100", "50", "30", "13",
        "--out", str(out),
    ])
    assert code == 0
    scenario = json.loads(out.read_text())
    validate_document(scenario)
    assert [s["site_id"] for s in scenario["sites"]] == ["rim-crest-a", "summit-b"]
    assert scenario["sites"][0]["lon_deg"] == 205.5 and scenario["sites"][0]["landing_utc"] == "2027-01-10T00:00:00.000Z"
    assert scenario["uncertainty"] == {"horizon_error_deg": 0.05, "landing_ellipse": {"semi_major_m": 100.0, "semi_minor_m": 50.0, "azimuth_deg": 30.0, "points": 13}}
    assert scenario["requirements"][0]["id"] == "stay" and scenario["data"]["dem_set_id"] == "any"


def _ridge_terrain():
    """Opens the terrain in a worker process (must be importable, hence at module level)."""
    return AnalyticTerrain(_ridge, R, ceiling_height_m=800.0, dem_set_id="ANALYTIC-ridges")


def test_sites_computed_in_parallel_give_the_same_packages(tmp_path):
    scenario = single_site_scenario(
        "ridge-a", "Analytic ridge site A", -86.0, 20.0, dem_set_id="any", synthetic=False, azimuth_step_deg=5.0, max_range_m=50_000.0,
    )
    scenario["scenario_id"] = "three-ridge-sites"
    scenario["sites"] += [
        {"site_id": "ridge-b", "name": "Analytic ridge site B", "lat_deg": -84.5, "lon_deg": 100.0},
        {"site_id": "ridge-c", "name": "Analytic ridge site C", "lat_deg": -87.2, "lon_deg": -60.0},
    ]
    one = run_scenario(scenario, tmp_path / "one", _ridge_terrain())
    many = run_scenario(scenario, tmp_path / "many", _ridge_terrain(), jobs=3, terrain_factory=_ridge_terrain)
    assert [p.name for p in one] == [p.name for p in many] and len(one) == 3
    for a, b in zip(one, many):
        ma, mb = validate_package(a), validate_package(b)
        assert ma["content_sha256"] == mb["content_sha256"] and ma["site"]["site_id"] == mb["site"]["site_id"]
    index = lambda root: [(p["kind"], p["package_id"]) for p in json.loads((root / "index.json").read_text())["packages"]]  # noqa: E731
    assert index(tmp_path / "one") == index(tmp_path / "many")


def test_event_searches_shared_among_processes_give_the_same_package(tmp_path):
    """One site with dates, a stated horizon error and a landing ellipse: the band and the
    ellipse survey are event searches that can run in other processes."""
    pytest.importorskip("spiceypy")
    from lsncore.ephem import kernels

    try:
        kernels.load()
    except FileNotFoundError as missing:
        pytest.skip(f"kernels are not on this machine: {missing}")
    scenario = single_site_scenario(
        "ridge-a", "Analytic ridge site A", -86.0, 20.0, dem_set_id="any", synthetic=False, heights_m=[0.0, 2.0], azimuth_step_deg=1.0, max_range_m=50_000.0,
    )
    scenario["time_window"] = {"start_utc": "2026-11-14T00:00:00.000Z", "end_utc": "2026-11-24T00:00:00.000Z", "step_s": 3600.0}
    scenario["uncertainty"] = {"horizon_error_deg": 0.2, "dem_height_error_m": 5.0, "landing_ellipse": {"semi_major_m": 3000.0, "semi_minor_m": 2000.0, "azimuth_deg": 20.0, "points": 4}}
    (_, a) = run_scenario(scenario, tmp_path / "one", _ridge_terrain())
    (_, b) = run_scenario(scenario, tmp_path / "many", _ridge_terrain(), jobs=4)
    ma, mb = validate_package(a), validate_package(b)
    assert ma["package_id"] == mb["package_id"] and ma["content_sha256"] == mb["content_sha256"]
    assert any(w["id"] == "sun_visible_certain" for w in ma["timeline"]["windows"]) and "landing_ellipse" in ma["timeline"]["uncertainty"]


def test_countdown_metrics_state_the_instant_they_count_from(tmp_path):
    """Planned landing if the scenario states one inside the window, else the first sample."""
    pytest.importorskip("spiceypy")
    from lsncore.ephem import kernels

    try:
        kernels.load()
    except FileNotFoundError as missing:
        pytest.skip(f"kernels are not on this machine: {missing}")
    scenario = single_site_scenario("ridge-a", "Analytic ridge site A", -86.0, 20.0, dem_set_id="any", synthetic=False, heights_m=[2.0], azimuth_step_deg=1.0, max_range_m=50_000.0)
    scenario["time_window"] = {"start_utc": "2026-11-14T00:00:00.000Z", "end_utc": "2026-11-24T00:00:00.000Z", "step_s": 3600.0}
    for landing, expected, what in (
        (None, "2026-11-14T00:00:00.000Z", "start of the time window"),
        ("2026-11-18T06:00:00.000Z", "2026-11-18T06:00:00.000Z", "planned landing of the site"),
        ("2030-01-01T00:00:00.000Z", "2026-11-14T00:00:00.000Z", "start of the time window"),  # outside the window
    ):
        scenario["sites"][0].pop("landing_utc", None)
        if landing:
            scenario["sites"][0]["landing_utc"] = landing
        manifest = validate_package(run_scenario(scenario, tmp_path / (landing or "none")[:10], _ridge_terrain())[-1])
        counted = [m for m in manifest["timeline"]["metrics"] if "_time_to_" in m["id"] or m["id"].endswith("_at_reference")]
        assert len(counted) >= 8 and all(m["reference"]["utc"] == expected and m["reference"]["is"] == what and m["reference"]["time_scale"] == "TDB" for m in counted)
        others = [m for m in manifest["timeline"]["metrics"] if m not in counted]
        assert others and not any("reference" in m for m in others)
        # the label still says it in words
        assert all(expected in m["label"] for m in counted if m["id"].endswith(("_time_to_set_s", "_at_reference")))


def test_default_height_is_part_of_the_request_and_of_the_package_id(tmp_path):
    """The default observer height decides default_height_index, the height of the band
    statistics, of the terrain source and of the site pairs. Two runs that differ only in
    it are different requests: they must not get the same package id (SPEC 3.4), or the
    second would overwrite the first."""
    scenario = single_site_scenario(
        "ridge-site", "Analytic ridge site", -86.0, 20.0, dem_set_id="ANALYTIC-ridges", synthetic=False, azimuth_step_deg=5.0, max_range_m=50_000.0,
    )
    manifests = {}
    for height in (2.0, 10.0, 2.0):
        scenario["default_height_m"] = height
        (path,) = run_scenario(scenario, tmp_path, _ridge_terrain())
        manifest = validate_package(path)
        assert manifest["request"]["default_height_m"] == height
        heights = manifest["horizon"]["observer_heights_m"]
        assert heights[manifest["horizon"]["default_height_index"]] == height
        manifests.setdefault(height, []).append(manifest)
    two, ten = manifests[2.0][0], manifests[10.0][0]
    assert two["package_id"] != ten["package_id"] and two["content_sha256"] != ten["content_sha256"]
    # both are on disk next to each other, and the same request gives the same package again
    assert sorted(p.name for p in (tmp_path / "site" / "ridge-site").iterdir()) == sorted([two["package_id"], ten["package_id"]])
    again = manifests[2.0][1]
    assert (again["package_id"], again["content_sha256"]) == (two["package_id"], two["content_sha256"])


@pytest.mark.parametrize("pixel_m, expected_m", [(5.0, 5.0), (20.0, 20.0), (116.4, 20.0), (237.0, 20.0)])
def test_method_card_states_where_the_search_really_starts(tmp_path, pixel_m, expected_m):
    """The first point of a ray is one pixel from the site but never farther than 20 m.
    The card of a package on a coarse product said one pixel (116.4 m) while the search had
    started at 20 m."""
    from lsncore.horizon import HorizonSettings, _layout

    terrain = AnalyticTerrain(_ridge, R, finest_pixel_m=pixel_m, ceiling_height_m=800.0, dem_set_id="ANALYTIC-ridges")
    scenario = single_site_scenario(
        "ridge-site", "Analytic ridge site", -86.0, 20.0, dem_set_id="ANALYTIC-ridges", synthetic=False, heights_m=[2.0], azimuth_step_deg=5.0, max_range_m=20_000.0,
    )
    (path,) = run_scenario(scenario, tmp_path, terrain)
    manifest = validate_package(path)
    stated = manifest["methods"][manifest["horizon"]["elevation_deg"]["method"]]["parameters"]["first_point_m"]
    assert stated == expected_m == _layout(terrain, 20_000.0, HorizonSettings())[0]


@pytest.mark.parametrize("spec", [{"quantity": "visible_fraction", "op": ">=", "value": 0.0}, {"quantity": "visible_fraction", "op": ">", "value": 1.0}])
def test_a_threshold_that_is_always_or_never_true_is_refused(spec):
    """'>' and '>=' give the same events except at the two ends of the scale, where one of
    them defines no event at all; the operator was not looked at."""
    pytest.importorskip("spiceypy")
    from lsncore.events.finder import threshold_from_contract

    with pytest.raises(ValueError, match="no event"):
        threshold_from_contract(spec)
    assert threshold_from_contract({"quantity": "visible_fraction", "op": ">", "value": 0.0}).limb == "upper_limb"
    assert threshold_from_contract({"quantity": "visible_fraction", "op": ">=", "value": 1.0}).limb == "lower_limb"
