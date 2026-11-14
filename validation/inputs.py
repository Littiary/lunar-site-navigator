"""Downloaded inputs of the validation scripts: where they live and how they are fetched.

Nothing that is downloaded lives inside a checkout of the repository. Every input sits
under the data root (``LSN_DATA_ROOT``; default ``C:\\lsn-data`` on Windows and
``~/lsn-data`` elsewhere, the rule of ``lsn_data.paths.data_root``)::

    <root>/raw/lola/...        LOLA elevation products        python -m lsn_data fetch
    <root>/kernels/            SPICE kernels                  python -m lsncore.ephem.fetch_kernels
    <root>/validation/pgda/    published illumination maps    python -m validation.pgda.fetch
    <root>/validation/lro/     LROC browse image              python -m validation.lro_images.fetch

Each folder can be moved on its own with ``LSN_KERNEL_DIR``, ``LSN_PGDA_DIR`` and
``LSN_LRO_DIR``. The committed record of each download (``files.json`` next to the fetch
script) holds URL, size, SHA-256 and retrieval time. It is the reference: a file that is
present and matches its record is not downloaded again, a download that does not match
its record is refused, and the record is not rewritten when the bytes match, so fetching
into a fresh clone leaves the working tree clean.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import urllib.request
from pathlib import Path

from lsncore.ephem import kernels

# Generic client name; no personal contact data is sent.
USER_AGENT = "lunar-validation-fetch/0.1 (python-urllib; one file at a time, cached)"


def input_dir(name: str, env_var: str) -> Path:
    """Folder of one group of downloaded inputs: ``env_var`` if set, else ``validation/<name>`` under the data root."""
    override = os.environ.get(env_var)
    return Path(override) if override else kernels.data_root() / "validation" / name


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc(timestamp: float) -> str:
    return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_file(url: str, path: Path, record: dict | None, update: bool = False) -> tuple:
    """Make sure ``path`` holds the file at ``url``. Returns its record and what was done.

    ``record`` is the committed entry for this file, or ``None`` if there is none yet.
    """
    if path.exists() and record is not None and sha256(path) == record["sha256"]:
        return record, "cached"
    if path.exists() and record is None:
        # Present before any record existed: record the file as it is, with its own modification time.
        return {"name": path.name, "url": url, "bytes": path.stat().st_size, "sha256": sha256(path), "server_last_modified": None, "retrieved_utc": _utc(path.stat().st_mtime)}, "recorded"
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=600) as response, partial.open("wb") as handle:
        last_modified = response.headers.get("Last-Modified")
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            handle.write(chunk)
    digest = sha256(partial)
    if record is not None and digest != record["sha256"] and not update:
        partial.unlink()
        raise RuntimeError(
            f"{path.name}: the file at {url} (sha256 {digest}) is not the recorded one (sha256 {record['sha256']}, retrieved {record['retrieved_utc']}). "
            "Nothing was kept. The stored results belong to the recorded file; pass --update only to record a new file on purpose."
        )
    partial.replace(path)
    if record is not None and digest == record["sha256"]:
        return record, "fetched"  # byte-identical to the recorded file: the record stays as it is
    return {"name": path.name, "url": url, "bytes": path.stat().st_size, "sha256": digest, "server_last_modified": last_modified, "retrieved_utc": _utc(path.stat().st_mtime)}, "fetched and recorded"


def read_records(manifest_path: Path) -> dict:
    """Committed records by file name; empty if there is no manifest yet."""
    if not manifest_path.exists():
        return {}
    return {entry["name"]: entry for entry in json.loads(manifest_path.read_text(encoding="utf-8"))["files"]}


def write_manifest(manifest_path: Path, manifest: dict) -> bool:
    """Write the manifest only if its content changed. Returns whether it was written."""
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8")) == manifest:
        return False
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return True
