"""Download the NAIF generic kernels and check them against ``kernel_manifest.json``.

The kernels go to ``kernels`` under the data root (``LSN_DATA_ROOT``; default
``C:\\lsn-data`` on Windows, ``~/lsn-data`` elsewhere) or to ``LSN_KERNEL_DIR``, never
into the repository. Files that are present and match the manifest are not downloaded
again; the committed manifest is not changed unless a kernel has no record yet or
``--update-manifest`` is given.

Usage::

    python -m lsncore.ephem.fetch_kernels [--force] [--update-manifest]
"""

from __future__ import annotations

import argparse

from . import kernels


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="download again even if the file is present")
    parser.add_argument("--update-manifest", action="store_true", help="record a downloaded file that differs from the manifest instead of refusing it (defines a new kernel set)")
    args = parser.parse_args()
    unavailable = []
    manifest = kernels.fetch(force=args.force, update_manifest=args.update_manifest, unavailable=unavailable)
    gone = {item["name"] for item in unavailable}
    for entry in manifest["kernels"] + manifest["station_kernels"]:
        state = "NOT AVAILABLE" if entry["name"] in gone else "ok"
        print(f"{entry['name']:38s} {entry['bytes']:>10d} bytes  sha256 {entry['sha256'][:16]}...  recorded {entry['retrieved_utc']}  {state}")
    print(f"kernel set id: {kernels.kernel_set_id()}; station group id: {kernels.station_kernel_set_id()}  ->  {kernels.kernel_dir()}")
    for item in unavailable:
        print(f"WARNING: {item['name']} could not be downloaded from {item['url']} ({item['error']}).")
    if unavailable:
        print(
            "WARNING: the ground-station group is incomplete. The base set is complete, so directions, events and eclipses are unaffected; "
            "the ground-station tests are skipped and direct-to-Earth windows cannot be recomputed with the recorded kernel set. "
            "NAIF keeps only the current high-precision Earth orientation file; a copy of the recorded file placed in the kernel folder is accepted if its checksum matches."
        )


if __name__ == "__main__":
    main()
