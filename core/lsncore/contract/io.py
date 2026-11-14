"""Writing and reading packages (manifest.json + raw little-endian arrays)."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .. import SCIENCE_VERSION, __version__

CONTRACT_NAME = "lsn-package"
CONTRACT_VERSION = "0.3"
CONTRACT_MAJOR = 0

_ID_PREFIX = {"site": "site", "direction_table": "dirtab"}
_EXTENSION = {"<f4": "f4", "<f8": "f8", "<i4": "i4", "|u1": "u1"}


def contract_dir() -> Path:
    """Directory that holds SPEC.md, schemas/ and sample/.

    Taken from LSN_CONTRACT_DIR if set, otherwise found relative to the repository
    checkout this module lives in (core/lsncore/contract/ -> docs/contract/).
    """
    env = os.environ.get("LSN_CONTRACT_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3] / "docs" / "contract"


def contract_header() -> dict[str, str]:
    return {"name": CONTRACT_NAME, "version": CONTRACT_VERSION}


def canonical_json(obj: Any) -> bytes:
    """Deterministic JSON used for hashing: sorted keys, no whitespace, ASCII, no NaN."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_package_id(kind: str, synthetic: bool, request: dict, inputs: dict) -> str:
    """Identity of a package: a digest of what was asked and of what it was computed from.

    Creation time and timings are not part of it, so the same request on the same data
    with the same science version always gets the same id.
    """
    payload = {
        "contract_major": CONTRACT_MAJOR,
        "kind": kind,
        "synthetic": bool(synthetic),
        "request": request,
        "inputs": inputs,
    }
    return f"{_ID_PREFIX[kind]}-{_sha256(canonical_json(payload))[:16]}"


def compute_content_sha256(manifest: dict) -> str:
    """Digest of everything a package states, including the digests of its arrays.

    The volatile 'provenance' block and the digest field itself are excluded.
    """
    body = {k: v for k, v in manifest.items() if k not in ("content_sha256", "provenance")}
    return _sha256(canonical_json(body))


def format_utc(when: _dt.datetime) -> str:
    """ISO 8601 UTC string with millisecond resolution and a Z suffix."""
    when = when.astimezone(_dt.timezone.utc)
    return when.strftime("%Y-%m-%dT%H:%M:%S.") + f"{when.microsecond // 1000:03d}Z"


def _git(args: list[str]) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def build_provenance(scenario_id: str | None = None, timings_s: dict | None = None) -> dict:
    """Record of how the package was produced. No host name, user name or absolute path."""
    commit = _git(["rev-parse", "HEAD"])
    status = _git(["status", "--porcelain"])
    return {
        "created_utc": format_utc(_dt.datetime.now(_dt.timezone.utc)),
        "scenario_id": scenario_id,
        "timings_s": {k: round(float(v), 6) for k, v in (timings_s or {}).items()},
        "software": {
            "core_version": __version__,
            "science_version": str(SCIENCE_VERSION),
            "git_commit": commit,
            "git_dirty": None if status is None else bool(status),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "os": f"{platform.system()} {platform.release()}",
            "byteorder": sys.byteorder,
        },
    }


def write_json(path: Path, obj: Any) -> None:
    text = json.dumps(obj, indent=2, ensure_ascii=True, allow_nan=False)
    path.write_text(text + "\n", encoding="ascii", newline="\n")


