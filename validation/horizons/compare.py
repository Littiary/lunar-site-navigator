"""Compare the science core with the stored Horizons responses.

Reads ``cases.json``, ``thresholds.json`` and ``raw/``; writes
``results/validation_table.json`` and ``results/validation_table.md``.
Nothing in ``raw/`` or ``thresholds.json`` is modified.

Usage (from the repository root)::

    python -m validation.horizons.compare
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np
import spiceypy as spice

from lsncore.ephem import directions as d
from lsncore.ephem import kernels

from .fetch import HERE, RAW, iter_cases, load_cases

RESULTS = HERE / "results"
AU_KM = 149597870.7
ARCSEC_PER_DEG = 3600.0
MONTHS = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}


def parse_response(path: Path) -> dict:
    """Extract the table of one stored response. The file itself is not changed."""
    payload = path.read_bytes()
    document = json.loads(payload)
    text = document["result"]
    block = text[text.index("$$SOE") + 5 : text.index("$$EOE")]
    utc, az, el, diam, delta_au, tdb_ut = [], [], [], [], [], []
    for line in block.strip().splitlines():
        cells = [cell.strip() for cell in line.split(",")]
        date, clock = cells[0].split()
        year, month, day = date.split("-")
        utc.append(f"{year}-{MONTHS[month]:02d}-{day}T{clock}")
        az.append(float(cells[3]))
        el.append(float(cells[4]))
        diam.append(float(cells[5]))
        delta_au.append(float(cells[6]))
        tdb_ut.append(float(cells[8]))
    header = text[: text.index("$$SOE")]
    return {
        "utc": utc,
        "az_deg": np.array(az),
        "el_deg": np.array(el),
        "ang_diam_arcsec": np.array(diam),
        "range_km": np.array(delta_au) * AU_KM,
        "tdb_minus_ut_s": np.array(tdb_ut),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "api_version": document.get("signature", {}).get("version"),
        "header_lines": [line.strip() for line in header.splitlines() if "source:" in line or "pole/equ" in line or "radii" in line],
    }


def compare_case(site_def: dict, body: str, ref: dict) -> dict:
    site = d.Site(site_def["lon_deg"], site_def["lat_deg"], site_def["height_km"])
    et = d.utc_to_et(ref["utc"])
    exact = d.topocentric_exact(site, et, body)
    table = d.topocentric_from_table(site, d.direction_table(et))[body]
    out = {"rows": int(et.size)}
    for name, ours in (("exact", exact), ("table", table)):
        sep = d.angular_separation_deg(ours.az_deg, ours.el_deg, ref["az_deg"], ref["el_deg"]) * ARCSEC_PER_DEG
        d_el = (ours.el_deg - ref["el_deg"]) * ARCSEC_PER_DEG
        d_az = ((ours.az_deg - ref["az_deg"] + 180.0) % 360.0 - 180.0) * np.cos(np.radians(ref["el_deg"])) * ARCSEC_PER_DEG
        out[name] = {
            "direction_arcsec_max": float(sep.max()),
            "direction_arcsec_rms": float(np.sqrt(np.mean(sep**2))),
            "elevation_arcsec_max_abs": float(np.abs(d_el).max()),
            "elevation_arcsec_mean": float(d_el.mean()),
            "azimuth_on_sky_arcsec_max_abs": float(np.abs(d_az).max()),
            "angular_diameter_arcsec_max_abs": float(np.abs(2.0 * ours.angular_radius_deg * ARCSEC_PER_DEG - ref["ang_diam_arcsec"]).max()),
            "range_km_max_abs": float(np.abs(ours.range_km - ref["range_km"]).max()),
            "worst_row_utc": ref["utc"][int(sep.argmax())],
        }
    ours_tdb_utc = np.array([spice.deltet(float(t), "ET") for t in et])
    out["tdb_minus_ut_seconds_max_abs"] = float(np.abs(ours_tdb_utc - ref["tdb_minus_ut_s"]).max())
    out["elevation_range_deg"] = [float(ref["el_deg"].min()), float(ref["el_deg"].max())]
    return out


def run() -> dict:
    kernels.load()
    cases = load_cases()
    thresholds = json.loads((HERE / "thresholds.json").read_text(encoding="utf-8"))["thresholds"]
    limits = {key: item["value"] for key, item in thresholds.items()}
    rows, api_versions, headers = [], set(), set()
    for case_id, site_def, body, span, _params in iter_cases(cases):
        path = RAW / f"{case_id}.json"
        if not path.exists():
            rows.append({"case_id": case_id, "status": "MISSING"})
            continue
        ref = parse_response(path)
        meta = json.loads((RAW / f"{case_id}.meta.json").read_text(encoding="utf-8"))
        if meta["sha256"] != ref["sha256"]:
            rows.append({"case_id": case_id, "status": "RAW FILE CHANGED"})
            continue
        result = compare_case(site_def, body, ref)
        checks = {
            "direction_exact": result["exact"]["direction_arcsec_max"] < limits["direction_arcsec_max"],
            "direction_table": result["table"]["direction_arcsec_max"] < limits["direction_arcsec_max"],
            "angular_diameter": result["exact"]["angular_diameter_arcsec_max_abs"] < limits["angular_diameter_arcsec_max"],
            "range": result["exact"]["range_km_max_abs"] < limits["range_km_max"],
            "tdb_minus_ut": result["tdb_minus_ut_seconds_max_abs"] < limits["tdb_minus_ut_seconds_max"],
        }
        api_versions.add(ref["api_version"])
        headers.update(ref["header_lines"])
        rows.append(
            {
                "case_id": case_id,
                "site": site_def,
                "body": body,
                "span": span["id"],
                "first_utc": ref["utc"][0],
                "last_utc": ref["utc"][-1],
                "retrieved_utc": meta["retrieved_utc"],
                "raw_sha256": ref["sha256"],
                "status": "PASS" if all(checks.values()) else "FAIL",
                "checks": checks,
                **result,
            }
        )
    report = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "thresholds": limits,
        "core": {
            "frame": d.FRAME,
            "aberration_correction": d.ABCORR,
            "time_scale": "TDB (computation), UTC (time tags)",
            "reference_radius_km": d.MOON_RADIUS_KM,
            "kernel_set_id": kernels.kernel_set_id(),
            "kernels": [entry["name"] for entry in kernels.read_manifest()["kernels"]],
            "spice_toolkit": spice.tkvrsn("TOOLKIT"),
        },
        "reference": {
            "system": "NASA/JPL Horizons On-Line Ephemeris System, https://ssd.jpl.nasa.gov/horizons/",
            "api_versions": sorted(v for v in api_versions if v),
            "header_statements": sorted(headers),
            "printed_resolution": "azimuth and elevation 0.000001 deg (0.0036 arcsec); angular diameter 0.001 arcsec",
        },
        "cases": rows,
    }
    return report


def to_markdown(report: dict) -> str:
    done = [row for row in report["cases"] if "exact" in row]
    lines = [
        "# Validation table: science core versus JPL Horizons",
        "",
        f"Generated {report['generated_utc']} by `validation/horizons/compare.py` from the stored raw responses. Do not edit by hand.",
        "",
        f"- Core: SPICE ({report['core']['spice_toolkit']}), frame `{report['core']['frame']}`, correction `{report['core']['aberration_correction']}`, "
        f"sphere {report['core']['reference_radius_km']} km, kernel set `{report['core']['kernel_set_id']}` ({', '.join(report['core']['kernels'])}).",
        f"- Reference: {report['reference']['system']}; API version {', '.join(report['reference']['api_versions'])}; printed resolution: {report['reference']['printed_resolution']}.",
        f"- Thresholds (fixed before the comparison, `thresholds.json`): direction < {report['thresholds']['direction_arcsec_max']}″, "
        f"angular diameter < {report['thresholds']['angular_diameter_arcsec_max']}″, range < {report['thresholds']['range_km_max']} km, "
        f"TDB−UT < {report['thresholds']['tdb_minus_ut_seconds_max']} s.",
        f"- Cases: {len(done)} compared, {sum(r['status'] == 'PASS' for r in done)} pass, {sum(r['rows'] for r in done)} rows in total.",
        "",
        "| Site (E lon°, lat°, h km) | Body | Span | Rows | Direction max ″ (exact) | Direction RMS ″ | Direction max ″ (table) | Ang. diam. max ″ | Range max km | TDB−UT max s | Status |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in report["cases"]:
        if "exact" not in row:
            lines.append(f"| {row['case_id']} | | | | | | | | | | {row['status']} |")
            continue
        s = row["site"]
        lines.append(
            f"| {s['id']} ({s['lon_deg']}, {s['lat_deg']}, {s['height_km']}) | {row['body'].title()} | {row['span']} | {row['rows']} | "
            f"{row['exact']['direction_arcsec_max']:.3f} | {row['exact']['direction_arcsec_rms']:.3f} | {row['table']['direction_arcsec_max']:.3f} | "
            f"{row['exact']['angular_diameter_arcsec_max_abs']:.4f} | {row['exact']['range_km_max_abs']:.4f} | "
            f"{row['tdb_minus_ut_seconds_max_abs']:.6f} | {row['status']} |"
        )
    if done:
        lines += [
            "",
            f"Worst case over all rows: direction {max(r['exact']['direction_arcsec_max'] for r in done):.3f}″ (exact path), "
            f"{max(r['table']['direction_arcsec_max'] for r in done):.3f}″ (direction table).",
        ]
    lines += ["", "Statements printed by Horizons in the response headers:", ""]
    lines += [f"- `{statement}`" for statement in report["reference"]["header_statements"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    report = run()
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "validation_table.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (RESULTS / "validation_table.md").write_text(to_markdown(report), encoding="utf-8")
    for row in report["cases"]:
        if "exact" in row:
            print(f"{row['case_id']:40s} {row['rows']:6d} rows  dir {row['exact']['direction_arcsec_max']:.3f}\" exact  {row['table']['direction_arcsec_max']:.3f}\" table  {row['status']}")
        else:
            print(f"{row['case_id']:40s} {row['status']}")


if __name__ == "__main__":
    main()
