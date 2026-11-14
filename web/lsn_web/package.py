"""Read a site package (contract 0.x) with the Python standard library only.

Every array is checked against its manifest entry (file size and SHA-256) before it is
used, so a chart is drawn only from the exact bytes the core wrote.

Any 0.x package is accepted (SPEC section 8: minor versions are additive). Fields added in
later minor versions are optional to this reader: whatever is absent is not shown.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path

CONTRACT_NAME = "lsn-package"
SUPPORTED_MAJOR = "0"

# dtype string in the manifest -> (struct format character, item size in bytes)
DTYPES = {"<f4": ("f", 4), "<f8": ("d", 8), "<i4": ("i", 4), "|u1": ("B", 1)}


class PackageError(Exception):
    """The package cannot be read safely."""


@dataclass(frozen=True)
class Array:
    values: list
    shape: tuple

    def row(self, index: int) -> list:
        """Row ``index`` of a two-dimensional array (C order)."""
        width = self.shape[-1]
        return self.values[index * width:(index + 1) * width]


@dataclass(frozen=True)
class SitePackage:
    path: Path
    manifest: dict

    @property
    def package_id(self) -> str:
        return self.manifest["package_id"]

    @property
    def contract_version(self) -> str:
        return str(self.manifest["contract"]["version"])

    @property
    def synthetic(self) -> bool:
        return bool(self.manifest.get("synthetic"))

    @property
    def timeline(self) -> dict | None:
        return self.manifest.get("timeline")

    def method_status(self, method_id: str) -> str:
        card = self.manifest.get("methods", {}).get(method_id, {})
        return card.get("validation", {}).get("status", "unknown")

    def array(self, ref: dict) -> Array:
        """Read the array described by ``ref`` and check its size and digest."""
        if ref["dtype"] not in DTYPES:
            raise PackageError(f"{ref['file']}: unsupported dtype {ref['dtype']}")
        code, size = DTYPES[ref["dtype"]]
        shape = tuple(int(n) for n in ref["shape"])
        count = math.prod(shape)
        data = (self.path / ref["file"]).read_bytes()
        if len(data) != count * size:
            raise PackageError(f"{ref['file']}: {len(data)} bytes, expected {count * size}")
        digest = hashlib.sha256(data).hexdigest()
        if digest != ref["sha256"]:
            raise PackageError(f"{ref['file']}: SHA-256 {digest} differs from the manifest")
        return Array(list(struct.unpack(f"<{count}{code}", data)), shape)


def array_refs(document) -> list[dict]:
    """Every array reference in a manifest (objects with file, dtype, shape and sha256)."""
    found = []
    if isinstance(document, dict):
        if {"file", "dtype", "shape", "sha256"} <= document.keys():
            found.append(document)
        for value in document.values():
            found += array_refs(value)
    elif isinstance(document, list):
        for value in document:
            found += array_refs(value)
    return found


def load_index(path: str | Path) -> list[SitePackage]:
    """The site packages listed in an ``index.json``, in the order of the index."""
    path = Path(path)
    try:
        index = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PackageError(f"{path}: cannot read the index ({error})") from error
    if index.get("kind") != "index":
        raise PackageError(f"{path}: kind is {index.get('kind')!r}, expected 'index'")
    _check_contract(path, index.get("contract", {}))
    return [load_site_package(path.parent / entry["path"]) for entry in index["packages"] if entry["kind"] == "site"]


def load_packages(paths: list[str]) -> list[SitePackage]:
    """Site package directories and/or index.json files, in the order given."""
    sites = []
    for item in paths:
        target = Path(item)
        sites += load_index(target) if target.is_file() else [load_site_package(target)]
    return sites


def _check_contract(path: Path, contract: dict) -> None:
    if contract.get("name") != CONTRACT_NAME:
        raise PackageError(f"{path}: not an {CONTRACT_NAME} document")
    major = str(contract.get("version", "")).split(".")[0]
    if major != SUPPORTED_MAJOR:
        raise PackageError(
            f"{path}: contract version {contract.get('version')}; this reader supports {SUPPORTED_MAJOR}.x only"
        )


def load_site_package(path: str | Path) -> SitePackage:
    """Open the site package in directory ``path``."""
    path = Path(path)
    try:
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PackageError(f"{path}: cannot read manifest.json ({error})") from error
    _check_contract(path, manifest.get("contract", {}))
    if manifest.get("kind") != "site":
        raise PackageError(f"{path}: kind is {manifest.get('kind')!r}, expected 'site'")
    if path.name != manifest.get("package_id"):
        raise PackageError(f"{path}: directory name differs from package_id {manifest.get('package_id')}")
    return SitePackage(path, manifest)
