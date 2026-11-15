"""What a package records about the elevation products it was computed from.

`inputs.dem.layers` is part of the package id (SPEC 3.4), so every layer must identify
the bytes it stands for. A review of the published packages (15 November 2026) found two
gaps: a product made of several data files (the six tiles of SLDEM2015_256) carried no
checksum and no source address, so the terrain of 13 site packages was not bound to their
ids; and a product that states no version of its own (the 5 m site rasters) was recorded
with the version "None".

Fixed before the first run:
* a layer of several data files carries, in `files`, the name, checksum and source address
  of each, and in `sha256` the SHA-256 of the lines "<name>:<sha256>\\n" of its data files in
  the order of their names;
* no layer has the version "None" or an empty one; a product without a version of its own
  is recorded as "file of <date>", the date its source reports for the data file.
"""

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pytest

from lsncore.contract import validate_package
from lsncore.pipeline import run_scenario
from lsncore.scenario import single_site_scenario

HEX64 = re.compile(r"^[0-9a-f]{64}$")
REPO = Path(__file__).resolve().parents[2]


def _combined(files):
    lines = "".join(f"{f['name']}:{f['sha256']}\n" for f in sorted(files, key=lambda f: f["name"]))
    return hashlib.sha256(lines.encode("ascii")).hexdigest()


@pytest.fixture(scope="module")
def two_tiles(tmp_path_factory):
    """A synthetic mosaic of two tiles in the format of the LOLA cylindrical products."""
    pytest.importorskip("lsn_data")
    from lsn_data import pyramid
    from lsn_data import synthetic_cyl as sc
    from lsn_data.cylindrical import CylDEM, CylMosaic
    from lsn_data.moon import MoonTerrain

    out = tmp_path_factory.mktemp("tiles")
    labels = [sc.write_tile(out, "SYNTH_CYL_8_WEST", 8.0, 30, 90, 0, 180, dtype="<i2"), sc.write_tile(out, "SYNTH_CYL_8_EAST", 8.0, 30, 90, 180, 360, dtype="<i2")]
    for label in labels:
        pyramid.build(CylDEM(label), out / "pyr" / label.stem, levels=4, log=lambda *a: None)
    tiles = [CylDEM(label, pyramid_dir=out / "pyr" / label.stem) for label in labels]
    return MoonTerrain([], [CylMosaic(tiles, product_id="SYNTH_CYL_8")]), labels


def test_a_mosaic_of_several_files_is_identified_by_all_of_them(two_tiles, tmp_path):
    from lsncore.dem import MoonTerrainAdapter

    moon, labels = two_tiles
    (layer,) = MoonTerrainAdapter(moon).describe()["layers"]
    names = sorted(label.with_suffix(".img").name for label in labels)
    assert [f["name"] for f in layer["files"]] == names
    for record, name in zip(layer["files"], names):
        assert record["sha256"] == hashlib.sha256((labels[0].parent / name).read_bytes()).hexdigest()
    assert HEX64.match(layer["sha256"]) and layer["sha256"] == _combined(layer["files"])

    # it reaches the package, and the package id depends on the bytes of every tile
    terrain = MoonTerrainAdapter(moon)
    scenario = single_site_scenario("tile-site", "Synthetic tile site", 60.0, 90.0, dem_set_id="any", synthetic=True, heights_m=[2.0], azimuth_step_deg=5.0, max_range_m=30_000.0)
    (path,) = run_scenario(scenario, tmp_path / "a", terrain, True)
    manifest = validate_package(path)
    (written,) = manifest["inputs"]["dem"]["layers"]
    assert written["sha256"] == layer["sha256"] and [f["sha256"] for f in written["files"]] == [f["sha256"] for f in layer["files"]]

    # the same mosaic with one sample of the other tile changed (a copy: the tiles above are open)
    import shutil

    from lsn_data.cylindrical import CylDEM, CylMosaic
    from lsn_data.moon import MoonTerrain

    copy = tmp_path / "changed"
    shutil.copytree(labels[0].parent, copy)
    other = copy / labels[1].with_suffix(".img").name  # the tile the site does not lie on
    data = bytearray(other.read_bytes())
    data[-2:] = (np.frombuffer(bytes(data[-2:]), dtype="<i2") + 1).astype("<i2").tobytes()
    other.write_bytes(bytes(data))
    tiles = [CylDEM(copy / label.name, pyramid_dir=copy / "pyr" / label.stem) for label in labels]
    changed = MoonTerrainAdapter(MoonTerrain([], [CylMosaic(tiles, product_id="SYNTH_CYL_8")]))
    (path2,) = run_scenario(scenario, tmp_path / "b", changed, True)
    second = validate_package(path2)
    assert second["package_id"] != manifest["package_id"]
    before = {f["name"]: f["sha256"] for f in written["files"]}
    after = {f["name"]: f["sha256"] for f in second["inputs"]["dem"]["layers"][0]["files"]}
    assert after[labels[0].with_suffix(".img").name] == before[labels[0].with_suffix(".img").name]  # the tile of the site is the same
    assert after[other.name] != before[other.name]


