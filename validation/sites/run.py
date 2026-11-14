"""End-to-end run for the published sites: the three project sites and the curated list.

Two scenarios are built from the site records of the data stream and run through the core
pipeline (terrain horizon with its obstacles -> SPICE direction table with the orientation
of the Earth -> events, windows, countdowns -> what the terrain costs, lunar-day calendar,
landing windows for the example requirements, mast-height trade, terrain patches):

* ``south-polar-sites``: the three project sites, with the 5 m near field, six observer
  heights, the uncertainty band of the sourced height-error model, the landing-circle
  survey, a planned landing and the site pairs;
* ``curated-sites``: the other sites of the curated list (past landings and one
  representative Artemis III point), without the near field, three observer heights, no
  stated uncertainty and no planned landing. Their pairs are not published.

The project sites are also computed without the near field (not published), so that the
summary can put the numbers before and after side by side. Every package is validated
against the contract. The scenarios and the summary are kept in this folder.

Usage (from the repository root, with the terrain under LSN_DATA_ROOT)::

    python -m validation.sites.run data/sites/sites.json --write-scenario
    python -m validation.sites.run data/sites/sites.json --publish
    python -m validation.sites.run data/sites/sites.json [--out FOLDER] [--start UTC] [--end UTC] [--only project|curated] [--no-before]

``--publish`` replaces the published packages in ``packages/`` at the repository root
(the folder the web pages and the Unreal scene read) and writes ``packages/README.md``,
the scenario files and the summary of this folder. The packages are first written to a
staging folder under ``build/`` (not under version control) and then copied, so that
writing them does not itself make the working tree differ from the commit recorded in
their provenance. Commit all code changes before publishing, including the scenario
files if a scenario changed (``--write-scenario`` writes them without computing anything).

Without ``--publish`` nothing in this folder or in ``packages/`` is touched: packages,
scenarios and summary go to ``--out`` (default ``build/packages/sites``).

``--jobs N`` sets the number of processes (default: half the processors, at most eight).
The sites are computed side by side; the packages are the same for any number of jobs.
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from lsncore.contract import contract_header, read_package, validate_document, validate_package, write_index
from lsncore.dem import open_lola, open_moon
from lsncore.ephem import kernels
from lsncore.pipeline import run_scenario
from lsncore.scenario import height_error_presets, requirement_presets

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PUBLISHED = REPO / "packages"
STAGING = REPO / "build" / "packages" / "publish-staging"
DEFAULT_START = "2026-11-14T00:00:00.000Z"
DEFAULT_END = "2028-11-14T00:00:00.000Z"

CURATED_SITES = REPO / "data" / "sites" / "curated_sites.json"
PROJECT_SCENARIO_ID = "south-polar-sites"
CURATED_SCENARIO_ID = "curated-sites"

# Stated inputs of the published scenarios. The landing circle and the planned landing time
# are chosen by the team to show what follows from them; they are not properties of the
# elevation data, of a lander or of any mission. The height-error model is the one the
# contract ships as default, measured by the data stream (docs/contract/presets).
LANDING_ELLIPSE = {"semi_major_m": 100.0, "semi_minor_m": 100.0, "azimuth_deg": 0.0, "points": 13}
PLANNED_LANDING_UTC = "2027-01-10T00:00:00.000Z"
PROJECT_HEIGHTS_M = [0.0, 1.0, 2.0, 5.0, 10.0, 20.0]
CURATED_HEIGHTS_M = [0.0, 2.0, 10.0]
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


def stated_height_error_model() -> dict:
    """The height-error model the contract ships as default (sourced; see its 'source' field)."""
    presets = height_error_presets()
    return presets["models"][presets["default"]]


def build_scenario(records: list, dem_set_id: str, start_utc: str, end_utc: str) -> dict:
    """The three project sites, with every option."""
    scenario = {
        "contract": contract_header(),
        "kind": "scenario",
        "scenario_id": PROJECT_SCENARIO_ID,
        "title": "Three south-polar candidate points, 24 months from the hackathon weekend",
        "description": "Site records of the data stream (derived from LOLA and IAU crater outlines; not official landing sites). Real LOLA terrain, SPICE ephemeris. "
        "The requirements are the team's examples, not requirements of NASA or of any mission; the landing circle and the planned landing time are stated "
        "assumptions chosen by the team to show what follows from them; the terrain height error is the sourced default model of the contract. Computed with the 5 m near field.",
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
        "observer_heights_m": PROJECT_HEIGHTS_M,
        "default_height_m": 2.0,
        "horizon": {"azimuth_step_deg": 0.25, "max_range_m": 300000.0},
        "time_window": {"start_utc": start_utc, "end_utc": end_utc, "step_s": 3600.0},
        "bodies": ["SUN", "EARTH"],
        "thresholds": THRESHOLDS,
        "mission_profile": None,
        "data": {"dem_set_id": dem_set_id, "kernel_set_id": kernels.kernel_set_id(), "direction_table_id": None},
        "requirements": list(requirement_presets().values()),
        "uncertainty": {"dem_height_error_model": stated_height_error_model(), "landing_ellipse": dict(LANDING_ELLIPSE)},
    }
    validate_document(scenario)
    return scenario


def build_curated_scenario(records: list, dem_set_id: str, start_utc: str, end_utc: str) -> dict:
    """The sites of the curated list that are not project sites: fewer observer heights, no stated uncertainty, no planned landing."""
    scenario = {
        "contract": contract_header(),
        "kind": "scenario",
        "scenario_id": CURATED_SCENARIO_ID,
        "title": "Curated list without the project sites: past landings and one representative Artemis III point, 24 months",
        "description": "Site records of the data stream (data/sites/curated_sites.json): past landing sites at the lander positions measured on LROC images, and one representative point "
        "of an Artemis III candidate region. Real terrain from every installed elevation product, without the 5 m near field; SPICE ephemeris. "
        "The requirements are the team's examples, not requirements of NASA or of any mission. No uncertainty is stated for these sites.",
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
            if record["category"] != "project_candidate"
        ],
        "observer_heights_m": CURATED_HEIGHTS_M,
        "default_height_m": 2.0,
        "horizon": {"azimuth_step_deg": 0.25, "max_range_m": 300000.0},
        "time_window": {"start_utc": start_utc, "end_utc": end_utc, "step_s": 3600.0},
        "bodies": ["SUN", "EARTH"],
        "thresholds": THRESHOLDS,
        "mission_profile": None,
        "data": {"dem_set_id": dem_set_id, "kernel_set_id": kernels.kernel_set_id(), "direction_table_id": None},
        "requirements": list(requirement_presets().values()),
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
    band = stated["horizon_error"]
    out["uncertainty"] = {
        "height_error_model": band["dem_height_error_model"]["id"],
        "height_error_model_label": band["dem_height_error_model"]["label"],
        "applied_height_error_m_min_median_max": [band["applied_height_error_m"][k] for k in ("min", "median", "max")],
        "applied_horizon_error_deg_min_median_max": [band["applied_error_deg"][k] for k in ("min", "median", "max")],
        "limiting_pixels": band["limiting_pixels"],
        "band_sources": band["sources"],
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
        "# End-to-end results: the three project sites, and the curated list",
        "",
        f"Generated {summary['generated_utc']} by `validation/sites/run.py`. Do not edit by hand.",
        "",
        f"- Window: {w['start_utc']} to {w['end_utc']} (UTC). Countdowns count from the planned landing time of the scenario, {summary['stated']['planned_landing_utc']}.",
        f"- **Inputs chosen by the team, not properties of the data or of a mission**: the three example requirements on the landing time (`docs/contract/presets/requirements.json`; they are not requirements of NASA or of any mission), "
        f"a landing circle of {summary['stated']['landing_ellipse']['semi_major_m']:g} m radius sampled at {summary['stated']['landing_ellipse']['points']} points, and the planned landing time. "
        "The numbers that follow from them say what would hold if they were true.",
        f"- **Stated terrain height error**: the model `{summary['stated']['dem_height_error_model']['id']}` shipped with the contract ({summary['stated']['dem_height_error_model']['label']}). "
        "It is the data stream's measurement of the elevation products against each other and the producers' own error maps, not a test against independent data.",
        "- The three sites are computed **with the 5 m near field**: inside the 5 m site rasters of the data stream the terrain is read from them, elsewhere from the 20 m and 60 m products. "
        "The section 'Before and after the 5 m near field' puts the 24-month numbers of both side by side.",
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
    if summary.get("near_field_before_after"):
        lines += _before_after_markdown(summary["near_field_before_after"])
    if summary.get("all_sites"):
        lines += _all_sites_markdown(summary["all_sites"], summary["size"])
    lines += [
        "## Limits",
        "",
        "- Shares and longest outages describe this 24-month window only; they are not multi-year averages.",
        "- Landing windows hold for the stated example requirements only; the tool reports when a stated requirement holds, it does not know what a mission needs. Landings later than the end of the window minus the mission duration cannot be judged.",
        "- The uncertainty band shows what follows from the stated height-error model: per azimuth the horizon is raised and lowered by the angle that height error spans at the distance of the limiting terrain. Every elevation product is built from LOLA returns, so an error common to all of them is in no band. The landing-circle survey over 13 points is not a probability.",
        "- The sites of the curated list other than the project sites carry no uncertainty band: the height-error model was measured on the polar products, and where a site is served by the 118 m product it is unresolved relief, not height error, that limits the horizon. Their packages carry the core's resolution warning.",
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
    h_lo, h_mid, h_hi = u["applied_height_error_m_min_median_max"]
    pixels = u["limiting_pixels"]
    ellipse = u["landing_ellipse"]
    lines += [
        "",
        f"**If the terrain were wrong by the stated height-error model** (`{u['height_error_model']}`: at the terrain points that set the horizon {h_lo:.2f} to {h_hi:.2f} m, median {h_mid:.2f} m, "
        f"which seen from the site is {lo:.3f} to {hi:.3f} deg, median {mid:.3f} deg; {100 * pixels['constrained']:.0f} % of those points lie on a pixel with a laser return, "
        f"{100 * pixels['interpolated']:.0f} % on interpolated ground): Sun visible for certain {u['visible_h']['sun']['certain']:.0f} h, possibly {u['visible_h']['sun']['possible']:.0f} h ({u['visible_h']['sun']['uncertain']:.0f} h uncertain); "
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


def describe_site(package_dir: Path, category: str) -> dict:
    """What a published site package carries and which terrain served it."""
    manifest = read_package(package_dir).manifest
    timeline, horizon = manifest["timeline"], manifest["horizon"]
    hd = horizon["default_height_index"]
    metrics = {x["id"]: x["value"] for x in timeline["metrics"] if x["height_index"] == hd}
    source = horizon["terrain_source"]
    stated = timeline.get("uncertainty") or {}
    request = manifest["request"]["timeline"]
    files = [f for f in Path(package_dir).iterdir() if f.is_file()]
    complete = [period["index"] for period in timeline["calendar"]["periods"] if period["complete"]]
    per_day = {q["id"]: q["values"][hd] for q in timeline["calendar"]["quantities"]}
    standard = [o for o in timeline.get("opportunities", []) if o["height_index"] == hd and o["requirement_id"] == "example-standard"]
    return {
        "site_id": manifest["site"]["site_id"],
        "name": manifest["site"]["name"],
        "category": category,
        "lat_deg": manifest["site"]["lat_deg"],
        "lon_deg": manifest["site"]["lon_deg"],
        "package_id": manifest["package_id"],
        "status": manifest["status"],
        "warnings": manifest["warnings"],
        "observer_heights_m": horizon["observer_heights_m"],
        "terrain_at_site": source["at_site"],
        "resolution_class": source["resolution_class"],
        "horizon_products": source["products"],
        "near_field": any(str(layer["product_id"]).startswith("LOLA5MPP") for layer in manifest["inputs"]["dem"]["layers"]),
        "uncertainty_band": stated.get("horizon_error", {}).get("dem_height_error_model", {}).get("id"),
        "landing_circle_survey": "landing_ellipse" in stated,
        "planned_landing_utc": request.get("landing_utc"),
        "requirements": [r["id"] for r in request.get("requirements", [])],
        "ground_stations": any(w["id"] == "earth_network_dsn" for w in timeline["windows"]),
        "sun_visible_share": metrics["sun_visible_fraction_of_time"],
        "earth_visible_share": metrics["earth_visible_fraction_of_time"],
        "sun_longest_outage_h": metrics["sun_longest_outage_s"] / 3600.0,
        "sun_visible_h_per_lunar_day_least_median_most": _spread(per_day["sun_visible_s"], complete),
        "landing_windows_example_standard": None if not standard else {"count": standard[0]["window_count"], "feasible_fraction": standard[0]["feasible_fraction"]},
        "size_bytes": sum(f.stat().st_size for f in files),
        "manifest_bytes": (Path(package_dir) / "manifest.json").stat().st_size,
    }


CATEGORY_TEXT = {
    "project_candidate": "project site",
    "past_landing": "past landing",
    "artemis_iii_candidate_region_representative": "representative point of an Artemis III candidate region",
}


def _product_text(product: dict) -> str:
    return f"{product['product_id']} ({product['pixel_m']:.0f} m)"


def _all_sites_rows(sites: list) -> list:
    lines = [
        "| Site | Kind | Height at the site read from | Class | Horizon at 2 m set by | Near field | Observer heights | Uncertainty band | Landing-circle survey | Planned landing | Size |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in sites:
        horizon = ", ".join(f"{_product_text(p)} {100 * p['azimuth_share']:.0f} %" for p in s["horizon_products"])
        lines.append(
            f"| {s['name']} (`{s['site_id']}`) | {CATEGORY_TEXT.get(s['category'], s['category'])} | {_product_text(s['terrain_at_site'])} | {s['resolution_class']} | {horizon} | "
            f"{'on' if s['near_field'] else 'off'} | {', '.join(f'{h:g}' for h in s['observer_heights_m'])} m | {'`' + s['uncertainty_band'] + '`' if s['uncertainty_band'] else 'none'} | "
            f"{'yes' if s['landing_circle_survey'] else 'no'} | {s['planned_landing_utc'][:10] if s['planned_landing_utc'] else 'none'} | {s['size_bytes'] / 1e6:.1f} MB |"
        )
    return lines


def _all_sites_markdown(sites: list, size: dict) -> list:
    lines = [
        "## All published sites",
        "",
        f"{len(sites)} site packages, {size['total_bytes'] / 1e6:.1f} MB with the direction table and the site pairs. Every package holds the horizon with its obstacles and terrain source, events, windows, countdowns, "
        "eclipses and the lit fraction of the Sun, ground-station windows, what the terrain costs, the lunar-day calendar, landing windows for the three example requirements, the height trade over its observer heights "
        "and three terrain patches. The columns say what differs.",
        "",
    ]
    lines += _all_sites_rows(sites)
    lines += [
        "",
        "| Site | Sun visible at 2 m | Longest time without the Sun | Sun-visible hours per complete lunar day: least, median, most | Earth visible at 2 m | Landing windows for `example-standard`: number, share of the judged range | Warnings in the package |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in sites:
        windows = s["landing_windows_example_standard"]
        lines.append(
            f"| {s['name']} | {100 * s['sun_visible_share']:.1f} % | {s['sun_longest_outage_h']:.0f} h | {_three(s['sun_visible_h_per_lunar_day_least_median_most'])} | {100 * s['earth_visible_share']:.1f} % | "
            f"{'n/a' if windows is None else str(windows['count']) + ', ' + format(100 * windows['feasible_fraction'], '.1f') + ' %'} | {'; '.join(s['warnings']) if s['warnings'] else 'none'} |"
        )
    lines.append("")
    return lines


def before_after(before: list, after: list) -> list:
    """The 24-month numbers of the project sites on the 20 m product and with the 5 m near field, side by side."""
    rows = []
    for old, new in zip(before, after):
        assert old["site_id"] == new["site_id"]
        hd = new["default_height_index"]
        pick = lambda site, h: next(row for row in site["per_height"] if row["observer_height_m"] == h)
        standard = lambda site: next(o for o in site["planning"]["landing_windows"] if o["requirement_id"] == "example-standard")
        pair = lambda f: [f(old), f(new)]
        rows.append({
            "site_id": new["site_id"],
            "name": new["name"],
            "terrain_at_site": pair(lambda s: s["terrain_source"]["at_site"]["product_id"]),
            "surface_height_m": pair(lambda s: s["surface_height_m"]),
            "horizon_set_within_1km_share": pair(lambda s: s["per_height"][hd]["share_of_horizon_set_closer_than_1km"]),
            "sun_visible_share_0m": pair(lambda s: pick(s, 0.0)["sun_visible_share"]),
            "sun_visible_share_2m": pair(lambda s: pick(s, 2.0)["sun_visible_share"]),
            "sun_visible_share_10m": pair(lambda s: pick(s, 10.0)["sun_visible_share"]),
            "sun_longest_outage_h_2m": pair(lambda s: pick(s, 2.0)["sun_longest_outage_h"]),
            "sun_visible_h_per_lunar_day_least_median_most_2m": pair(lambda s: s["planning"]["lunar_days"]["sun_visible_h_least_median_most"]),
            "earth_visible_share_2m": pair(lambda s: pick(s, 2.0)["earth_visible_share"]),
            "earth_visible_share_10m": pair(lambda s: pick(s, 10.0)["earth_visible_share"]),
            "sun_lost_to_terrain_h_2m": pair(lambda s: s["planning"]["terrain_against_smooth_sphere"]["sun"]["lost_to_terrain_h"]),
            "sun_gained_from_terrain_h_2m": pair(lambda s: s["planning"]["terrain_against_smooth_sphere"]["sun"]["gained_from_terrain_h"]),
            "landing_windows_example_standard": pair(lambda s: [standard(s)["window_count"], standard(s)["feasible_fraction"]]),
            "planned_landing_feasible": pair(lambda s: standard(s)["planned_landing"]["feasible"]),
            "band_sun_certain_possible_h_2m": pair(lambda s: [s["planning"]["uncertainty"]["visible_h"]["sun"]["certain"], s["planning"]["uncertainty"]["visible_h"]["sun"]["possible"]]),
            "applied_horizon_error_deg_median": pair(lambda s: s["planning"]["uncertainty"]["applied_horizon_error_deg_min_median_max"][1]),
            "landing_circle_sun_least_median_h": pair(lambda s: [s["planning"]["uncertainty"]["landing_ellipse"]["visible_h"]["sun"]["min"], s["planning"]["uncertainty"]["landing_ellipse"]["visible_h"]["sun"]["median"]]),
        })
    return rows


def _before_after_markdown(rows: list) -> list:
    def cell(values, fmt):
        return f"{fmt(values[0])} / {fmt(values[1])}"

    pct = lambda v: f"{100 * v:.1f} %"
    hours = lambda v: f"{v:.0f} h"
    lines = [
        "## Before and after the 5 m near field",
        "",
        "The three project sites over the same time range, with everything else the same: first on the 20 m product (not published), second with the 5 m site rasters inside it (the published packages). "
        "Sun: any part of the disc; Earth: centre. The band uses the same height-error model in both; without the near field it has no error map to read and applies 5 m or 7 m by slope.",
        "",
        "| 20 m product / with the 5 m near field | " + " | ".join(row["name"] for row in rows) + " |",
        "|---|" + "---|" * len(rows),
        "| Height at the site read from | " + " | ".join(cell(row["terrain_at_site"], str) for row in rows) + " |",
        "| Terrain height at the site | " + " | ".join(cell(row["surface_height_m"], lambda v: f"{v:.2f} m") for row in rows) + " |",
        "| Horizon at 2 m set within 1 km, share of azimuths | " + " | ".join(cell(row["horizon_set_within_1km_share"], lambda v: f"{100 * v:.0f} %") for row in rows) + " |",
        "| Sun visible on the surface | " + " | ".join(cell(row["sun_visible_share_0m"], pct) for row in rows) + " |",
        "| Sun visible at 2 m | " + " | ".join(cell(row["sun_visible_share_2m"], pct) for row in rows) + " |",
        "| Sun visible at 10 m | " + " | ".join(cell(row["sun_visible_share_10m"], pct) for row in rows) + " |",
        "| Longest time without the Sun at 2 m | " + " | ".join(cell(row["sun_longest_outage_h_2m"], hours) for row in rows) + " |",
        "| Sun-visible hours per complete lunar day at 2 m: least, median, most | " + " | ".join(cell(row["sun_visible_h_per_lunar_day_least_median_most_2m"], lambda v: ", ".join(f"{x:.0f}" for x in v)) for row in rows) + " |",
        "| Sun time the terrain takes at 2 m, against a smooth sphere | " + " | ".join(cell(row["sun_lost_to_terrain_h_2m"], hours) for row in rows) + " |",
        "| Sun time the terrain gives at 2 m | " + " | ".join(cell(row["sun_gained_from_terrain_h_2m"], hours) for row in rows) + " |",
        "| Earth visible at 2 m | " + " | ".join(cell(row["earth_visible_share_2m"], pct) for row in rows) + " |",
        "| Earth visible at 10 m | " + " | ".join(cell(row["earth_visible_share_10m"], pct) for row in rows) + " |",
        "| Landing windows for `example-standard` at 2 m: number, share of the judged range | " + " | ".join(cell(row["landing_windows_example_standard"], lambda v: f"{v[0]}, {100 * v[1]:.1f} %") for row in rows) + " |",
        "| Planned landing feasible for `example-standard` | " + " | ".join(cell(row["planned_landing_feasible"], lambda v: "yes" if v else "no") for row in rows) + " |",
        "| Band at 2 m: Sun visible for certain, possibly | " + " | ".join(cell(row["band_sun_certain_possible_h_2m"], lambda v: f"{v[0]:.0f}, {v[1]:.0f} h") for row in rows) + " |",
        "| Horizon error the model gives, median over the azimuths | " + " | ".join(cell(row["applied_horizon_error_deg_median"], lambda v: f"{v:.3f} deg") for row in rows) + " |",
        "| Landing circle of 100 m, 13 points, Sun: least, median | " + " | ".join(cell(row["landing_circle_sun_least_median_h"], lambda v: f"{v[0]:.0f}, {v[1]:.0f} h") for row in rows) + " |",
        "",
        "A difference is not an error of one side that the other corrects: the two elevation products are built from the same laser returns and differ in gridding and in a measured horizontal offset "
        "(6.6 m at the Malapert record, data stream). Where the horizon is set by terrain within a few hundred metres, as on the Malapert summit, a few pixels decide; the numbers of such a site at low observer heights "
        "are as uncertain as the difference shown here.",
        "",
    ]
    return lines


def _clear_published(root: Path) -> None:
    """Remove the previously published packages (only what the pipeline itself writes)."""
    for name in PACKAGE_FOLDERS:
        if (root / name).exists():
            shutil.rmtree(root / name)
    for name in ("index.json", "README.md"):
        if (root / name).exists():
            (root / name).unlink()


def write_readme(root: Path, written: list, scenarios: dict, summary: dict, command: str) -> None:
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
    project, curated = scenarios[PROJECT_SCENARIO_ID], scenarios[CURATED_SCENARIO_ID]
    w = project["time_window"]
    model = project["uncertainty"]["dem_height_error_model"]
    layers = {}
    for m in sites:
        for layer in m["inputs"]["dem"]["layers"]:
            layers.setdefault(layer["product_id"], layer)
    data_files = json.loads((REPO / "data" / "manifest" / "manifest.json").read_text(encoding="utf-8"))["files"]
    used = {s["terrain_at_site"]["product_id"] for s in summary["all_sites"]} | {p["product_id"] for s in summary["all_sites"] for p in s["horizon_products"]}
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
        f"| Contract | `{table['contract']['name']}` version {table['contract']['version']} |",
        f"| Time range | {w['start_utc']} to {w['end_utc']}, series step {w['step_s']:g} s, the same for every site |",
        f"| Scenario of the project sites | `validation/sites/scenario.json` (`{project['scenario_id']}`): {len(project['sites'])} sites, observer heights {', '.join(f'{h:g}' for h in project['observer_heights_m'])} m, "
        f"**5 m near field on**; uncertainty band of the height-error model `{model['id']}`; landing circle of {project['uncertainty']['landing_ellipse']['semi_major_m']:g} m radius, "
        f"{project['uncertainty']['landing_ellipse']['points']} points; planned landing {project['sites'][0]['landing_utc']} at every site; site pairs |",
        f"| Scenario of the other sites | `validation/sites/scenario_curated.json` (`{curated['scenario_id']}`): {len(curated['sites'])} sites of `data/sites/curated_sites.json`, observer heights "
        f"{', '.join(f'{h:g}' for h in curated['observer_heights_m'])} m, near field off, no stated uncertainty, no planned landing; their pairs are not published |",
        "| Example requirements | " + ", ".join(f"`{r['id']}`" for r in project["requirements"]) + " in both scenarios: the examples of `docs/contract/presets/requirements.json`, **not requirements of NASA or of any mission** |",
        f"| Height-error model | `{model['id']}`: {model['label']}. Source: {model['source']} |",
    ]
    for product_id in sorted(layers, key=lambda name: layers[name]["pixel_m"]):
        layer = layers[product_id]
        tiles = [record for record in data_files.values() if str(record.get("product_id", "")).startswith(product_id + "_") and record.get("role") == "data"]
        recorded = (
            f"sha256 `{layer['sha256']}`, {layer['source_url']}"
            if layer.get("sha256")
            else f"a mosaic of {len(tiles)} tiles; the packages record no checksum for it, the tiles are in `data/manifest/manifest.json` (`{product_id}_*`), each with its SHA-256 and source"
        )
        role = "served at least one site" if product_id in used else "installed and listed in the packages, but no published site or horizon was read from it"
        lines.append(f"| Elevation product | {product_id} {layer['version']}, {layer['pixel_m']:.0f} m; {recorded}; {role} |")
    lines += [
        f"| Kernel set | `{kernels.kernel_set_id()}`: " + ", ".join(entry["name"] for entry in kernel_manifest["kernels"]) + " |",
        f"| Station and Earth orientation kernels | `{kernels.station_kernel_set_id()}`: " + ", ".join(entry["name"] for entry in kernel_manifest["station_kernels"]) + " |",
        f"| Body-fixed frame | `{table['frame']}`, aberration correction `{table['aberration_correction']}` |",
        f"| Size | {summary['size']['total_bytes'] / 1e6:.1f} MB in {summary['size']['files']} files (without this file): direction table {summary['size']['direction_table_bytes'] / 1e6:.1f} MB, "
        f"site packages {summary['size']['site_bytes'] / 1e6:.1f} MB, site pairs {summary['size']['pairs_bytes'] / 1e6:.2f} MB |",
        "",
        "Kernel checksums are in `core/lsncore/ephem/kernel_manifest.json`; the elevation files are described in `data/manifest/manifest.json`.",
        "",
        "## Sites: what served each one and what its package carries",
        "",
        "Every site package holds, each with its method card: the 360 degree terrain horizon with the position, height and height error of the limiting terrain, the obstacles and the elevation products that served the site (`horizon.terrain_source`); "
        "the direction series of the Sun and the Earth, the visible fraction of each disc, the lit fraction of the Sun (terrain and eclipses by the Earth together) and the horizon sample that limits the view; "
        "rise and set events with the quality of the terrain behind each (`terrain_quality`), visibility windows (with eclipses and per-station direct-to-Earth windows) and metrics; what each obstacle costs against a smooth sphere; "
        "the lunar-day calendar; the landing windows for the three example requirements; the height trade over the observer heights of the package; three terrain patches for drawing (4, 16 and 64 km wide). "
        "The table says what differs from site to site.",
        "",
    ]
    lines += _all_sites_rows(summary["all_sites"])
    lines += [
        "",
        "- **Near field on** means: inside the 5 m site raster of the data stream the terrain is read from it, elsewhere from the 20 m and 60 m products. The 5 m rasters exist for the three project sites only.",
        "- **Class** is the resolution class the core writes (`horizon.terrain_source.resolution_class`: fine up to 30 m pixels at the site, medium up to 120 m, coarse above). A package whose class is not fine carries a warning that names the pixel: "
        "relief narrower than about two pixels is not in its horizon. The site list of the data stream uses narrower classes (fine up to 20 m, medium up to 60 m) and calls the 118 m product coarse.",
        "- **Uncertainty band** and **landing-circle survey** are in the project sites only. The height-error model was measured on the polar products; it is not applied to sites served by the 118 m product, "
        "where unresolved relief, not height error, limits the horizon.",
        "- The terrain patches are for drawing only and are read at 20 m and coarser, also where the near field is on: near a project site the drawn ground and the 5 m surface behind the numbers differ by about a metre.",
        "- The direction table holds the orientation of the Earth for every record (`earth_view`), so that a viewer can turn a textured Earth the right way.",
        "",
        "## Content",
        "",
        "`index.json` lists every package. It covers both scenarios, so its `scenario_id` is null. Paths are relative to this folder.",
        "",
        "| Kind | Package | Site | Status | Path |",
        "|---|---|---|---|---|",
        f"| direction table | `{table['package_id']}` | all sites | {table['status']} | `direction_table/{table['package_id']}` |",
    ]
    for m in sites:
        s = m["site"]
        lines.append(f"| site | `{m['package_id']}` | {s['name']} ({s['lat_deg']:.5f}, {s['lon_deg']:.5f}) | {m['status']} | `site/{s['site_id']}/{m['package_id']}` |")
    for m in pairs:
        lines.append(f"| site pairs | `{m['package_id']}` | every two of the {len(m['sites'])} project sites | {m['status']} | `site_pairs/{m['package_id']}` |")
    lines += [
        "",
        "## What these numbers are",
        "",
        "- The three project sites are candidate points derived from LOLA and IAU crater outlines by the data stream; **they are not official landing sites**. The past landing sites are the lander positions measured on LROC images; "
        "the Artemis III point is one representative point of a candidate region, not a landing site NASA has named. Sources and what is unverified are in `data/sites/curated_sites.json`.",
        "- The method behind these numbers reproduces the published LOLA illumination maps of NASA Goddard at 100 points on terrain of the same resolution, and the ephemeris, the eclipse contacts and the ground-station geometry are validated against independent sources (`validation/card/validation_card.md`). Of two dated LROC images, the shadowed state of the south pole agrees; the comparison along an image strip fails its registered criterion (89.3 % agreement against 90 %; the image rule reads dimly lit ground as shadow), see `validation/lro_images`. **The numbers of these sites themselves have no independent counterpart**: no source gives rise and set times for these points. Every number carries a method card with its validation status and limits; a viewer must show `unverified` where a card says so.",
        "- **The requirements, the landing circle and the planned landing time are inputs chosen by the team**, not requirements of NASA or of any mission. A viewer must show the label of a requirement next to every number derived from it, and must present the uncertainty band and the landing-circle survey as what follows from stated assumptions.",
        "- Where an event is set by terrain closer than about 1 km, the elevation grid limits its accuracy; the event carries `obstacle_distance_m` and `terrain_quality`, and an obstacle within 1 km carries `near_field`.",
        "- A summary per site, the numbers of the project sites before and after the 5 m near field, and the table of all sites are in `validation/sites/results/site_summary.md`.",
        "",
        "## Checking and regenerating",
        "",
        "```",
        "python -m lsncore validate packages/index.json packages/direction_table/* packages/site/*/* packages/site_pairs/*",
        "python -m validation.sites.run data/sites/sites.json --publish",
        "```",
        "",
        "Regenerating needs the kernels (`python -m lsncore.ephem.fetch_kernels`) and, under `LSN_DATA_ROOT`, every elevation product marked above as having served a site, with the 5 m site rasters and their error maps "
        "(`python -m lsn_data fetch` with the product names; the default download fetches the south-polar products only). Package ids depend only on the request and the data versions, so the same request on the same data gives the same ids.",
    ]
    (root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _folder_bytes(folder: Path) -> int:
    return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file()) if folder.exists() else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sites_file", help="site records of the project sites (data/sites/sites.json)")
    parser.add_argument("--curated", default=str(CURATED_SITES), help="curated site list of the data stream")
    parser.add_argument("--publish", action="store_true", help="replace the published packages in packages/ and write their README")
    parser.add_argument("--write-scenario", action="store_true", help="write the two scenario files of the published set and stop")
    parser.add_argument("--out", default=str(REPO / "build" / "packages" / "sites"))
    parser.add_argument("--jobs", type=int, default=0, help="processes the run may use (default: half the processors, at most 8); the packages do not depend on it")
    parser.add_argument("--only", choices=["project", "curated"], help="compute one of the two sets only (not with --publish)")
    parser.add_argument("--no-before", action="store_true", help="do not compute the project sites a second time without the near field (not with --publish)")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END)
    args = parser.parse_args()
    if args.publish and (args.only or args.no_before):
        parser.error("--publish computes both sets and the comparison without the near field")
    jobs = args.jobs if args.jobs > 0 else max(1, min((os.cpu_count() or 2) // 2, 8))

    project_records = json.loads(Path(args.sites_file).read_text(encoding="utf-8"))["sites"]
    curated_records = json.loads(Path(args.curated).read_text(encoding="utf-8"))["sites"]
    categories = {record["site_id"].replace("_", "-"): record["category"] for record in curated_records}
    for record in project_records:
        categories.setdefault(record["site_id"].replace("_", "-"), "project_candidate")

    near_field = functools.partial(open_lola, near_field=True)
    project_terrain, curated_terrain = near_field(), open_moon()
    scenarios = {
        PROJECT_SCENARIO_ID: build_scenario(project_records, project_terrain.describe()["dem_set_id"], args.start, args.end),
        CURATED_SCENARIO_ID: build_curated_scenario(curated_records, curated_terrain.describe()["dem_set_id"], args.start, args.end),
    }
    files = {PROJECT_SCENARIO_ID: "scenario.json", CURATED_SCENARIO_ID: "scenario_curated.json"}

    out = STAGING if args.publish else Path(args.out)
    before_root = out.parent / (out.name + "-before-near-field")
    for folder in (out, before_root):
        if args.publish and folder.exists():
            shutil.rmtree(folder)
    scenario_dir = HERE if (args.publish or args.write_scenario) else out
    if args.publish or args.write_scenario:
        if (args.start, args.end) != (DEFAULT_START, DEFAULT_END):
            parser.error("the published scenarios use the default time window; --start and --end are for runs that are not published")
    else:
        out.mkdir(parents=True, exist_ok=True)
    for scenario_id, name in files.items():
        (scenario_dir / name).write_text(json.dumps(scenarios[scenario_id], indent=2) + "\n", encoding="utf-8", newline="\n")
    if args.write_scenario:
        print(", ".join((HERE / name).relative_to(REPO).as_posix() for name in files.values()))
        return
    if args.publish:
        # The packages record the commit and whether the working tree differs from it. A
        # published package must name a clean commit, so stop before the long computation.
        changed = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True).stdout.strip()
        if changed:
            parser.error(
                "the working tree differs from the last commit, so the packages would record uncommitted changes:\n"
                + changed
                + "\nCommit first. If a scenario file under validation/sites is listed, the scenario itself changed (for example its contract version after a merge): "
                "commit it and publish again."
            )
    results = HERE / "results" if args.publish else out / "summary"

    t0 = time.perf_counter()
    written = []
    if args.only != "curated":
        written += run_scenario(scenarios[PROJECT_SCENARIO_ID], out, project_terrain, jobs=jobs, terrain_factory=near_field)
    if args.only != "project":
        for path in run_scenario(scenarios[CURATED_SCENARIO_ID], out, curated_terrain, jobs=jobs, terrain_factory=open_moon):
            if read_package(path).manifest["kind"] == "site_pairs":
                shutil.rmtree(path)  # pairs are published among the project sites only
            elif path not in written:
                written.append(path)
    write_index(out, None)  # one index for both scenarios
    elapsed = time.perf_counter() - t0
    for path in written:
        validate_package(path)
    validate_document(json.loads((out / "index.json").read_text(encoding="utf-8")))

    kinds = {path: read_package(path).manifest["kind"] for path in written}
    site_dirs = [path for path in written if kinds[path] == "site"]
    project_ids = {site["site_id"] for site in scenarios[PROJECT_SCENARIO_ID]["sites"]}
    project_dirs = [path for path in site_dirs if read_package(path).manifest["site"]["site_id"] in project_ids]
    sites = [summarise(path) for path in project_dirs]
    pair_dirs = [path for path in written if kinds[path] == "site_pairs"]
    all_sites = [describe_site(path, categories[read_package(path).manifest["site"]["site_id"]]) for path in site_dirs]
    order = [site["site_id"] for scenario in scenarios.values() for site in scenario["sites"]]
    all_sites.sort(key=lambda s: order.index(s["site_id"]))

    comparison, before_time = None, None
    if sites and not args.no_before:
        t1 = time.perf_counter()
        before_dirs = run_scenario(scenarios[PROJECT_SCENARIO_ID], before_root, open_lola(), jobs=jobs, terrain_factory=open_lola)
        before_time = time.perf_counter() - t1
        before_sites = [summarise(path) for path in before_dirs if read_package(path).manifest["kind"] == "site"]
        by_id = {site["site_id"]: site for site in before_sites}
        comparison = before_after([by_id[site["site_id"]] for site in sites], sites)

    table_dir = next(path for path in written if kinds[path] == "direction_table")
    summary = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "contract_version": read_package(table_dir).manifest["contract"]["version"],
        "window": scenarios[PROJECT_SCENARIO_ID]["time_window"],
        "stated": {**scenarios[PROJECT_SCENARIO_ID]["uncertainty"], "planned_landing_utc": PLANNED_LANDING_UTC, "requirements": [r["id"] for r in scenarios[PROJECT_SCENARIO_ID]["requirements"]]},
        "site_pairs": summarise_pairs(pair_dirs[0]) if pair_dirs else None,
        "thresholds": THRESHOLDS,
        "dem_set_id": sites[0]["dem_set_id"] if sites else None,
        "kernel_set_id": kernels.kernel_set_id(),
        "direction_table_id": read_package(table_dir).manifest["package_id"],
        "run_time_s": elapsed,
        "run_time_without_near_field_s": before_time,
        "jobs": jobs,
        "status": "method checked against the published LOLA illumination maps on 60 m terrain (validation/pgda); one of two dated-image checks fails its registered criterion (validation/lro_images); the numbers of these sites themselves have no independent counterpart",
        "sites": sites,
        "near_field_before_after": comparison,
        "all_sites": all_sites,
        "size": {
            "total_bytes": sum(_folder_bytes(out / name) for name in PACKAGE_FOLDERS) + (out / "index.json").stat().st_size,
            "files": sum(1 for name in PACKAGE_FOLDERS for f in (out / name).rglob("*") if f.is_file()) + 1,
            "direction_table_bytes": _folder_bytes(out / "direction_table"),
            "site_bytes": _folder_bytes(out / "site"),
            "pairs_bytes": _folder_bytes(out / "site_pairs"),
        },
    }
    results.mkdir(parents=True, exist_ok=True)
    (results / "site_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    if sites and pair_dirs:
        (results / "site_summary.md").write_text(to_markdown(summary), encoding="utf-8", newline="\n")
    if args.publish:
        _clear_published(PUBLISHED)
        PUBLISHED.mkdir(exist_ok=True)
        for name in PACKAGE_FOLDERS:
            shutil.copytree(out / name, PUBLISHED / name)
        shutil.copy2(out / "index.json", PUBLISHED / "index.json")
        published = [PUBLISHED / path.relative_to(out) for path in written]
        sites_arg = Path(args.sites_file).as_posix()
        write_readme(PUBLISHED, published, scenarios, summary, f"python -m validation.sites.run {sites_arg} --publish")
        out = PUBLISHED
    print(f"{len(written)} packages ({len(site_dirs)} sites), contract {summary['contract_version']}, {summary['size']['total_bytes'] / 1e6:.1f} MB, in {elapsed:.1f} s with {jobs} jobs -> {out}")
    if before_time is not None:
        print(f"project sites without the near field (for the comparison, not published): {before_time:.1f} s")
    for site in all_sites:
        print(
            f"{site['site_id']:44s} {site['status']:8s} {site['terrain_at_site']['product_id']:16s} {site['resolution_class']:7s} near field {'on ' if site['near_field'] else 'off'} "
            f"sun {100 * site['sun_visible_share']:5.1f} %  earth {100 * site['earth_visible_share']:5.1f} %  {site['size_bytes'] / 1e6:5.1f} MB"
        )


if __name__ == "__main__":
    main()
