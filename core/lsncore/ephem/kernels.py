"""SPICE kernel set: definition, download, integrity check and loading.

The kernels are NAIF generic kernels. They are never committed; this module
downloads them unmodified and records what was downloaded in
``core/lsncore/ephem/kernel_manifest.json`` (file name, URL, size, SHA-256, retrieval
time). Loading checks every file against that manifest, so a result can always
be traced to an exact kernel set.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import spiceypy as spice

NAIF_ROOT = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/"

# Generic client name; no personal contact data is sent.
USER_AGENT = "lunar-ephemeris-tool/0.1 (python-urllib; kernel download)"

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = Path(__file__).resolve().parent / "kernel_manifest.json"


@dataclass(frozen=True)
class Kernel:
    name: str
    subdir: str
    kind: str
    role: str

    @property
    def url(self) -> str:
        return f"{NAIF_ROOT}{self.subdir}/{self.name}"


# Load order matters: later kernels take precedence, and the binary lunar PCK
# must override nothing in the text PCK that we use (it only provides the
# MOON_PA orientation, which the text PCK does not define).
KERNEL_SET: tuple[Kernel, ...] = (
    Kernel("naif0012.tls", "lsk", "LSK", "Leap seconds; UTC <-> TDB conversion"),
    Kernel("pck00011.tpc", "pck", "text PCK", "Body radii (Moon, Sun, Earth)"),
    Kernel("de440s.bsp", "spk/planets", "SPK", "Positions of the Sun, the Earth and the Moon (JPL DE440)"),
    Kernel("moon_pa_de440_200625.bpc", "pck", "binary PCK", "Orientation of the lunar principal-axis frame (DE440)"),
    Kernel(
        "moon_de440_250416.tf",
        "fk/satellites",
        "FK",
        "Defines MOON_PA_DE440 and MOON_ME_DE440_ME421 (alias MOON_ME): the "
        "mean-Earth/polar-axis frame aligned with the DE421 mean-Earth frame",
    ),
)


def kernel_dir() -> Path:
    """Directory holding the downloaded kernels (not under version control)."""
    override = os.environ.get("LSN_KERNEL_DIR")
    return Path(override) if override else REPO_ROOT / "data" / "kernels"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(force: bool = False) -> dict:
    """Download the kernel set and write the manifest. Returns the manifest."""
    target = kernel_dir()
    target.mkdir(parents=True, exist_ok=True)
    previous = read_manifest() if MANIFEST_PATH.exists() else {"kernels": []}
    known = {entry["name"]: entry for entry in previous["kernels"]}
    entries = []
    for kernel in KERNEL_SET:
        path = target / kernel.name
        entry = known.get(kernel.name)
        if force or not path.exists() or entry is None or _sha256(path) != entry["sha256"]:
            request = urllib.request.Request(kernel.url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=300) as response:
                payload = response.read()
                last_modified = response.headers.get("Last-Modified")
            path.write_bytes(payload)  # binary write: text kernels stay byte-identical
            entry = {
                "name": kernel.name,
                "kind": kernel.kind,
                "role": kernel.role,
                "url": kernel.url,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "server_last_modified": last_modified,
                "retrieved_utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        entries.append(entry)
    manifest = {
        "description": "NAIF generic kernels used by the ephemeris stream, in load order. "
        "Written by lsncore.ephem.fetch_kernels; do not edit by hand.",
        "source_root": NAIF_ROOT,
        "kernels": entries,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def read_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


_LOADED = False


def load(verify: bool = True) -> None:
    """Load the kernel set into the SPICE kernel pool (idempotent).

    With ``verify`` every file is checked against the SHA-256 in the manifest.
    """
    global _LOADED
    if _LOADED:
        return
    manifest = {entry["name"]: entry for entry in read_manifest()["kernels"]}
    directory = kernel_dir()
    for kernel in KERNEL_SET:
        path = directory / kernel.name
        if not path.exists():
            raise FileNotFoundError(
                f"Kernel {kernel.name} not found in {directory}. Run: python -m lsncore.ephem.fetch_kernels"
            )
        if verify and _sha256(path) != manifest[kernel.name]["sha256"]:
            raise RuntimeError(f"Kernel {kernel.name} does not match the manifest checksum")
        spice.furnsh(str(path))
    _LOADED = True


def unload() -> None:
    global _LOADED
    spice.kclear()
    _LOADED = False


def kernel_set_id() -> str:
    """Short identifier of the kernel set: first 12 hex digits of the hash of all file hashes."""
    manifest = {entry["name"]: entry for entry in read_manifest()["kernels"]}
    joined = "".join(manifest[kernel.name]["sha256"] for kernel in KERNEL_SET)
    return hashlib.sha256(joined.encode("ascii")).hexdigest()[:12]
