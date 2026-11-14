"""Contract v0: the walking skeleton writes packages that the validator accepts, the
validator rejects damaged packages, and the committed sample is valid and reproducible."""

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from lsncore import cli
from lsncore.contract import (
    ContractError,
    contract_dir,
    load_schema,
    read_package,
    validate_document,
    validate_package,
)
from lsncore.scenario import load_scenario
from lsncore.synthetic import run_synthetic_scenario

SAMPLE = contract_dir() / "sample"


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    out = tmp_path_factory.mktemp("packages")
    scenario = load_scenario(SAMPLE / "SYNTHETIC_scenario.json")
    paths = run_synthetic_scenario(scenario, out)
    return out, paths


def _site_dir(paths):
    return next(p for p in paths if p.name.startswith("site-"))


def _table_dir(paths):
    return next(p for p in paths if p.name.startswith("dirtab-"))


def test_schema_is_a_valid_json_schema():
    from jsonschema import Draft202012Validator

    Draft202012Validator.check_schema(load_schema())


def test_skeleton_writes_valid_packages(generated):
    out, paths = generated
    assert len(paths) == 4  # direction table, two sites, their comparison
    for path in paths:
        validate_package(path)
    validate_document(json.loads((out / "index.json").read_text()))


def test_cli_site_command_end_to_end(tmp_path):
    code = cli.main(
        ["site", "--lat", "-89.5", "--lon", "200", "--name", "Skeleton test", "--out", str(tmp_path), "--synthetic"]
    )
    assert code == 0
    index = json.loads((tmp_path / "index.json").read_text())
    (entry,) = index["packages"]
    manifest = validate_package(tmp_path / entry["path"])
    assert manifest["site"]["lon_deg"] == -160.0  # wrapped to (-180, 180]
    assert "timeline" not in manifest and entry["has_timeline"] is False
    assert cli.main(["validate", str(tmp_path / entry["path"]), str(tmp_path / "index.json")]) == 0


def test_six_contract_decisions_are_in_the_packages(generated):
    _, paths = generated
    site = read_package(_site_dir(paths))
    table = read_package(_table_dir(paths))
    m = site.manifest
    hz = m["horizon"]
    n_heights = len(hz["observer_heights_m"])
    n_az = hz["azimuth"]["count"]
    # 1: distance to the obstacle in every azimuth, next to the elevation
    assert site.array(hz["distance_m"]).shape == (n_heights, n_az)
    assert site.array(hz["elevation_deg"]).shape == (n_heights, n_az)
    # 2: several observer heights in one package
    assert n_heights >= 2
    # 3: the direction table is its own package and knows nothing about the site
    assert m["inputs"]["direction_table"]["package_id"] == table.package_id
    assert "site" not in table.manifest
    assert table.array(table.manifest["positions_km"]).shape == (table.manifest["time"]["count"], 2, 3)
    # 4: one time-grid object, same fields in both packages
    assert m["timeline"]["time"].keys() == table.manifest["time"].keys()
    # 5: the request echoes the scenario
    assert m["request"]["site"]["site_id"] == "synthetic-sample-site"
    # 6: every number names a method card
    card = m["methods"][hz["elevation_deg"]["method"]]
    assert {"definition", "algorithm", "frame", "time_scale", "data", "validation", "limits"} <= card.keys()


def test_series_agree_with_windows(generated):
    _, paths = generated
    site = read_package(_site_dir(paths))
    tl = site.manifest["timeline"]
    h = site.manifest["horizon"]["default_height_index"]
    fraction = site.array(tl["series"]["SUN"]["visible_fraction"])[h]
    t = tl["time"]["start_et_s"] + np.arange(tl["time"]["count"]) * tl["time"]["step_s"]
    window = next(w for w in tl["windows"] if w["id"] == "sun_visible" and w["height_index"] == h)
    inside = np.zeros(t.size, dtype=bool)
    for a, b in window["intervals_et_s"]:
        inside |= (t > a) & (t < b)
    assert np.array_equal(inside, fraction > 0)
    assert len(tl["events"]) > 0


