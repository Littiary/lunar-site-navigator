"""Contract 0.3: lunar-day calendar, stated requirements, landing windows, slip tolerance."""

import copy
import json
import shutil

import pytest

from lsncore.calendar import landing_windows, slip_report
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


def test_calendar_periods_tile_the_range_and_totals_add_up(site):
    tl = site.manifest["timeline"]
    calendar = tl["calendar"]
    periods = calendar["periods"]
    start, end = _domain(tl)
    assert calendar["period"] == "lunar_day" and calendar["method"] in site.manifest["methods"]
    assert periods[0]["start_et_s"] == start and periods[-1]["end_et_s"] == end
    assert all(a["end_et_s"] == b["start_et_s"] for a, b in zip(periods, periods[1:]))
    assert not periods[0]["complete"] and not periods[-1]["complete"]
    n_h = len(site.manifest["horizon"]["observer_heights_m"])
    by_id = {q["id"]: q for q in calendar["quantities"]}
    assert {"sun_visible_s", "earth_visible_s", "sun_and_earth_visible_s", "sun_longest_outage_s"} <= by_id.keys()
    for qid in ("sun_visible_s", "earth_visible_s", "sun_and_earth_visible_s"):
        q = by_id[qid]
        assert len(q["values"]) == n_h and all(len(row) == len(periods) for row in q["values"])
        for h in range(n_h):
            assert sum(q["values"][h]) == pytest.approx(_window(tl, q["window"], h).total_s(), abs=1e-6)
    for h in range(n_h):
        for value, period in zip(by_id["sun_longest_outage_s"]["values"][h], periods):
            assert 0.0 <= value <= period["end_et_s"] - period["start_et_s"] + 1e-6


def test_landing_windows_follow_from_the_stated_requirement(site, scenario):
    tl = site.manifest["timeline"]
    stated = site.manifest["request"]["timeline"]["requirements"]
    assert stated == scenario["requirements"]
    (requirement,) = stated
    n_h = len(site.manifest["horizon"]["observer_heights_m"])
    assert len(tl["opportunities"]) == n_h
    planned_utc = site.manifest["request"]["timeline"]["landing_utc"]
    assert planned_utc == scenario["sites"][0]["landing_utc"]
    some_window = False
    for record in tl["opportunities"]:
        h = record["height_index"]
        windows = {c["window"]: _window(tl, c["window"], h) for c in requirement["conditions"]}
        feasible, info = landing_windows(requirement, windows, _domain(tl))
        assert record["landing_windows_et_s"] == feasible.as_list()
        assert record["latest_landing_et_s"] == info["latest_landing_et_s"] == _domain(tl)[1] - requirement["mission_duration_s"]
        assert record["window_count"] == len(feasible)
        assert record["longest_window_s"] == pytest.approx(feasible.longest_s(), abs=1e-6)
        assert sum(record["feasible_s_per_period"]) == pytest.approx(feasible.total_s(), abs=1e-6)
        # every feasible landing time really has the Earth in view and 48 h of Sun ahead
        for a, b in feasible.intervals:
            middle = 0.5 * (a + b)
            assert windows["earth_visible"].contains(middle)
            assert any(s <= middle and middle + 172800.0 <= e + 1e-6 for s, e in windows["sun_visible"].intervals)
        planned = record["planned_landing"]
        assert planned["utc"] == planned_utc
        report = slip_report(feasible, planned["et_s"])
        assert planned["feasible"] == report["feasible"]
        assert planned["slip_tolerance_s"] == pytest.approx(report["slip_tolerance_s"], abs=1e-6)
        assert planned["early_tolerance_s"] == pytest.approx(report["early_tolerance_s"], abs=1e-6)
        some_window = some_window or len(feasible) > 0
    assert some_window
    default = tl["opportunities"][site.manifest["horizon"]["default_height_index"]]
    assert default["planned_landing"]["feasible"] and default["planned_landing"]["slip_tolerance_s"] > 0  # the sample shows a tolerance


