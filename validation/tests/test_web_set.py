"""The web set: the published packages without arrays the web view does not use.

The web set is built here from ``packages/`` into a temporary folder, as the web build
does it, and compared with the published set. Nothing is computed and neither terrain
data nor kernels are needed.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

from lsncore.contract import validate_document, validate_package
from lsncore.contract.io import write_json
from validation.web_set import build as web_set

REPO = Path(__file__).resolve().parents[2]
FULL = REPO / "packages"
WEB_CODE = REPO / "web"


@pytest.fixture(scope="module")
def web(tmp_path_factory):
    """The web set as the command builds it by default."""
    root = tmp_path_factory.mktemp("packages_web")
    return {"root": root, "sizes": web_set.build(FULL, root), "smaller": False}


@pytest.fixture(scope="module")
def smaller(tmp_path_factory):
    """The web set with --smaller. The build validates every package it writes and raises if one fails."""
    root = tmp_path_factory.mktemp("packages_web_smaller")
    return {"root": root, "sizes": web_set.build(FULL, root, smaller=True), "smaller": True}


@pytest.fixture(scope="module")
def published():
    return _manifests(FULL)


def _manifests(root: Path) -> dict:
    """Package id -> (folder, manifest) of every package under a root."""
    found = {}
    for path in sorted(root.rglob("manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        found[manifest["package_id"]] = (path.parent, manifest)
    return found


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _web_sources() -> dict:
    """The code of the web stream, without its tests and the libraries it carries: file -> text."""
    paths = [path for pattern in ("viewer/js/*.js", "viewer/*.html", "lsn_web/*.py") for path in WEB_CODE.glob(pattern)]
    return {path.relative_to(WEB_CODE).as_posix(): path.read_text(encoding="utf-8") for path in paths}


def test_every_package_of_the_web_set_passes_the_contract_validator(web):
    root = web["root"]
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    validate_document(index)
    listed = sorted(entry["path"] for entry in index["packages"])
    assert listed == sorted(path.parent.relative_to(root).as_posix() for path in root.rglob("manifest.json"))
    assert sorted(entry["kind"] for entry in index["packages"]) == ["site"] * 20 + ["site_pairs"]
    for entry in index["packages"]:
        manifest = validate_package(root / entry["path"])  # schema, every array with its checksum, package id, content digest
        assert manifest["package_id"] == entry["package_id"]
    # Nothing but the index, the manifests and the arrays the manifests name.
    files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    named = {"index.json"}
    for folder, manifest in _manifests(root).values():
        relative = folder.relative_to(root).as_posix()
        named |= {f"{relative}/manifest.json"} | {f"{relative}/{name}" for name in web_set._array_files(manifest)}
    assert files == named


def _same_numbers(built: dict, full: dict) -> set:
    """Compare every web-set manifest with the published one. Returns the method cards that are not in the web set."""
    thin = _manifests(built["root"])
    keys = web_set.left_out(built["smaller"])
    assert set(thin) == {package_id for package_id, (_, manifest) in full.items() if manifest["kind"] != "direction_table"}
    cards_gone = set()
    for package_id, (_, slim) in thin.items():
        complete = full[package_id][1]
        if complete["kind"] == "site_pairs":
            assert slim == complete
            continue
        # What the web view shows from a manifest, section by section.
        for section in ("time", "bodies", "events", "windows", "metrics", "blockers", "calendar", "height_trade", "opportunities", "uncertainty"):
            assert slim["timeline"].get(section) == complete["timeline"].get(section), (package_id, section)
        for section in ("contract", "kind", "status", "synthetic", "request", "inputs", "site", "terrain", "provenance"):
            assert slim.get(section) == complete.get(section), (package_id, section)
        for key in ("azimuth", "observer_heights_m", "default_height_index", "max_range_m", "obstacles", "obstacle_id", "terrain_source", "error_bounds", "flags"):
            assert slim["horizon"].get(key) == complete["horizon"].get(key), (package_id, key)
        # The countdowns in particular, with the instant they count from.
        countdown = lambda timeline: [metric for metric in timeline["metrics"] if metric["id"].endswith(("_time_to_set_s", "_time_to_rise_s"))]
        assert countdown(slim["timeline"]) and countdown(slim["timeline"]) == countdown(complete["timeline"])

        # The whole manifest differs in nothing but the arrays left out, cards only they referred to, the note and the digest.
        expected = json.loads(json.dumps(complete))
        left = []
        for key in keys["horizon"]:
            if expected["horizon"].pop(key, None) is not None:
                left.append(f"horizon.{key}")
        for body, series in expected["timeline"]["series"].items():
            for key in keys["series"]:
                if series.pop(key, None) is not None:
                    left.append(f"series.{body}.{key}")
        assert left, package_id
        gone = set(complete["methods"]) - set(slim["methods"])
        rest = json.dumps({key: value for key, value in slim.items() if key != "methods"})
        assert all(f'"{method_id}"' not in rest for method_id in gone)
        cards_gone |= gone
        expected["methods"] = {method_id: card for method_id, card in expected["methods"].items() if method_id not in gone}
        note = slim["warnings"][-1]
        assert slim["warnings"][:-1] == complete["warnings"]
        assert note.startswith("web subset:") and complete["package_id"] in note and complete["content_sha256"] in note and all(name in note for name in left)
        expected["warnings"] = slim["warnings"]
        expected["content_sha256"] = slim["content_sha256"]
        assert slim == expected, package_id
        assert slim["content_sha256"] != complete["content_sha256"]
    return cards_gone


def test_every_number_of_a_web_package_is_that_of_the_published_package(web, published):
    """Countdowns and other metrics, window lists, calendar, landing windows, uncertainty bands, obstacle rows,
    events and method cards: compared value for value over all twenty sites, not by sample."""
    assert _same_numbers(web, published) == set()  # no method card is lost


def test_the_smaller_set_has_the_same_numbers_and_loses_one_method_card(smaller, published):
    assert _same_numbers(smaller, published) == {"timeline.lit_fraction"}
    assert smaller["sizes"]["web_total_bytes"] == sum(path.stat().st_size for path in smaller["root"].rglob("*") if path.is_file())


@pytest.mark.parametrize("which", ["web", "smaller"])
def test_arrays_that_stay_are_the_published_files_byte_for_byte(which, request, published):
    built = request.getfixturevalue(which)
    for package_id, (folder, slim) in _manifests(built["root"]).items():
        source, complete = published[package_id]
        kept = web_set._array_files(slim)
        assert set(kept) <= set(web_set._array_files(complete))
        for name in kept:
            assert _sha256(folder / name) == _sha256(source / name), (package_id, name)
        # What the viewer fetches for a site is all there, and the terrain patches the request names.
        if slim["kind"] == "site":
            for key in web_set.READ_BY_THE_VIEWER["horizon"]:
                assert slim["horizon"][key] == complete["horizon"][key]
            for body, series in slim["timeline"]["series"].items():
                for key in web_set.READ_BY_THE_VIEWER["series"]:
                    assert series[key] == complete["timeline"]["series"][body][key]
            assert slim.get("terrain") == complete.get("terrain")


def test_what_is_left_out_is_optional_in_the_contract():
    schema = json.loads((REPO / "docs" / "contract" / "schemas" / "lsn-contract.schema.json").read_text(encoding="utf-8"))["$defs"]
    for place, block in (("horizon", "horizon_block"), ("series", "body_series")):
        keys = set(web_set.left_out(smaller=True)[place])
        assert not keys & set(schema[block]["required"])
        assert keys <= set(schema[block]["properties"])
        assert set(web_set.READ_BY_THE_VIEWER[place]) <= set(schema[block]["properties"]) and not keys & set(web_set.READ_BY_THE_VIEWER[place])


def test_what_is_left_out_is_not_used_by_the_web_code():
    sources = _web_sources()
    if not sources:
        pytest.skip("the web code is not in this checkout")
    named = lambda key: sorted(name for name, text in sources.items() if re.search(rf"\b{key}\b", text))
    # Left out by default: no file of the web code names the array at all.
    for key in web_set.LEFT_OUT["horizon"] + web_set.LEFT_OUT["series"]:
        assert named(key) == [], key
    # Left out with --smaller: named only where the ground view looks whether the manifest has it; never fetched.
    for key in web_set.CHECKED_FOR["horizon"] + web_set.CHECKED_FOR["series"]:
        assert named(key) == ["viewer/js/viewer.js"], key
    fetches = [line for text in sources.values() for line in text.splitlines() if ".array(" in line and "def array" not in line and "async array" not in line]
    assert fetches
    for line in fetches:
        assert not any(re.search(rf"\b{key}\b", line) for key in web_set.left_out(smaller=True)["horizon"] + web_set.left_out(smaller=True)["series"]), line
    # Every array the viewer is recorded to fetch is fetched somewhere.
    for key in web_set.READ_BY_THE_VIEWER["horizon"] + web_set.READ_BY_THE_VIEWER["series"]:
        assert any(re.search(rf"\b{key}\b", line) for line in fetches), key


def test_the_pages_of_the_web_stream_are_the_same_from_both_sets(web, published):
    """The evidence page and the charts, built by the code of the web stream from the published set and from the
    web set, differ in the content digest of each package and in the banner that shows the web-subset note."""
    if not (WEB_CODE / "lsn_web" / "evidence.py").exists():
        pytest.skip("the web code is not in this checkout")
    sys.path.insert(0, str(WEB_CODE))
    try:
        from lsn_web import charts, evidence
        from lsn_web.package import load_packages
    finally:
        sys.path.remove(str(WEB_CODE))
    complete = load_packages([str(FULL / "index.json")])
    slim = load_packages([str(web["root"] / "index.json")])
    assert [site.package_id for site in slim] == [site.package_id for site in complete] and len(slim) == 20

    # The arrays, through the reader of the web stream.
    for site, other in zip(slim, complete):
        h = site.manifest["horizon"]["default_height_index"]
        assert list(site.array(site.manifest["horizon"]["elevation_deg"]).row(h)) == list(other.array(other.manifest["horizon"]["elevation_deg"]).row(h))
        for body, series in site.timeline["series"].items():
            for key in ("azimuth_deg", "elevation_deg"):
                assert list(site.array(series[key]).values) == list(other.array(other.timeline["series"][body][key]).values), (site.package_id, body, key)

    digest = {site.manifest["content_sha256"]: other.manifest["content_sha256"] for site, other in zip(slim, complete)}

    def with_published_digests(text: str) -> str:
        for mine, theirs in digest.items():
            text = text.replace(mine, theirs).replace(mine[:16], theirs[:16])
        return text

    for site, other in zip(slim, complete):
        assert with_published_digests(charts.horizon_panorama(site, None)) == charts.horizon_panorama(other, None), site.package_id
    assert with_published_digests(charts.window_strip(slim, None)) == charts.window_strip(complete, None)

    card = REPO / "validation" / "card" / "validation_card.json"
    chart = re.compile(r'src="data:image/svg\+xml;base64,[^"]*"')  # the charts are compared above
    page_full = chart.sub('src="chart"', evidence.build_page(complete, card, None, chart_links=True))
    page_web = chart.sub('src="chart"', evidence.build_page(slim, card, None, chart_links=True))
    assert page_web != page_full
    lines_full = page_full.splitlines()
    lines_web = with_published_digests(page_web).splitlines()
    extra = [line for line in lines_web if "web subset:" in line]
    assert len(extra) == 20 and all(line.count("web subset:") == 1 for line in extra)
    assert [line for line in lines_web if "web subset:" not in line] == lines_full


def test_the_same_published_set_gives_the_same_web_set(web, published, tmp_path):
    for package_id, (folder, slim) in _manifests(web["root"]).items():
        if slim["kind"] != "site":
            continue
        again, _ = web_set.thin_manifest(published[package_id][1])
        write_json(tmp_path / "manifest.json", again, compact=True)
        assert (tmp_path / "manifest.json").read_bytes() == (folder / "manifest.json").read_bytes(), package_id
    index = json.loads((FULL / "index.json").read_text(encoding="utf-8"))
    assert json.loads((web["root"] / "index.json").read_text(encoding="utf-8")) == {**index, "packages": [entry for entry in index["packages"] if entry["kind"] != "direction_table"]}


def test_sizes_are_what_the_build_reports(web, smaller, published):
    for built in (web, smaller):
        sizes, root = built["sizes"], built["root"]
        assert sizes["web_total_bytes"] == sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
        thin = _manifests(root)
        left = 0
        for package_id, (folder, complete) in published.items():
            if complete["kind"] == "site":
                kept = set(web_set._array_files(thin[package_id][1]))
                left += sum((folder / name).stat().st_size for name in web_set._array_files(complete) if name not in kept)
        assert left == sizes["left_out_bytes"] > 0
        # The viewer fetches the same arrays from either set, so the first load differs only by the manifest and the index.
        for row in sizes["first_load"].values():
            assert 0 <= row["full"]["bytes"] - row["web"]["bytes"] < 0.02 * row["full"]["bytes"]
            assert row["web"]["bytes_json_gzip"] < row["web"]["bytes"]
    assert smaller["sizes"]["web_total_bytes"] < web["sizes"]["web_total_bytes"] < web["sizes"]["full_total_bytes"]
    assert smaller["sizes"]["full_total_bytes"] == web["sizes"]["full_total_bytes"]
    sent = web_set.transfer_bytes(smaller["root"])
    assert sent["bytes"] == smaller["sizes"]["web_total_bytes"] and sent["all_gzip_bytes"] < sent["json_gzip_bytes"] < sent["bytes"]
