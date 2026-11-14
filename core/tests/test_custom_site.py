"""One command for a site given by coordinates and a start date: a complete package.

`python -m lsncore custom --lat … --lon … --start … --out …` writes the horizon, the Sun
and Earth timeline with countdowns, the landing windows of the example requirements and
the uncertainty band of the default height-error model, reuses a direction table that
covers the window, and prints progress lines a caller can show.

Thresholds, fixed before the first run:

* A package computed on a reused, longer direction table has the same events as one
  computed on a table written for its own window, each within 1 s (twice the 0.5 s to
  which the event finder locates an event).
* A 30-day package of one site is written within 30 s: the command inside a running
  interpreter, best of three, on a machine that is doing nothing else.
"""

import json
import re
import time
from pathlib import Path

import numpy as np
import pytest

from lsncore import cli
from lsncore.contract import read_package, validate_document, validate_package
from lsncore.dem import AnalyticTerrain
from lsncore.pipeline import find_direction_table, run_scenario
from lsncore.scenario import custom_site_scenario, height_error_presets, requirement_presets

TOL_EVENT_TIME_S = 1.0
MAX_RUNTIME_CUSTOM_S = 30.0
EXIT_NOT_INSTALLED = 3

R = 1_737_400.0
PROGRESS = re.compile(r"^progress (\d+)/(\d+) \S.*$")


def _ridge(lon, lat):
    return 800.0 * np.sin(np.radians(lon) * 3.0) * np.cos(np.radians(lat) * 40.0)


def _terrain():
    return AnalyticTerrain(_ridge, R, ceiling_height_m=800.0, dem_set_id="ANALYTIC-ridges")


def _kernels():
    pytest.importorskip("spiceypy")
    from lsncore.ephem import kernels

    try:
        kernels.load()
    except FileNotFoundError as missing:
        pytest.skip(f"kernels are not on this machine: {missing}")
    return kernels


def _fixture_label():
    lsn_data = pytest.importorskip("lsn_data")
    label = Path(lsn_data.__file__).resolve().parents[1] / "fixtures" / "synth_s90_100m.lbl"
    if not label.exists():
        pytest.skip("synthetic DEM fixture of the data stream not found")
    return label


def _lines(capsys):
    return [line for line in capsys.readouterr().out.splitlines() if line.strip()]


def _site_manifest(root):
    index = json.loads((Path(root) / "index.json").read_text(encoding="utf-8"))
    validate_document(index)
    (entry,) = [p for p in index["packages"] if p["kind"] == "site"]
    return validate_package(Path(root) / entry["path"]), index


# ----------------------------------------------------------------- the scenario it runs


def test_custom_scenario_states_window_requirements_and_band():
    scenario = custom_site_scenario(26.1, 3.6, "2026-11-14", days=30.0)
    validate_document(scenario)
    (site,) = scenario["sites"]
    assert site["lat_deg"] == 26.1 and site["lon_deg"] == 3.6 and "landing_utc" not in site
    assert site["name"] == "Custom site 26.1000 N, 3.6000 E" and site["site_id"] == "custom-26-1000n-3-6000e"
    assert scenario["time_window"] == {"start_utc": "2026-11-14T00:00:00.000Z", "end_utc": "2026-12-14T00:00:00.000Z", "step_s": 3600.0}
    assert [r["id"] for r in scenario["requirements"]] == list(requirement_presets())
    presets = height_error_presets()
    assert scenario["uncertainty"] == {"dem_height_error_model": presets["models"][presets["default"]]}
    assert scenario["synthetic"] is False and scenario["data"]["dem_set_id"] == "any"


@pytest.mark.parametrize(
    "start, expected",
    [
        ("2026-11-14", "2026-11-14T00:00:00.000Z"),
        ("2026-11-14T06:30Z", "2026-11-14T06:30:00.000Z"),
        ("2026-11-14T06:30:15Z", "2026-11-14T06:30:15.000Z"),
        ("2026-11-14T06:30:15.250Z", "2026-11-14T06:30:15.250Z"),
        ("2026-11-14 06:30", "2026-11-14T06:30:00.000Z"),
    ],
)
def test_start_date_is_read_as_utc(start, expected):
    scenario = custom_site_scenario(-85.0, 200.0, start, days=1.5)
    assert scenario["time_window"]["start_utc"] == expected
    assert scenario["sites"][0]["name"] == "Custom site 85.0000 S, 160.0000 W"


