"""Download the NAIF generic kernels and write ``kernel_manifest.json``.

Usage (from the repository root)::

    python -m lsncore.ephem.fetch_kernels [--force]
"""

from __future__ import annotations

import argparse

from . import kernels


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="download again even if the file is present")
    args = parser.parse_args()
    manifest = kernels.fetch(force=args.force)
    for entry in manifest["kernels"] + manifest["station_kernels"]:
        print(f"{entry['name']:28s} {entry['bytes']:>10d} bytes  sha256 {entry['sha256'][:16]}...  {entry['retrieved_utc']}")
    print(f"kernel set id: {kernels.kernel_set_id()}; station group id: {kernels.station_kernel_set_id()}  ->  {kernels.kernel_dir()}")


if __name__ == "__main__":
    main()