class PackageWriter:
    """Collects arrays and writes one package directory.

    Usage: register arrays with :meth:`array` (each call returns the array reference to
    put in the manifest), then call :meth:`write` with the manifest body.
    """

    def __init__(self, kind: str):
        if kind not in _ID_PREFIX:
            raise ValueError(f"unknown package kind: {kind}")
        self.kind = kind
        self._blobs: dict[str, bytes] = {}

    def array(self, name: str, values: np.ndarray, dtype: str, unit: str, method: str) -> dict:
        if dtype not in _EXTENSION:
            raise ValueError(f"dtype not allowed by the contract: {dtype}")
        arr = np.ascontiguousarray(np.asarray(values).astype(np.dtype(dtype), copy=False))
        file = f"{name}.{_EXTENSION[dtype]}"
        if file in self._blobs:
            raise ValueError(f"array registered twice: {file}")
        data = arr.tobytes(order="C")
        self._blobs[file] = data
        nan_count = int(np.isnan(arr).sum()) if arr.dtype.kind == "f" else 0
        return {
            "file": file,
            "dtype": dtype,
            "shape": [int(n) for n in arr.shape],
            "unit": unit,
            "method": method,
            "sha256": _sha256(data),
            "nan_count": nan_count,
        }

    def write(
        self,
        root: Path,
        group: str | None,
        *,
        status: str,
        synthetic: bool,
        synthetic_notice: str | None,
        warnings: list[str],
        request: dict,
        inputs: dict,
        methods: dict,
        sections: dict,
        scenario_id: str | None = None,
        timings_s: dict | None = None,
    ) -> Path:
        """Write the package under root/<kind>/[group/]<package_id>/ and return that path."""
        package_id = compute_package_id(self.kind, synthetic, request, inputs)
        manifest: dict[str, Any] = {
            "contract": contract_header(),
            "kind": self.kind,
            "package_id": package_id,
            "content_sha256": "",
            "status": status,
            "synthetic": bool(synthetic),
        }
        if synthetic:
            manifest["synthetic_notice"] = synthetic_notice or "SYNTHETIC DATA"
        manifest["warnings"] = list(warnings)
        manifest["request"] = request
        manifest["inputs"] = inputs
        manifest["methods"] = methods
        manifest.update(sections)
        manifest["content_sha256"] = compute_content_sha256(manifest)
        manifest["provenance"] = build_provenance(scenario_id, timings_s)

        parent = Path(root) / self.kind
        if group:
            parent = parent / group
        final = parent / package_id
        tmp = parent / f".tmp-{package_id}-{os.getpid()}"
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        for file, data in self._blobs.items():
            (tmp / file).write_bytes(data)
        write_json(tmp / "manifest.json", manifest)
        if final.exists():
            shutil.rmtree(final)
        tmp.rename(final)
        return final


@dataclass
class Package:
    """A package read from disk."""

    path: Path
    manifest: dict

    @property
    def kind(self) -> str:
        return self.manifest["kind"]

    @property
    def package_id(self) -> str:
        return self.manifest["package_id"]

    def array(self, ref: dict) -> np.ndarray:
        """Load the array described by an array reference of this package."""
        data = np.fromfile(self.path / ref["file"], dtype=np.dtype(ref["dtype"]))
        return data.reshape(ref["shape"])


def read_package(path: Path | str) -> Package:
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    return Package(path=path, manifest=manifest)


def write_index(root: Path | str, scenario_id: str | None = None) -> Path:
    """Scan a package root and write index.json listing every package found in it."""
    root = Path(root)
    entries = []
    for manifest_path in sorted(root.glob("**/manifest.json")):
        if any(part.startswith(".tmp-") for part in manifest_path.parts):
            continue
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = {
            "kind": m["kind"],
            "package_id": m["package_id"],
            "path": manifest_path.parent.relative_to(root).as_posix(),
            "synthetic": m["synthetic"],
            "status": m["status"],
        }
        if m["kind"] == "site":
            entry.update(
                site_id=m["site"]["site_id"],
                name=m["site"]["name"],
                lat_deg=m["site"]["lat_deg"],
                lon_deg=m["site"]["lon_deg"],
                has_timeline="timeline" in m,
            )
        entries.append(entry)
    index = {
        "contract": contract_header(),
        "kind": "index",
        "generated_utc": format_utc(_dt.datetime.now(_dt.timezone.utc)),
        "scenario_id": scenario_id,
        "packages": entries,
    }
    out = root / "index.json"
    write_json(out, index)
    return out
