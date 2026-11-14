"""Contract 0.4: band for a stated horizon error and survey of a stated landing ellipse."""

import copy
import json
import shutil

import numpy as np
import pytest

from lsncore.contract import ContractError, contract_dir, read_package, validate_document, validate_package
from lsncore.scenario import load_scenario
from lsncore.synthetic import run_synthetic_scenario
from lsncore.timeline import IntervalSet

SAMPLE = contract_dir() / "sample"


@pytest.fixture(scope="module")
def scenario():
    return load_scenario(SAMPLE / "SYNTHETIC_scenario.json")


@pytest.fixture(scope="module")
def site(tmp_path_factory, scenario):
    out = tmp_path_factory.mktemp("packages")
    paths = run_synthetic_scenario(scenario, out)
    path = next(p for p in paths if p.name.startswith("site-"))
    validate_package(path)
    return read_package(path)


def _domain(tl):
    grid = tl["time"]
    return (grid["start_et_s"], grid["start_et_s"] + (grid["count"] - 1) * grid["step_s"])


def _window(tl, wid, h):
    (record,) = [w for w in tl["windows"] if w["id"] == wid and w["height_index"] == h]
    return IntervalSet(record["intervals_et_s"], _domain(tl))


def _metric(tl, mid, h):
    (record,) = [m for m in tl["metrics"] if m["id"] == mid and m["height_index"] == h]
    return record["value"]


def test_band_windows_are_nested_and_the_assumption_is_stated(site, scenario):
    tl = site.manifest["timeline"]
    stated = scenario["uncertainty"]
    assert site.manifest["request"]["timeline"]["uncertainty"] == stated
    block = tl["uncertainty"]["horizon_error"]
    assert block["error_deg"] == stated["horizon_error_deg"]
    assert "shifted" in block["assumption"] and block["method"] in site.manifest["methods"]
    some_band = False
    for body in tl["bodies"]:
        tag = body.lower()
        for h in range(len(site.manifest["horizon"]["observer_heights_m"])):
            nominal = _window(tl, f"{tag}_visible", h)
            certain = _window(tl, f"{tag}_visible_certain", h)
            possible = _window(tl, f"{tag}_visible_possible", h)
            uncertain = _window(tl, f"{tag}_visible_uncertain", h)
            assert certain.intersection(nominal) == certain      # certain is inside nominal
            assert nominal.intersection(possible) == nominal     # nominal is inside possible
            assert uncertain == possible.intersection(certain.complement())
            assert _metric(tl, f"{tag}_visible_certain_s", h) == pytest.approx(certain.total_s(), abs=1e-6)
            assert _metric(tl, f"{tag}_visible_possible_s", h) == pytest.approx(possible.total_s(), abs=1e-6)
            assert _metric(tl, f"{tag}_visible_uncertain_s", h) == pytest.approx(possible.total_s() - certain.total_s(), abs=1e-6)
            some_band = some_band or uncertain.total_s() > 0
    assert some_band


def test_every_event_carries_its_earliest_and_latest_time(site):
    tl = site.manifest["timeline"]
    assert tl["events"]
    wider = 0
    for event in tl["events"]:
        assert event["earliest_et_s"] <= event["et_s"] <= event["latest_et_s"]
        assert event["earliest_utc"] <= event["utc"] <= event["latest_utc"]  # ISO strings sort like times
        uncertain = _window(tl, f"{event['body'].lower()}_visible_uncertain", event["height_index"])
        if event["latest_et_s"] > event["earliest_et_s"]:
            wider += 1
            assert any(a == event["earliest_et_s"] and b == event["latest_et_s"] for a, b in uncertain.intervals)
    assert wider > 0


