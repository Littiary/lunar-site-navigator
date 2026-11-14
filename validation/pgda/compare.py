"""Compare our long-term visibility shares with the published LOLA illumination maps.

Reads ``points.json`` and ``thresholds.json`` (committed before any map value was read),
``results/our_shares.json`` (written by ``compute.py`` without the maps) and the maps
downloaded by ``fetch.py``; writes ``results/validation_table.json`` and ``.md``.

Usage (from the repository root)::

    python -m validation.pgda.compare
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np

from .fetch import cache_dir, read_files
from .select_points import grid as selection_grid

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
MAPS = {"sun": "AVGVISIB_85S_060M_201608", "earth": "AVGVISIB_85S_060M_201608_EARTH", "permanent_shadow": "LPSR_85S_060M_201608"}
STRATA = ("ridge_or_rim", "plain_or_slope", "floor", "site_record")


def read_map(name: str):
    """A published map as a float array of physical values, with its grid from the label."""
    from lsn_data.georef import PolarGrid
    from lsn_data.pdslabel import parse_label

    label = parse_label(cache_dir() / f"{name}.LBL")
    g = PolarGrid.from_label(label)
    raw = np.memmap(cache_dir() / f"{name}.IMG", dtype="<i2", mode="r", shape=(g.n_rows, g.n_cols))
    return raw, float(label["SCALING_FACTOR"]), float(label["OFFSET"]), g


def _stats(ours: np.ndarray, ref: np.ndarray) -> dict:
    diff = ours - ref
    out = {
        "points": int(diff.size),
        "mean_signed": float(diff.mean()),
        "median_signed": float(np.median(diff)),
        "p10_signed": float(np.quantile(diff, 0.10)),
        "p90_signed": float(np.quantile(diff, 0.90)),
        "median_absolute": float(np.median(np.abs(diff))),
        "max_absolute": float(np.abs(diff).max()),
        "beyond_0.05": int(np.count_nonzero(np.abs(diff) > 0.05)),
        "beyond_0.10": int(np.count_nonzero(np.abs(diff) > 0.10)),
        "beyond_0.20": int(np.count_nonzero(np.abs(diff) > 0.20)),
    }
    out["pearson_r"] = float(np.corrcoef(ours, ref)[0, 1]) if diff.size > 2 and ours.std() > 0 and ref.std() > 0 else None
    return out


def run() -> dict:
    points = json.loads((HERE / "points.json").read_text(encoding="utf-8"))["points"]
    limits = json.loads((HERE / "thresholds.json").read_text(encoding="utf-8"))["thresholds_run_A"]
    ours = json.loads((RESULTS / "our_shares.json").read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in ours["points"]}

    maps = {key: read_map(name) for key, name in MAPS.items()}
    reference_grid = selection_grid()
    for _, _, _, g in maps.values():
        assert (g.n_rows, g.n_cols, g.pixel_m, g.x_ul_m, g.y_ul_m) == (reference_grid.n_rows, reference_grid.n_cols, reference_grid.pixel_m, reference_grid.x_ul_m, reference_grid.y_ul_m), "the grid of the maps differs from the grid the points were chosen on"

    rows = []
    for p in points:
        i, j = p["line"], p["sample"]
        ref = {key: float(raw[i, j]) * scale + offset for key, (raw, scale, offset, _) in maps.items() if key != "permanent_shadow"}
        raw, scale, offset, _ = maps["permanent_shadow"]
        flags = np.round(raw[max(i - 1, 0) : i + 2, max(j - 1, 0) : j + 2].astype(np.float64) * scale + offset)
        mine = by_id[p["id"]]
        rows.append({
            "id": p["id"], "stratum": p["stratum"], "lon_deg": p["lon_deg"], "lat_deg": p["lat_deg"],
            "published_sun": ref["sun"], "published_earth": ref["earth"], "published_permanent_shadow": int(flags[min(i, 1), min(j, 1)]),
            "permanent_shadow_neighbourhood_mixed": bool(flags.min() != flags.max()),
            "run_A": mine["run_A_60m"]["shares"], "run_B": mine["run_B_production"]["shares"],
            "run_A_second_cycle": mine["run_A_60m"].get("shares_second_cycle"),
            "share_of_horizon_set_closer_than_1km": {"run_A": mine["run_A_60m"]["share_of_horizon_set_closer_than_1km"], "run_B": mine["run_B_production"]["share_of_horizon_set_closer_than_1km"]},
        })

    def series(run_key: str, height: str, body: str, subset=None):
        chosen = [r for r in rows if subset is None or r["stratum"] == subset]
        return np.array([r[run_key][height][body] for r in chosen]), np.array([r[f"published_{body}"] for r in chosen])

    tables = {}
    for run_key in ("run_A", "run_B"):
        for height in ("0m", "2m"):
            for body in ("sun", "earth"):
                entry = {"all": _stats(*series(run_key, height, body))}
                for stratum in STRATA:
                    entry[stratum] = _stats(*series(run_key, height, body, stratum))
                tables[f"{run_key}/{height}/{body}"] = entry

    # Permanent shadow: "never lit in our period" against the published flag.
    clear = [r for r in rows if not r["permanent_shadow_neighbourhood_mixed"]]
    agree = [r for r in clear if (r["run_A"]["0m"]["sun"] == 0.0) == (r["published_permanent_shadow"] == 1)]
    shadow = {
        "points_compared": len(clear), "points_left_out_as_boundary": len(rows) - len(clear), "agreement": len(agree) / len(clear),
        "published_shadow_and_ours_never_lit": sum(1 for r in clear if r["published_permanent_shadow"] == 1 and r["run_A"]["0m"]["sun"] == 0.0),
        "published_shadow_but_ours_lit": [{"id": r["id"], "our_share": r["run_A"]["0m"]["sun"]} for r in clear if r["published_permanent_shadow"] == 1 and r["run_A"]["0m"]["sun"] > 0.0],
        "published_lit_but_ours_never_lit": [{"id": r["id"], "published_share": r["published_sun"]} for r in clear if r["published_permanent_shadow"] == 0 and r["run_A"]["0m"]["sun"] == 0.0],
    }

    checks = []
    for body in ("sun", "earth"):
        s, limit = tables[f"run_A/0m/{body}"]["all"], limits[body]
        checks += [
            {"id": f"{body}_correlation", "measured": s["pearson_r"], "threshold": limit["pearson_r_min"], "rule": ">=", "status": "PASS" if s["pearson_r"] >= limit["pearson_r_min"] else "FAIL"},
            {"id": f"{body}_median_absolute_difference", "measured": s["median_absolute"], "threshold": limit["median_absolute_difference_max"], "rule": "<=", "status": "PASS" if s["median_absolute"] <= limit["median_absolute_difference_max"] else "FAIL"},
            {"id": f"{body}_median_signed_difference", "measured": s["median_signed"], "threshold": limit["median_signed_difference_abs_max"], "rule": "abs <=", "status": "PASS" if abs(s["median_signed"]) <= limit["median_signed_difference_abs_max"] else "FAIL"},
        ]
    checks.append({"id": "sun_permanent_shadow_agreement", "measured": shadow["agreement"], "threshold": limits["sun"]["permanent_shadow_agreement_min"], "rule": ">=",
                   "status": "PASS" if shadow["agreement"] >= limits["sun"]["permanent_shadow_agreement_min"] else "FAIL"})

    second = [r for r in rows if r["run_A_second_cycle"]]
    period = {body: float(max(abs(r["run_A"]["0m"][body] - r["run_A_second_cycle"]["0m"][body]) for r in second)) for body in ("sun", "earth")}
    files = {entry["name"]: entry for entry in read_files()["files"]}
    return {
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "our_settings": ours["settings"], "our_terrain": ours["terrain"],
        "published_maps": {key: {"file": f"{name}.IMG", "sha256": files[f"{name}.IMG"]["sha256"], "url": files[f"{name}.IMG"]["url"], "retrieved_utc": files[f"{name}.IMG"]["retrieved_utc"]} for key, name in MAPS.items()},
        "summary": {"checks": len(checks), "passed": sum(c["status"] == "PASS" for c in checks), "failed": sum(c["status"] == "FAIL" for c in checks)},
        "checks": checks,
        "distribution": tables,
        "permanent_shadow": shadow,
        "period_sensitivity": {"points": len(second), "largest_change_between_two_nodal_cycles": period},
        "points": rows,
    }


def to_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        "# Validation table: long-term Sun and Earth visibility versus the published LOLA illumination maps",
        "",
        f"Generated {report['generated_utc']} by `validation/pgda/compare.py`. Do not edit by hand.",
        "",
        f"**{s['passed']} of {s['checks']} pre-registered checks pass, {s['failed']} fail** (run A, observer at 0 m; thresholds in `thresholds.json`, points in `points.json`, both committed before the maps were read: commit d044186).",
        "",
        "| Check (run A: 60 m terrain, 0 m, 100 points) | Measured | Threshold | Result |",
        "|---|---|---|---|",
    ]
    for c in report["checks"]:
        lines.append(f"| {c['id'].replace('_', ' ')} | {c['measured']:+.4f} | {c['rule']} {c['threshold']} | **{c['status']}** |")
    lines += ["", "## Distribution of the differences (our share minus the published value)", "",
              "| Run | Height | Body | Stratum | Points | r | Median | Mean | 10th pct | 90th pct | Median abs | Max abs | > 0.05 | > 0.10 | > 0.20 |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    names = {"run_A": "A: 60 m terrain", "run_B": "B: production terrain"}
    for key, entry in report["distribution"].items():
        run_key, height, body = key.split("/")
        for stratum, st in entry.items():
            r = "" if st["pearson_r"] is None else f"{st['pearson_r']:.3f}"
            lines.append(f"| {names[run_key]} | {height} | {body} | {stratum.replace('_', ' ')} | {st['points']} | {r} | {st['median_signed']:+.3f} | {st['mean_signed']:+.3f} | {st['p10_signed']:+.3f} | {st['p90_signed']:+.3f} | "
                         f"{st['median_absolute']:.3f} | {st['max_absolute']:.3f} | {st['beyond_0.05']} | {st['beyond_0.10']} | {st['beyond_0.20']} |")
    sh, ps = report["permanent_shadow"], report["period_sensitivity"]
    lines += [
        "",
        "## Permanent shadow",
        "",
        f"{sh['points_compared']} points compared ({sh['points_left_out_as_boundary']} left out because their 3 x 3 neighbourhood in the published flag map is mixed): agreement {100 * sh['agreement']:.1f} %. "
        f"Published as permanent shadow and never lit in our period: {sh['published_shadow_and_ours_never_lit']}. Published as permanent shadow but lit in ours: {len(sh['published_shadow_but_ours_lit'])}. Published as lit but never lit in ours: {len(sh['published_lit_but_ours_never_lit'])}.",
        "",
        "## Effect of the period",
        "",
        f"For {ps['points']} points the share was also computed over a second nodal cycle starting 2000-01-01: the largest change is {ps['largest_change_between_two_nodal_cycles']['sun']:.4f} for the Sun and {ps['largest_change_between_two_nodal_cycles']['earth']:.4f} for the Earth.",
        "",
        "## Sources",
        "",
    ]
    for key, entry in report["published_maps"].items():
        lines.append(f"- {key.replace('_', ' ')}: `{entry['file']}`, sha256 `{entry['sha256']}`, {entry['url']} (retrieved {entry['retrieved_utc']})")
    return "\n".join(lines) + "\n"


def main() -> None:
    report = run()
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "validation_table.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    (RESULTS / "validation_table.md").write_text(to_markdown(report), encoding="utf-8")
    for c in report["checks"]:
        print(f"{c['id']:36s} measured {c['measured']:+.4f}  {c['rule']} {c['threshold']}  {c['status']}")
    for key in ("run_A/0m/sun", "run_A/0m/earth", "run_B/0m/sun", "run_B/0m/earth", "run_A/2m/sun"):
        for stratum, st in report["distribution"][key].items():
            print(f"{key:16s} {stratum:15s} n {st['points']:3d} r {st['pearson_r'] if st['pearson_r'] is None else round(st['pearson_r'], 3)} median {st['median_signed']:+.3f} mean {st['mean_signed']:+.3f} p10 {st['p10_signed']:+.3f} p90 {st['p90_signed']:+.3f} medabs {st['median_absolute']:.3f} max {st['max_absolute']:.3f} >0.05 {st['beyond_0.05']} >0.10 {st['beyond_0.10']} >0.20 {st['beyond_0.20']}")
    print("permanent shadow", {k: v for k, v in report["permanent_shadow"].items() if not isinstance(v, list)}, len(report["permanent_shadow"]["published_shadow_but_ours_lit"]), len(report["permanent_shadow"]["published_lit_but_ours_never_lit"]))
    print("period", report["period_sensitivity"])
    print(report["summary"])


if __name__ == "__main__":
    main()