@pytest.mark.parametrize("start", ["14.11.2026", "2026-13-01", "tomorrow", "2026-11-14T06:30+03:00"])
def test_a_start_date_that_is_not_a_utc_date_is_refused(start):
    with pytest.raises(ValueError, match="start"):
        custom_site_scenario(0.0, 0.0, start)


@pytest.mark.parametrize("lat, lon, days", [(91.0, 0.0, 30.0), (0.0, 400.0, 30.0), (0.0, 0.0, 0.0), (0.0, 0.0, -2.0)])
def test_coordinates_and_length_outside_their_range_are_refused(lat, lon, days):
    with pytest.raises(ValueError):
        custom_site_scenario(lat, lon, "2026-11-14", days=days)


def test_options_of_the_custom_scenario():
    scenario = custom_site_scenario(
        -89.8, 205.7, "2026-11-14", days=10.0, name="Rim", site_id="rim", landing_utc="2026-11-16T00:00:00.000Z",
        requirement_ids=["example-loose"], band=False, step_s=1800.0,
    )
    validate_document(scenario)
    assert scenario["sites"][0] == {"site_id": "rim", "name": "Rim", "lat_deg": -89.8, "lon_deg": 205.7, "landing_utc": "2026-11-16T00:00:00.000Z"}
    assert [r["id"] for r in scenario["requirements"]] == ["example-loose"] and "uncertainty" not in scenario
    assert scenario["time_window"]["end_utc"] == "2026-11-24T00:00:00.000Z" and scenario["time_window"]["step_s"] == 1800.0
    with pytest.raises(ValueError, match="requirement"):
        custom_site_scenario(0.0, 0.0, "2026-11-14", requirement_ids=["no-such-preset"])


# ------------------------------------------------------------ reusing a direction table


def _window_scenario(start, end):
    scenario = custom_site_scenario(-86.0, 20.0, start, days=1.0, band=False)
    scenario["time_window"]["end_utc"] = end
    scenario["observer_heights_m"] = [2.0]
    scenario["horizon"] = {"azimuth_step_deg": 1.0, "max_range_m": 50_000.0}
    return scenario


def test_a_table_that_covers_the_window_is_found_and_others_are_not(tmp_path):
    _kernels()
    long = run_scenario(_window_scenario("2026-11-14T00:00:00.000Z", "2026-12-14T00:00:00.000Z"), tmp_path / "long", _terrain())[0]
    assert read_package(long).kind == "direction_table"
    found = find_direction_table([tmp_path / "long"], "2026-11-20T00:00:00.000Z", "2026-11-30T00:00:00.000Z")
    assert found == long
    assert find_direction_table([tmp_path / "long"], "2026-11-14T00:00:00.000Z", "2026-12-14T00:00:00.000Z") == long
    # one record of margin on each side is needed, as in a table written for the window
    assert find_direction_table([tmp_path / "long"], "2026-11-13T00:00:00.000Z", "2026-11-30T00:00:00.000Z") is None
    assert find_direction_table([tmp_path / "long"], "2026-12-01T00:00:00.000Z", "2026-12-14T06:00:00.000Z") is None
    assert find_direction_table([tmp_path / "nothing-here"], "2026-11-20T00:00:00.000Z", "2026-11-30T00:00:00.000Z") is None


def test_a_synthetic_or_damaged_table_is_not_reused(tmp_path):
    _kernels()
    sample = Path(cli.contract_dir()) / "sample" / "packages"
    assert list(sample.glob("direction_table/*/manifest.json"))  # the invented table of the contract sample
    assert find_direction_table([sample], "2026-11-20T00:00:00.000Z", "2026-11-30T00:00:00.000Z") is None

    table = run_scenario(_window_scenario("2026-11-14T00:00:00.000Z", "2026-11-24T00:00:00.000Z"), tmp_path, _terrain())[0]
    assert find_direction_table([tmp_path], "2026-11-16T00:00:00.000Z", "2026-11-18T00:00:00.000Z") == table
    manifest = json.loads((table / "manifest.json").read_text(encoding="utf-8"))
    array = table / manifest["positions_km"]["file"]
    blob = bytearray(array.read_bytes())
    blob[100] ^= 0xFF
    array.write_bytes(bytes(blob))
    assert find_direction_table([tmp_path], "2026-11-16T00:00:00.000Z", "2026-11-18T00:00:00.000Z") is None


