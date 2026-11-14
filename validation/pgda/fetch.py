"""Download the published LOLA illumination maps used by the PGDA check.

The maps are not committed (about 154 MB). They are stored under ``data/cache/pgda``
(or ``LSN_PGDA_DIR``); ``files.json`` in this folder records, for every file, its URL,
size, SHA-256 and retrieval time. A file that is already present with the recorded
checksum is not downloaded again.

Usage (from the repository root)::

    python -m validation.pgda.fetch
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
ROOT_URL = "http://imbrium.mit.edu/EXTRAS/ILLUMINATION/"
PRODUCTS = ("AVGVISIB_85S_060M_201608", "AVGVISIB_85S_060M_201608_EARTH", "LPSR_85S_060M_201608")
FILES = ["README_ILLUMINATION_2016.TXT"] + [f"IMG/{name}.{ext}" for name in PRODUCTS for ext in ("LBL", "IMG")]

# Generic client name; no personal contact data is sent.
USER_AGENT = "lunar-validation-fetch/0.1 (python-urllib; one file at a time, cached)"


def cache_dir() -> Path:
    override = os.environ.get("LSN_PGDA_DIR")
    return Path(override) if override else REPO / "data" / "cache" / "pgda"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_files() -> dict:
    return json.loads((HERE / "files.json").read_text(encoding="utf-8"))


def main() -> None:
    target = cache_dir()
    target.mkdir(parents=True, exist_ok=True)
    known = {entry["name"]: entry for entry in read_files()["files"]} if (HERE / "files.json").exists() else {}
    entries = []
    for relative in FILES:
        name = relative.split("/")[-1]
        path = target / name
        entry = known.get(name)
        if entry is None or not path.exists() or _sha256(path) != entry["sha256"]:
            url = ROOT_URL + relative
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=600) as response, path.open("wb") as handle:
                last_modified = response.headers.get("Last-Modified")
                while True:
                    chunk = response.read(1 << 20)
                    if not chunk:
                        break
                    handle.write(chunk)
            entry = {"name": name, "url": url, "bytes": path.stat().st_size, "sha256": _sha256(path), "server_last_modified": last_modified,
                     "retrieved_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
            print(f"fetched {name}: {entry['bytes']} bytes", flush=True)
        else:
            print(f"cached  {name}", flush=True)
        entries.append(entry)
    manifest = {
        "description": "Published LOLA illumination maps used by the PGDA check, as downloaded. Written by validation/pgda/fetch.py; do not edit by hand.",
        "product_page": "https://pgda.gsfc.nasa.gov/products/69",
        "files": entries,
    }
    (HERE / "files.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