def test_no_requirement_means_no_opportunities_but_still_a_calendar(tmp_path, scenario):
    plain = copy.deepcopy(scenario)
    plain.pop("requirements")
    plain["sites"][0].pop("landing_utc")
    paths = run_synthetic_scenario(plain, tmp_path)
    manifest = validate_package(next(p for p in paths if p.name.startswith("site-")))
    assert "calendar" in manifest["timeline"] and "opportunities" not in manifest["timeline"]
    assert manifest["request"]["timeline"]["landing_utc"] is None


def test_requirement_naming_an_unknown_window_is_refused(tmp_path, scenario):
    broken = copy.deepcopy(scenario)
    broken["requirements"][0]["conditions"][0]["window"] = "no_such_window"
    with pytest.raises(ValueError, match="no_such_window"):
        run_synthetic_scenario(broken, tmp_path)


def test_scenario_schema_checks_requirements(scenario):
    validate_document(scenario)
    missing = copy.deepcopy(scenario)
    missing["requirements"][0]["conditions"][1].pop("min_s")  # 'continuous_from_landing' needs a duration
    with pytest.raises(ContractError):
        validate_document(missing)
    unknown = copy.deepcopy(scenario)
    unknown["requirements"][0]["conditions"][0]["kind"] = "sometimes"
    with pytest.raises(ContractError):
        validate_document(unknown)


@pytest.mark.parametrize(
    "case, change, expected",
    [
        ("opportunity for an unstated requirement", lambda m: m["timeline"]["opportunities"][0].update(requirement_id="other"), "requirement_id"),
        ("calendar row of the wrong length", lambda m: m["timeline"]["calendar"]["quantities"][0]["values"][0].append(1.0), "values must be"),
        ("gap between periods", lambda m: m["timeline"]["calendar"]["periods"][1].update(start_et_s=m["timeline"]["calendar"]["periods"][1]["start_et_s"] + 5.0), "without gaps"),
    ],
)
def test_validator_rejects_broken_0_3_fields(site, tmp_path, case, change, expected):
    dst = tmp_path / site.path.name
    shutil.copytree(site.path, dst)
    manifest = json.loads((dst / "manifest.json").read_text())
    change(manifest)
    (dst / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ContractError) as info:
        validate_package(dst)
    assert expected in str(info.value)


def test_requirement_presets_are_valid_and_labelled_as_examples(tmp_path, scenario):
    """The presets are the one documented place viewers read example requirements from."""
    from lsncore import cli
    from lsncore.contract import contract_dir
    from lsncore.scenario import requirement_presets

    presets = requirement_presets()
    raw = json.loads((contract_dir() / "presets" / "requirements.json").read_text(encoding="utf-8"))
    assert "not requirements of NASA" in raw["notice"]
    assert list(presets) == ["example-standard", "example-strict", "example-loose"]
    for preset in presets.values():
        assert preset["label"].startswith("EXAMPLE chosen by the team, not a NASA requirement")
        candidate = copy.deepcopy(scenario)
        candidate["requirements"] = [preset]
        validate_document(candidate)  # the schema of a requirement
        assert {c["window"] for c in preset["conditions"]} <= {"sun_visible", "earth_visible"}
    # the stricter one asks for more of the same, the looser one for less
    need = {name: next(c["min_s"] for c in p["conditions"] if c["kind"] == "continuous_from_landing") for name, p in presets.items()}
    assert need["example-loose"] < need["example-standard"] < need["example-strict"]
    assert need["example-standard"] == 10 * 86400.0

    records = {"sites": [{"site_id": "a", "name": "A", "lon_deg_east": 10.0, "lat_deg": -89.0}]}
    (tmp_path / "sites.json").write_text(json.dumps(records))
    out = tmp_path / "scenario.json"
    args = ["scenario", "--sites", str(tmp_path / "sites.json"), "--id", "one", "--start", "2026-11-14T00:00:00.000Z", "--end", "2027-11-14T00:00:00.000Z", "--out", str(out)]
    assert cli.main(args + ["--preset", "all"]) == 0
    assert [r["id"] for r in json.loads(out.read_text())["requirements"]] == list(presets)
    assert cli.main(args + ["--preset", "example-loose"]) == 0
    assert [r["id"] for r in json.loads(out.read_text())["requirements"]] == ["example-loose"]
    assert cli.main(args + ["--preset", "no-such-preset"]) == 2
