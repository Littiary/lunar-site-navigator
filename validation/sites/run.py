"""End-to-end run for the south-polar site records of the data stream.

Builds one scenario with every site record, runs the core pipeline (LOLA terrain horizon
-> SPICE direction table -> events, windows, countdowns), validates every package against
the contract and writes a summary. The scenario and the summary are kept in this folder.

Usage (from the repository root, with the LOLA data under LSN_DATA_ROOT)::

    python -m validation.sites.run data/sites/sites.json --publish
    python -m validation.sites.run data/sites/sites.json [--out FOLDER] [--start UTC] [--end UTC]

``--publish`` replaces the published packages in ``packages/`` at the repository root
(the folder the web pages and the Unreal scene read) and writes ``packages/README.md``.
The packages are first written to a staging folder under ``build/`` (not under version
control) and then copied, so that writing them does not itself make the working tree
differ from the commit recorded in their provenance. Commit all code changes before
publishing. Without ``--publish`` the packages go to ``build/packages/sites``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from lsncore.contract import contract_header, read_package, validate_document, validate_package
from lsncore.dem import open_lola
from lsncore.ephem import kernels
from lsncore.pipeline import run_scenario

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PUBLISHED = REPO / "packages"
STAGING = REPO / "build" / "packages" / "publish-staging"
DEFAULT_START = "2026-11-14T00:00:00.000Z"
DEFAULT_END = "2027-11-14T00:00:00.000Z"
NEAR_TERRAIN_M = 1000.0
RELAY_NEED = {
    0: "direct link possible at all times",
    1: "interrupted only by station gaps on the Earth",
    2: "interrupted by lunar terrain: relay or waiting needed during those outages",
    3: "no station ever above the lunar terrain: relay required",
}
THRESHOLDS = {
    "SUN": {"quantity": "visible_fraction", "op": ">", "value": 0.0},
    "EARTH": {"quantity": "margin_deg", "op": ">", "value": 0.0},
}


class TerrainWithFileProvenance:
    """The core's terrain adapter, with the checksum and source of each elevation file.

    The data reader reports provenance per file of a product (data file, label, overview
    levels); the core's adapter looks for one checksum per product and finds none. This
    wrapper fills the layer entry of the package with the SHA-256 and the source URL of
    the product's data file. Everything else is passed through unchanged.
    """

    def __init__(self, terrain, provenance: list):
        self._terrain = terrain
        self._data_files = {}
        for item in provenance:
            data = [f for f in item.get("files", []) if f.get("role") == "data"]
            if len(data) == 1:
                self._data_files[str(item["product_id"])] = data[0]

    def __getattr__(self, name):
        return getattr(self._terrain, name)

    def describe(self) -> dict:
        described = self._terrain.describe()
        layers = []
        for layer in described["layers"]:
            data = self._data_files.get(layer["product_id"])
            if data is not None and not layer.get("sha256"):
                layer = {**layer, "sha256": data["sha256"], "source_url": data["source_url"] or ""}
            layers.append(layer)
        return {**described, "layers": layers}


def build_scenario(records: list, dem_set_id: str, start_utc: str, end_utc: str) -> dict:
    scenario = {
        "contract": contract_header(),
        "kind": "scenario",
        "scenario_id": "south-polar-sites",
        "title": "Three south-polar candidate points, twelve months from the hackathon weekend",
        "description": "Site records of the data stream (derived from LOLA and IAU crater outlines; not official landing sites). Real LOLA terrain, SPICE ephemeris.",
        "synthetic": False,
        "sites": [
            {
                "site_id": record["site_id"].replace("_", "-"),
                "name": record["name"],
                "lat_deg": record["lat_deg"],
                "lon_deg": record["lon_deg_east"],
                "notes": record["status"],
            }
            for record in records
        ],
        "observer_heights_m": [0.0, 1.0, 2.0, 5.0, 10.0, 20.0],
        "default_height_m": 2.0,
        "horizon": {"azimuth_step_deg": 0.25, "max_range_m": 300000.0},
        "time_window": {"start_utc": start_utc, "end_utc": end_utc, "step_s": 3600.0},
        "bodies": ["SUN", "EARTH"],
        "thresholds": THRESHOLDS,
        "mission_profile": None,
        "data": {"dem_set_id": dem_set_id, "kernel_set_id": kernels.kernel_set_id(), "direction_table_id": None},
    }
    validate_document(scenario)
    return scenario


def summarise(package_dir: Path) -> dict:
    package = read_package(package_dir)
    m = package.manifest
    timeline = m["timeline"]
    heights = m["horizon"]["observer_heights_m"]
    elevation = package.array(m["horizon"]["elevation_deg"])
    distance = package.array(m["horizon"]["distance_m"])
    per_height = []
    for h, height in enumerate(heights):
        metrics = {x["id"]: x["value"] for x in timeline["metrics"] if x["height_index"] == h}
        events = [e for e in timeline["events"] if e["height_index"] == h]
        sun_sets = [e for e in events if e["body"] == "SUN" and e["type"] == "set"]
        near = [e for e in events if e["body"] == "SUN" and e["obstacle_distance_m"] is not None and e["obstacle_distance_m"] < NEAR_TERRAIN_M]
        per_height.append(
            {
                "observer_height_m": height,
                "sun_visible_share": metrics["sun_visible_fraction_of_time"],
                "sun_longest_outage_h": metrics["sun_longest_outage_s"] / 3600.0,
                "sun_longest_visible_d": metrics["sun_longest_visible_s"] / 86400.0,
                "sun_events": sum(e["body"] == "SUN" for e in events),
                "sun_events_set_by_terrain_closer_than_1km": len(near),
                "sun_time_to_set_d": metrics["sun_time_to_set_s"] / 86400.0,
                "sun_time_to_set_is_lower_bound": bool(metrics["sun_time_to_set_is_lower_bound"]),
                "first_sun_set_utc": sun_sets[0]["utc"] if sun_sets else None,
                "earth_visible_share": metrics["earth_visible_fraction_of_time"],
                "earth_longest_outage_h": metrics["earth_longest_outage_s"] / 3600.0,
                "earth_events": sum(e["body"] == "EARTH" for e in events),
                "earth_visible_at_start": bool(metrics["earth_visible_at_reference"]),
                "earth_time_to_set_d": metrics["earth_time_to_set_s"] / 86400.0,
                "earth_time_to_set_is_lower_bound": bool(metrics["earth_time_to_set_is_lower_bound"]),
                "horizon_min_deg": float(elevation[h].min()),
                "horizon_max_deg": float(elevation[h].max()),
                "share_of_horizon_set_closer_than_1km": float((distance[h] < NEAR_TERRAIN_M).mean()),
                "dte": None if "dte_relay_need_level" not in metrics else {
                    "relay_need_level": int(metrics["dte_relay_need_level"]),
                    "network_two_way_share": metrics["dte_network_share"],
                    "network_receive_share": metrics["dte_network_receive_share"],
                    "station_shares": {name: metrics[f"dte_station_{name}_share"] for name in ("goldstone", "canberra", "madrid")},
                    "longest_outage_h": metrics["dte_longest_outage_s"] / 3600.0,
                    "longest_terrain_outage_h": metrics["dte_longest_terrain_outage_s"] / 3600.0,
                },
            }
        )
    site_metrics = {x["id"]: x["value"] for x in timeline["metrics"] if x["height_index"] is None}
    eclipse_windows = {w["id"]: w for w in timeline["windows"] if w["height_index"] == 0 and w["id"] in ("sun_eclipsed_by_earth", "sun_totally_eclipsed_by_earth")}
    sun = package.array(timeline["series"]["SUN"]["elevation_deg"])
    earth = package.array(timeline["series"]["EARTH"]["elevation_deg"])
    return {
        "site_id": m["site"]["site_id"],
        "name": m["site"]["name"],
        "lat_deg": m["site"]["lat_deg"],
        "lon_deg": m["site"]["lon_deg"],
        "surface_height_m": m["site"]["surface_height_m"]["value"],
        "package_id": m["package_id"],
        "content_sha256": m["content_sha256"],
        "status": m["status"],
        "warnings": m["warnings"],
        "direction_table_id": timeline["direction_table_id"],
        "dem_set_id": m["inputs"]["dem"]["dem_set_id"],
        "horizon_error_bounds": {k: v["value"] for k, v in m["horizon"].get("error_bounds", {}).items()},
        "timings_s": m["provenance"].get("timings_s"),
        "sun_centre_elevation_range_deg": [float(sun.min()), float(sun.max())],
        "earth_centre_elevation_range_deg": [float(earth.min()), float(earth.max())],
        "default_height_index": m["horizon"]["default_height_index"],
        "eclipses_of_the_sun_by_the_earth": {
            "count": int(site_metrics["sun_eclipse_count"]),
            "total_at_the_site": int(site_metrics["sun_eclipse_total_count"]),
            "longest_totality_h": site_metrics["sun_eclipse_longest_totality_s"] / 3600.0,
            "max_covered_fraction": site_metrics["sun_eclipse_max_covered_fraction"],
            "partial_intervals_utc": eclipse_windows["sun_eclipsed_by_earth"]["intervals_utc"],
            "total_intervals_utc": eclipse_windows["sun_totally_eclipsed_by_earth"]["intervals_utc"],
        },
        "per_height": per_height,
    }


def to_markdown(summary: dict) -> str:
    w = summary["window"]
    lines = [
        "# End-to-end results: three south-polar candidate points",
        "",
        f"Generated {summary['generated_utc']} by `validation/sites/run.py`. Do not edit by hand.",
        "",
        f"- Window: {w['start_utc']} to {w['end_utc']} (UTC). Countdowns count from the start of the window.",
        f"- Terrain: `{summary['dem_set_id']}`, search radius 300 km, azimuth step 0.25 deg. Ephemeris: kernel set `{summary['kernel_set_id']}`, direction table `{summary['direction_table_id']}`.",
        "- Sun visible = any part of the disc above the terrain horizon. Earth visible = centre of the disc above the terrain horizon.",
        "- The points are project candidates derived from LOLA and IAU crater outlines by the data stream; **they are not official landing sites**.",
        "- **Status: unverified against an independent illumination product or mission record.** The ephemeris part is validated (see the validation card); the terrain horizon has passed analytic tests only.",
        "",
    ]
    for site in summary["sites"]:
        sun_lo, sun_hi = site["sun_centre_elevation_range_deg"]
        earth_lo, earth_hi = site["earth_centre_elevation_range_deg"]
        lines += [
            f"## {site['name']}",
            "",
            f"{abs(site['lat_deg']):.5f} deg S, {site['lon_deg']:.5f} deg E, terrain height {site['surface_height_m']:.1f} m above the 1737.4 km sphere. "
            f"Package `{site['package_id']}`, status `{site['status']}`. Sun centre elevation {sun_lo:.2f} to {sun_hi:.2f} deg; "
            f"Earth centre elevation {earth_lo:.2f} to {earth_hi:.2f} deg.",
            "",
            "| Observer height | Sun visible | Longest time without Sun | Sun rise/set events | of which set by terrain < 1 km away | Time to next Sun set | Earth visible | Longest time without Earth | Time to next Earth set | Horizon set by terrain < 1 km |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for row in site["per_height"]:
            sun_to = ("at least " if row["sun_time_to_set_is_lower_bound"] else "") + f"{row['sun_time_to_set_d']:.2f} d"
            earth_to = ("at least " if row["earth_time_to_set_is_lower_bound"] else "") + f"{row['earth_time_to_set_d']:.2f} d"
            lines.append(
                f"| {row['observer_height_m']:g} m | {100 * row['sun_visible_share']:.1f} % | {row['sun_longest_outage_h']:.1f} h | {row['sun_events']} | "
                f"{row['sun_events_set_by_terrain_closer_than_1km']} | {sun_to} | {100 * row['earth_visible_share']:.1f} % | {row['earth_longest_outage_h']:.1f} h | {earth_to} | "
                f"{100 * row['share_of_horizon_set_closer_than_1km']:.0f} % |"
            )
        if site["per_height"][0]["dte"] is not None:
            lines += [
                "",
                "Direct link with the Deep Space Network (three complexes; station mask 10 deg for a two-way link, 6 deg to receive; geometry only):",
                "",
                "| Observer height | Two-way link possible | Receive possible | Goldstone | Canberra | Madrid | Longest time without a link | Longest time with every station behind lunar terrain | Relay need |",
                "|---|---|---|---|---|---|---|---|---|",
            ]
            for row in site["per_height"]:
                x = row["dte"]
                s = x["station_shares"]
                lines.append(
                    f"| {row['observer_height_m']:g} m | {100 * x['network_two_way_share']:.1f} % | {100 * x['network_receive_share']:.1f} % | {100 * s['goldstone']:.1f} % | {100 * s['canberra']:.1f} % | "
                    f"{100 * s['madrid']:.1f} % | {x['longest_outage_h']:.1f} h | {x['longest_terrain_outage_h']:.1f} h | {x['relay_need_level']}: {RELAY_NEED[x['relay_need_level']]} |"
                )
        e = site["eclipses_of_the_sun_by_the_earth"]
        lines.append("")
        if e["count"]:
            spans = "; ".join(f"{a} to {b}" for a, b in e["partial_intervals_utc"])
            lines.append(f"Eclipses of the Sun by the Earth in the window: {e['count']} ({e['total_at_the_site']} total at the site); largest covered fraction of the Sun {e['max_covered_fraction']:.3f}; {spans}.")
        else:
            lines.append("Eclipses of the Sun by the Earth in the window: none.")
        lines.append("")
    lines += [
        "## Limits",
        "",
        "- Shares and longest outages describe this twelve-month window only; they are not multi-year averages.",
        "- Where an event is set by terrain closer than about 1 km, the 20 m elevation grid, not the method, limits the accuracy, and the event time can be off by hours. The column on near terrain counts those events.",
        "- Event times are numerically exact to 0.25 s for the given horizon profile; that is not their physical accuracy.",
        "- The direct-link figures are geometric: a station above the lunar terrain horizon and the site above the station's elevation limit. No link budget, no azimuth-dependent station masks, no scheduling, no multipath near the lunar horizon. A relay need of 2 means that for part of the time no ground station at all can be reached.",
        "- A countdown marked 'at least' has no set inside the computed window.",
        "- The shares of time above are cut by the terrain only. Eclipses of the Sun by the Earth are listed per site (opaque Earth, no atmosphere) and are in the package as the windows 'sun_eclipsed_by_earth', 'sun_totally_eclipsed_by_earth' and 'sun_lit'.",
    ]
    return "\n".join(lines) + "\n"


def _clear_published(root: Path) -> None:
    """Remove the previously published packages (only what the pipeline itself writes)."""
    for name in ("direction_table", "site"):
        if (root / name).exists():
            shutil.rmtree(root / name)
    for name in ("index.json", "README.md"):
        if (root / name).exists():
            (root / name).unlink()


def write_readme(root: Path, written: list, scenario: dict, summary: dict, command: str) -> None:
    """The README of the published packages: what they are and exactly how they were made.

    The commit and the state of the working tree are those the package writer recorded in
    the provenance of each package.
    """
    manifests = [read_package(path).manifest for path in written]
    software = [m["provenance"]["software"] for m in manifests]
    commits = sorted({s["git_commit"][:7] for s in software})
    dirty = any(s["git_dirty"] for s in software)
    commit = ", ".join(commits)
    table = next(m for m in manifests if m["kind"] == "direction_table")
    sites = [m for m in manifests if m["kind"] == "site"]
    kernel_manifest = kernels.read_manifest()
    size = sum(f.stat().st_size for f in root.rglob("*") if f.is_file())
    w = scenario["time_window"]
    lines = [
        "# Published packages",
        "",
        "Real result packages of the science core, in the format of [the contract](../docs/contract/SPEC.md). The web pages and the Unreal scene read them from here.",
        "",
        "**These files are regenerated by the command below and are never edited by hand.** A test (`validation/tests/test_published_packages.py`) checks that every package here passes the contract validator, which includes the checksum of every array.",
        "",
        "## How they were made",
        "",
        "| Item | Value |",
        "|---|---|",
        f"| Command | `{command}` |",
        f"| Code | commit `{commit}`" + (" **with uncommitted or untracked changes in the working tree** (as recorded in the provenance of the packages)" if dirty else " (clean working tree, as recorded in the provenance of every package)") + " |",
        f"| Generated | {summary['generated_utc']} |",
        f"| Scenario | `validation/sites/scenario.json` (`{scenario['scenario_id']}`): {len(sites)} sites, {w['start_utc']} to {w['end_utc']}, series step {w['step_s']:g} s |",
        f"| Contract | `{table['contract']['name']}` version {table['contract']['version']} |",
        f"| Terrain | `{sites[0]['inputs']['dem']['dem_set_id']}` |",
    ]
    for layer in sites[0]["inputs"]["dem"]["layers"]:
        recorded = f"data file sha256 `{layer['sha256']}`, {layer['source_url']}" if layer["sha256"] else "checksum and source URL are not recorded in the package; see `data/manifest/manifest.json`"
        lines.append(f"| Terrain layer | {layer['product_id']} {layer['version']}, {layer['pixel_m']:g} m; {recorded} |")
    lines += [
        f"| Kernel set | `{kernels.kernel_set_id()}`: " + ", ".join(entry["name"] for entry in kernel_manifest["kernels"]) + " |",
        f"| Station kernel group | `{kernels.station_kernel_set_id()}`: " + ", ".join(entry["name"] for entry in kernel_manifest["station_kernels"]) + " |",
        f"| Body-fixed frame | `{table['frame']}`, aberration correction `{table['aberration_correction']}` |",
        f"| Size | {size / 1e6:.1f} MB in {sum(1 for f in root.rglob('*') if f.is_file())} files (without this file) |",
        "",
        "Kernel checksums are in `core/lsncore/ephem/kernel_manifest.json`; the terrain files are described in `data/manifest/manifest.json`.",
        "",
        "## Content",
        "",
        "`index.json` lists the packages. Paths are relative to this folder.",
        "",
        "| Kind | Package | Site | Status | Path |",
        "|---|---|---|---|---|",
        f"| direction table | `{table['package_id']}` | all sites | {table['status']} | `direction_table/{table['package_id']}` |",
    ]
    for m in sites:
        s = m["site"]
        lines.append(f"| site | `{m['package_id']}` | {s['name']} ({s['lat_deg']:.5f}, {s['lon_deg']:.5f}) | {m['status']} | `site/{s['site_id']}/{m['package_id']}` |")
    lines += [
        "",
        "Every site package holds the 360 degree terrain horizon for six observer heights and, for the time window, the direction series of the Sun and the Earth, rise and set events, visibility windows (including eclipses of the Sun by the Earth and per-station direct-to-Earth windows) and metrics, each with its method card.",
        "",
        "## What these numbers are",
        "",
        "- The sites are project candidate points derived from LOLA and IAU crater outlines by the data stream; **they are not official landing sites**.",
        "- **Unverified against an independent illumination product or mission record.** The ephemeris, the eclipse contacts and the ground-station geometry are validated (`validation/card/validation_card.md`); the terrain horizon has passed the core stream's own tests. Every number carries a method card with its validation status and limits; a viewer must show `unverified` where a card says so.",
        "- Where an event is set by terrain closer than about 1 km, the 20 m elevation grid limits its accuracy; the event carries `obstacle_distance_m`.",
        "- A summary per site and observer height is in `validation/sites/results/site_summary.md`.",
        "",
        "## Checking and regenerating",
        "",
        "```",
        "python -m lsncore validate packages/index.json packages/direction_table/* packages/site/*/*",
        "python -m validation.sites.run data/sites/sites.json --publish",
        "```",
        "",
        "Regenerating needs the LOLA products under `LSN_DATA_ROOT` and the kernels (`python -m lsncore.ephem.fetch_kernels`). Package ids depend only on the request and the data versions, so the same request on the same data gives the same ids.",
    ]
    (root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sites_file")
    parser.add_argument("--publish", action="store_true", help="replace the published packages in packages/ and write their README")
    parser.add_argument("--out", default=str(REPO / "build" / "packages" / "sites"))
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    args = parser.parse_args()
    records = json.loads(Path(args.sites_file).read_text(encoding="utf-8"))["sites"]
    import lsn_data

    terrain = TerrainWithFileProvenance(open_lola(), lsn_data.open_terrain().provenance())
    scenario = build_scenario(records, terrain.describe()["dem_set_id"], args.start, args.end)
    (HERE / "scenario.json").write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")
    out = STAGING if args.publish else Path(args.out)
    if args.publish and out.exists():
        shutil.rmtree(out)
    t0 = time.perf_counter()
    written = run_scenario(scenario, out, terrain)
    elapsed = time.perf_counter() - t0
    for path in written:
        validate_package(path)
    sites = [summarise(path) for path in written if read_package(path).manifest["kind"] == "site"]
    summary = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "window": scenario["time_window"],
        "thresholds": THRESHOLDS,
        "dem_set_id": sites[0]["dem_set_id"],
        "kernel_set_id": kernels.kernel_set_id(),
        "direction_table_id": sites[0]["direction_table_id"],
        "run_time_s": elapsed,
        "status": "unverified against an independent illumination product or mission record",
        "sites": sites,
    }
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "site_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (HERE / "results" / "site_summary.md").write_text(to_markdown(summary), encoding="utf-8")
    if args.publish:
        _clear_published(PUBLISHED)
        PUBLISHED.mkdir(exist_ok=True)
        for name in ("direction_table", "site"):
            shutil.copytree(out / name, PUBLISHED / name)
        shutil.copy2(out / "index.json", PUBLISHED / "index.json")
        published = [PUBLISHED / path.relative_to(out) for path in written]
        sites_arg = Path(args.sites_file).as_posix()
        write_readme(PUBLISHED, published, scenario, summary, f"python -m validation.sites.run {sites_arg} --publish")
        out = PUBLISHED
    print(f"{len(written)} packages in {elapsed:.1f} s -> {out}")
    for site in sites:
        row = site["per_height"][site["default_height_index"]]
        print(
            f"{site['site_id']:26s} {site['status']:8s} sun {100 * row['sun_visible_share']:.1f} %  longest outage {row['sun_longest_outage_h']:.1f} h  "
            f"earth {100 * row['earth_visible_share']:.1f} %  events sun {row['sun_events']} earth {row['earth_events']}  timings {site['timings_s']}"
        )


if __name__ == "__main__":
    main()
