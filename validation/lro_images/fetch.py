"""Download the LROC browse image read by the image check.

The image is not committed (7.8 MB). It is stored under ``data/cache/lro`` (or
``LSN_LRO_DIR``); ``files.json`` in this folder records its URL, size, SHA-256 and
retrieval time. A file that is already present with the recorded checksum is not
downloaded again. The URL is the one fixed in ``cases.json``.

Usage (from the repository root)::

    python -m validation.lro_images.fetch
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
BROWSE_NAME = "M146846913LC_pyr.tif"

# Generic client name; no personal contact data is sent.
USER_AGENT = "lunar-validation-fetch/0.1 (python-urllib; one file at a time, cached)"


def cache_dir() -> Path:
    override = os.environ.get("LSN_LRO_DIR")
    return Path(override) if override else REPO / "data" / "cache" / "lro"


def browse_url() -> str:
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    case = next(case for case in cases["cases"] if case["id"] == "nadir_strip_2010")
    return case["published"]["browse_url"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _modified_utc(path: Path) -> str:
    return dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def download(target: Path) -> dict:
    """Download the browse image into ``target`` and describe it."""
    target.mkdir(parents=True, exist_ok=True)
    path, url = target / BROWSE_NAME, browse_url()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=600) as response, path.open("wb") as handle:
        last_modified = response.headers.get("Last-Modified")
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            handle.write(chunk)
    return describe(path, url, last_modified)


def describe(path: Path, url: str, last_modified) -> dict:
    # The retrieval time is the modification time of the file as it was written by the download.
    return {"name": path.name, "url": url, "bytes": path.stat().st_size, "sha256": _sha256(path), "server_last_modified": last_modified, "retrieved_utc": _modified_utc(path)}


def main() -> None:
    target, manifest_path = cache_dir(), HERE / "files.json"
    path = target / BROWSE_NAME
    known = {entry["name"]: entry for entry in json.loads(manifest_path.read_text(encoding="utf-8"))["files"]} if manifest_path.exists() else {}
    entry = known.get(BROWSE_NAME)
    if path.exists() and entry is not None and _sha256(path) == entry["sha256"]:
        print(f"cached  {BROWSE_NAME}")
    elif path.exists() and entry is None:
        # Downloaded before this record existed: record the file as it is, with its own modification time.
        entry = describe(path, browse_url(), None)
        print(f"recorded {BROWSE_NAME}: {entry['bytes']} bytes, retrieved {entry['retrieved_utc']}")
    else:
        entry = download(target)
        print(f"fetched {BROWSE_NAME}: {entry['bytes']} bytes")
    manifest = {
        "description": "LROC browse image read by the image check, as downloaded. Written by validation/lro_images/fetch.py; do not edit by hand.",
        "data_page": "https://data.lroc.im-ldi.com/lroc/view_lroc/LRO-L-LROC-2-EDR-V1.0/M146846913LE",
        "files": [entry],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
