"""The packages published in ``packages/`` must pass the contract validator as they are.

Runs offline and needs neither terrain data nor kernels: it only reads the published
files. The validator applies the contract schema and checks, for every array, that the
file exists with the stated size, checksum and NaN count, and that the package id and
content digest can be recomputed. The tests below add what the validator cannot know:
that the published set is the curated site list of the data stream, written with the
contract version of the code in this checkout; which options the project sites and the
other sites carry; that a site served by a product that is not fine carries the core's
resolution warning; and that the README says for every site what served it.
"""

import json
from pathlib import Path

from lsncore.contract import validate_document, validate_package
from lsncore.contract.io import CONTRACT_VERSION
from lsncore.scenario import height_error_presets, requirement_presets

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "packages"
PROJECT_SITES = ("shackleton-rim-crest", "de-gerlache-rim-crest", "malapert-massif-summit")
PROJECT_HEIGHTS_M = [0.0, 1.0, 2.0, 5.0, 10.0, 20.0]
OTHER_HEIGHTS_M = [0.0, 2.0, 10.0]


def _curated() -> dict:
    """Site id -> record of the curated list of the data stream."""
    records = json.loads((REPO / "data" / "sites" / "curated_sites.json").read_text(encoding="utf-8"))["sites"]
    return {record["site_id"].replace("_", "-"): record for record in records}


def _tiles(product_id: str) -> list:
    """Data files of the tiles of a mosaic product, as the data stream's manifest records them."""
    files = json.loads((REPO / "data" / "manifest" / "manifest.json").read_text(encoding="utf-8"))["files"]
    return [record for record in files.values() if str(record.get("product_id", "")).startswith(product_id + "_") and record.get("role") == "data"]


def _size(path: Path) -> int:
    """Size of a published file as the pipeline wrote it: a JSON file is counted with LF line ends,
    whatever a checkout did to them (the arrays are binary and never converted)."""
    if path.suffix == ".json":
        return len(path.read_bytes().replace(b"\r\n", b"\n"))
    return path.stat().st_size


def _package_dirs() -> list:
    return sorted(path.parent for path in ROOT.rglob("manifest.json"))


def _manifests(kind: str) -> list:
    found = [json.loads((directory / "manifest.json").read_text(encoding="utf-8")) for directory in _package_dirs()]
    return [manifest for manifest in found if manifest["kind"] == kind]


def _sites() -> dict:
    return {manifest["site"]["site_id"]: manifest for manifest in _manifests("site")}


def test_index_is_valid_and_lists_exactly_the_published_packages():
    index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
    validate_document(index)
    listed = sorted(entry["path"] for entry in index["packages"])
    present = sorted(path.relative_to(ROOT).as_posix() for path in _package_dirs())
    assert listed == present
    assert sum(entry["kind"] == "direction_table" for entry in index["packages"]) == 1
    assert sum(entry["kind"] == "site" for entry in index["packages"]) == len(_curated())
    assert sum(entry["kind"] == "site_pairs" for entry in index["packages"]) == 1
    assert index["scenario_id"] is None  # the index covers two scenarios


def test_every_published_package_passes_the_contract_validator():
    directories = _package_dirs()
    assert len(directories) == len(_curated()) + 2
    table_ids = set()
    for directory in directories:
        manifest = validate_package(directory)
        assert manifest["synthetic"] is False, directory.name
        assert directory.name == manifest["package_id"]
        if manifest["kind"] == "direction_table":
            table_ids.add(manifest["package_id"])
    for site_id, manifest in _sites().items():
        assert manifest["timeline"]["direction_table_id"] in table_ids, site_id
        assert manifest["site"]["frame"] == "MOON_ME_DE440_ME421"
        # Every terrain layer names the elevation file it came from. A product that is a mosaic of
        # tiles has no single checksum in the package; its tiles are then in the manifest of the data
        # stream, each with its checksum and source.
        layers = manifest["inputs"]["dem"]["layers"]
        assert len(layers) >= 1
        for layer in layers:
            if layer["sha256"] is None:
                tiles = _tiles(layer["product_id"])
                assert len(tiles) >= 2, (site_id, layer["layer_id"])
                assert all(len(tile["sha256"]) == 64 and tile["source_url"].startswith("https://") for tile in tiles), (site_id, layer["layer_id"])
            else:
                assert isinstance(layer["sha256"], str) and len(layer["sha256"]) == 64, (site_id, layer["layer_id"])
                assert layer["source_url"].startswith("https://"), (site_id, layer["layer_id"])