def test_ellipse_survey_brackets_the_site(site, scenario):
    tl = site.manifest["timeline"]
    stated = scenario["uncertainty"]["landing_ellipse"]
    block = tl["uncertainty"]["landing_ellipse"]
    hd = site.manifest["horizon"]["default_height_index"]
    assert block["height_index"] == hd and len(block["points"]) == stated["points"]
    assert block["points"][0]["lat_deg"] == site.manifest["site"]["lat_deg"]  # the centre is the site
    assert "not a probability" in block["assumption"]
    n = tl["time"]["count"]
    for body in tl["bodies"]:
        tag = body.lower()
        centre = _window(tl, f"{tag}_visible", hd)
        everywhere = _window(tl, f"{tag}_visible_all_points", hd)
        somewhere = _window(tl, f"{tag}_visible_any_point", hd)
        assert everywhere.intersection(centre) == everywhere
        assert centre.intersection(somewhere) == centre
        share = site.array(tl["series"][body]["ellipse_visible_share"])
        assert share.shape == (n,) and share.min() >= 0.0 and share.max() <= 1.0
        # the share is 1 inside "all points" and 0 outside "any point", at the samples of the series
        t = tl["time"]["start_et_s"] + np.arange(n) * tl["time"]["step_s"]
        inside_all = np.array([everywhere.contains(x) for x in t])
        outside_any = np.array([not somewhere.contains(x) for x in t])
        assert np.all(share[inside_all] == 1.0) and np.all(share[outside_any] == 0.0)
        totals = [p["visible_s"][body] for p in block["points"]]
        stats = block["visible_s"][body]
        assert stats["centre_s"] == pytest.approx(centre.total_s(), abs=1e-6) == pytest.approx(totals[0], abs=1e-6)
        assert stats["min_s"] == pytest.approx(min(totals)) and stats["max_s"] == pytest.approx(max(totals))
        assert stats["median_s"] == pytest.approx(float(np.median(totals)))
        assert stats["min_s"] <= stats["centre_s"] <= stats["max_s"]


def test_a_requirement_can_ask_for_certain_visibility(tmp_path, scenario):
    """Robust landing windows: the same requirement on the pessimistic windows is harder to meet."""
    robust = copy.deepcopy(scenario)
    for condition in robust["requirements"][0]["conditions"]:
        condition["window"] = condition["window"] + "_certain"
    paths = run_synthetic_scenario(robust, tmp_path / "robust")
    strict = validate_package(next(p for p in paths if p.name.startswith("site-")))
    paths = run_synthetic_scenario(scenario, tmp_path / "nominal")
    nominal = validate_package(next(p for p in paths if p.name.startswith("site-")))
    for a, b in zip(strict["timeline"]["opportunities"], nominal["timeline"]["opportunities"]):
        domain = _domain(nominal["timeline"])
        sa, sb = IntervalSet(a["landing_windows_et_s"], domain), IntervalSet(b["landing_windows_et_s"], domain)
        assert sa.intersection(sb) == sa and sa.total_s() <= sb.total_s()


def test_without_stated_assumptions_nothing_is_added(tmp_path, scenario):
    plain = copy.deepcopy(scenario)
    plain.pop("uncertainty")
    paths = run_synthetic_scenario(plain, tmp_path)
    manifest = validate_package(next(p for p in paths if p.name.startswith("site-")))
    tl = manifest["timeline"]
    assert "uncertainty" not in tl and "earliest_et_s" not in tl["events"][0]
    assert not any("certain" in w["id"] or "points" in w["id"] for w in tl["windows"])


def test_schema_checks_the_stated_assumptions(scenario):
    for change in (
        lambda s: s["uncertainty"].update(horizon_error_deg=0.0),
        lambda s: s["uncertainty"]["landing_ellipse"].update(points=0),
        lambda s: s["uncertainty"]["landing_ellipse"].pop("azimuth_deg"),
        lambda s: s["uncertainty"].update(sigma=3),
    ):
        broken = copy.deepcopy(scenario)
        change(broken)
        with pytest.raises(ContractError):
            validate_document(broken)


def test_validator_rejects_an_event_outside_its_own_bounds(site, tmp_path):
    dst = tmp_path / site.path.name
    shutil.copytree(site.path, dst)
    manifest = json.loads((dst / "manifest.json").read_text())
    event = manifest["timeline"]["events"][0]
    event["latest_et_s"] = event["et_s"] - 10.0
    (dst / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ContractError, match="earliest and latest"):
        validate_package(dst)
