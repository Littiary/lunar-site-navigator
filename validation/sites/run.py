"""End-to-end run for the south-polar site records of the data stream.

Builds one scenario with every site record, runs the core pipeline (LOLA terrain horizon
-> SPICE direction table with the orientation of the Earth -> events, windows, countdowns
-> obstacles, lunar-day calendar, landing windows for the example requirements,
uncertainty band and landing-ellipse survey, mast-height trade, terrain patches for
drawing, complementary site pairs), validates every package against the contract and
writes a summary. The scenario and the summary are kept in this folder.

Usage (from the repository root, with the LOLA data under LSN_DATA_ROOT)::

    python -m validation.sites.run data/sites/sites.json --write-scenario
    python -m validation.sites.run data/sites/sites.json --publish
    python -m validation.sites.run data/sites/sites.json [--out FOLDER] [--start UTC] [--end UTC]

``--jobs N`` sets the number of processes (default: half the processors, at most eight).
The sites are computed side by side; the packages are the same for any number of jobs.

``--publish`` replaces the published packages in ``packages/`` at the repository root
(the folder the web pages and the Unreal scene read) and writes ``packages/README.md``,
the scenario file and the summary of this folder. The packages are first written to a
staging folder under ``build/`` (not under version control) and then copied, so that
writing them does not itself make the working tree differ from the commit recorded in
their provenance. Commit all code changes before publishing, including the scenario
file if the scenario changed (``--write-scenario`` writes it without computing anything).

Without ``--publish`` nothing in this folder or in ``packages/`` is touched: packages,
scenario and summary go to ``--out`` (default ``build/packages/sites``).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from lsncore.contract import contract_header, read_package, validate_document, validate_package
from lsncore.dem import open_lola
from lsncore.ephem import kernels
from lsncore.pipeline import run_scenario
from lsncore.scenario import requirement_presets

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PUBLISHED = REPO / "packages"
STAGING = REPO / "build" / "packages" / "publish-staging"
DEFAULT_START = "2026-11-14T00:00:00.000Z"
DEFAULT_END = "2028-11-14T00:00:00.000Z"

# Stated assumptions of the published scenario. They are inputs, chosen by the team to
# show what follows from them (the numbers of docs/method/uncertainty.md and calendar.md).
# They are not properties of the elevation data, of a lander or of any mission.
HORIZON_ERROR_DEG = 0.05
DEM_HEIGHT_ERROR_M = 1.0
LANDING_ELLIPSE = {"semi_major_m": 100.0, "semi_minor_m": 100.0, "azimuth_deg": 0.0, "points": 13}
PLANNED_LANDING_UTC = "2027-01-10T00:00:00.000Z"
NEAR_TERRAIN_M = 1000.0
PACKAGE_FOLDERS = ("direction_table", "site", "site_pairs")
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


def build_scenario(records: list, dem_set_id: str, start_utc: str, end_utc: str) -> dict:
    scenario = {
        "contract": contract_header(),
        "kind": "scenario",
        "scenario_id": "south-polar-sites",
        "title": "Three south-polar candidate points, 24 months from the hackathon weekend",
        "description": "Site records of the data stream (derived from LOLA and IAU crater outlines; not official landing sites). Real LOLA terrain, SPICE ephemeris. "
        "The requirements are the team's examples, not requirements of NASA or of any mission; the horizon error, the terrain height error, the landing ellipse "
        "and the planned landing time are stated assumptions chosen by the team to show what follows from them.",
        "synthetic": False,
        "sites": [
            {
                "site_id": record["site_id"].replace("_", "-"),
                "name": record["name"],
                "lat_deg": record["lat_deg"],
                "lon_deg": record["lon_deg_east"],
                "landing_utc": PLANNED_LANDING_UTC,
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
        "requirements": list(requirement_presets().values()),
        "uncertainty": {"horizon_error_deg": HORIZON_ERROR_DEG, "dem_height_error_m": DEM_HEIGHT_ERROR_M, "landing_ellipse": dict(LANDING_ELLIPSE)},
    }
    validate_document(scenario)
    return scenario


def _spread(values: list, pick: list) -> list:
    """Least, median and largest of ``values`` at the positions ``pick``, in hours."""
    chosen = sorted(values[k] for k in pick)
    if not chosen:
        return [None, None, None]
    middle = chosen[len(chosen) // 2] if len(chosen) % 2 else 0.5 * (chosen[len(chosen) // 2 - 1] + chosen[len(chosen) // 2])
    return [chosen[0] / 3600.0, middle / 3600.0, chosen[-1] / 3600.0]


def summarise_planning(manifest: dict) -> dict:
    """Obstacles, lunar-day calendar, landing windows, uncertainty and height trade at the default observer height."""
    timeline, horizon = manifest["timeline"], manifest["horizon"]
    hd = horizon["default_height_index"]
    metrics = {x["id"]: x["value"] for x in timeline["metrics"] if x["height_index"] == hd}
    out = {"observer_height_m": horizon["observer_heights_m"][hd]}

    out["terrain_against_smooth_sphere"] = {
        body: {
            "visible_h": metrics[f"{body}_visible_s"] / 3600.0,
            "visible_over_a_smooth_sphere_h": metrics[f"{body}_visible_smooth_sphere_s"] / 3600.0,
            "lost_to_terrain_h": metrics[f"{body}_lost_to_terrain_s"] / 3600.0,
            "gained_from_terrain_h": metrics[f"{body}_gained_from_terrain_s"] / 3600.0,
        }
        for body in ("sun", "earth")
    }
    out["largest_obstacles_of_the_sun"] = [
        {
            "lost_h": b["lost_s"] / 3600.0,
            "share_of_lost": b["share_of_lost"],
            "peak_azimuth_deg": b["peak_azimuth_deg"],
            "peak_elevation_deg": b["peak_elevation_deg"],
            "peak_distance_m": b["peak_distance_m"],
            "near_field": b["near_field"],
        }
        for b in [b for b in timeline["blockers"] if b["body"] == "SUN" and b["height_index"] == hd][:3]
    ]
    out["obstacle_count"] = sum(o["height_index"] == hd for o in horizon["obstacles"])

    calendar = timeline["calendar"]
    complete = [period["index"] for period in calendar["periods"] if period["complete"]]
    per_day = {q["id"]: q["values"][hd] for q in calendar["quantities"]}
    out["lunar_days"] = {
        "periods": len(calendar["periods"]),
        "complete": len(complete),
        "sun_visible_h_least_median_most": _spread(per_day["sun_visible_s"], complete),
        "sun_longest_outage_h_least_median_most": _spread(per_day["sun_longest_outage_s"], complete),
        "earth_visible_h_least_median_most": _spread(per_day["earth_visible_s"], complete),
    }

    labels = {r["id"]: r["label"] for r in manifest["request"]["timeline"]["requirements"]}
    out["landing_windows"] = [
        {
            "requirement_id": o["requirement_id"],
            "label": labels[o["requirement_id"]],
            "window_count": o["window_count"],
            "feasible_fraction": o["feasible_fraction"],
            "longest_window_d": o["longest_window_s"] / 86400.0,
            "median_window_d": None if o["median_window_s"] is None else o["median_window_s"] / 86400.0,
            "latest_landing_utc": o["latest_landing_utc"],
            "planned_landing": None if o["planned_landing"] is None else {
                "utc": o["planned_landing"]["utc"],
                "feasible": o["planned_landing"]["feasible"],
                "slip_tolerance_d": o["planned_landing"]["slip_tolerance_s"] / 86400.0,
                "slip_tolerance_is_lower_bound": o["planned_landing"]["slip_tolerance_is_lower_bound"],
                "wait_d": None if o["planned_landing"]["wait_s"] is None else o["planned_landing"]["wait_s"] / 86400.0,
            },
        }
        for o in timeline["opportunities"]
        if o["height_index"] == hd
    ]

    stated = timeline["uncertainty"]
    ellipse = stated["landing_ellipse"]
    out["uncertainty"] = {
        "stated_horizon_error_deg": stated["horizon_error"].get("error_deg"),
        "stated_terrain_height_error_m": stated["horizon_error"].get("dem_height_error_m"),
        "applied_horizon_error_deg_min_median_max": [stated["horizon_error"]["applied_error_deg"][k] for k in ("min", "median", "max")],
        "visible_h": {
            body: {
                "certain": metrics[f"{body}_visible_certain_s"] / 3600.0,
                "possible": metrics[f"{body}_visible_possible_s"] / 3600.0,
                "uncertain": metrics[f"{body}_visible_uncertain_s"] / 3600.0,
            }
            for body in ("sun", "earth")
        },
        "landing_ellipse": {
            "semi_major_m": ellipse["semi_major_m"],
            "semi_minor_m": ellipse["semi_minor_m"],
            "points": len(ellipse["points"]),
            "visible_h": {body: {k[:-2]: v / 3600.0 for k, v in ellipse["visible_s"][body.upper()].items()} for body in ("sun", "earth")},
        },
    }

    trade = {q["id"]: q for q in timeline["height_trade"]["quantities"]}
    out["height_trade"] = {
        "observer_heights_m": timeline["height_trade"]["observer_heights_m"],
        "sun_visible_h": [v / 3600.0 for v in trade["sun_visible_s"]["values"]],
        "sun_visible_change_h": [v / 3600.0 for v in trade["sun_visible_s"]["change_s"]],
        "sun_longest_outage_h": [v / 3600.0 for v in trade["sun_longest_outage_s"]["values"]],
        "sun_least_lunar_day_h": [v / 3600.0 for v in trade["sun_least_lunar_day_s"]["values"]],
    }
    return out


def summarise_pairs(package_dir: Path) -> dict:
    manifest = read_package(package_dir).manifest
    names = {s["site_id"]: s["name"] for s in manifest["sites"]}
    pairs = []
    for pair in manifest["pairs"]:
        rows = {row["window"]: row for row in pair["windows"]}
        pairs.append({
            "site_a": pair["site_a"],
            "site_b": pair["site_b"],
            "names": [names[pair["site_a"]], names[pair["site_b"]]],
            "distance_km": pair["distance_m"] / 1000.0,
            "windows": {
                window: {
                    "a_share": row["a_s"] / (row["either_s"] + row["neither_s"]),
                    "b_share": row["b_s"] / (row["either_s"] + row["neither_s"]),
                    "either_share": row["either_fraction"],
                    "longest_neither_h": row["longest_neither_s"] / 3600.0,
                    "gain_over_better_h": row["gain_over_better_s"] / 3600.0,
                    "covered_share_of_better_outage": row["covered_share_of_better_outage"],
                }
                for window, row in rows.items()
            },
        })
    return {"package_id": manifest["package_id"], "content_sha256": manifest["content_sha256"], "observer_heights_m": [s["observer_height_m"] for s in manifest["sites"]], "pairs": pairs}


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
        "terrain_source": {key: m["horizon"]["terrain_source"][key] for key in ("at_site", "resolution_class", "products")},
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
        "planning": summarise_planning(m),
    }


def to_markdown(summary: dict) -> str:
    w = summary["window"]
    lines = [
        "# End-to-end results: three south-polar candidate points",
        "",
        f"Generated {summary['generated_utc']} by `validation/sites/run.py`. Do not edit by hand.",
        "",
        f"- Window: {w['start_utc']} to {w['end_utc']} (UTC). Countdowns count from the planned landing time of the scenario, {summary['stated']['planned_landing_utc']}.",
        f"- **Inputs chosen by the team, not properties of the data or of a mission**: the three example requirements on the landing time (`docs/contract/presets/requirements.json`; they are not requirements of NASA or of any mission), "
        f"a horizon error of {summary['stated']['horizon_error_deg']:g} deg, a terrain height error of {summary['stated']['dem_height_error_m']:g} m, a landing circle of {summary['stated']['landing_ellipse']['semi_major_m']:g} m radius "
        f"sampled at {summary['stated']['landing_ellipse']['points']} points, and the planned landing time. The numbers that follow from them say what would hold if they were true.",
        f"- Terrain: `{summary['dem_set_id']}`, search radius 300 km, azimuth step 0.25 deg. Ephemeris: kernel set `{summary['kernel_set_id']}`, direction table `{summary['direction_table_id']}`.",
        "- Sun visible = any part of the disc above the terrain horizon. Earth visible = centre of the disc above the terrain horizon.",
        "- The points are project candidates derived from LOLA and IAU crater outlines by the data stream; **they are not official landing sites**.",
        "- **Status.** The method behind these numbers reproduces the published LOLA illumination maps of NASA Goddard at 100 points on terrain of the same resolution (`validation/pgda`), and the ephemeris is validated (see the validation card). Of two dated LROC images, the shadowed state of the south pole agrees; the comparison along an image strip fails its registered criterion (89.3 % agreement against 90 %; the image rule reads dimly lit ground as shadow), see `validation/lro_images`. The numbers of these three sites themselves have no independent counterpart: they use the finer 20 m terrain, a 24-month window and several observer heights, and no source gives rise and set times for these points.",
        "",
    ]
    for site in summary["sites"]:
        sun_lo, sun_hi = site["sun_centre_elevation_range_deg"]
        earth_lo, earth_hi = site["earth_centre_elevation_range_deg"]
        lines += [
            f"## {site['name']}",
            "",
            f"{abs(site['lat_deg']):.5f} deg S, {site['lon_deg']:.5f} deg E, terrain height {site['surface_height_m']:.1f} m above the 1737.4 km sphere. "
            f"Package `{site['package_id']}`, status `{site['status']}`. Terrain: {_terrain_source_text(site['terrain_source'])}. Sun centre elevation {sun_lo:.2f} to {sun_hi:.2f} deg; "
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
        lines += _planning_markdown(site["planning"])
    lines += _pairs_markdown(summary["site_pairs"])
    lines += [
        "## Limits",
        "",
        "- Shares and longest outages describe this 24-month window only; they are not multi-year averages.",
        "- Landing windows hold for the stated example requirements only; the tool reports when a stated requirement holds, it does not know what a mission needs. Landings later than the end of the window minus the mission duration cannot be judged.",
        "- The uncertainty band and the landing-circle survey show what follows from the stated horizon error, height error and circle. The stated numbers are not measured errors of the elevation model, and the survey over 13 points is not a probability.",
        "- The site pairs say when at least one of two sites sees the body; they do not say that power or data can be moved between the sites.",
        "- Where an event is set by terrain closer than about 1 km, the 20 m elevation grid, not the method, limits the accuracy, and the event time can be off by hours. The column on near terrain counts those events.",
        "- Event times are numerically exact to 0.25 s for the given horizon profile; that is not their physical accuracy.",
        "- The direct-link figures are geometric: a station above the lunar terrain horizon and the site above the station's elevation limit. No link budget, no azimuth-dependent station masks, no scheduling, no multipath near the lunar horizon. A relay need of 2 means that for part of the time no ground station at all can be reached.",
        "- A countdown marked 'at least' has no set inside the computed window.",
        "- The shares of time above are cut by the terrain only. Eclipses of the Sun by the Earth are listed per site (opaque Earth, no atmosphere) and are in the package as the windows 'sun_eclipsed_by_earth', 'sun_totally_eclipsed_by_earth' and 'sun_lit'.",
    ]
    return "\n".join(lines) + "\n"


def _terrain_source_text(source: dict) -> str:
    """Which elevation products served a site, in one sentence."""
    at = source["at_site"]
    horizon = ", ".join(f"{p['product_id']} ({p['pixel_m']:g} m) in {100 * p['azimuth_share']:.1f} % of the azimuths" for p in source["products"])
    return f"the height at the site is read from {at['product_id']} ({at['pixel_m']:g} m pixels, resolution class {source['resolution_class']}); the horizon at the default observer height is set by {horizon}"


def _three(values: list, unit: str = "h") -> str:
    return "n/a" if values[0] is None else ", ".join(f"{v:.0f}" for v in values) + f" {unit}"


def _planning_markdown(plan: dict) -> list:
    height = plan["observer_height_m"]
    sun, earth = plan["terrain_against_smooth_sphere"]["sun"], plan["terrain_against_smooth_sphere"]["earth"]
    lines = [
        f"**What the terrain costs (observer {height:g} m).** Over a smooth sphere through the site the Sun would be visible for {sun['visible_over_a_smooth_sphere_h']:.0f} h of the window; "
        f"the terrain takes {sun['lost_to_terrain_h']:.0f} h and gives {sun['gained_from_terrain_h']:.0f} h (terrain below the smooth horizon), leaving {sun['visible_h']:.0f} h. "
        f"Earth: {earth['visible_over_a_smooth_sphere_h']:.0f} h, minus {earth['lost_to_terrain_h']:.0f} h, plus {earth['gained_from_terrain_h']:.0f} h, leaving {earth['visible_h']:.0f} h.",
        "",
    ]
    if plan["largest_obstacles_of_the_sun"]:
        lines += ["| Obstacle of the Sun (largest cost first) | Costs | Share of the lost time | Highest point: azimuth, elevation, distance | Within 1 km |", "|---|---|---|---|---|"]
        for k, b in enumerate(plan["largest_obstacles_of_the_sun"], start=1):
            lines.append(f"| {k} | {b['lost_h']:.0f} h | {100 * b['share_of_lost']:.0f} % | {b['peak_azimuth_deg']:.1f} deg, {b['peak_elevation_deg']:+.2f} deg, {b['peak_distance_m'] / 1000.0:.1f} km | {'yes: depends on single pixels of the elevation model' if b['near_field'] else 'no'} |")
        lines.append("")
    days = plan["lunar_days"]
    lines += [
        f"**Lunar days.** {days['periods']} in the window, {days['complete']} of them complete. Per complete lunar day (least, median, most): Sun visible {_three(days['sun_visible_h_least_median_most'])}; "
        f"longest stretch without the Sun {_three(days['sun_longest_outage_h_least_median_most'])}; Earth visible {_three(days['earth_visible_h_least_median_most'])}.",
        "",
        "| Example requirement (not a requirement of NASA or of any mission) | Landing windows | Share of the judged range that is a feasible landing time | Longest, median window | Planned landing |",
        "|---|---|---|---|---|",
    ]
    for o in plan["landing_windows"]:
        planned = o["planned_landing"]
        if planned is None:
            state = "none stated"
        elif planned["feasible"]:
            state = f"{planned['utc'][:10]}: feasible; can slip {'at least ' if planned['slip_tolerance_is_lower_bound'] else ''}{planned['slip_tolerance_d']:.1f} d"
        elif planned["wait_d"] is None:
            state = f"{planned['utc'][:10]}: not feasible; no later window in the range"
        else:
            state = f"{planned['utc'][:10]}: not feasible; next window in {planned['wait_d']:.1f} d"
        median = "n/a" if o["median_window_d"] is None else f"{o['median_window_d']:.1f} d"
        lines.append(f"| `{o['requirement_id']}`: {o['label'].split(': ', 1)[-1]} | {o['window_count']} | {100 * o['feasible_fraction']:.1f} % | {o['longest_window_d']:.1f} d, {median} | {state} |")
    u = plan["uncertainty"]
    lo, mid, hi = u["applied_horizon_error_deg_min_median_max"]
    ellipse = u["landing_ellipse"]
    lines += [
        "",
        f"**If the horizon were wrong by the stated amount** ({u['stated_horizon_error_deg']:g} deg everywhere plus what {u['stated_terrain_height_error_m']:g} m of terrain height error gives at the distance of the limiting terrain: "
        f"{lo:.3f} to {hi:.3f} deg, median {mid:.3f} deg): Sun visible for certain {u['visible_h']['sun']['certain']:.0f} h, possibly {u['visible_h']['sun']['possible']:.0f} h ({u['visible_h']['sun']['uncertain']:.0f} h uncertain); "
        f"Earth for certain {u['visible_h']['earth']['certain']:.0f} h, possibly {u['visible_h']['earth']['possible']:.0f} h ({u['visible_h']['earth']['uncertain']:.0f} h uncertain).",
        "",
        f"**Inside the stated landing circle** ({ellipse['semi_major_m']:g} m radius, {ellipse['points']} points, each with its own terrain horizon): Sun visible {ellipse['visible_h']['sun']['centre']:.0f} h at the site; "
        f"{ellipse['visible_h']['sun']['min']:.0f} h least, {ellipse['visible_h']['sun']['median']:.0f} h median, {ellipse['visible_h']['sun']['max']:.0f} h most over the points. "
        f"Earth: {ellipse['visible_h']['earth']['centre']:.0f} h at the site; {ellipse['visible_h']['earth']['min']:.0f}, {ellipse['visible_h']['earth']['median']:.0f}, {ellipse['visible_h']['earth']['max']:.0f} h.",
        "",
        "| Observer height | Sun visible in the window | Change against the surface | Longest time without the Sun | Sun visible in the least sunlit complete lunar day |",
        "|---|---|---|---|---|",
    ]
    trade = plan["height_trade"]
    for k, h in enumerate(trade["observer_heights_m"]):
        lines.append(f"| {h:g} m | {trade['sun_visible_h'][k]:.0f} h | {trade['sun_visible_change_h'][k]:+.0f} h | {trade['sun_longest_outage_h'][k]:.1f} h | {trade['sun_least_lunar_day_h'][k]:.0f} h |")
    lines.append("")
    return lines


def _pairs_markdown(pairs: dict) -> list:
    lines = [
        "## Two sites together",
        "",
        f"Package `{pairs['package_id']}`. Each site at its default observer height. 'Either' is the share of the window in which at least one of the two sites sees the body.",
        "",
        "| Sites | Distance | Sun: each alone | Sun: either | Longest time with the Sun at neither | What the second site adds | Earth: either | Longest time with the Earth at neither |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for pair in pairs["pairs"]:
        sun, earth = pair["windows"]["sun_visible"], pair["windows"]["earth_visible"]
        covered = "" if sun["covered_share_of_better_outage"] is None else f" ({100 * sun['covered_share_of_better_outage']:.0f} % of the better site's dark time)"
        lines.append(
            f"| {pair['names'][0]} and {pair['names'][1]} | {pair['distance_km']:.0f} km | {100 * sun['a_share']:.1f} %, {100 * sun['b_share']:.1f} % | {100 * sun['either_share']:.1f} % | {sun['longest_neither_h']:.0f} h | "
            f"{sun['gain_over_better_h']:.0f} h{covered} | {100 * earth['either_share']:.1f} % | {earth['longest_neither_h']:.0f} h |"
        )
    lines.append("")
    return lines


def _clear_published(root: Path) -> None:
    """Remove the previously published packages (only what the pipeline itself writes)."""
    for name in PACKAGE_FOLDERS:
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
    pairs = [m for m in manifests if m["kind"] == "site_pairs"]
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
        "| Stated inputs of the scenario | "
        + "requirements " + ", ".join(f"`{r['id']}`" for r in scenario["requirements"]) + " (the examples of `docs/contract/presets/requirements.json`; not requirements of NASA or of any mission); "
        + f"horizon error {scenario['uncertainty']['horizon_error_deg']:g} deg; terrain height error {scenario['uncertainty']['dem_height_error_m']:g} m; "
        + f"landing circle of {scenario['uncertainty']['landing_ellipse']['semi_major_m']:g} m radius, {scenario['uncertainty']['landing_ellipse']['points']} points; "
        + f"planned landing {scenario['sites'][0]['landing_utc']} at every site. All chosen by the team to show what follows from them |",
        f"| Contract | `{table['contract']['name']}` version {table['contract']['version']} |",
        f"| Terrain | `{sites[0]['inputs']['dem']['dem_set_id']}` |",
    ]
    for layer in sites[0]["inputs"]["dem"]["layers"]:
        recorded = f"data file sha256 `{layer['sha256']}`, {layer['source_url']}" if layer["sha256"] else "checksum and source URL are not recorded in the package; see `data/manifest/manifest.json`"
        lines.append(f"| Terrain layer | {layer['product_id']} {layer['version']}, {layer['pixel_m']:g} m; {recorded} |")
    for m in sites:
        lines.append(f"| Terrain that served {m['site']['name']} | {_terrain_source_text(m['horizon']['terrain_source'])[0].upper() + _terrain_source_text(m['horizon']['terrain_source'])[1:]} |")
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
    for m in pairs:
        lines.append(f"| site pairs | `{m['package_id']}` | every two of the {len(m['sites'])} sites | {m['status']} | `site_pairs/{m['package_id']}` |")
    lines += [
        "",
        "Every site package holds, each with its method card:",
        "",
        "- the 360 degree terrain horizon for six observer heights, with the position and height of the limiting terrain at every azimuth, the list of obstacles (`horizon.obstacles`) and the elevation products that served the site with their resolution class (`horizon.terrain_source`);",
        "- for the time window, the direction series of the Sun and the Earth, the visible fraction of each disc, the lit fraction of the Sun (terrain and eclipses by the Earth together) and, for every sample, the horizon sample that limits the view (`blocker_azimuth_index`);",
        "- rise and set events with their range for the stated horizon error, visibility windows (including eclipses of the Sun by the Earth and per-station direct-to-Earth windows) and metrics;",
        "- the obstacles that cost visible time compared with a smooth sphere (`timeline.blockers`);",
        "- the lunar-day calendar (`timeline.calendar`) and, for each example requirement and observer height, the landing windows and the slip report of the planned landing (`timeline.opportunities`);",
        "- the uncertainty band for the stated horizon error and the survey of the stated landing circle (`timeline.uncertainty`, `series.<BODY>.ellipse_visible_share`);",
        "- the mast-height trade (`timeline.height_trade`);",
        "- three terrain patches around the site for drawing (`terrain.patches`: 4, 16 and 64 km wide). They are for drawing only: visibility, events and windows come from the timeline, which was computed on the finest elevation data.",
        "",
        "The direction table also holds the orientation of the Earth for every record (`earth_view`), so that a viewer can turn a textured Earth the right way.",
        "",
        "The site-pairs package compares every two sites at their default observer height: when at least one of them sees the Sun or the Earth, and the joint outages.",
        "",
        "## What these numbers are",
        "",
        "- The sites are project candidate points derived from LOLA and IAU crater outlines by the data stream; **they are not official landing sites**.",
        "- The method behind these numbers reproduces the published LOLA illumination maps of NASA Goddard at 100 points on terrain of the same resolution, and the ephemeris, the eclipse contacts and the ground-station geometry are validated against independent sources (`validation/card/validation_card.md`). Of two dated LROC images, the shadowed state of the south pole agrees; the comparison along an image strip fails its registered criterion (89.3 % agreement against 90 %; the image rule reads dimly lit ground as shadow), see `validation/lro_images`. **The numbers of these sites themselves have no independent counterpart**: they use the finer 20 m terrain, a 24-month window and several observer heights, and no source gives rise and set times for these points. Every number carries a method card with its validation status and limits; a viewer must show `unverified` where a card says so.",
        "- **The requirements, the horizon error, the terrain height error, the landing circle and the planned landing time are inputs chosen by the team**, not requirements of NASA or of any mission and not measured errors. A viewer must show the label of a requirement next to every number derived from it, and must present the uncertainty band and the landing-circle survey as what follows from stated assumptions.",
        "- Where an event is set by terrain closer than about 1 km, the 20 m elevation grid limits its accuracy; the event carries `obstacle_distance_m`, and an obstacle within 1 km carries `near_field`.",
        "- A summary per site and observer height is in `validation/sites/results/site_summary.md`.",
        "",
        "## Checking and regenerating",
        "",
        "```",
        "python -m lsncore validate packages/index.json packages/direction_table/* packages/site/*/* packages/site_pairs/*",
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
    parser.add_argument("--write-scenario", action="store_true", help="write validation/sites/scenario.json for the published scenario and stop")
    parser.add_argument("--out", default=str(REPO / "build" / "packages" / "sites"))
    parser.add_argument("--jobs", type=int, default=0, help="processes the run may use (default: half the processors, at most 8); the packages do not depend on it")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    args = parser.parse_args()
    records = json.loads(Path(args.sites_file).read_text(encoding="utf-8"))["sites"]
    terrain = open_lola()
    scenario = build_scenario(records, terrain.describe()["dem_set_id"], args.start, args.end)
    out = STAGING if args.publish else Path(args.out)
    if args.publish and out.exists():
        shutil.rmtree(out)
    if args.publish or args.write_scenario:
        if (args.start, args.end) != (DEFAULT_START, DEFAULT_END):
            parser.error("the published scenario uses the default time window; --start and --end are for runs that are not published")
        (HERE / "scenario.json").write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8", newline="\n")
        if args.write_scenario:
            print((HERE / "scenario.json").relative_to(REPO).as_posix())
            return
        # The packages record the commit and whether the working tree differs from it. A
        # published package must name a clean commit, so stop before the long computation.
        changed = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True).stdout.strip()
        if changed:
            parser.error(
                "the working tree differs from the last commit, so the packages would record uncommitted changes:\n"
                + changed
                + "\nCommit first. If validation/sites/scenario.json is listed, the scenario itself changed (for example its contract version after a merge): "
                "commit it and publish again."
            )
    else:
        out.mkdir(parents=True, exist_ok=True)
        (out / "scenario.json").write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8", newline="\n")
    results = HERE / "results" if args.publish else out / "summary"
    t0 = time.perf_counter()
    jobs = args.jobs if args.jobs > 0 else max(1, min((os.cpu_count() or 2) // 2, 8))
    written = run_scenario(scenario, out, terrain, jobs=jobs, terrain_factory=open_lola)
    elapsed = time.perf_counter() - t0
    for path in written:
        validate_package(path)
    kinds = {path: read_package(path).manifest["kind"] for path in written}
    sites = [summarise(path) for path in written if kinds[path] == "site"]
    (pairs_dir,) = [path for path in written if kinds[path] == "site_pairs"]
    summary = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "contract_version": read_package(pairs_dir).manifest["contract"]["version"],
        "window": scenario["time_window"],
        "stated": {**scenario["uncertainty"], "planned_landing_utc": PLANNED_LANDING_UTC, "requirements": [r["id"] for r in scenario["requirements"]]},
        "site_pairs": summarise_pairs(pairs_dir),
        "thresholds": THRESHOLDS,
        "dem_set_id": sites[0]["dem_set_id"],
        "kernel_set_id": kernels.kernel_set_id(),
        "direction_table_id": sites[0]["direction_table_id"],
        "run_time_s": elapsed,
        "status": "method checked against the published LOLA illumination maps on 60 m terrain (validation/pgda); one of two dated-image checks fails its registered criterion (validation/lro_images); the numbers of these sites themselves have no independent counterpart",
        "sites": sites,
    }
    results.mkdir(parents=True, exist_ok=True)
    (results / "site_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    (results / "site_summary.md").write_text(to_markdown(summary), encoding="utf-8", newline="\n")
    if args.publish:
        _clear_published(PUBLISHED)
        PUBLISHED.mkdir(exist_ok=True)
        for name in PACKAGE_FOLDERS:
            shutil.copytree(out / name, PUBLISHED / name)
        shutil.copy2(out / "index.json", PUBLISHED / "index.json")
        published = [PUBLISHED / path.relative_to(out) for path in written]
        sites_arg = Path(args.sites_file).as_posix()
        write_readme(PUBLISHED, published, scenario, summary, f"python -m validation.sites.run {sites_arg} --publish")
        out = PUBLISHED
    print(f"{len(written)} packages, contract {summary['contract_version']}, in {elapsed:.1f} s with {jobs} jobs -> {out}")
    for site in sites:
        row = site["per_height"][site["default_height_index"]]
        print(
            f"{site['site_id']:26s} {site['status']:8s} sun {100 * row['sun_visible_share']:.1f} %  longest outage {row['sun_longest_outage_h']:.1f} h  "
            f"earth {100 * row['earth_visible_share']:.1f} %  events sun {row['sun_events']} earth {row['earth_events']}  timings {site['timings_s']}"
        )


if __name__ == "__main__":
    main()