def test_packages_were_written_with_the_contract_version_of_this_checkout():
    for directory in _package_dirs():
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["contract"] == {"name": "lsn-package", "version": CONTRACT_VERSION}, directory.name
    index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
    assert index["contract"]["version"] == CONTRACT_VERSION


def test_published_sites_are_the_curated_list_of_the_data_stream():
    curated, sites = _curated(), _sites()
    assert sorted(sites) == sorted(curated) and len(sites) == 20
    # 'kind' holds the machine value; older versions of the list had it in 'category'.
    assert {site_id for site_id, record in curated.items() if record.get("kind", record["category"]) == "project_candidate"} == set(PROJECT_SITES)
    for site_id, record in curated.items():
        site = sites[site_id]["site"]
        assert abs(site["lat_deg"] - record["lat_deg"]) < 1e-9, site_id
        assert abs((site["lon_deg"] - record["lon_deg_east"] + 180.0) % 360.0 - 180.0) < 1e-9, site_id
        assert site["name"] == record["name"]
        # The labels of the data stream are passed through to the package and to the index (contract 0.11).
        assert (site["programme"], site["category"]) == (record["programme"], record["category"]), site_id
    index = {entry["site_id"]: entry for entry in json.loads((ROOT / "index.json").read_text(encoding="utf-8"))["packages"] if entry["kind"] == "site"}
    for site_id, record in curated.items():
        assert (index[site_id]["programme"], index[site_id]["category"]) == (record["programme"], record["category"]), site_id
    assert len({record["programme"] for record in curated.values()}) >= 5


def test_every_site_package_holds_the_common_fields():
    presets = requirement_presets()
    for site_id, manifest in _sites().items():
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
        # Lit fraction of the Sun: terrain and eclipses by the Earth together.
        assert timeline["series"]["SUN"]["lit_fraction"]["shape"] == [len(heights), count], site_id
        assert "timeline.lit_fraction" in manifest["methods"]

        # Which elevation products served the site, and their resolution class (contract 0.9).
        source = horizon["terrain_source"]
        assert source["method"] == "horizon.terrain_source" and "horizon.terrain_source" in manifest["methods"]
        assert source["resolution_class"] in ("fine", "medium", "coarse")
        layer_ids = {layer["product_id"] for layer in manifest["inputs"]["dem"]["layers"]}
        assert source["at_site"]["product_id"] in layer_ids
        assert {product["product_id"] for product in source["products"]} <= layer_ids
        assert abs(sum(product["azimuth_share"] for product in source["products"]) - 1.0) < 1e-9

        # 24 months: the lunar-day calendar and the landing windows of the three example requirements.
        days = (count - 1) * timeline["time"]["step_s"] / 86400.0
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

        # Mast-height trade over the observer heights of the package.
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

        # Eclipses, ground stations and what the terrain costs.
        window_ids = {window["id"] for window in timeline["windows"]}
        assert {"sun_lit", "sun_eclipsed_by_earth", "earth_network_dsn", "sun_lost_to_terrain", "sun_gained_from_terrain"} <= window_ids
        metric_ids = {metric["id"] for metric in timeline["metrics"]}
        assert {"sun_lost_to_terrain_s", "sun_gained_from_terrain_s", "sun_visible_smooth_sphere_s"} <= metric_ids


