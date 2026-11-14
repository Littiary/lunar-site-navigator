"""The packages published in ``packages/`` must pass the contract validator as they are.

Runs offline and needs neither terrain data nor kernels: it only reads the published
files. The validator applies the contract schema and checks, for every array, that the
file exists with the stated size, checksum and NaN count, and that the package id and
content digest can be recomputed. The tests below add what the validator cannot know:
that the published set is complete (every kind of package and every field the core
writes for a scenario with requirements and stated uncertainties) and that it was written
with the contract version of the code in this checkout.
"""

import json
from pathlib import Path

from lsncore.contract import validate_document, validate_package
from lsncore.contract.io import CONTRACT_VERSION
from lsncore.scenario import requirement_presets

ROOT = Path(__file__).resolve().parents[2] / "packages"
SITES = ("shackleton-rim-crest", "de-gerlache-rim-crest", "malapert-massif-summit")


def _package_dirs() -> list:
    return sorted(path.parent for path in ROOT.rglob("manifest.json"))


def _manifests(kind: str) -> list:
    found = [json.loads((directory / "manifest.json").read_text(encoding="utf-8")) for directory in _package_dirs()]
    return [manifest for manifest in found if manifest["kind"] == kind]


def test_index_is_valid_and_lists_exactly_the_published_packages():
    index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
    validate_document(index)
    listed = sorted(entry["path"] for entry in index["packages"])
    present = sorted(path.relative_to(ROOT).as_posix() for path in _package_dirs())
    assert listed == present
    assert sum(entry["kind"] == "direction_table" for entry in index["packages"]) == 1
    assert sum(entry["kind"] == "site" for entry in index["packages"]) == len(SITES)
    assert sum(entry["kind"] == "site_pairs" for entry in index["packages"]) == 1


def test_every_published_package_passes_the_contract_validator():
    directories = _package_dirs()
    assert len(directories) == len(SITES) + 2
    table_ids = set()
    for directory in directories:
        manifest = validate_package(directory)
        assert manifest["synthetic"] is False, directory.name
        assert directory.name == manifest["package_id"]
        if manifest["kind"] == "direction_table":
            table_ids.add(manifest["package_id"])
    for directory in directories:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if manifest["kind"] == "site":
            assert manifest["timeline"]["direction_table_id"] in table_ids
            assert manifest["site"]["frame"] == "MOON_ME_DE440_ME421"
            # Every terrain layer names the elevation file it came from.
            layers = manifest["inputs"]["dem"]["layers"]
            assert len(layers) >= 1
            for layer in layers:
                assert isinstance(layer["sha256"], str) and len(layer["sha256"]) == 64, layer["layer_id"]
                assert layer["source_url"].startswith("https://"), layer["layer_id"]


def test_packages_were_written_with_the_contract_version_of_this_checkout():
    for directory in _package_dirs():
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["contract"] == {"name": "lsn-package", "version": CONTRACT_VERSION}, directory.name
    index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
    assert index["contract"]["version"] == CONTRACT_VERSION


