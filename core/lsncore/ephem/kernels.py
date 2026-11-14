"""SPICE kernel set: definition, download, integrity check and loading.

The kernels are NAIF generic kernels. They are never committed; this module
downloads them unmodified into a folder outside any checkout of the repository
(``kernels`` under the data root, see ``data_root``) and compares each file with
``core/lsncore/ephem/kernel_manifest.json`` (file name, URL, size, SHA-256, retrieval
time). The committed manifest is the record of the kernel set: a download that does
not match it is refused, and loading checks every file against it, so a result can
always be traced to an exact kernel set.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import spiceypy as spice

NAIF_ROOT = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/"

# Generic client name; no personal contact data is sent.
USER_AGENT = "lunar-ephemeris-tool/0.1 (python-urllib; kernel download)"

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = Path(__file__).resolve().parent / "kernel_manifest.json"

DATA_ROOT_ENV = "LSN_DATA_ROOT"
KERNEL_DIR_ENV = "LSN_KERNEL_DIR"
FETCH_COMMAND = "python -m lsncore.ephem.fetch_kernels"
MANIFEST_DESCRIPTION = "NAIF generic kernels used by the ephemeris stream, in load order. Written by lsncore.ephem.fetch_kernels; do not edit by hand."


class KernelsMissing(FileNotFoundError):
    """A kernel of the set has not been downloaded. The tests turn this into a skip."""


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


# Optional second group, needed only for ground-station geometry (direct-to-Earth windows):
# the orientation of the Earth and the positions of the Deep Space Network stations. It is
# kept apart from KERNEL_SET so that the identifier of the base set, which is part of
# every package id, does not change. Load order: the long-term Earth orientation first,
# the recent high-precision one second, so that the latter wins where both have data.
STATION_KERNEL_SET: tuple[Kernel, ...] = (
    Kernel("earth_1962_260806_2126_combined.bpc", "pck", "binary PCK", "Orientation of the Earth (ITRF93), 1962 to 2126; measured to August 2026, predicted after"),
    Kernel("earth_000101_270208_261113.bpc", "pck", "binary PCK", "Orientation of the Earth (ITRF93), high precision, 2000 to 8 February 2027; measured to 13 November 2026"),
    Kernel("earthstns_itrf93_260814.bsp", "spk/stations", "SPK", "Positions of the Deep Space Network stations in ITRF93"),
    Kernel("earth_topo_260814.tf", "fk/stations", "FK", "Topocentric frames of the Deep Space Network stations"),
)


def data_root() -> Path:
    """Root of all downloaded inputs, outside any checkout of the repository.

    ``LSN_DATA_ROOT`` if set, otherwise ``C:\\lsn-data`` on Windows and ``~/lsn-data``
    elsewhere. This is the rule of the data stream (``lsn_data.paths.data_root``); it is
    repeated here because the core does not depend on that package, and a test checks
    that the two agree.
    """
    override = os.environ.get(DATA_ROOT_ENV)
    if override:
        return Path(override)
    return Path("C:/lsn-data") if os.name == "nt" else Path.home() / "lsn-data"


def kernel_dir() -> Path:
    """Directory holding the downloaded kernels: ``LSN_KERNEL_DIR`` if set, otherwise ``kernels`` under the data root."""
    override = os.environ.get(KERNEL_DIR_ENV)
    return Path(override) if override else data_root() / "kernels"


def missing(stations: bool = False) -> list:
    """Names of the kernels of the base set (and of the station group) that are not in ``kernel_dir()``."""
    directory = kernel_dir()
    group = KERNEL_SET + (STATION_KERNEL_SET if stations else ())
    return [kernel.name for kernel in group if not (directory / kernel.name).exists()]


def _missing_message(name: str, directory: Path) -> str:
    return f"SPICE kernel {name} not found in {directory}. Download the kernel set with: {FETCH_COMMAND} (see docs/setup.md)"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fetch_group(group: tuple, known: dict, force: bool, update_manifest: bool, unavailable: list | None = None) -> list:
    """Fetch one group. With ``unavailable`` given, a file the server no longer offers is noted there instead of stopping the run."""
    target = kernel_dir()
    target.mkdir(parents=True, exist_ok=True)
    entries = []
    for kernel in group:
        path = target / kernel.name
        entry = known.get(kernel.name)
        if force or not path.exists() or entry is None or _sha256(path) != entry["sha256"]:
            request = urllib.request.Request(kernel.url, headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(request, timeout=300) as response:
                    payload = response.read()
                    last_modified = response.headers.get("Last-Modified")
            except (urllib.error.URLError, OSError) as error:
                if unavailable is None:
                    raise RuntimeError(f"{kernel.name} could not be downloaded from {kernel.url}: {error}") from error
                unavailable.append({"name": kernel.name, "url": kernel.url, "error": str(error)})
                if entry is not None:
                    entries.append(entry)  # the record of the kernel set stays as it is
                continue
            digest = hashlib.sha256(payload).hexdigest()
            if entry is not None and digest != entry["sha256"] and not update_manifest:
                raise RuntimeError(
                    f"{kernel.name}: the file at {kernel.url} (sha256 {digest}) is not the recorded one (sha256 {entry['sha256']}, "
                    f"retrieved {entry['retrieved_utc']}). Nothing was written. Results computed with a different file are not those "
                    "of the recorded kernel set; pass --update-manifest only to record a new kernel set on purpose."
                )
            path.write_bytes(payload)  # binary write: text kernels stay byte-identical
            if entry is None or digest != entry["sha256"]:
                entry = {
                    "name": kernel.name,
                    "kind": kernel.kind,
                    "role": kernel.role,
                    "url": kernel.url,
                    "bytes": len(payload),
                    "sha256": digest,
                    "server_last_modified": last_modified,
                    "retrieved_utc": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            # Otherwise the download is byte-identical to the recorded file: the record stays as it is.
        entries.append(entry)
    return entries


def fetch(force: bool = False, stations: bool = True, update_manifest: bool = False, unavailable: list | None = None) -> dict:
    """Download the kernels that are absent into ``kernel_dir()`` and check them against the manifest.

    The committed manifest is not changed when every file matches its record, so a fresh
    clone stays clean. A file that differs from its record is refused unless
    ``update_manifest`` is set; a kernel without a record is recorded. Returns the manifest.

    A kernel of the base set that cannot be downloaded is an error. A kernel of the
    optional station group that the server no longer offers is appended to ``unavailable``
    (if given) and the run goes on: NAIF replaces the high-precision Earth orientation
    file at least twice per week and keeps only the current one.
    """
    previous = read_manifest() if MANIFEST_PATH.exists() else {}
    known = {entry["name"]: entry for entry in previous.get("kernels", []) + previous.get("station_kernels", [])}
    manifest = {
        "description": MANIFEST_DESCRIPTION,
        "source_root": NAIF_ROOT,
        "kernels": _fetch_group(KERNEL_SET, known, force, update_manifest),
        "station_kernels": _fetch_group(STATION_KERNEL_SET, known, force, update_manifest, unavailable) if stations else previous.get("station_kernels", []),
    }
    if manifest != previous:
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
            raise KernelsMissing(_missing_message(kernel.name, directory))
        if verify and _sha256(path) != manifest[kernel.name]["sha256"]:
            raise RuntimeError(f"Kernel {kernel.name} in {directory} does not match the manifest checksum")
        spice.furnsh(str(path))
    _LOADED = True


_STATIONS_LOADED = False


def stations_available() -> bool:
    """True if the optional station kernels have been downloaded."""
    directory = kernel_dir()
    listed = {entry["name"] for entry in read_manifest().get("station_kernels", [])}
    return all(kernel.name in listed and (directory / kernel.name).exists() for kernel in STATION_KERNEL_SET)


def load_stations(verify: bool = True) -> None:
    """Load the base set and the station group (idempotent)."""
    global _STATIONS_LOADED
    load(verify)
    if _STATIONS_LOADED:
        return
    manifest = {entry["name"]: entry for entry in read_manifest().get("station_kernels", [])}
    directory = kernel_dir()
    for kernel in STATION_KERNEL_SET:
        path = directory / kernel.name
        if not path.exists() or kernel.name not in manifest:
            raise KernelsMissing(_missing_message(kernel.name, directory))
        if verify and _sha256(path) != manifest[kernel.name]["sha256"]:
            raise RuntimeError(f"Kernel {kernel.name} in {directory} does not match the manifest checksum")
        spice.furnsh(str(path))
    _STATIONS_LOADED = True


def station_kernel_set_id() -> str:
    """Short identifier of the station kernel group."""
    manifest = {entry["name"]: entry for entry in read_manifest()["station_kernels"]}
    joined = "".join(manifest[kernel.name]["sha256"] for kernel in STATION_KERNEL_SET)
    return hashlib.sha256(joined.encode("ascii")).hexdigest()[:12]


def unload() -> None:
    global _LOADED, _STATIONS_LOADED
    spice.kclear()
    _LOADED = False
    _STATIONS_LOADED = False


def kernel_set_id() -> str:
    """Short identifier of the kernel set: first 12 hex digits of the hash of all file hashes."""
    manifest = {entry["name"]: entry for entry in read_manifest()["kernels"]}
    joined = "".join(manifest[kernel.name]["sha256"] for kernel in KERNEL_SET)
    return hashlib.sha256(joined.encode("ascii")).hexdigest()[:12]