def test_events_on_a_reused_table_agree_with_a_table_of_the_window(tmp_path):
    _kernels()
    long = run_scenario(_window_scenario("2026-11-01T00:00:00.000Z", "2026-12-31T00:00:00.000Z"), tmp_path / "long", _terrain())[0]
    scenario = _window_scenario("2026-11-17T05:00:00.000Z", "2026-12-10T05:00:00.000Z")
    fresh = run_scenario(scenario, tmp_path / "fresh", _terrain())
    reused = run_scenario(scenario, tmp_path / "reused", _terrain(), direction_table=long)
    a, b = validate_package(fresh[-1]), validate_package(reused[-1])
    assert b["inputs"]["direction_table"]["package_id"] == long.name != a["inputs"]["direction_table"]["package_id"]
    assert b["timeline"]["time"] == a["timeline"]["time"]  # the series covers the window, not the table
    ea, eb = a["timeline"]["events"], b["timeline"]["events"]
    assert len(ea) == len(eb) > 0
    for x, y in zip(ea, eb):
        assert (x["type"], x["body"], x["height_index"]) == (y["type"], y["body"], y["height_index"])
        assert abs(x["et_s"] - y["et_s"]) <= TOL_EVENT_TIME_S
    assert [p["index"] for p in a["timeline"]["calendar"]["periods"]] == [p["index"] for p in b["timeline"]["calendar"]["periods"]]
    # the reused table is listed in the package root it was used for
    kinds = sorted(p["kind"] for p in json.loads((tmp_path / "reused" / "index.json").read_text())["packages"])
    assert kinds == ["direction_table", "site"]
    assert (tmp_path / "reused" / "direction_table" / long.name / "manifest.json").exists()


# ------------------------------------------------------------------------- the command


def test_custom_command_writes_a_complete_package_and_prints_progress(tmp_path, capsys):
    _kernels()
    label = _fixture_label()
    code = cli.main([
        "custom", "--lat", "-90", "--lon", "0", "--start", "2026-11-14", "--days", "4", "--out", str(tmp_path),
        "--dem-label", str(label), "--max-range-km", "19", "--azimuth-step", "1", "--jobs", "1",
    ])
    lines = _lines(capsys)
    assert code == 0

    progress = [PROGRESS.match(line) for line in lines if line.startswith("progress ")]
    assert progress and all(progress)
    steps = [(int(m.group(1)), int(m.group(2))) for m in progress]
    assert [k for k, _ in steps] == list(range(1, len(steps) + 1)) and all(n == len(steps) for _, n in steps)
    # what is not progress: the package directories and, last, the index
    others = [line for line in lines if not line.startswith("progress ")]
    assert Path(others[-1]) == tmp_path / "index.json" and len(others) == 3 and all(Path(line).is_dir() for line in others[:-1])
    last_progress = max(i for i, line in enumerate(lines) if line.startswith("progress "))
    assert last_progress < min(i for i, line in enumerate(lines) if not line.startswith("progress "))

    manifest, index = _site_manifest(tmp_path)
    assert sorted(p["kind"] for p in index["packages"]) == ["direction_table", "site"]
    assert manifest["status"] == "ok" and manifest["site"]["name"] == "Custom site 90.0000 S, 0.0000 E"
    timeline = manifest["timeline"]
    assert timeline["time"]["start_utc"] == "2026-11-14T00:00:00.000Z" and timeline["time"]["end_utc"] == "2026-11-18T00:00:00.000Z"
    assert {"sun_visible", "earth_visible"} <= {w["id"] for w in timeline["windows"]}
    counted = [m for m in timeline["metrics"] if "reference" in m]
    assert len(counted) >= 8 and all(m["reference"]["utc"] == "2026-11-14T00:00:00.000Z" for m in counted)
    assert [r["id"] for r in manifest["request"]["timeline"]["requirements"]] == list(requirement_presets())
    assert timeline["calendar"]["periods"] and "opportunities" in timeline
    band = timeline["uncertainty"]
    assert band["horizon_error"]["dem_height_error_model"]["id"] == height_error_presets()["default"]
    assert "landing_ellipse" not in band and "landing_ellipse" not in manifest["request"]["timeline"]["uncertainty"]
    assert any(w["id"] == "sun_visible_certain" for w in timeline["windows"])