def test_package_id_is_reproducible_and_depends_on_the_request(generated, tmp_path):
    _, paths = generated
    scenario = load_scenario(SAMPLE / "SYNTHETIC_scenario.json")
    again = run_synthetic_scenario(scenario, tmp_path / "a")
    assert sorted(p.name for p in again) == sorted(p.name for p in paths)
    a, b = read_package(_site_dir(again)).manifest, read_package(_site_dir(paths)).manifest
    assert a["content_sha256"] == b["content_sha256"]
    scenario["sites"][0]["lat_deg"] = -87.0
    moved = run_synthetic_scenario(scenario, tmp_path / "b")
    assert _site_dir(moved).name != _site_dir(paths).name


def _flip_byte(path: Path) -> None:
    data = bytearray(path.read_bytes())
    data[100] ^= 0xFF
    path.write_bytes(bytes(data))


def _edit(directory: Path, change) -> None:
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text())
    change(manifest)
    path.write_text(json.dumps(manifest))


DAMAGE = {
    "array file removed": (lambda d, m: (d / m["horizon"]["distance_m"]["file"]).unlink(), "missing array file"),
    "array file truncated": (lambda d, m: (d / m["horizon"]["elevation_deg"]["file"]).write_bytes(b"\0" * 8), "bytes"),
    "array content changed": (lambda d, m: _flip_byte(d / m["horizon"]["elevation_deg"]["file"]), "sha256"),
    "unknown method card": (lambda d, m: _edit(d, lambda x: x["horizon"]["elevation_deg"].update(method="no.such.card")), "not defined"),
    "distance array missing": (lambda d, m: _edit(d, lambda x: x["horizon"].pop("distance_m")), "distance_m"),
    "site differs from request": (lambda d, m: _edit(d, lambda x: x["site"].update(lat_deg=10.0)), "site/lat_deg"),
    "synthetic notice removed": (lambda d, m: _edit(d, lambda x: x.pop("synthetic_notice")), "synthetic_notice"),
    "request edited": (lambda d, m: _edit(d, lambda x: x["request"]["site"].update(name="other")), "package_id"),
    "other contract version": (lambda d, m: _edit(d, lambda x: x["contract"].update(version="0.9")), "contract/version"),
    "unknown top-level field": (lambda d, m: _edit(d, lambda x: x.update(surprise=1)), "surprise"),
    "synthetic flag cleared": (lambda d, m: _edit(d, lambda x: x.update(synthetic=False)), "not marked synthetic"),
}


@pytest.mark.parametrize("case", DAMAGE)
def test_validator_rejects_damaged_packages(generated, tmp_path, case):
    damage, expected = DAMAGE[case]
    _, paths = generated
    src = _site_dir(paths)
    dst = tmp_path / src.name
    shutil.copytree(src, dst)
    damage(dst, read_package(dst).manifest)
    with pytest.raises(ContractError) as info:
        validate_package(dst)
    assert expected in str(info.value)


def test_committed_sample_is_valid_and_marked_synthetic():
    index = json.loads((SAMPLE / "packages" / "index.json").read_text())
    validate_document(index)
    assert {e["kind"] for e in index["packages"]} == {"site", "direction_table", "site_pairs"}
    for entry in index["packages"]:
        manifest = validate_package(SAMPLE / "packages" / entry["path"])
        assert manifest["synthetic"] is True
        assert "SYNTHETIC" in manifest["synthetic_notice"]
        assert all(c["validation"]["status"] == "synthetic" for c in manifest["methods"].values())


def _array_refs(node, where=""):
    if isinstance(node, dict):
        if "file" in node and "dtype" in node:
            yield where, node
        else:
            for key, value in node.items():
                yield from _array_refs(value, f"{where}/{key}")


def _lookup(node, where):
    for key in where.strip("/").split("/"):
        node = node[key]
    return node


def test_committed_sample_matches_a_fresh_run(generated):
    out, _ = generated
    index = json.loads((SAMPLE / "packages" / "index.json").read_text())
    for entry in index["packages"]:
        committed = read_package(SAMPLE / "packages" / entry["path"])
        fresh = read_package(out / entry["path"])  # same id, hence the same path
        refs = list(_array_refs(committed.manifest))
        assert refs or entry["kind"] == "site_pairs"  # a comparison holds no arrays
        for where, ref in refs:
            np.testing.assert_allclose(
                committed.array(ref), fresh.array(_lookup(fresh.manifest, where)), rtol=0, atol=1e-6, err_msg=where
            )
