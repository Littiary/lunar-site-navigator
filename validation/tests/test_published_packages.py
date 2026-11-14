"""The packages published in ``packages/`` must pass the contract validator as they are.

Runs offline and needs neither terrain data nor kernels: it only reads the published
files. The validator applies the contract schema and checks, for every array, that the
file exists with the stated size, checksum and NaN count, and that the package id and
content digest can be recomputed.
"""

import json
from pathlib import Path

from lsncore.contract import validate_document, validate_package

ROOT = Path(__file__).resolve().parents[2] / "packages"


def _package_dirs() -> list:
    return sorted(path.parent for path in ROOT.rglob("manifest.json"))


def test_index_is_valid_and_lists_exactly_the_published_packages():
    index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
    validate_document(index)
    listed = sorted(entry["path"] for entry in index["packages"])
    present = sorted(path.relative_to(ROOT).as_posix() for path in _package_dirs())
    assert listed == present
    assert sum(entry["kind"] == "direction_table" for entry in index["packages"]) == 1
    assert sum(entry["kind"] == "site" for entry in index["packages"]) >= 3


def test_every_published_package_passes_the_contract_validator():
    directories = _package_dirs()
    assert len(directories) >= 4
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


def test_nothing_but_packages_index_and_readme_is_published():
    top = sorted(path.name for path in ROOT.iterdir())
    assert top == ["README.md", "direction_table", "index.json", "site"]
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
