"""First end-to-end result: one south-polar site, real terrain, real ephemeris.

Builds a scenario for one site record of the data stream, runs the core pipeline
(terrain horizon -> direction table -> timeline) and prints a short summary.
Packages are written to the given output folder; nothing is written to the repository.

Usage (from the repository root, with the LOLA data under LSN_DATA_ROOT)::

    python -m validation.first_result.run <sites.json> <site_id> <output folder>
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from lsncore.contract import contract_header, read_package, validate_document, validate_package
from lsncore.dem import open_lola
from lsncore.ephem import kernels
from lsncore.pipeline import run_scenario

WINDOW = {"start_utc": "2026-11-14T00:00:00.000Z", "end_utc": "2027-01-13T00:00:00.000Z", "step_s": 3600.0}


def main() -> None:
    sites_file, site_id, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    record = next(s for s in json.loads(sites_file.read_text(encoding="utf-8"))["sites"] if s["site_id"] == site_id)
    terrain = open_lola()
    scenario = {
        "contract": contract_header(),
        "kind": "scenario",
        "scenario_id": "first-result-" + site_id.replace("_", "-"),
        "title": f"First end-to-end result: {record['name']}",
        "description": "One site, 60 days from the hackathon weekend, real LOLA terrain and SPICE ephemeris.",
        "synthetic": False,
        "sites": [{"site_id": site_id.replace("_", "-"), "name": record["name"], "lat_deg": record["lat_deg"], "lon_deg": record["lon_deg_east"]}],
        "observer_heights_m": [0.0, 1.0, 2.0, 5.0, 10.0, 20.0],
        "default_height_m": 2.0,
        "horizon": {"azimuth_step_deg": 0.25, "max_range_m": 300000.0},
        "time_window": WINDOW,
        "bodies": ["SUN", "EARTH"],
        "thresholds": {
            "SUN": {"quantity": "visible_fraction", "op": ">", "value": 0.0},
            "EARTH": {"quantity": "margin_deg", "op": ">", "value": 0.0},
        },
        "mission_profile": None,
        "data": {"dem_set_id": terrain.describe()["dem_set_id"], "kernel_set_id": kernels.kernel_set_id(), "direction_table_id": None},
    }
    validate_document(scenario)
    out.mkdir(parents=True, exist_ok=True)
    (out / "scenario.json").write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")
    t0 = time.perf_counter()
    written = run_scenario(scenario, out / "packages", terrain)
    elapsed = time.perf_counter() - t0
    for path in written:
        validate_package(path)
    site = read_package(written[-1]).manifest
    h = site["horizon"]["default_height_index"]
    print(f"{record['name']}: lat {site['site']['lat_deg']}, lon {site['site']['lon_deg']}, surface height {site['site']['surface_height_m']['value']:.1f} m")
    print(f"status {site['status']}, synthetic {site['synthetic']}, total {elapsed:.1f} s, timings {site['provenance'].get('timings_s')}")
    print(f"observer height {site['horizon']['observer_heights_m'][h]} m; horizon error bounds: " + ", ".join(f"{k}={v['value']}" for k, v in site["horizon"].get("error_bounds", {}).items()))
    for warning in site["warnings"]:
        print("warning:", warning)
    events = [e for e in site["timeline"]["events"] if e["height_index"] == h]
    print(f"{len(events)} events at this height ({len(site['timeline']['events'])} over all heights)")
    for e in events:
        print(f"  {e['body']:5s} {e['type']:4s} {e['utc']}  az {e['azimuth_deg']:7.2f}  horizon {e['horizon_elevation_deg']:+.3f} deg  obstacle {e['obstacle_distance_m'] / 1000.0:7.2f} km  rate {e['closing_rate_deg_per_h']:+.4f} deg/h")
    for w in site["timeline"]["windows"]:
        if w["height_index"] == h:
            total = sum(b - a for a, b in w["intervals_et_s"]) / 86400.0
            print(f"  window {w['id']:26s} {len(w['intervals_et_s']):3d} intervals, {total:7.3f} d, clipped {w['clipped_start']}/{w['clipped_end']}")
    for m in site["timeline"]["metrics"]:
        if m["height_index"] == h:
            print(f"  metric {m['id']:34s} {m['value']} {m['unit']}")


if __name__ == "__main__":
    main()