def test_project_sites_carry_every_option_and_the_near_field():
    sites = _sites()
    model = height_error_presets()
    for site_id in PROJECT_SITES:
        manifest = sites[site_id]
        horizon, timeline, request = manifest["horizon"], manifest["timeline"], manifest["request"]["timeline"]
        count = timeline["time"]["count"]
        assert horizon["observer_heights_m"] == PROJECT_HEIGHTS_M, site_id

        # The 5 m near field: the site raster is a layer of the package and serves the site.
        rasters = [layer for layer in manifest["inputs"]["dem"]["layers"] if layer["product_id"].startswith("LOLA5MPP")]
        assert len(rasters) == 1 and rasters[0]["pixel_m"] == 5.0, site_id
        assert horizon["terrain_source"]["at_site"]["product_id"] == rasters[0]["product_id"]
        assert horizon["terrain_source"]["resolution_class"] == "fine"

        # Stated uncertainties: the band of the sourced height-error model and the landing-circle survey.
        stated = request["uncertainty"]
        assert set(stated) == {"dem_height_error_model", "landing_ellipse"}
        assert stated["dem_height_error_model"] == model["models"][model["default"]]
        band, ellipse = timeline["uncertainty"]["horizon_error"], timeline["uncertainty"]["landing_ellipse"]
        assert band["dem_height_error_model"]["id"] == model["default"] and "error_deg" not in band
        assert 0.0 < band["applied_height_error_m"]["min"] <= band["applied_height_error_m"]["max"]
        assert abs(sum(band["limiting_pixels"].values()) - 1.0) < 1e-9
        assert len(ellipse["points"]) == stated["landing_ellipse"]["points"] == 13
        for body in ("SUN", "EARTH"):
            assert timeline["series"][body]["ellipse_visible_share"]["shape"] == [count], site_id
        # Every event carries its range for the stated error and what the terrain behind it is worth (contract 0.10).
        assert len(timeline["events"]) > 0
        assert all(event["earliest_et_s"] <= event["et_s"] <= event["latest_et_s"] for event in timeline["events"])
        assert all("terrain_quality" in event for event in timeline["events"]), site_id
        for name in ("obstacle_height_error_m", "obstacle_constrained"):
            assert horizon[name]["shape"] == horizon["elevation_deg"]["shape"], (site_id, name)
        metric_ids = {metric["id"] for metric in timeline["metrics"]}
        assert {"sun_visible_certain_s", "sun_visible_possible_s", "earth_visible_certain_s"} <= metric_ids

        assert manifest["warnings"] == [], (site_id, manifest["warnings"])

        # The planned landing and its slip report.
        assert request["landing_utc"] is not None
        for opportunity in timeline["opportunities"]:
            assert opportunity["planned_landing"] is not None and opportunity["planned_landing"]["utc"] == request["landing_utc"]


def test_other_sites_carry_the_stated_reduced_set_and_the_resolution_warning():
    sites = _sites()
    others = [site_id for site_id in sites if site_id not in PROJECT_SITES]
    assert len(others) == 17
    classes = set()
    for site_id in others:
        manifest = sites[site_id]
        horizon, timeline, request = manifest["horizon"], manifest["timeline"], manifest["request"]["timeline"]
        assert horizon["observer_heights_m"] == OTHER_HEIGHTS_M, site_id
        assert horizon["observer_heights_m"][horizon["default_height_index"]] == 2.0
        # No near field, no stated uncertainty, no planned landing.
        assert not any(layer["product_id"].startswith("LOLA5MPP") for layer in manifest["inputs"]["dem"]["layers"]), site_id
        assert "uncertainty" not in timeline and not request.get("uncertainty") and not request.get("landing_utc"), site_id
        assert all("ellipse_visible_share" not in timeline["series"][body] for body in ("SUN", "EARTH"))
        assert all(opportunity["planned_landing"] is None for opportunity in timeline["opportunities"])
        # A site that is not served by a fine product says so in a warning that names the product and the pixel;
        # there is no other warning in a published package.
        assert all("resolution class" in warning for warning in manifest["warnings"]), (site_id, manifest["warnings"])
        source = horizon["terrain_source"]
        classes.add(source["resolution_class"])
        warnings = [warning for warning in manifest["warnings"] if "resolution class" in warning]
        if source["resolution_class"] == "fine":
            assert warnings == [], site_id
        else:
            assert len(warnings) == 1 and source["at_site"]["product_id"] in warnings[0] and f"{source['at_site']['pixel_m']:.0f} m" in warnings[0], site_id
        if source["at_site"]["pixel_m"] > 100.0:
            assert source["resolution_class"] != "fine" and warnings, site_id
    assert "fine" in classes and len(classes) >= 2


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


