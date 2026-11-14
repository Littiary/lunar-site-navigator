"""Download the LROC browse image read by the image check.

The image is not committed (7.8 MB). It is stored outside the repository, under
``validation/lro`` in the data root (``LSN_DATA_ROOT``) or in ``LSN_LRO_DIR``; see
``validation/inputs.py``. ``files.json`` in this folder records its URL, size, SHA-256
and retrieval time: a file that is present with the recorded checksum is not downloaded
again, and a download that differs from the record is refused. The URL is the one fixed
in ``cases.json``.

Usage (from the repository root)::

    python -m validation.lro_images.fetch [--update]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validation import inputs

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "files.json"
BROWSE_NAME = "M146846913LC_pyr.tif"


def cache_dir() -> Path:
    return inputs.input_dir("lro", "LSN_LRO_DIR")


def browse_url() -> str:
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    case = next(case for case in cases["cases"] if case["id"] == "nadir_strip_2010")
    return case["published"]["browse_url"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="record a downloaded file that differs from files.json instead of refusing it")
    args = parser.parse_args()
    entry, done = inputs.fetch_file(browse_url(), cache_dir() / BROWSE_NAME, inputs.read_records(MANIFEST).get(BROWSE_NAME), update=args.update)
    print(f"{done:8s} {BROWSE_NAME}: {entry['bytes']} bytes -> {cache_dir()}")
    inputs.write_manifest(MANIFEST, {
        "description": "LROC browse image read by the image check, as downloaded. Written by validation/lro_images/fetch.py; do not edit by hand.",
        "data_page": "https://data.lroc.im-ldi.com/lroc/view_lroc/LRO-L-LROC-2-EDR-V1.0/M146846913LE",
        "files": [entry],
    })


if __name__ == "__main__":
    main()
