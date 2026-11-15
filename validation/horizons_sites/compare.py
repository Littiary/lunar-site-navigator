"""Sun and Earth directions at the three south-polar site records against JPL Horizons.

The comparison of ``validation/horizons``, with its code and its thresholds (fixed there
before any response was fetched), on the twelve queries of this folder: three site
records, Sun and Earth, the hackathon weekend at 10 minutes and one year at 25 hours.
The raw responses are those stored in ``raw/``; nothing is fetched.

This is an additional check. It is not a row of the validation card.

Usage (from the repository root, with the kernels installed)::

    python -m validation.horizons_sites.compare
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from lsncore.ephem import directions as d
from lsncore.ephem import kernels
from validation.horizons import compare as base
from validation.horizons.fetch import iter_cases, load_cases

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
RESULTS = HERE / "results"
THRESHOLDS = base.HERE / "thresholds.json"


def run() -> dict:
    kernels.load()
    limits = {key: item["value"] for key, item in json.loads(THRESHOLDS.read_text(encoding="utf-8"))["thresholds"].items()}
    rows = []
    for case_id, site_def, body, span, _params in iter_cases(load_cases(HERE)):
        ref = base.parse_response(RAW / f"{case_id}.json")
        meta = json.loads((RAW / f"{case_id}.meta.json").read_text(encoding="utf-8"))
        if meta["sha256"] != ref["sha256"]:
            raise RuntimeError(f"{case_id}: the raw response differs from its record")
        result = base.compare_case(site_def, body, ref)
        checks = {
            "direction_exact": result["exact"]["direction_arcsec_max"] < limits["direction_arcsec_max"],
            "direction_table": result["table"]["direction_arcsec_max"] < limits["direction_arcsec_max"],
            "angular_diameter": result["exact"]["angular_diameter_arcsec_max_abs"] < limits["angular_diameter_arcsec_max"],
            "range": result["exact"]["range_km_max_abs"] < limits["range_km_max"],
            "tdb_minus_ut": result["tdb_minus_ut_seconds_max_abs"] < limits["tdb_minus_ut_seconds_max"],
        }
        rows.append({"case_id": case_id, "site": site_def["id"], "body": body, "span": span["id"], "first_utc": ref["utc"][0], "last_utc": ref["utc"][-1],
                     "retrieved_utc": meta["retrieved_utc"], "raw_sha256": ref["sha256"], "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, **result})
    return {
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "thresholds": limits,
        "thresholds_from": "validation/horizons/thresholds.json",
        "core": {"frame": d.FRAME, "aberration_correction": d.ABCORR, "reference_radius_km": d.MOON_RADIUS_KM, "kernel_set_id": kernels.kernel_set_id()},
        "summary": {
            "cases": len(rows), "passed": sum(row["status"] == "PASS" for row in rows), "rows": sum(row["rows"] for row in rows),
            "direction_exact_arcsec_max": max(row["exact"]["direction_arcsec_max"] for row in rows),
            "direction_table_arcsec_max": max(row["table"]["direction_arcsec_max"] for row in rows),
        },
        "cases": rows,
    }


def to_markdown(report: dict) -> str:
    s, limits = report["summary"], report["thresholds"]
    lines = [
        "# Validation table: Sun and Earth directions at the three site records versus JPL Horizons",
        "",
        f"Generated {report['generated_utc']} by `validation/horizons_sites/compare.py` from the stored raw responses. Do not edit by hand.",
        "",
        f"**{s['passed']} of {s['cases']} queries inside the thresholds, {s['rows']} rows.** Largest direction difference: {s['direction_exact_arcsec_max']:.4f} arcsec with the observer at the site, "
        f"{s['direction_table_arcsec_max']:.4f} arcsec through the direction table that the packages use.",
        "",
        f"- Thresholds: those of `{report['thresholds_from']}` (direction {limits['direction_arcsec_max']} arcsec, angular diameter {limits['angular_diameter_arcsec_max']} arcsec, range {limits['range_km_max']} km, "
        f"TDB - UT {limits['tdb_minus_ut_seconds_max']} s), fixed before any Horizons response was fetched.",
        f"- Core: frame `{report['core']['frame']}`, correction `{report['core']['aberration_correction']}`, sphere {report['core']['reference_radius_km']} km, kernel set `{report['core']['kernel_set_id']}`.",
        "- An additional check: not a row of the validation card. Both sides use JPL ephemerides of the same family and neither has terrain.",
        "",
        "| Query | Rows | Direction, observer at the site (arcsec) | Direction, through the table (arcsec) | Angular diameter (arcsec) | Range (km) | TDB - UT (s) | Result |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in report["cases"]:
        lines.append(f"| `{row['case_id']}` | {row['rows']} | {row['exact']['direction_arcsec_max']:.4f} | {row['table']['direction_arcsec_max']:.4f} | {row['exact']['angular_diameter_arcsec_max_abs']:.4f} | "
                     f"{row['exact']['range_km_max_abs']:.4f} | {row['tdb_minus_ut_seconds_max_abs']:.6f} | **{row['status']}** |")
    return "\n".join(lines) + "\n"


def main() -> None:
    report = run()
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "validation_table.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (RESULTS / "validation_table.md").write_text(to_markdown(report), encoding="utf-8")
    s = report["summary"]
    print(f"{s['passed']} of {s['cases']} queries pass, {s['rows']} rows; direction {s['direction_exact_arcsec_max']:.4f} arcsec at the site, {s['direction_table_arcsec_max']:.4f} arcsec through the table")


if __name__ == "__main__":
    main()
