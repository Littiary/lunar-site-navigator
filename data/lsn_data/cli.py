"""Command line: ``python -m lsn_data <command>``."""

from __future__ import annotations

import argparse
import sys

from . import catalog, manifest as mf
from .paths import data_root, manifest_path


def _below_normal_priority() -> None:
    import os

    if os.name == "nt":
        import ctypes

        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)
    else:
        os.nice(10)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="lsn-data", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="download products and write the manifest")
    f.add_argument("products", nargs="*", default=list(catalog.DEFAULT_SET), choices=list(catalog.PRODUCTS))
    f.add_argument("--prefer", choices=["pds", "mit"], default="mit", help="source tried first (default: mit, faster)")
    f.add_argument("--force", action="store_true", help="download again even if the size matches")
    f.add_argument("--workers", type=int, default=3)
    f.add_argument("--segments", type=int, default=1, help="parallel byte ranges per large file (the mirror limits each connection)")

    sub.add_parser("verify", help="checkpoint 1: compare every file with the manifest")

    x = sub.add_parser("cross-check", help="hash each file again from its other source and compare")
    x.add_argument("paths", nargs="*")

    pp = sub.add_parser("pyramid", help="build overview levels (polar, cylindrical tiles, 5 m site GeoTIFFs)")
    pp.add_argument("products", nargs="*", default=["LDEM_80S_20M", "LDEM_60S_60M"])
    pp.add_argument("--levels", type=int, default=6)
    pp.add_argument("--hash-only", action="store_true", help="only record SHA-256 of existing level files in pyramid.json")
    pp.add_argument("--low-priority", action="store_true", help="run at below-normal process priority (Windows) / nice 10")

    sub.add_parser("checkpoints", help="run the three data checkpoints and write data/checkpoints/report.json")

    sub.add_parser("where", help="print the data root and manifest path")

    a = ap.parse_args(argv)
    root = data_root()

    if a.cmd == "where":
        print(f"data root : {root}\nmanifest  : {manifest_path()}")
        return 0
    if a.cmd == "fetch":
        from .fetch import run_fetch

        run_fetch(root, a.products, a.prefer, a.force, a.workers, a.segments)
        return 0
    if a.cmd == "verify":
        m = mf.load(manifest_path())
        problems = mf.verify(m, root)
        for p in problems:
            print("FAIL", p)
        n = len(m.get("files", {}))
        print(f"{'OK' if not problems else 'FAILED'}: {n} files checked against {manifest_path()}")
        return 1 if problems else 0
    if a.cmd == "pyramid":
        from . import pyramid

        if a.low_priority:
            _below_normal_priority()
        if a.hash_only:
            from .paths import derived_dir

            for pid in a.products:
                meta = pyramid.add_file_hashes(derived_dir(root) / pid)
                print(f"{pid}: recorded {len(meta['files'])} file hashes")
            return 0
        for pid in a.products:
            meta = pyramid.build_product(pid, root, a.levels)
            print(f"{pid}: levels {meta['levels']} written", flush=True)
        pyramid.write_record(root)
        return 0
    if a.cmd == "checkpoints":
        import json

        from . import checkpoints
        from .paths import repo_data_dir

        rep = checkpoints.run_all(root)
        out = repo_data_dir() / "checkpoints" / "report.json"
        out.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
        print(json.dumps(rep, indent=1))
        print("ALL PASSED" if rep["all_passed"] else "FAILED", "->", out)
        return 0 if rep["all_passed"] else 1
    if a.cmd == "cross-check":
        from .fetch import cross_check

        bad = cross_check(root, a.paths or None)
        return 1 if bad else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
