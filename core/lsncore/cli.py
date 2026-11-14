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
from .synthetic import SYNTHETIC_DEM_SET_ID, run_synthetic_scenario


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:64] or "site"


def _run(scenario: dict, out: Path) -> int:
    if not scenario["synthetic"]:
        print(
            "error: only synthetic scenarios can be run so far; the terrain engine is not "
            "connected to this command yet",
            file=sys.stderr,
        )
        return 2
    for path in run_synthetic_scenario(scenario, out):
        validate_package(path)
        print(path.as_posix())
    print((out / "index.json").as_posix())
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    return _run(load_scenario(args.scenario), Path(args.out))


def cmd_site(args: argparse.Namespace) -> int:
    if not args.synthetic:
        print("error: pass --synthetic; real terrain is not connected to this command yet", file=sys.stderr)
        return 2
    scenario = single_site_scenario(
        args.site_id or _slug(args.name),
        args.name,
        args.lat,
        args.lon,
        dem_set_id=SYNTHETIC_DEM_SET_ID,
        synthetic=True,
    )
    return _run(scenario, Path(args.out))


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

    p = sub.add_parser("run", help="compute every site of a scenario file and write packages")
    p.add_argument("scenario")
    p.add_argument("--out", required=True, help="package root directory")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("site", help="compute one site given by latitude and longitude")
    p.add_argument("--lat", type=float, required=True, help="latitude, degrees")
    p.add_argument("--lon", type=float, required=True, help="east longitude, degrees")
    p.add_argument("--name", required=True)
    p.add_argument("--site-id")
    p.add_argument("--out", required=True, help="package root directory")
    p.add_argument("--synthetic", action="store_true", help="write invented numbers (walking skeleton)")
    p.set_defaults(func=cmd_site)

    p = sub.add_parser("sample", help="regenerate the synthetic contract sample")
    p.add_argument("--dir", help="sample directory (default: docs/contract/sample)")
    p.set_defaults(func=cmd_sample)

    p = sub.add_parser("validate", help="check package directories or JSON documents against the contract")
    p.add_argument("paths", nargs="+")
    p.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
