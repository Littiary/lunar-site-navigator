"""Command line front end. It contains no science: it reads a request and writes packages."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .contract import ContractError, contract_dir, contract_header, validate_document, validate_package, write_json
from .scenario import (
    DEFAULT_HEIGHT_M,
    DEFAULT_OBSERVER_HEIGHTS_M,
    custom_site_scenario,
    height_error_presets,
    load_scenario,
    requirement_presets,
    single_site_scenario,
    site_labels,
)
from .scenario import slug as _slug
from .synthetic import SYNTHETIC_DEM_SET_ID

# Exit codes: 0 done; 2 the request cannot be carried out as stated (the message says
# why); 3 something that must be installed on this machine is missing (kernels, terrain).
EXIT_ERROR = 2
EXIT_NOT_INSTALLED = 3


def _terrain(args: argparse.Namespace):
    """Terrain source selected on the command line: (terrain, is_synthetic)."""
    terrain = _open_terrain(args.dem_label, getattr(args, "near_field", False))
    return terrain, terrain.is_synthetic


def _open_terrain(labels=None, near_field: bool = False):
    """Named labels: those products. Otherwise every installed product, for a site anywhere;
    near_field adds the 5 m site rasters where the data stream has them."""
    from .dem import open_lola, open_moon

    return open_lola(label_paths=labels) if labels else open_moon(near_field=near_field)


def _jobs(requested: int, scenario: dict) -> int:
    """Processes a run may use: as asked, or by default half the processors and at most
    eight. Sites are computed side by side; the rest is shared inside each site."""
    import os

    if requested > 0:
        return requested
    return max(1, min((os.cpu_count() or 2) // 2, 8))


def _run(scenario: dict, out: Path, terrain=None, terrain_is_synthetic: bool = False, jobs: int = 1, terrain_factory=None) -> int:
    from .pipeline import run_scenario

    for path in run_scenario(scenario, out, terrain, terrain_is_synthetic, jobs=jobs, terrain_factory=terrain_factory):
        validate_package(path)
        print(path.as_posix())
    print((out / "index.json").as_posix())
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    scenario = load_scenario(args.scenario)
    if scenario["synthetic"] and not args.dem_label:
        return _run(scenario, Path(args.out))
    import functools

    terrain, synthetic = _terrain(args)
    factory = functools.partial(_open_terrain, args.dem_label, args.near_field)
    return _run(scenario, Path(args.out), terrain, synthetic, jobs=_jobs(args.jobs, scenario), terrain_factory=factory)


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
        site_id, args.name, args.lat, args.lon, dem_set_id="any", synthetic=synthetic, **common
    )
    return _run(scenario, Path(args.out), terrain, synthetic)


def cmd_scenario(args: argparse.Namespace) -> int:
    """Write a scenario file from the site records of the data stream."""
    records = json.loads(Path(args.sites).read_text(encoding="utf-8"))["sites"]
    sites = []
    for record in records:
        site = {
            "site_id": _slug(record["site_id"]),
            "name": record["name"],
            "lat_deg": float(record["lat_deg"]),
            "lon_deg": float(record["lon_deg_east"] if "lon_deg_east" in record else record["lon_deg"]),
        }
        if args.landing_utc:
            site["landing_utc"] = args.landing_utc
        site.update(site_labels(record))  # programme, category: passed through as they are
        sites.append(site)
    scenario = {
        "contract": contract_header(),
        "kind": "scenario",
        "scenario_id": args.id,
        "title": args.title or args.id,
        "synthetic": False,
        "sites": sites,
        "observer_heights_m": args.heights or DEFAULT_OBSERVER_HEIGHTS_M,
        "default_height_m": DEFAULT_HEIGHT_M,
        "horizon": {"azimuth_step_deg": args.azimuth_step, "max_range_m": args.max_range_km * 1000.0},
        "time_window": {"start_utc": args.start, "end_utc": args.end, "step_s": args.step},
        "bodies": ["SUN", "EARTH"],
        "data": {"dem_set_id": "any", "kernel_set_id": None},
    }
    requirements = []
    if args.preset:
        presets = requirement_presets()
        wanted = list(presets) if "all" in args.preset else args.preset
        unknown = [name for name in wanted if name not in presets]
        if unknown:
            raise ValueError(f"unknown requirement preset {unknown}; available: {sorted(presets)}")
        requirements += [presets[name] for name in wanted]
    if args.requirements:
        requirements += json.loads(Path(args.requirements).read_text(encoding="utf-8"))
    if requirements:
        scenario["requirements"] = requirements
    uncertainty = {}
    if args.horizon_error_deg:
        uncertainty["horizon_error_deg"] = args.horizon_error_deg
    if args.dem_height_error_m and args.height_error_preset:
        raise ValueError("state the terrain height error either as a number or as a preset, not both")
    if args.dem_height_error_m:
        uncertainty["dem_height_error_m"] = args.dem_height_error_m
    if args.height_error_preset:
        presets = height_error_presets()
        name = presets["default"] if args.height_error_preset == "default" else args.height_error_preset
        if name not in presets["models"]:
            raise ValueError(f"unknown height-error preset '{name}'; available: {sorted(presets['models'])}")
        uncertainty["dem_height_error_model"] = presets["models"][name]
    if args.ellipse:
        major, minor, azimuth, points = args.ellipse
        uncertainty["landing_ellipse"] = {"semi_major_m": major, "semi_minor_m": minor, "azimuth_deg": azimuth, "points": int(points)}
    if uncertainty:
        scenario["uncertainty"] = uncertainty
    validate_document(scenario)
    write_json(Path(args.out), scenario)
    print(Path(args.out).as_posix())
    return 0


_CUSTOM_STAGES = {
    "check": "checking the kernels and opening the terrain",
    "directions": "Sun and Earth directions",
    "horizon": "terrain horizon",
    "timeline": "Sun and Earth visibility, events, countdowns and landing windows",
    "uncertainty": "uncertainty band",
    "package": "terrain patches and package files",
}


def _kernel_problem() -> str | None:
    """What is missing for the Sun and Earth directions, in one line, or None."""
    try:
        from .ephem import kernels
    except ImportError as err:
        return f"kernels: the SPICE library is not installed ({err}); install the core with: pip install -e core"
    missing = kernels.missing()
    if missing:
        return (
            f"kernels: {len(missing)} of {len(kernels.KERNEL_SET)} kernel files are missing in {kernels.kernel_dir()} "
            f"({', '.join(missing)}). Download them once with: {kernels.FETCH_COMMAND} (docs/setup.md)"
        )
    try:
        kernels.load()
    except (RuntimeError, OSError) as err:
        return f"kernels: {err}. Download them again with: {kernels.FETCH_COMMAND} (docs/setup.md)"
    return None


def _terrain_problem(err: Exception) -> str:
    """Why no terrain serves the site, where it was looked for and how to install it."""
    try:
        from lsn_data.paths import data_root

        where = f" Data root: {data_root()}."
    except ImportError:
        where = ""
    reason = "no elevation product is installed" if str(err) == "no products" else str(err).rstrip(".")
    return f"terrain: {reason}.{where} Install the elevation products with: python -m lsn_data fetch, then python -m lsn_data pyramid (docs/setup.md)"


def cmd_custom(args: argparse.Namespace) -> int:
    """One site given by coordinates and a start date: a complete package.

    Horizon, Sun and Earth timeline with countdowns, landing windows of the example
    requirements, uncertainty band of the default height-error model; no landing ellipse.
    Prints 'progress k/n text' lines, then the package directories and the index.
    """
    scenario = custom_site_scenario(
        args.lat, args.lon, args.start, days=args.days, step_s=args.step, name=args.name, site_id=args.site_id,
        landing_utc=args.landing_utc, requirement_ids=None if not args.preset or "all" in args.preset else [p for p in args.preset if p != "none"],
        band=not args.no_band, heights_m=args.heights, azimuth_step_deg=args.azimuth_step, max_range_m=args.max_range_km * 1000.0,
    )
    stages = [name for name in _CUSTOM_STAGES if name != "uncertainty" or "uncertainty" in scenario]

    def tell(stage: str, detail: str = "") -> None:
        if stage in stages:
            text = _CUSTOM_STAGES[stage] + (f": {detail}" if detail else "")
            print(f"progress {stages.index(stage) + 1}/{len(stages)} {text}", flush=True)

    tell("check")
    problems = [_kernel_problem()]
    terrain = None
    try:
        terrain, synthetic = _terrain(args)
        if hasattr(terrain, "for_site"):
            terrain.for_site(float(args.lat), float(args.lon), args.max_range_km * 1000.0)
    except (RuntimeError, FileNotFoundError, ValueError) as err:
        problems.append(_terrain_problem(err))
    problems = [p for p in problems if p]
    if problems:
        for line in problems:
            print(f"error: {line}", file=sys.stderr)
        return EXIT_NOT_INSTALLED
    scenario["synthetic"] = bool(synthetic)

    from .pipeline import find_direction_table, run_scenario

    out = Path(args.out)
    window = scenario["time_window"]
    table = find_direction_table([out, *(args.tables or [])], window["start_utc"], window["end_utc"])
    tell("directions", f"reusing {table.name}" if table is not None else "computing them for the window")
    details = {
        "horizon": f"{round(360.0 / args.azimuth_step)} azimuths out to {args.max_range_km:g} km",
        "timeline": f"{args.days:g} days from {window['start_utc']}",
    }
    paths = run_scenario(
        scenario, out, terrain, synthetic, jobs=_jobs(args.jobs, scenario), direction_table=table,
        progress=lambda stage: tell(stage, details.get(stage, "")),
    )
    for path in paths:
        validate_package(path)
        print(path.as_posix(), flush=True)
    print((out / "index.json").as_posix(), flush=True)
    return 0


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
    p.add_argument("--near-field", action="store_true", help="use the 5 m site rasters inside the polar products where they are installed")
    p.add_argument("--jobs", type=int, default=0, help="processes the run may use (default: half the processors, at most 8); sites are computed side by side")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("site", help="compute the terrain horizon of one site given by latitude and longitude")
    p.add_argument("--lat", type=float, required=True, help="latitude, degrees")
    p.add_argument("--lon", type=float, required=True, help="east longitude, degrees")
    p.add_argument("--name", required=True)
    p.add_argument("--site-id")
    p.add_argument("--out", required=True, help="package root directory")
    p.add_argument("--dem-label", action="append", help=dem_help)
    p.add_argument("--near-field", action="store_true", help="use the 5 m site rasters inside the polar products where they are installed")
    p.add_argument("--heights", type=float, nargs="+", help="observer heights in metres (default 0 1 2 5 10 20)")
    p.add_argument("--azimuth-step", type=float, default=0.25, help="degrees (default 0.25)")
    p.add_argument("--max-range-km", type=float, default=300.0, help="search radius (default 300)")
    p.add_argument("--synthetic", action="store_true", help="write invented numbers instead of computing (walking skeleton)")
    p.set_defaults(func=cmd_site)

    p = sub.add_parser(
        "custom",
        help="one site given by latitude, longitude and a start date: a complete package (horizon, Sun, Earth, countdowns, landing windows, uncertainty band)",
    )
    p.add_argument("--lat", type=float, required=True, help="latitude, degrees")
    p.add_argument("--lon", type=float, required=True, help="east longitude, degrees")
    p.add_argument("--start", required=True, help="start of the time window, UTC: 2026-11-14 or 2026-11-14T06:00Z")
    p.add_argument("--days", type=float, default=30.0, help="length of the time window in days (default 30)")
    p.add_argument("--out", required=True, help="package root directory")
    p.add_argument("--name", help="name of the site (default: 'Custom site' with its coordinates)")
    p.add_argument("--site-id", help="identifier of the site (default: from the name)")
    p.add_argument("--landing-utc", help="planned landing; the countdowns count from it if it lies in the window, otherwise from the start")
    p.add_argument("--step", type=float, default=3600.0, help="step of the stored series in seconds (default 3600)")
    p.add_argument("--preset", action="append", help="example requirement to state (repeatable; default: all of docs/contract/presets; 'none' for no landing windows)")
    p.add_argument("--no-band", action="store_true", help="leave out the uncertainty band of the default height-error model")
    p.add_argument("--tables", action="append", help="another package root to look in for a direction table that covers the window (repeatable)")
    p.add_argument("--dem-label", action="append", help=dem_help)
    p.add_argument("--near-field", action="store_true", help="use the 5 m site rasters inside the polar products where they are installed")
    p.add_argument("--heights", type=float, nargs="+", help="observer heights in metres (default 0 1 2 5 10 20)")
    p.add_argument("--azimuth-step", type=float, default=0.25, help="degrees (default 0.25)")
    p.add_argument("--max-range-km", type=float, default=300.0, help="search radius (default 300)")
    p.add_argument("--jobs", type=int, default=0, help="processes the uncertainty band may use (default: half the processors, at most 8)")
    p.set_defaults(func=cmd_custom)

    p = sub.add_parser("scenario", help="write a scenario file from site records (data/sites/sites.json)")
    p.add_argument("--sites", required=True, help="site records of the data stream")
    p.add_argument("--id", required=True, help="scenario id (lower case, digits, hyphens)")
    p.add_argument("--title")
    p.add_argument("--start", required=True, help="UTC, e.g. 2026-11-14T00:00:00.000Z")
    p.add_argument("--end", required=True)
    p.add_argument("--step", type=float, default=3600.0, help="step of the stored series in seconds (default 3600)")
    p.add_argument("--heights", type=float, nargs="+", help="observer heights in metres (default 0 1 2 5 10 20)")
    p.add_argument("--azimuth-step", type=float, default=0.25)
    p.add_argument("--max-range-km", type=float, default=300.0)
    p.add_argument("--landing-utc", help="planned landing, used for the slip tolerance")
    p.add_argument("--preset", action="append", help="example requirement from docs/contract/presets (repeatable; 'all' for every preset)")
    p.add_argument("--requirements", help="JSON file with a list of requirements (SPEC 5.6)")
    p.add_argument("--horizon-error-deg", type=float, help="stated horizon error for the uncertainty band (common to all azimuths)")
    p.add_argument("--dem-height-error-m", type=float, help="stated height error of the limiting terrain as one number; widens the band for near terrain")
    p.add_argument("--height-error-preset", help="stated height-error model from docs/contract/presets/terrain_height_error.json ('default' for the sourced one)")
    p.add_argument("--ellipse", type=float, nargs=4, metavar=("SEMI_MAJOR_M", "SEMI_MINOR_M", "AZIMUTH_DEG", "POINTS"), help="stated landing ellipse")
    p.add_argument("--out", required=True, help="scenario file to write")
    p.set_defaults(func=cmd_scenario)

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
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
