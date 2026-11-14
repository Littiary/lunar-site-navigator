"""Descriptive labels of a site (contract 0.11): `programme` and `category`.

They are passed through unchanged from the site record to the scenario, the site package
and the index entry, so that a viewer can group its site list. No number depends on
them, and they are not part of the request: a label does not change the package id.
"""

import json

import numpy as np
import pytest

from lsncore import cli
from lsncore.contract import ContractError, validate_document, validate_package
from lsncore.dem import AnalyticTerrain
from lsncore.pipeline import run_scenario
from lsncore.scenario import single_site_scenario

R = 1_737_400.0


def _ridge(lon, lat):
    return 800.0 * np.sin(np.radians(lon) * 3.0) * np.cos(np.radians(lat) * 40.0)


def _terrain():
    return AnalyticTerrain(_ridge, R, ceiling_height_m=800.0, dem_set_id="ANALYTIC-ridges")


def _scenario(**labels):
    scenario = single_site_scenario(
        "ridge-site", "Analytic ridge site", -86.0, 20.0, dem_set_id="any", synthetic=False, azimuth_step_deg=5.0, max_range_m=50_000.0,
    )
    scenario["sites"][0].update(labels)
    validate_document(scenario)
    return scenario


def _site_entry(root):
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    validate_document(index)
    (entry,) = [p for p in index["packages"] if p["kind"] == "site"]
    return entry


def test_labels_reach_the_site_package_and_the_index_unchanged(tmp_path):
    (path,) = run_scenario(_scenario(programme="Chang'e", category="past landing"), tmp_path, _terrain())
    manifest = validate_package(path)
    assert manifest["site"]["programme"] == "Chang'e" and manifest["site"]["category"] == "past landing"
    entry = _site_entry(tmp_path)
    assert entry["programme"] == "Chang'e" and entry["category"] == "past landing"


def test_labels_are_optional_and_independent_of_each_other(tmp_path):
    (plain,) = run_scenario(_scenario(), tmp_path / "plain", _terrain())
    manifest = validate_package(plain)
    assert "programme" not in manifest["site"] and "category" not in manifest["site"]
    entry = _site_entry(tmp_path / "plain")
    assert "programme" not in entry and "category" not in entry

    (one,) = run_scenario(_scenario(category="candidate"), tmp_path / "one", _terrain())
    manifest = validate_package(one)
    assert manifest["site"]["category"] == "candidate" and "programme" not in manifest["site"]
    entry = _site_entry(tmp_path / "one")
    assert entry["category"] == "candidate" and "programme" not in entry


def test_a_label_is_not_part_of_the_request_and_does_not_change_the_package_id(tmp_path):
    (plain,) = run_scenario(_scenario(), tmp_path / "plain", _terrain())
    (labelled,) = run_scenario(_scenario(programme="Apollo", category="past landing"), tmp_path / "labelled", _terrain())
    a, b = validate_package(plain), validate_package(labelled)
    assert a["package_id"] == b["package_id"]
    assert a["request"] == b["request"] and "programme" not in b["request"]["site"] and "category" not in b["request"]["site"]
    # the label is content: the digest of the content tells the two apart
    assert a["content_sha256"] != b["content_sha256"]


def test_labels_reach_the_synthetic_packages_as_well(tmp_path):
    scenario = single_site_scenario("invented", "Invented site", -89.0, 10.0, dem_set_id="SYNTHETIC-v1", synthetic=True)
    scenario["sites"][0].update(programme="Invented programme", category="project site")
    from lsncore.synthetic import SYNTHETIC_DEM_SET_ID

    scenario["data"]["dem_set_id"] = SYNTHETIC_DEM_SET_ID
    (path,) = run_scenario(scenario, tmp_path)
    manifest = validate_package(path)
    assert manifest["site"]["programme"] == "Invented programme" and manifest["site"]["category"] == "project site"
    assert _site_entry(tmp_path)["programme"] == "Invented programme"


@pytest.mark.parametrize("label", ["programme", "category"])
@pytest.mark.parametrize("value", [5, "", None, ["Apollo"]])
def test_a_label_must_be_text(label, value):
    scenario = _scenario()
    scenario["sites"][0][label] = value
    with pytest.raises(ContractError):
        validate_document(scenario)


def test_scenario_command_takes_the_labels_from_the_site_records(tmp_path):
    records = {
        "schema": "site records",
        "sites": [
            {"site_id": "rim_crest_a", "name": "Rim crest A", "lon_deg_east": 205.5, "lat_deg": -89.8, "kind": "project_candidate", "category": "project site", "programme": "Project sites"},
            {"site_id": "old_lander", "name": "Old lander", "lon_deg_east": 23.5, "lat_deg": 0.7, "programme": "Apollo"},
            {"site_id": "summit_b", "name": "Summit B", "lon_deg_east": 2.0, "lat_deg": -86.0},
        ],
    }
    (tmp_path / "sites.json").write_text(json.dumps(records))
    out = tmp_path / "scenario.json"
    code = cli.main([
        "scenario", "--sites", str(tmp_path / "sites.json"), "--id", "labelled", "--start", "2026-11-14T00:00:00.000Z",
        "--end", "2026-11-20T00:00:00.000Z", "--out", str(out),
    ])
    assert code == 0
    sites = json.loads(out.read_text())["sites"]
    assert sites[0]["programme"] == "Project sites" and sites[0]["category"] == "project site" and "kind" not in sites[0]
    assert sites[1]["programme"] == "Apollo" and "category" not in sites[1]
    assert "programme" not in sites[2] and "category" not in sites[2]


def test_the_curated_site_records_of_the_data_stream_pass_through(tmp_path):
    """Every curated record that states a programme or a category keeps it word for word."""
    lsn_data = pytest.importorskip("lsn_data")
    from pathlib import Path

    curated = Path(lsn_data.__file__).resolve().parents[1] / "sites" / "curated_sites.json"
    if not curated.exists():
        pytest.skip("curated site records of the data stream not found")
    records = json.loads(curated.read_text(encoding="utf-8"))["sites"]
    if not any("programme" in r for r in records):
        pytest.skip("the curated site records carry no programme yet")
    out = tmp_path / "scenario.json"
    assert cli.main(["scenario", "--sites", str(curated), "--id", "curated", "--start", "2026-11-14T00:00:00.000Z", "--end", "2026-11-20T00:00:00.000Z", "--out", str(out)]) == 0
    sites = json.loads(out.read_text(encoding="utf-8"))["sites"]
    assert len(sites) == len(records)
    for record, site in zip(records, sites):
        for label in ("programme", "category"):
            assert site.get(label) == record.get(label), record["site_id"]
