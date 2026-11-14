"""Compare the event finder (smooth sphere) with the rise and set rows of JPL Horizons.

Reads ``cases.json``, ``thresholds.json`` and ``raw/``; writes ``results/``.
Nothing in ``raw/`` or ``thresholds.json`` is modified.

Usage (from the repository root)::

    python -m validation.horizons_rts.compare
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np

from lsncore import events as ev
from lsncore.ephem import directions as d
from lsncore.ephem import kernels
from validation.horizons.compare import MONTHS
from validation.horizons.fetch import iter_cases, load_cases

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
RESULTS = HERE / "results"
EDGE_S = 600.0


def parse_rows(path: Path) -> dict:
    payload = path.read_bytes()
    text = json.loads(payload)["result"]
    block = text[text.index("$$SOE") + 5 : text.index("$$EOE")]
    rows = []
    for line in block.strip().splitlines():
        cells = [cell.strip() for cell in line.split(",")]
        date, clock = cells[0].split()
        year, month, day = date.split("-")
        rows.append({"utc": f"{year}-{MONTHS[month]:02d}-{day}T{clock}", "marker": cells[2], "el_deg": float(cells[4]), "ang_diam_arcsec": float(cells[5])})
    return {"rows": rows, "sha256": hashlib.sha256(payload).hexdigest(), "text": text}


def core_events(site_def: dict, span: dict) -> list:
    site = d.Site(site_def["lon_deg"], site_def["lat_deg"], site_def["height_km"])
    start = d.utc_to_et(span["start_utc"].replace(" ", "T"))
    stop = d.utc_to_et(span["stop_utc"].replace(" ", "T"))
    table = d.direction_table(start - 3600.0 + 3600.0 * np.arange(int((stop - start) / 3600.0) + 4))
    horizon = ev.Horizon.smooth_sphere(observer_height_m=site_def["height_km"] * 1000.0)
    result = ev.find_events(ev.site_direction(site, table, "SUN"), horizon, start, stop, thresholds=("upper_limb",))
    return [(event.type, event.et_s) for event in result.events], start, stop


def run() -> dict:
    kernels.load()
    cases = load_cases(HERE)
    limits = {key: item["value"] for key, item in json.loads((HERE / "thresholds.json").read_text(encoding="utf-8"))["thresholds"].items()}
    out = []
    for case_id, site_def, _body, span, _params in iter_cases(cases):
        ref = parse_rows(RAW / f"{case_id}.json")
        meta = json.loads((RAW / f"{case_id}.meta.json").read_text(encoding="utf-8"))
        assert meta["sha256"] == ref["sha256"], f"raw file changed: {case_id}"
        ours, start, stop = core_events(site_def, span)
        used, pairs, unmatched = set(), [], 0
        for row in ref["rows"]:
            kind = {"r": "rise", "s": "set"}.get(row["marker"])
            if kind is None:
                continue
            et = d.utc_to_et(row["utc"])
            candidates = [(abs(t - et), i) for i, (k, t) in enumerate(ours) if k == kind and i not in used]
            if not candidates or min(candidates)[0] > limits["event_time_seconds_max"]:
                unmatched += 1
                pairs.append({"type": kind, "horizons_utc": row["utc"], "core_utc": None, "horizons_minus_core_s": None})
                continue
            _, i = min(candidates)
            used.add(i)
            pairs.append({"type": kind, "horizons_utc": row["utc"], "core_utc": d.et_to_utc(ours[i][1], 3), "horizons_minus_core_s": float(et - ours[i][1]), "horizons_center_elevation_deg": row["el_deg"]})
        extra = [i for i, (_, t) in enumerate(ours) if i not in used and start + EDGE_S < t < stop - EDGE_S]
        unmatched += len(extra)
        diffs = [p["horizons_minus_core_s"] for p in pairs if p["horizons_minus_core_s"] is not None]
        worst = max((abs(x) for x in diffs), default=None)
        status = "PASS" if unmatched <= limits["unmatched_events_max"] and worst is not None and worst < limits["event_time_seconds_max"] else "FAIL"
        out.append({"case_id": case_id, "site": site_def, "span": span, "retrieved_utc": meta["retrieved_utc"], "raw_sha256": ref["sha256"], "events": pairs, "unmatched": unmatched, "max_abs_difference_s": worst, "status": status})
    return {
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "thresholds": limits,
        "definition": "Sun, upper limb on the true visual horizon of the 1737.4 km sphere (dip included for a site above the sphere), no refraction.",
        "core": {"scan_step_s": ev.DEFAULT_SCAN_STEP_S, "bisection_tolerance_s": ev.DEFAULT_TOL_S, "kernel_set_id": kernels.kernel_set_id(), "frame": d.FRAME},
        "reference": "NASA/JPL Horizons, rise/transit/set search, 1-minute step, TVH mode; a row is the first search step at which the condition holds, so it lies 0 to 60 s after the true instant; stated accuracy: twice the search step.",
        "cases": out,
    }


def to_markdown(report: dict) -> str:
    lines = [
        "# Validation table: event finder versus JPL Horizons rise and set times",
        "",
        f"Generated {report['generated_utc']} by `validation/horizons_rts/compare.py` from the stored raw responses. Do not edit by hand.",
        "",
        f"- Event: {report['definition']}",
        f"- Reference: {report['reference']}",
        f"- Core: scan step {report['core']['scan_step_s']:g} s, bisection to {report['core']['bisection_tolerance_s']:g} s, frame `{report['core']['frame']}`, kernel set `{report['core']['kernel_set_id']}`.",
        f"- Threshold (fixed before the data was fetched): |difference| < {report['thresholds']['event_time_seconds_max']:g} s, unmatched events ≤ {report['thresholds']['unmatched_events_max']}.",
        "",
        "| Site (E lon°, lat°, h km) | Event | Horizons row (UTC) | Core (UTC) | Horizons − core (s) |",
        "|---|---|---|---|---|",
    ]
    for case in report["cases"]:
        s = case["site"]
        for pair in case["events"]:
            diff = "unmatched" if pair["horizons_minus_core_s"] is None else f"{pair['horizons_minus_core_s']:+.1f}"
            lines.append(f"| {s['id']} ({s['lon_deg']}, {s['lat_deg']}, {s['height_km']}) | {pair['type']} | {pair['horizons_utc']} | {pair['core_utc']} | {diff} |")
    lines.append("")
    for case in report["cases"]:
        lines.append(f"- {case['case_id']}: {len(case['events'])} events, largest |difference| {case['max_abs_difference_s']:.1f} s, unmatched {case['unmatched']}: **{case['status']}**")
    return "\n".join(lines) + "\n"


def main() -> None:
    report = run()
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "validation_table.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (RESULTS / "validation_table.md").write_text(to_markdown(report), encoding="utf-8")
    for case in report["cases"]:
        print(f"{case['case_id']:40s} {len(case['events'])} events  max {case['max_abs_difference_s']} s  unmatched {case['unmatched']}  {case['status']}")


if __name__ == "__main__":
    main()
