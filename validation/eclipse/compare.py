"""Compare the eclipse code of the core with the published eclipse of 14 March 2025.

Reads ``cases.json`` and ``thresholds.json`` (committed before the first run) and writes
``results/validation_table.json`` and ``.md``.

Usage (from the repository root)::

    python -m validation.eclipse.compare
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np

from lsncore import events as ev
from lsncore.ephem import directions as d
from lsncore.ephem import kernels
from lsncore.events import eclipse as ec

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


def load() -> tuple[dict, dict]:
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    rules = json.loads((HERE / "thresholds.json").read_text(encoding="utf-8"))["rules"]
    return cases, rules


def _published(cases: dict, item: str):
    return next(p for p in cases["published"] if p["id"] == item)["value"]


def _row(check_id, kind, quantity, published, computed, unit, threshold=None, difference=None, status=None, note=""):
    return {"id": check_id, "kind": kind, "quantity": quantity, "published": published, "computed": computed, "unit": unit,
            "difference": difference, "threshold": threshold, "status": status, "note": note}


def run() -> dict:
    kernels.load()
    cases, rules = load()
    s = cases["site"]["value"]
    site = d.Site(s["lon_deg"], s["lat_deg"], s["height_m"] / 1000.0)
    start, stop = d.utc_to_et("2025-03-13T18:00:00"), d.utc_to_et("2025-03-14T18:00:00")
    table = d.direction_table(start - 3600.0 + 3600.0 * np.arange(int((stop - start) / 3600.0) + 4))
    found = ec.find_eclipses(ec.site_geometry(site, table), start, stop)
    if len(found) != 1 or found[0].total_start_et_s is None:
        raise RuntimeError(f"expected one total eclipse at the site, found {found}")
    e = found[0]
    c1, c2, c3, c4 = e.partial_start_et_s, e.total_start_et_s, e.total_end_et_s, e.partial_end_et_s
    utc = d.et_to_utc_z

    limit = rules["E1_contact_time_at_the_site"]["threshold_minutes"]
    rows = []
    for check_id, label, item, value in (
        ("eclipse_partial_start", "Partial eclipse begins at the site (C1)", "firefly_partial_start", c1),
        ("eclipse_totality_start", "Totality begins at the site (C2)", "firefly_totality_start", c2),
        ("eclipse_partial_end", "Partial eclipse ends at the site (C4)", "firefly_partial_end", c4),
    ):
        published = _published(cases, item)
        diff = (value - d.utc_to_et(published)) / 60.0
        rows.append(_row(check_id, "pass_fail", label, published + "Z", utc(value), "min", limit, diff, "PASS" if abs(diff) < limit else "FAIL"))
    limit2 = rules["E2_duration_of_totality"]["threshold_minutes"]
    duration = (c3 - c2) / 60.0
    diff = duration - _published(cases, "firefly_totality_duration_min")
    rows.append(_row("eclipse_totality_duration", "pass_fail", "Duration of totality at the site (C3 - C2)", float(_published(cases, "firefly_totality_duration_min")), duration, "min", limit2, diff,
                     "PASS" if abs(diff) < limit2 else "FAIL", f"totality ends (C3) at {utc(c3)}"))

    nasa = {key: d.utc_to_et(value) for key, value in _published(cases, "nasa_whole_moon_contacts").items()}
    allow = 60.0 * rules["E3_nesting_inside_whole_moon_contacts"]["allowance_minutes"]
    printed = _published(cases, "nasa_whole_moon_contacts")

    def nested(check_id, label, value, low, high, low_name, high_name):
        ok = (low is None or value >= low - allow) and (high is None or value <= high + allow)
        margins = [m for m in ((value - low) / 60.0 if low is not None else None, (high - value) / 60.0 if high is not None else None) if m is not None]
        bounds = " and ".join(f"{name} = {printed[name]}Z" for name in (low_name, high_name) if name)
        rows.append(_row(check_id, "pass_fail", label, bounds, utc(value), "min", f"inside the bounds, allowance {allow / 60.0:g} min", min(margins), "PASS" if ok else "FAIL",
                         "difference: smallest margin to a bound, in minutes (positive = inside)"))

    nested("eclipse_c1_after_p1", "C1 at the site is not before the Moon enters the penumbra (P1)", c1, nasa["P1"], None, "P1", None)
    nested("eclipse_c2_between_u1_and_u2", "C2 at the site lies between U1 and U2", c2, nasa["U1"], nasa["U2"], "U1", "U2")
    nested("eclipse_c3_between_u3_and_u4", "C3 at the site lies between U3 and U4", c3, nasa["U3"], nasa["U4"], "U3", "U4")
    nested("eclipse_c4_before_p4", "C4 at the site is not after the Moon leaves the penumbra (P4)", c4, None, nasa["P4"], None, "P4")

    geometry = ec.site_geometry(site, table)
    observed = _published(cases, "firefly_observed")
    image_et = np.array([d.utc_to_et(value) for value in observed.values()])
    sep, rs, re = geometry(image_et)
    hidden = ec.covered_fraction(sep, rs, re)
    rows.append(_row("eclipse_observed_images", "reported", "Fraction of the Sun hidden by the Earth at the times of the published images",
                     {key: value + "Z (about)" for key, value in observed.items()},
                     {key: float(h) for key, h in zip(observed, hidden)}, "fraction",
                     note=f"the diamond ring was photographed about {(c3 - image_et[2]) / 60.0:.0f} min before the computed end of totality"))

    grid = np.arange(c1 - 1800.0, c4 + 1800.0 + 1.0, 600.0)
    line = ec.power_line(site, table, ev.Horizon.smooth_sphere(2.0), grid)
    sun = d.topocentric_from_table(site, d.interpolate_table(table, np.array([e.minimum_separation_et_s])))
    rows.append(_row("eclipse_power_line", "reported", "Eclipse-aware power line at the site (fraction of the Sun's disc that is lit)", "none",
                     {
                         "hours_without_any_sunlight": (c3 - c2) / 3600.0,
                         "hours_with_reduced_sunlight": (c4 - c1) / 3600.0,
                         "lit_fraction_every_10_min": [round(float(v), 4) for v in line],
                         "first_sample_utc": utc(grid[0]),
                         "smallest_separation_deg": e.minimum_separation_deg,
                         "time_of_smallest_separation": utc(e.minimum_separation_et_s),
                         "sun_elevation_deg": float(sun["SUN"].el_deg[0]),
                         "earth_elevation_deg": float(sun["EARTH"].el_deg[0]),
                         "earth_azimuth_deg": float(sun["EARTH"].az_deg[0]),
                         "sun_angular_radius_deg": float(sun["SUN"].angular_radius_deg[0]),
                         "earth_angular_radius_deg": float(sun["EARTH"].angular_radius_deg[0]),
                     }, "fraction"))

    registered = [check["id"] for check in cases["checks"]]
    assert sorted(row["id"] for row in rows) == sorted(registered), (sorted(row["id"] for row in rows), sorted(registered))
    judged = [row for row in rows if row["kind"] == "pass_fail"]
    return {
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "core": {"frame": d.FRAME, "aberration_correction": d.ABCORR, "kernel_set_id": kernels.kernel_set_id(), "model": "opaque Earth disc of the equatorial radius, no atmosphere; uniform Sun disc; angles seen from the site"},
        "site": cases["site"],
        "contacts_utc": {"C1": utc(c1), "C2": utc(c2), "C3": utc(c3), "C4": utc(c4)},
        "summary": {"pass_fail_checks": len(judged), "passed": sum(r["status"] == "PASS" for r in judged), "failed": sum(r["status"] == "FAIL" for r in judged),
                    "reported_without_verdict": len(rows) - len(judged)},
        "rows": rows,
    }


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def to_markdown(report: dict, cases: dict) -> str:
    s, c = report["summary"], report["contacts_utc"]
    lines = [
        "# Validation table: eclipse of the Sun by the Earth, 14 March 2025, at the Blue Ghost landing point",
        "",
        f"Generated {report['generated_utc']} by `validation/eclipse/compare.py`. Do not edit by hand.",
        "",
        f"**{s['passed']} of {s['pass_fail_checks']} pass/fail checks pass; {s['failed']} fail; {s['reported_without_verdict']} comparisons are reported without a verdict.**",
        "Published values, sources and thresholds are in `cases.json` and `thresholds.json`, committed before the first run (commit a8bbc5a). The test is not blind: see the disclosure in `thresholds.json`.",
        "",
        f"Model: {report['core']['model']}. Site: {report['site']['as_printed']} (LROC).",
        f"Computed contacts (UTC): C1 {c['C1']}, C2 {c['C2']}, C3 {c['C3']}, C4 {c['C4']}.",
        "",
        "| Quantity | Published | Computed | Difference | Threshold | Result |",
        "|---|---|---|---|---|---|",
    ]
    details = []
    for row in report["rows"]:
        diff = "" if row["difference"] is None else f"{row['difference']:+.2f} {row['unit']}"
        threshold = "" if row["threshold"] is None else (f"< {row['threshold']} {row['unit']}" if isinstance(row["threshold"], float) else str(row["threshold"]))
        status = f"**{row['status']}**" if row["status"] else "reported"
        published, computed = row["published"], row["computed"]
        if isinstance(computed, dict):
            details.append(row)
            published = "see below" if isinstance(published, dict) else published
            computed = "see below"
        lines.append(f"| {row['quantity']} | {_fmt(published)} | {_fmt(computed)} | {diff} | {threshold} | {status} |")
    lines.append("")
    for row in report["rows"]:
        if row["note"]:
            lines.append(f"- *{row['quantity']}*: {row['note']}.")
    for row in details:
        if isinstance(row["published"], dict):
            lines.append(f"- *{row['quantity']}*, published: " + "; ".join(f"{k.replace('_', ' ')} {v}" for k, v in row["published"].items()))
        lines.append(f"- *{row['quantity']}*, computed:")
        lines += [f"  - {key.replace('_', ' ')}: {_fmt(value)}" for key, value in row["computed"].items()]
    lines += ["", "Time zone of the operator's times: " + cases["time_zone_of_the_firefly_times"]["reading_used"] + " " + cases["time_zone_of_the_firefly_times"]["check_without_the_core"], "", "## Sources", ""]
    for key, src in cases["sources"].items():
        lines.append(f"- `{key}`: {src['title']}. {src['url']} (retrieved {src['retrieved_utc']})")
    return "\n".join(lines) + "\n"


def main() -> None:
    report = run()
    cases, _ = load()
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "validation_table.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (RESULTS / "validation_table.md").write_text(to_markdown(report, cases), encoding="utf-8")
    print("contacts", report["contacts_utc"])
    for row in report["rows"]:
        diff = "" if row["difference"] is None else f"{row['difference']:+.3f}"
        print(f"{row['id']:32s} {row['kind']:9s} {str(row['status']):5s} diff {diff:9s} computed {str(row['computed'])[:110]}")
    print(report["summary"])


if __name__ == "__main__":
    main()
