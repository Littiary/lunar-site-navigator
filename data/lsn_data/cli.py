"""Command line: ``python -m lsn_data <command>``."""

from __future__ import annotations

import argparse
import sys

from . import catalog, manifest as mf
from .paths import data_root, manifest_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="lsn-data", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="download products and write the manifest")
    f.add_argument("products", nargs="*", default=list(catalog.DEFAULT_SET), choices=list(catalog.PRODUCTS))
    f.add_argument("--prefer", choices=["pds", "mit"], default="mit", help="source tried first (default: mit, faster)")
    f.add_argument("--force", action="store_true", help="download again even if the size matches")
    f.add_argument("--workers", type=int, default=3)

    sub.add_parser("verify", help="checkpoint 1: compare every file with the manifest")

    x = sub.add_parser("cross-check", help="hash each file again from its other source and compare")
    x.add_argument("paths", nargs="*")

    pp = sub.add_parser("pyramid", help="build overview levels for the polar products")
    pp.add_argument("products", nargs="*", default=["LDEM_80S_20M", "LDEM_60S_60M"])
    pp.add_argument("--levels", type=int, default=6)

    sub.add_parser("checkpoints", help="run the three data checkpoints and write data/checkpoints/report.json")

    sub.add_parser("where", help="print the data root and manifest path")

    a = ap.parse_args(argv)
    root = data_root()

    if a.cmd == "where":
        print(f"data root : {root}\nmanifest  : {manifest_path()}")
        return 0
    if a.cmd == "fetch":
        from .fetch import run_fetch

        run_fetch(root, a.products, a.prefer, a.force, a.workers)
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
        from .dem import PolarDEM
        from .paths import derived_dir, raw_dir

        m = mf.load(manifest_path())
        for pid in a.products:
            rel = f"raw/lola/{pid}/{pid.lower()}.img"
            sha = m["files"].get(rel, {}).get("sha256")
            dem = PolarDEM(raw_dir(root) / pid / f"{pid.lower()}.lbl")
            meta = pyramid.build(dem, derived_dir(root) / pid, a.levels, source_sha256=sha)
            print(f"{pid}: levels {meta['levels']} written to {derived_dir(root) / pid}")
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