@pytest.fixture(scope="module")
def installed():
    lsn_data = pytest.importorskip("lsn_data")
    from lsncore.dem import open_lola, open_moon

    try:
        return lsn_data, open_moon(near_field=True), open_lola(near_field=True)
    except (ValueError, FileNotFoundError, RuntimeError) as missing:
        pytest.skip(f"elevation products are not on this machine: {missing}")


def test_every_installed_layer_names_its_bytes_and_a_version(installed):
    lsn_data, moon, polar = installed
    for adapter in (moon, polar):
        described = adapter.describe()
        assert "@None" not in described["dem_set_id"] and "@+" not in described["dem_set_id"] and not described["dem_set_id"].endswith("@")
        for layer in described["layers"]:
            assert layer["version"] not in ("None", "", "null") and layer["version"] == layer["version"].strip(), layer["product_id"]
            assert HEX64.match(layer["sha256"] or ""), layer["product_id"]
            assert layer["source_url"].startswith("https://"), layer["product_id"]
            if "files" in layer:
                assert len(layer["files"]) >= 2 and layer["sha256"] == _combined(layer["files"])
                assert all(HEX64.match(f["sha256"]) and f["source_url"].startswith("https://") for f in layer["files"])


def test_the_tiles_of_the_global_mosaic_are_those_of_the_data_manifest(installed):
    lsn_data, moon, _ = installed
    layers = {layer["product_id"]: layer for layer in moon.describe()["layers"]}
    if "SLDEM2015_256" not in layers:
        pytest.skip("SLDEM2015_256 is not on this machine")
    recorded = json.loads((REPO / "data" / "manifest" / "manifest.json").read_text(encoding="utf-8"))["files"]
    tiles = {Path(key).name: entry for key, entry in recorded.items() if "SLDEM2015_256_" in key and entry.get("role") == "data"}
    files = layers["SLDEM2015_256"]["files"]
    assert len(files) == 6 == len(tiles)
    for record in files:
        assert record["sha256"] == tiles[record["name"]]["sha256"] and record["source_url"] == tiles[record["name"]]["source_url"]
    assert layers["SLDEM2015_256"]["source_url"] == "https://imbrium.mit.edu/DATA/SLDEM2015/TILES/FLOAT_IMG/"


def test_a_site_raster_without_a_version_of_its_own_is_dated_by_its_source_file(installed):
    from email.utils import parsedate_to_datetime

    lsn_data, moon, polar = installed
    recorded = json.loads((REPO / "data" / "manifest" / "manifest.json").read_text(encoding="utf-8"))["files"]
    seen = 0
    for adapter in (moon, polar):
        for layer in adapter.describe()["layers"]:
            if not layer["product_id"].startswith("LOLA5MPP_"):
                continue
            entry = next(e for e in recorded.values() if e.get("product_id") == layer["product_id"] and e.get("role") == "data")
            assert entry["product_version"] is None  # the product states none: the reason for this rule
            date = parsedate_to_datetime(entry["http_last_modified"]).date().isoformat()
            assert layer["version"] == f"file of {date}"
            seen += 1
    if not seen:
        pytest.skip("no 5 m site raster is open on this machine")