def test_every_site_package_holds_every_field_the_core_writes():
    sites = {manifest["site"]["site_id"]: manifest for manifest in _manifests("site")}
    assert sorted(sites) == sorted(SITES)
    presets = requirement_presets()
    for site_id, manifest in sites.items():
        horizon, timeline, request = manifest["horizon"], manifest["timeline"], manifest["request"]["timeline"]
        heights = horizon["observer_heights_m"]
        count = timeline["time"]["count"]

        # Obstacles of the horizon and the time each one costs.
        for name in ("obstacle_height_m", "obstacle_lat_deg", "obstacle_lon_deg", "obstacle_id"):
            assert horizon[name]["shape"] == horizon["elevation_deg"]["shape"], (site_id, name)
        assert len(horizon["obstacles"]) > 0
        lost = sum(metric["value"] for metric in timeline["metrics"] if metric["id"] in ("sun_lost_to_terrain_s", "earth_lost_to_terrain_s"))
        assert (len(timeline["blockers"]) > 0) == (lost > 0), site_id
        assert {blocker["body"] for blocker in timeline["blockers"]} <= {"SUN", "EARTH"}
        for body in ("SUN", "EARTH"):
            assert timeline["series"][body]["blocker_azimuth_index"]["shape"] == [len(heights), count], site_id
            assert timeline["series"][body]["ellipse_visible_share"]["shape"] == [count], site_id
        # Lit fraction of the Sun: terrain and eclipses by the Earth together.
        assert timeline["series"]["SUN"]["lit_fraction"]["shape"] == [len(heights), count], site_id
        assert "timeline.lit_fraction" in manifest["methods"]

        # 24 months: the lunar-day calendar and the landing windows of the three example requirements.
        days = (timeline["time"]["count"] - 1) * timeline["time"]["step_s"] / 86400.0
        assert 729.0 < days < 733.0, site_id
        periods = timeline["calendar"]["periods"]
        assert 24 <= len(periods) <= 26 and sum(period["complete"] for period in periods) >= 23, site_id
        assert {q["id"] for q in timeline["calendar"]["quantities"]} >= {"sun_visible_s", "earth_visible_s", "sun_and_earth_visible_s", "sun_longest_outage_s", "earth_longest_outage_s", "sun_lit_s"}
        assert [r["id"] for r in request["requirements"]] == list(presets)
        for requirement in request["requirements"]:
            assert requirement == presets[requirement["id"]], requirement["id"]
            assert requirement["label"].startswith("EXAMPLE chosen by the team, not a NASA requirement")
        found = {(o["requirement_id"], o["height_index"]) for o in timeline["opportunities"]}
        assert found == {(name, h) for name in presets for h in range(len(heights))}, site_id
        for opportunity in timeline["opportunities"]:
            assert len(opportunity["feasible_s_per_period"]) == len(periods)
            assert opportunity["planned_landing"] is not None and opportunity["planned_landing"]["utc"] == request["landing_utc"]

        # Stated uncertainties: horizon error band and landing-ellipse survey.
        stated = request["uncertainty"]
        assert set(stated) == {"horizon_error_deg", "dem_height_error_m", "landing_ellipse"}
        band, ellipse = timeline["uncertainty"]["horizon_error"], timeline["uncertainty"]["landing_ellipse"]
        assert band["error_deg"] == stated["horizon_error_deg"] and band["dem_height_error_m"] == stated["dem_height_error_m"]
        assert len(ellipse["points"]) == stated["landing_ellipse"]["points"]
        assert all(event["earliest_et_s"] <= event["et_s"] <= event["latest_et_s"] for event in timeline["events"] if "earliest_et_s" in event)
        assert any("earliest_et_s" in event for event in timeline["events"])
        metric_ids = {metric["id"] for metric in timeline["metrics"]}
        assert {"sun_visible_certain_s", "sun_visible_possible_s", "sun_lost_to_terrain_s", "sun_gained_from_terrain_s"} <= metric_ids

        # Mast-height trade.
        trade = timeline["height_trade"]
        assert trade["observer_heights_m"] == heights
        assert {q["id"] for q in trade["quantities"]} >= {"sun_visible_s", "earth_visible_s", "sun_longest_outage_s", "sun_least_lunar_day_s"}

        # Terrain patches for drawing (contract 0.7): the default near, mid and far patches, each a square grid around the site.
        terrain = manifest["terrain"]
        assert terrain["use"] == "drawing" and terrain["method"] == "terrain.patch" and "terrain.patch" in manifest["methods"]
        assert [patch["id"] for patch in terrain["patches"]] == ["near", "mid", "far"] == [patch["id"] for patch in manifest["request"]["terrain_patches"]]
        for patch in terrain["patches"]:
            assert patch["up_m"]["shape"] == [patch["count_north"], patch["count_east"]], (site_id, patch["id"])
            assert patch["count_east"] == patch["count_north"] == round(2 * patch["half_width_m"] / patch["spacing_m"]) + 1
            assert patch["east_min_m"] == patch["north_min_m"] == -patch["half_width_m"]

        # Eclipses and ground stations, as before.
        window_ids = {window["id"] for window in timeline["windows"]}
        assert {"sun_lit", "sun_eclipsed_by_earth", "earth_network_dsn", "sun_lost_to_terrain", "sun_gained_from_terrain"} <= window_ids


def test_direction_table_holds_the_orientation_of_the_earth():
    """Contract 0.8: three series for drawing the Earth, with the kernels its orientation was read from."""
    (table,) = _manifests("direction_table")
    assert table["request"]["earth_view"] is True
    count = table["time"]["count"]
    assert set(table["earth_view"]) >= {"sub_lunar_lat_deg", "sub_lunar_lon_deg", "north_pole_angle_deg"}
    for name in ("sub_lunar_lat_deg", "sub_lunar_lon_deg", "north_pole_angle_deg"):
        assert table["earth_view"][name]["shape"] == [count] and table["earth_view"][name]["method"] == "dirtab.earth_view", name
    assert "dirtab.earth_view" in table["methods"]
    kernels = table["inputs"]["earth_orientation_kernels"]
    assert len(kernels) >= 1
    for kernel in kernels:
        assert len(kernel["sha256"]) == 64 and kernel["source_url"].startswith("https://naif.jpl.nasa.gov/"), kernel["name"]
    assert not any("earth_view" in warning for warning in table["warnings"])


def test_site_pairs_package_compares_every_two_published_sites():
    (pairs,) = _manifests("site_pairs")
    sites = {manifest["site"]["site_id"]: manifest for manifest in _manifests("site")}
    assert {entry["site_id"]: entry["package_id"] for entry in pairs["inputs"]["site_packages"]} == {site_id: manifest["package_id"] for site_id, manifest in sites.items()}
    for entry in pairs["inputs"]["site_packages"]:
        assert entry["content_sha256"] == sites[entry["site_id"]]["content_sha256"]
    assert sorted(tuple(sorted((pair["site_a"], pair["site_b"]))) for pair in pairs["pairs"]) == sorted(
        tuple(sorted((a, b))) for k, a in enumerate(SITES) for b in SITES[k + 1 :]
    )
    for pair in pairs["pairs"]:
        assert {row["window"] for row in pair["windows"]} == {"sun_visible", "earth_visible", "sun_and_earth_visible"}
        for row in pair["windows"]:
            assert row["either_s"] >= max(row["a_s"], row["b_s"]) and row["both_s"] <= min(row["a_s"], row["b_s"])


def test_nothing_but_packages_index_and_readme_is_published():
    top = sorted(path.name for path in ROOT.iterdir())
    assert top == ["README.md", "direction_table", "index.json", "site", "site_pairs"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"version {CONTRACT_VERSION}" in readme
    for directory in _package_dirs():
        assert directory.name in readme
        names = {path.name for path in directory.iterdir()}
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        assert "manifest.json" in names and len(names) == 1 + _count_arrays(manifest)


def _count_arrays(node) -> int:
    if isinstance(node, dict):
        own = 1 if {"file", "dtype", "shape", "sha256"} <= node.keys() else 0
        return own + sum(_count_arrays(value) for value in node.values())
    if isinstance(node, list):
        return sum(_count_arrays(value) for value in node)
    return 0
