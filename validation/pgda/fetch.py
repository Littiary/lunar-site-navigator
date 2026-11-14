"""Download the published LOLA illumination maps used by the PGDA check.

The maps are not committed (about 154 MB). They are stored outside the repository, under
``validation/pgda`` in the data root (``LSN_DATA_ROOT``) or in ``LSN_PGDA_DIR``; see
``validation/inputs.py``. ``files.json`` in this folder records, for every file, its URL,
size, SHA-256 and retrieval time: a file that is present with the recorded checksum is
not downloaded again, and a download that differs from the record is refused.

Usage (from the repository root)::

    python -m validation.pgda.fetch [--update]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validation import inputs

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "files.json"
ROOT_URL = "http://imbrium.mit.edu/EXTRAS/ILLUMINATION/"
PRODUCTS = ("AVGVISIB_85S_060M_201608", "AVGVISIB_85S_060M_201608_EARTH", "LPSR_85S_060M_201608")
FILES = ["README_ILLUMINATION_2016.TXT"] + [f"IMG/{name}.{ext}" for name in PRODUCTS for ext in ("LBL", "IMG")]


def cache_dir() -> Path:
    return inputs.input_dir("pgda", "LSN_PGDA_DIR")


def read_files() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="record a downloaded file that differs from files.json instead of refusing it")
    args = parser.parse_args()
    known, entries = inputs.read_records(MANIFEST), []
    for relative in FILES:
        name = relative.split("/")[-1]
        entry, done = inputs.fetch_file(ROOT_URL + relative, cache_dir() / name, known.get(name), update=args.update)
        print(f"{done:8s} {name}: {entry['bytes']} bytes", flush=True)
        entries.append(entry)
    print(f"-> {cache_dir()}")
    inputs.write_manifest(MANIFEST, {
        "description": "Published LOLA illumination maps used by the PGDA check, as downloaded. Written by validation/pgda/fetch.py; do not edit by hand.",
        "product_page": "https://pgda.gsfc.nasa.gov/products/69",
        "files": entries,
    })


if __name__ == "__main__":
    main()
