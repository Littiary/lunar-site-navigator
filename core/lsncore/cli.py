"""Command line front end. It contains no science: it reads a request and writes packages."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from .contract import ContractError, contract_dir, validate_document, validate_package
from .scenario import load_scenario, single_site_scenario
from .synthetic import SYNTHETIC_DEM_SET_ID


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:64] or "site"


def _terrain(args: argparse.Namespace):
    """Terrain source selected on the command line: (terrain, is_synthetic)."""
    from .dem import open_lola

    terrain = open_lola(label_paths=args.dem_label or None)
    return terrain, terrain.is_synthetic


def _run(scenario: dict, out: Path, terrain=None, terrain_is_synthetic: bool = False) -> int:
    from .pipeline import run_scenario

    for path in run_scenario(scenario, out, terrain, terrain_is_synthetic):
        validate_package(path)
        print(path.as_posix())
    print((out / "index.json").as_posix())
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    scenario = load_scenario(args.scenario)
    if scenario["synthetic"] and not args.dem_label:
        return _run(scenario, Path(args.out))
    terrain, synthetic = _terrain(args)
    return _run(scenario, Path(args.out), terrain, synthetic)


def cmd_site(args: argparse.Namespace) -> int:
    site_id = args.site_id or _slug(args.name)
    common = dict(
        heights_m=args.heights,
        azimuth_step_deg=args.azimuth_step,
        max_range_m=args.max_range_km * 1000.0,
    )
    if args.synthetic:
        scenario = single_site_scenario(
            site_id, args.name, args.lat, args.lon, dem_set_id=SYNTHETIC_DEM_SET_ID, synthetic=True, **common
        )
        return _run(scenario, Path(args.out))
    terrain, synthetic = _terrain(args)
    scenario = single_site_scenario(
        site_id, args.name, args.lat, args.lon, dem_set_id=terrain.describe()["dem_set_id"], synthetic=synthetic, **common
    )
    return _run(scenario, Path(args.out), terrain, synthetic)


def cmd_sample(args: argparse.Namespace) -> int:
    sample = Path(args.dir) if args.dir else contract_dir() / "sample"
    packages = sample / "packages"
    if packages.exists():
        shutil.rmtree(packages)
    return _run(load_scenario(sample / "SYNTHETIC_scenario.json"), packages)


def cmd_validate(args: argparse.Namespace) -> int:
    failed = 0
    for target in args.paths:
        path = Path(target)
        try:
            if path.is_dir():
                validate_package(path)
            else:
                validate_document(json.loads(path.read_text(encoding="utf-8")))
            print(f"ok       {target}")
        except ContractError as err:
            failed += 1
            print(f"INVALID  {target}")
            for line in err.errors:
                print(f"         {line}")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lsn", description="Lunar Site Navigator science core")
    sub = parser.add_subparsers(dest="command", required=True)
    dem_help = "PDS3 label of an elevation product (repeatable); default: the LOLA products under the data root"

    p = sub.add_parser("run", help="compute every site of a scenario file and write packages")
    p.add_argument("scenario")
    p.add_argument("--out", required=True, help="package root directory")
    p.add_argument("--dem-label", action="append", help=dem_help)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("site", help="compute the terrain horizon of one site given by latitude and longitude")
    p.add_argument("--lat", type=float, required=True, help="latitude, degrees")
    p.add_argument("--lon", type=float, required=True, help="east longitude, degrees")
    p.add_argument("--name", required=True)
    p.add_argument("--site-id")
    p.add_argument("--out", required=True, help="package root directory")
    p.add_argument("--dem-label", action="append", help=dem_help)
    p.add_argument("--heights", type=float, nargs="+", help="observer heights in metres (default 0 1 2 5 10 20)")
    p.add_argument("--azimuth-step", type=float, default=0.25, help="degrees (default 0.25)")
    p.add_argument("--max-range-km", type=float, default=300.0, help="search radius (default 300)")
    p.add_argument("--synthetic", action="store_true", help="write invented numbers instead of computing (walking skeleton)")
    p.set_defaults(func=cmd_site)

    p = sub.add_parser("sample", help="regenerate the synthetic contract sample")
    p.add_argument("--dir", help="sample directory (default: docs/contract/sample)")
    p.set_defaults(func=cmd_sample)

    p = sub.add_parser("validate", help="check package directories or JSON documents against the contract")
    p.add_argument("paths", nargs="+")
    p.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (RuntimeError, FileNotFoundError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