def test_custom_command_reuses_the_table_of_an_earlier_run(tmp_path, capsys):
    _kernels()
    label = _fixture_label()
    common = ["--lat", "-90", "--lon", "0", "--out", str(tmp_path), "--dem-label", str(label), "--max-range-km", "19", "--azimuth-step", "1", "--jobs", "1"]
    assert cli.main(["custom", "--start", "2026-11-14", "--days", "6", *common]) == 0
    first = _lines(capsys)
    assert any(line.startswith("progress ") and "computing" in line and "direction" in line for line in first)
    (table,) = (tmp_path / "direction_table").iterdir()

    assert cli.main(["custom", "--start", "2026-11-16", "--days", "2", "--site-id", "second", *common]) == 0
    second = _lines(capsys)
    assert any(line.startswith("progress ") and "reusing" in line and table.name in line for line in second)
    assert [p.name for p in (tmp_path / "direction_table").iterdir()] == [table.name]
    manifest = validate_package(next((tmp_path / "site" / "second").iterdir()))
    assert manifest["inputs"]["direction_table"]["package_id"] == table.name

    # a table in another package root is copied, so that the root stays complete
    other = tmp_path / "elsewhere"
    assert cli.main(["custom", "--start", "2026-11-15", "--days", "3", "--tables", str(tmp_path), *common[:5], str(other), *common[6:]]) == 0
    third = _lines(capsys)
    assert any(line.startswith("progress ") and "reusing" in line and table.name in line for line in third)
    assert validate_package(other / "direction_table" / table.name)["package_id"] == table.name
    manifest, index = _site_manifest(other)
    assert manifest["inputs"]["direction_table"]["package_id"] == table.name


def test_custom_command_says_which_kernels_are_missing(tmp_path, capsys, monkeypatch):
    pytest.importorskip("spiceypy")
    label = _fixture_label()
    empty = tmp_path / "no-kernels"
    empty.mkdir()
    monkeypatch.setenv("LSN_KERNEL_DIR", str(empty))
    code = cli.main(["custom", "--lat", "-90", "--lon", "0", "--start", "2026-11-14", "--out", str(tmp_path / "out"), "--dem-label", str(label), "--max-range-km", "19"])
    captured = capsys.readouterr()
    assert code == EXIT_NOT_INSTALLED
    (line,) = [text for text in captured.err.splitlines() if text.startswith("error: kernels:")]
    assert "naif0012.tls" in line and "python -m lsncore.ephem.fetch_kernels" in line and str(empty) in line
    assert not (tmp_path / "out").exists()  # nothing half-written


def test_custom_command_says_that_no_terrain_is_installed(tmp_path, capsys, monkeypatch):
    kernels = _kernels()
    pytest.importorskip("lsn_data")
    monkeypatch.setenv("LSN_KERNEL_DIR", str(kernels.kernel_dir()))
    empty = tmp_path / "no-terrain"
    empty.mkdir()
    monkeypatch.setenv("LSN_DATA_ROOT", str(empty))
    code = cli.main(["custom", "--lat", "26.1", "--lon", "3.6", "--start", "2026-11-14", "--out", str(tmp_path / "out")])
    captured = capsys.readouterr()
    assert code == EXIT_NOT_INSTALLED
    (line,) = [text for text in captured.err.splitlines() if text.startswith("error: terrain:")]
    assert "python -m lsn_data fetch" in line and str(empty) in line
    assert not (tmp_path / "out").exists()


# ------------------------------------------------------------------------ real terrain


def _real_terrain():
    _kernels()
    pytest.importorskip("lsn_data")
    try:
        from lsncore.dem import open_moon

        return open_moon()
    except (ValueError, FileNotFoundError, RuntimeError) as missing:
        pytest.skip(f"elevation products are not on this machine: {missing}")


@pytest.mark.parametrize("lat, lon", [(26.1, 3.6), (-89.80531, 205.76891)])
def test_a_30_day_custom_package_is_written_within_half_a_minute(tmp_path, capsys, lat, lon):
    """Best of three on an otherwise idle machine; the first run under the limit settles it."""
    terrain = _real_terrain()
    try:
        terrain.for_site(lat, lon, 300_000.0)
    except ValueError as missing:
        pytest.skip(f"no elevation product for this site on this machine: {missing}")
    runs = []
    for k in range(3):
        t0 = time.perf_counter()
        code = cli.main(["custom", "--lat", str(lat), "--lon", str(lon), "--start", "2026-11-14", "--out", str(tmp_path / f"run{k}")])
        runs.append(time.perf_counter() - t0)
        assert code == 0
        if runs[-1] <= MAX_RUNTIME_CUSTOM_S:
            break
    capsys.readouterr()
    assert min(runs) <= MAX_RUNTIME_CUSTOM_S, f"runs {[round(r, 1) for r in runs]} s"
    manifest, index = _site_manifest(tmp_path / f"run{len(runs) - 1}")
    assert manifest["status"] == "ok" and manifest["synthetic"] is False
    assert manifest["timeline"]["time"]["count"] == 721 and "uncertainty" in manifest["timeline"]
    assert sorted(p["kind"] for p in index["packages"]) == ["direction_table", "site"]
