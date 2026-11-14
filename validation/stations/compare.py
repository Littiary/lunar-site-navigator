"""Compare the ground-station geometry of the core with the stored Horizons responses.

Reads ``cases.json``, ``thresholds.json`` and ``raw/``; writes ``results/``.
Nothing in ``raw/`` or ``thresholds.json`` is modified.

Usage (from the repository root)::

    python -m validation.stations.compare
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np

from lsncore.ephem import directions as d
from lsncore.ephem import kernels
from lsncore.ephem import stations as st
from validation.horizons.compare import MONTHS
from validation.horizons.fetch import iter_cases, load_cases

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
RESULTS = HERE / "results"
ARCSEC = 3600.0


def parse_stations_response(path: Path) -> dict:
    """The azimuth and elevation columns of a stored response, plus the site lines of its header."""
    payload = path.read_bytes()
    text = json.loads(payload)["result"]
    block = text[text.index("$$SOE") + 5 : text.index("$$EOE")]
    # The number of flag columns after the date differs between Earth and Moon observers:
    # the azimuth column is located from the column header that Horizons prints.
    columns = next(line for line in text[: text.index("$$SOE")].splitlines() if "Azi_(a-app)" in line)
    i_az = [name.strip() for name in columns.split(",")].index("Azi_(a-app)")
    utc, az, el = [], [], []
    for line in block.strip().splitlines():
        cells = [cell.strip() for cell in line.split(",")]
        date, clock = cells[0].split()
        year, month, day = date.split("-")
        utc.append(f"{year}-{MONTHS[month]:02d}-{day}T{clock}")
        az.append(float(cells[i_az]))
        el.append(float(cells[i_az + 1]))
    header = text[: text.index("$$SOE")]
    named = [line.strip() for line in header.splitlines() if line.startswith(("Target body name", "Center-site name", "Center body name", "Center geodetic", "Target geodetic", "Center pole/equ", "Target pole/equ"))]
    return {"utc": utc, "az_deg": np.array(az), "el_deg": np.array(el), "sha256": hashlib.sha256(payload).hexdigest(), "header": named}


def run() -> dict:
    kernels.load_stations()
    cases = load_cases(HERE)
    limits = {key: item["value"] for key, item in json.loads((HERE / "thresholds.json").read_text(encoding="utf-8"))["thresholds"].items()}
    rows, headers = [], {}
    table = None
    for case_id, query, _body, _span, _params in iter_cases(cases):
        ref = parse_stations_response(RAW / f"{case_id}.json")
        meta = json.loads((RAW / f"{case_id}.meta.json").read_text(encoding="utf-8"))
        assert meta["sha256"] == ref["sha256"], f"raw file changed: {case_id}"
        headers[case_id] = ref["header"]
        s = cases["lunar_sites"][query["lunar_site"]]
        site = d.Site(s["lon_deg"], s["lat_deg"], s["height_km"])
        et = d.utc_to_et(ref["utc"])
        if table is None:
            table = st.station_table(et[0], et[-1])
        k = [station.name for station in st.DSN_STATIONS].index(query["station"])
        fast = st.link_geometry(site, table, et)
        row = {"case_id": case_id, "end": query["end"], "station": query["station"], "lunar_site": query["lunar_site"], "rows": int(et.size),
               "retrieved_utc": meta["retrieved_utc"], "raw_sha256": ref["sha256"], "elevation_range_deg": [float(ref["el_deg"].min()), float(ref["el_deg"].max())]}
        if query["end"] == "earth":
            az, el = st.site_from_station_exact(site, query["station"], et)
            exact = d.angular_separation_deg(az, el, ref["az_deg"], ref["el_deg"]) * ARCSEC
            fast_diff = np.abs(fast.site_el_at_station_deg[k] - ref["el_deg"])
            row.update({
                "exact_direction_arcsec_max": float(exact.max()),
                "exact_elevation_arcsec_max": float(np.abs(el - ref["el_deg"]).max() * ARCSEC),
                "fast_elevation_deg_max": float(fast_diff.max()),
                "checks": {"exact": bool(exact.max() < limits["earth_end_direction_arcsec_max"]), "fast": bool(fast_diff.max() < limits["fast_path_earth_end_deg_max"])},
            })
        else:
            az, el = st.station_from_site_exact(site, query["station"], et)
            exact = d.angular_separation_deg(az, el, ref["az_deg"], ref["el_deg"]) * ARCSEC
            fast_sep = d.angular_separation_deg(fast.station_az_deg[k], fast.station_el_deg[k], ref["az_deg"], ref["el_deg"]) * ARCSEC
            row.update({
                "exact_direction_arcsec_max": float(exact.max()),
                "fast_direction_arcsec_max": float(fast_sep.max()),
                "checks": {"exact": bool(exact.max() < limits["moon_end_direction_arcsec_max"]), "fast": bool(fast_sep.max() < limits["fast_path_moon_end_arcsec_max"])},
            })
        row["status"] = "PASS" if all(row["checks"].values()) else "FAIL"
        rows.append(row)
    earth = [r for r in rows if r["end"] == "earth"]
    moon = [r for r in rows if r["end"] == "moon"]
    return {
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "thresholds": limits,
        "core": {"frame": d.FRAME, "aberration_correction": d.ABCORR, "kernel_set_id": kernels.kernel_set_id(), "station_kernel_set_id": kernels.station_kernel_set_id(),
                 "station_kernels": [entry["name"] for entry in kernels.read_manifest()["station_kernels"]]},
        "summary": {
            "cases": len(rows), "passed": sum(r["status"] == "PASS" for r in rows), "rows": sum(r["rows"] for r in rows),
            "earth_end_exact_arcsec_max": max(r["exact_direction_arcsec_max"] for r in earth),
            "earth_end_fast_elevation_deg_max": max(r["fast_elevation_deg_max"] for r in earth),
            "moon_end_exact_arcsec_max": max(r["exact_direction_arcsec_max"] for r in moon),
            "moon_end_fast_arcsec_max": max(r["fast_direction_arcsec_max"] for r in moon),
        },
        "horizons_headers": headers,
        "cases": rows,
    }


def to_markdown(report: dict) -> str:
    s, t = report["summary"], report["thresholds"]
    lines = [
        "# Validation table: ground-station geometry versus JPL Horizons",
        "",
        f"Generated {report['generated_utc']} by `validation/stations/compare.py` from the stored raw responses. Do not edit by hand.",
        "",
        f"- Core: frame `{report['core']['frame']}`, correction `{report['core']['aberration_correction']}`, kernel set `{report['core']['kernel_set_id']}`, station group `{report['core']['station_kernel_set_id']}` ({', '.join(report['core']['station_kernels'])}).",
        f"- Thresholds (fixed before the data was fetched, commit 6f74153): exact path < {t['earth_end_direction_arcsec_max']} arcsec at both ends; fast path < {t['fast_path_earth_end_deg_max']} deg in elevation at the station and < {t['fast_path_moon_end_arcsec_max']} arcsec at the lunar site.",
        f"- {s['passed']} of {s['cases']} cases pass, {s['rows']} rows, 14 to 16 November 2026 at 10 minutes.",
        "",
        "| End | Station | Lunar site | Rows | Exact path, direction max (arcsec) | Fast path max | Elevation range (deg) | Status |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in report["cases"]:
        fast = f"{row['fast_elevation_deg_max']:.5f} deg in elevation" if row["end"] == "earth" else f"{row['fast_direction_arcsec_max']:.3f} arcsec"
        end = "Earth end: lunar site seen from the station" if row["end"] == "earth" else "Moon end: station seen from the lunar site"
        lines.append(f"| {end} | {row['station']} | {row['lunar_site']} | {row['rows']} | {row['exact_direction_arcsec_max']:.3f} | {fast} | {row['elevation_range_deg'][0]:.1f} to {row['elevation_range_deg'][1]:.1f} | {row['status']} |")
    lines += ["", "Site and target lines printed by Horizons (first query of each station):", ""]
    seen = set()
    for case_id, header in report["horizons_headers"].items():
        station = case_id.split("__")[1]
        if case_id.startswith("earth_end") and station not in seen:
            seen.add(station)
            lines += [f"- `{case_id}`: " + " | ".join(" ".join(line.split()) for line in header)]
    return "\n".join(lines) + "\n"


def main() -> None:
    report = run()
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "validation_table.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (RESULTS / "validation_table.md").write_text(to_markdown(report), encoding="utf-8")
    for row in report["cases"]:
        fast = row.get("fast_elevation_deg_max", row.get("fast_direction_arcsec_max"))
        print(f"{row['case_id']:30s} exact {row['exact_direction_arcsec_max']:.4f} arcsec  fast {fast:.5f}  {row['status']}")
    print(report["summary"])


if __name__ == "__main__":
    main()
