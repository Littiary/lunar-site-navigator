"""Contract 0.5: mast-height trade table in the site package, and the site_pairs package."""

import json
import shutil

import pytest

from lsncore.contract import ContractError, contract_dir, read_package, validate_document, validate_package
from lsncore.pairs import pair_report
from lsncore.scenario import load_scenario
from lsncore.synthetic import run_synthetic_scenario
from lsncore.timeline import IntervalSet

SAMPLE = contract_dir() / "sample"


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("packages")
    paths = run_synthetic_scenario(load_scenario(SAMPLE / "SYNTHETIC_scenario.json"), out)
    for path in paths:
        validate_package(path)
    sites = [read_package(p) for p in paths if p.name.startswith("site-")]
    (pairs,) = [read_package(p) for p in paths if p.name.startswith("pairs-")]
    return out, sites, pairs


def _domain(grid):
    return (grid["start_et_s"], grid["start_et_s"] + (grid["count"] - 1) * grid["step_s"])


def _window(manifest, wid, h):
    tl = manifest["timeline"]
    (record,) = [w for w in tl["windows"] if w["id"] == wid and w["height_index"] == h]
    return IntervalSet(record["intervals_et_s"], _domain(tl["time"]))


def test_height_trade_is_read_off_the_windows(run):
    _, sites, _ = run
    for site in sites:
        m = site.manifest
        heights = m["horizon"]["observer_heights_m"]
        trade = m["timeline"]["height_trade"]
        assert trade["observer_heights_m"] == heights and trade["method"] in m["methods"]
        by_id = {q["id"]: q for q in trade["quantities"]}
        assert {"sun_visible_s", "sun_longest_outage_s", "earth_visible_s", "sun_and_earth_visible_s"} <= by_id.keys()
        for h in range(len(heights)):
            sun = _window(m, "sun_visible", h)
            assert by_id["sun_visible_s"]["values"][h] == pytest.approx(sun.total_s(), abs=1e-6)
            assert by_id["sun_longest_outage_s"]["values"][h] == pytest.approx(sun.complement().longest_s(), abs=1e-6)
            assert by_id["sun_visible_s"]["change_s"][h] == pytest.approx(sun.total_s() - _window(m, "sun_visible", 0).total_s(), abs=1e-6)
        assert all(q["change_s"][0] == 0.0 for q in trade["quantities"])
        # in the sample a higher observer never sees the Sun for a shorter time
        values = by_id["sun_visible_s"]["values"]
        assert all(b >= a - 1e-6 for a, b in zip(values, values[1:]))


def test_pairs_package_follows_from_the_site_packages(run):
    out, sites, pairs = run
    m = pairs.manifest
    assert m["kind"] == "site_pairs" and m["synthetic"] is True and "SYNTHETIC" in m["synthetic_notice"]
    assert [s["package_id"] for s in m["sites"]] == [s.package_id for s in sites] == m["request"]["site_package_ids"]
    assert [p["content_sha256"] for p in m["inputs"]["site_packages"]] == [s.manifest["content_sha256"] for s in sites]
    assert m["time"] == sites[0].manifest["timeline"]["time"]
    (pair,) = m["pairs"]
    a, b = sites
    assert (pair["site_a"], pair["site_b"]) == (a.manifest["site"]["site_id"], b.manifest["site"]["site_id"])
    assert 20_000.0 < pair["distance_m"] < 26_000.0  # half a degree of latitude and 15 degrees of longitude near the pole
    for row in pair["windows"]:
        wa = _window(a.manifest, row["window"], a.manifest["horizon"]["default_height_index"])
        wb = _window(b.manifest, row["window"], b.manifest["horizon"]["default_height_index"])
        expected = pair_report(wa, wb)
        for key in ("a_s", "b_s", "either_s", "both_s", "neither_s", "longest_neither_s", "gain_over_better_s"):
            assert row[key] == pytest.approx(expected[key], abs=1e-6)
        assert row["neither_intervals_et_s"] == expected["neither"].as_list()
        assert len(row["neither_intervals_utc"]) == len(row["neither_intervals_et_s"])
        assert row["method"] in m["methods"]
    assert {row["window"] for row in pair["windows"]} == {"sun_visible", "earth_visible", "sun_and_earth_visible"}
    # the index lists the new kind
    index = json.loads((out / "index.json").read_text())
    validate_document(index)
    (entry,) = [e for e in index["packages"] if e["kind"] == "site_pairs"]
    assert entry["site_ids"] == [s["site_id"] for s in m["sites"]] and entry["path"] == f"site_pairs/{m['package_id']}"


def test_one_site_gives_no_pairs_package(tmp_path):
    scenario = load_scenario(SAMPLE / "SYNTHETIC_scenario.json")
    scenario["sites"] = scenario["sites"][:1]
    paths = run_synthetic_scenario(scenario, tmp_path)
    assert not any(p.name.startswith("pairs-") for p in paths)


@pytest.mark.parametrize(
    "case, change, expected",
    [
        ("totals that do not add up", lambda m: m["pairs"][0]["windows"][0].update(either_s=m["pairs"][0]["windows"][0]["either_s"] + 100.0), "either_s + neither_s"),
        ("pair of a site with itself", lambda m: m["pairs"][0].update(site_b=m["pairs"][0]["site_a"]), "two different sites"),
        ("site list changed", lambda m: m["sites"][0].update(package_id="site-0000000000000000"), "package ids differ"),
        ("row without a method", lambda m: m["pairs"][0]["windows"][0].pop("method"), "method"),
    ],
)
def test_validator_rejects_broken_pairs_packages(run, tmp_path, case, change, expected):
    _, _, pairs = run
    dst = tmp_path / pairs.path.name
    shutil.copytree(pairs.path, dst)
    manifest = json.loads((dst / "manifest.json").read_text())
    change(manifest)
    (dst / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ContractError) as info:
        validate_package(dst)
    assert expected in str(info.value)


def test_validator_rejects_a_trade_table_of_the_wrong_length(run, tmp_path):
    _, sites, _ = run
    dst = tmp_path / sites[0].path.name
    shutil.copytree(sites[0].path, dst)
    manifest = json.loads((dst / "manifest.json").read_text())
    manifest["timeline"]["height_trade"]["quantities"][0]["values"].pop()
    (dst / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ContractError, match="one value per observer height"):
        validate_package(dst)
