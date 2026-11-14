"""Compare the orientation of the Earth as seen from the Moon with the stored Horizons responses.

Reads ``cases.json``, ``thresholds.json`` and ``raw/``; writes
``results/validation_table.json`` and ``results/validation_table.md``.
Nothing in ``raw/`` or ``thresholds.json`` is modified.

Usage (from the repository root)::

    python -m validation.earth_view.compare
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from lsncore.earth_view import earth_view
from lsncore.ephem import directions as d
from lsncore.ephem import kernels
from validation.horizons.fetch import iter_cases, load_cases

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
RESULTS = HERE / "results"
MONTHS = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}


def parse_response(path: Path) -> dict:
    """Extract the table of one stored response. The file itself is not changed."""
    payload = path.read_bytes()
    document = json.loads(payload)
    text = document["result"]
    block = text[text.index("$$SOE") + 5 : text.index("$$EOE")]
    utc, lon, lat, pole = [], [], [], []
    for line in block.strip().splitlines():
        cells = [cell.strip() for cell in line.split(",")]
        date, clock = cells[0].split()
        year, month, day = date.split("-")
        utc.append(f"{year}-{MONTHS[month]:02d}-{day}T{clock}")
        lon.append(float(cells[3]))
        lat.append(float(cells[4]))
        pole.append(float(cells[5]))
    header = text[: text.index("$$SOE")]
    footer = text[text.index("$$EOE") :]
    start = footer.find("'NP.ang")
    return {
        "utc": utc,
        "sub_lon_deg": np.array(lon),
        "sub_lat_deg": np.array(lat),
        "north_pole_angle_deg": np.array(pole),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "api_version": document.get("signature", {}).get("version"),
        "header_lines": [line.strip() for line in header.splitlines() if "pole/equ" in line or "radii" in line or "EOP" in line],
        "north_pole_definition": " ".join(footer[start : footer.find("Units", start)].split()) if start >= 0 else None,
    }


def _short_way(a, b) -> np.ndarray:
    return (np.asarray(a) - np.asarray(b) + 180.0) % 360.0 - 180.0


def compare_case(case_id: str, ref: dict) -> dict:
    et = np.array([float(d.utc_to_et(utc)) for utc in ref["utc"]])
    ours = earth_view(et)
    pole = _short_way(ours["north_pole_angle_deg"], ref["north_pole_angle_deg"])
    row = {"case_id": case_id, "rows": len(ref["utc"]), "first_utc": ref["utc"][0], "last_utc": ref["utc"][-1]}
    if case_id.startswith("earth_from_moon"):
        # the registered comparison of the sub-lunar point; the pole angle of this query is reported, not judged
        row["sub_lunar_latitude_deg_max_abs"] = float(np.abs(ours["sub_lunar_lat_deg"] - ref["sub_lat_deg"]).max())
        row["sub_lunar_longitude_deg_max_abs"] = float(np.abs(_short_way(ours["sub_lunar_lon_deg"], ref["sub_lon_deg"])).max())
        row["north_pole_angle_deg_max_abs_reported_only"] = float(np.abs(pole).max())
    else:
        # the registered comparison of the pole angle: the Moon's north pole seen from the centre of the Earth
        row["north_pole_angle_deg_max_abs"] = float(np.abs(pole).max())
    return row


def run() -> dict:
    kernels.load_stations()
    limits = {key: item["value"] for key, item in json.loads((HERE / "thresholds.json").read_text(encoding="utf-8"))["thresholds"].items()}
    cases, definitions, headers = [], set(), {}
    for case_id, *_ in iter_cases(load_cases(HERE)):
        ref = parse_response(RAW / f"{case_id}.json")
        row = compare_case(case_id, ref)
        checks = {
            "sub_lunar_latitude_deg_max": row.get("sub_lunar_latitude_deg_max_abs"),
            "sub_lunar_longitude_deg_max": row.get("sub_lunar_longitude_deg_max_abs"),
            "north_pole_angle_deg_max": row.get("north_pole_angle_deg_max_abs"),
        }
        row["status"] = "PASS" if all(value is None or value < limits[key] for key, value in checks.items()) else "FAIL"
        row["response_sha256"] = ref["sha256"]
        cases.append(row)
        definitions.add(ref["north_pole_definition"])
        headers[case_id] = ref["header_lines"]
    worst = {
        "sub_lunar_latitude_deg": max(row["sub_lunar_latitude_deg_max_abs"] for row in cases if "sub_lunar_latitude_deg_max_abs" in row),
        "sub_lunar_longitude_deg": max(row["sub_lunar_longitude_deg_max_abs"] for row in cases if "sub_lunar_longitude_deg_max_abs" in row),
        "north_pole_angle_deg": max(row["north_pole_angle_deg_max_abs"] for row in cases if "north_pole_angle_deg_max_abs" in row),
    }
    report = {
        "title": "Orientation of the Earth as seen from the Moon: science core against JPL Horizons",
        "thresholds": limits,
        "rows": sum(row["rows"] for row in cases),
        "cases": cases,
        "worst": worst,
        "status": "PASS" if all(row["status"] == "PASS" for row in cases) else "FAIL",
        "north_pole_definition_in_the_responses": sorted(x for x in definitions if x),
        "response_headers": headers,
        "kernel_set_id": kernels.kernel_set_id(),
        "station_kernel_set_id": kernels.station_kernel_set_id(),
    }
    return report


def to_markdown(report: dict) -> str:
    limits = report["thresholds"]
    lines = [
        f"# {report['title']}",
        "",
        f"Overall: **{report['status']}**, {report['rows']} rows in {len(report['cases'])} queries. Thresholds (fixed beforehand): sub-lunar latitude and longitude "
        f"{limits['sub_lunar_latitude_deg_max']} deg, position angle of the north pole {limits['north_pole_angle_deg_max']} deg.",
        "",
        "| Query | Rows | Span (UT) | Sub-lunar latitude, largest difference | Sub-lunar longitude | Pole angle | Status |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in report["cases"]:
        cell = lambda key: f"{row[key]:.4f} deg" if key in row else "not in this query"  # noqa: E731
        pole = cell("north_pole_angle_deg_max_abs") if "north_pole_angle_deg_max_abs" in row else f"{row['north_pole_angle_deg_max_abs_reported_only']:.4f} deg (reported, not judged)"
        lines.append(
            f"| `{row['case_id']}` | {row['rows']} | {row['first_utc']} to {row['last_utc']} | {cell('sub_lunar_latitude_deg_max_abs')} | {cell('sub_lunar_longitude_deg_max_abs')} | {pole} | {row['status']} |"
        )
    lines += [
        "",
        "The pole angle is judged on the queries with the Moon as target and the centre of the Earth as observer: the angle between the two projected poles is the same seen from either end of the line. "
        "The queries with the Earth as target print a pole angle as well; it is listed for information.",
        "",
        "Definition printed in the responses: " + " / ".join(report["north_pole_definition_in_the_responses"]),
        "",
        "Horizons prints longitude and latitude with six decimals and the pole angle with four; the rounding is not subtracted.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    report = run()
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "validation_table.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (RESULTS / "validation_table.md").write_text(to_markdown(report), encoding="utf-8")
    print(to_markdown(report))


if __name__ == "__main__":
    main()