def test_site_pairs_package_compares_the_project_sites_only():
    (pairs,) = _manifests("site_pairs")
    sites = _sites()
    assert {entry["site_id"]: entry["package_id"] for entry in pairs["inputs"]["site_packages"]} == {site_id: sites[site_id]["package_id"] for site_id in PROJECT_SITES}
    for entry in pairs["inputs"]["site_packages"]:
        assert entry["content_sha256"] == sites[entry["site_id"]]["content_sha256"]
    assert sorted(tuple(sorted((pair["site_a"], pair["site_b"]))) for pair in pairs["pairs"]) == sorted(
        tuple(sorted((a, b))) for k, a in enumerate(PROJECT_SITES) for b in PROJECT_SITES[k + 1 :]
    )
    for pair in pairs["pairs"]:
        assert {row["window"] for row in pair["windows"]} == {"sun_visible", "earth_visible", "sun_and_earth_visible"}
        for row in pair["windows"]:
            assert row["either_s"] >= max(row["a_s"], row["b_s"]) and row["both_s"] <= min(row["a_s"], row["b_s"])


def test_readme_says_for_every_site_what_served_it_and_what_it_carries():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"version {CONTRACT_VERSION}" in readme
    rows = {}
    for line in readme.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("| ") and len(cells) == 11 and "(`" in cells[0]:
            rows[cells[0].split("`")[1]] = cells
    for site_id, manifest in _sites().items():
        row = rows[site_id]
        source = manifest["horizon"]["terrain_source"]
        near_field = any(layer["product_id"].startswith("LOLA5MPP") for layer in manifest["inputs"]["dem"]["layers"])
        assert manifest["site"]["name"] in row[0]
        assert row[1] == f"{manifest['site']['programme']}: {manifest['site']['category']}", site_id
        assert source["at_site"]["product_id"] in row[2] and row[3] == source["resolution_class"], site_id
        assert all(product["product_id"] in row[4] for product in source["products"]), site_id
        assert row[5] == ("on" if near_field else "off"), site_id
        assert row[6] == ", ".join(f"{h:g}" for h in manifest["horizon"]["observer_heights_m"]) + " m", site_id
        assert (row[7] == "none") == ("uncertainty" not in manifest["timeline"]), site_id
        assert row[8] == ("yes" if "landing_ellipse" in manifest["timeline"].get("uncertainty", {}) else "no"), site_id
        size = sum(_size(f) for f in (ROOT / "site" / site_id / manifest["package_id"]).iterdir())
        assert row[10] == f"{size / 1e6:.1f} MB", site_id
    total = sum(_size(f) for f in ROOT.rglob("*") if f.is_file() and f.name != "README.md")
    assert f"| Size | {total / 1e6:.1f} MB" in readme


def test_nothing_but_packages_index_and_readme_is_published():
    top = sorted(path.name for path in ROOT.iterdir())
    assert top == ["README.md", "direction_table", "index.json", "site", "site_pairs"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
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
