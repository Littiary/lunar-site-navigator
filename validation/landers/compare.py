"""Compare the core with published records of real lunar landers.

Reads ``cases.json`` and ``thresholds.json`` (both committed before this script was run
for the first time) and writes ``results/validation_table.json`` and ``.md``.

Usage (from the repository root; the Chandrayaan-3 case needs the LOLA data)::

    python -m validation.landers.compare
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import spiceypy as spice

from lsncore import events as ev
from lsncore.ephem import directions as d
from lsncore.ephem import kernels

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
OBSERVER_HEIGHT_M = 2.0


def load() -> tuple[dict, dict]:
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    rules = json.loads((HERE / "thresholds.json").read_text(encoding="utf-8"))["rules"]
    return cases, rules


def _published(case: dict, item: str):
    return next(p for p in case["published"] if p["id"] == item)["value"]


# --------------------------------------------------------------------------- geometry helpers


def centre_direction(et: float, body: str) -> np.ndarray:
    """Unit vector from the Moon's centre to the body, body-fixed frame, as seen (LT+S)."""
    position, _ = spice.spkpos(body, et, d.FRAME, d.ABCORR, "MOON")
    return np.asarray(position) / np.linalg.norm(position)


def sub_point(et: float, body: str) -> tuple[float, float]:
    """East longitude and latitude (deg) of the point on the Moon that has the body at its zenith."""
    u = centre_direction(et, body)
    return float(np.degrees(np.arctan2(u[1], u[0]))), float(np.degrees(np.arcsin(u[2])))


def altaz_without_parallax(et: float, body: str, lon_deg: float, lat_deg: float) -> tuple[float, float]:
    """Altitude and azimuth at a site of the direction from the Moon's centre to the body."""
    east, north, up = d.Site(lon_deg, lat_deg).enu()
    u = centre_direction(et, body)
    return float(np.degrees(np.arcsin(u @ up))), float(np.degrees(np.arctan2(u @ east, u @ north)) % 360.0)


def _wrap(angle_deg: float) -> float:
    return (angle_deg + 180.0) % 360.0 - 180.0


def _row(check_id, kind, quantity, published, computed, unit, threshold=None, difference=None, status=None, note=""):
    return {"id": check_id, "kind": kind, "quantity": quantity, "published": published, "computed": computed, "unit": unit,
            "difference": difference, "threshold": threshold, "status": status, "note": note}


# --------------------------------------------------------------------------- Apollo


def apollo(case: dict, rules: dict) -> list:
    prefix = case["id"]
    limit = rules["R1_angle_same_inputs"]["threshold_deg"]
    et = d.utc_to_et(_published(case, "landing_time"))
    site = _published(case, "alsj_site")
    row = _published(case, "alsj_landing_row")
    actual = _published(case, "landing_site_actual")
    out = []

    def judged(name, quantity, published, computed, difference):
        out.append(_row(f"{prefix}_{name}", "pass_fail", quantity, published, computed, "deg", limit, difference, "PASS" if abs(difference) < limit else "FAIL"))

    for body, tag, label in (("SUN", "sun", "Sun"), ("EARTH", "earth", "Earth")):
        alt, az = altaz_without_parallax(et, body, site["lon_deg"], site["lat_deg"])
        lon, lat = sub_point(et, body)
        sub = "sub_solar" if body == "SUN" else "sub_earth"
        judged(f"{tag}_altitude", f"{label} altitude at landing (source's site coordinates)", row[f"{tag}_alt_deg"], alt, alt - row[f"{tag}_alt_deg"])
        d_az = _wrap(az - row[f"{tag}_az_deg"])
        out.append(_row(f"{prefix}_{tag}_azimuth", "pass_fail", f"{label} azimuth at landing (difference on the sky)", row[f"{tag}_az_deg"], az, "deg", limit,
                        d_az * np.cos(np.radians(alt)), "PASS" if abs(d_az * np.cos(np.radians(alt))) < limit else "FAIL", f"azimuth difference {d_az:+.3f} deg at altitude {alt:.1f} deg"))
        judged(f"{sub}_longitude", f"East longitude of the {sub.replace('_', '-')} point", row[f"{sub}_lon_deg"], lon, _wrap(lon - row[f"{sub}_lon_deg"]))
        judged(f"{sub}_latitude", f"Latitude of the {sub.replace('_', '-')} point", row[f"{sub}_lat_deg"], lat, lat - row[f"{sub}_lat_deg"])

    real_site = d.Site(actual["lon_deg"], actual["lat_deg"], 0.0)
    sun_actual = d.topocentric_exact(real_site, et, "SUN")
    target = _published(case, "targeted_sun_angle")
    if prefix == "apollo11":
        out.append(_row("apollo11_sun_at_actual_site", "reported", "Sun elevation at the actual landing site and time, against the launch-window target", target, float(sun_actual.el_deg[0]), "deg",
                        difference=float(sun_actual.el_deg[0]) - target, note="The published value is a planned angle; it is not judged."))
        earth = d.topocentric_exact(real_site, et, "EARTH")
        out.append(_row("apollo11_earth_topocentric", "reported", "Earth elevation seen from the actual site (with parallax) against the source's value (without parallax)", row["earth_alt_deg"], float(earth.el_deg[0]), "deg",
                        difference=float(earth.el_deg[0]) - row["earth_alt_deg"], note="Shows the size of the parallax the source leaves out."))
    else:
        limit2 = rules["R2_targeted_sun_angle"]["threshold_deg"]
        et_planned = d.utc_to_et(_published(case, "planned_landing_time"))
        sun_planned = d.topocentric_exact(real_site, et_planned, "SUN")
        diff = float(sun_planned.el_deg[0]) - target
        out.append(_row("apollo16_targeted_sun_at_planned_time", "pass_fail", "Sun elevation at the planned landing time against the targeted angle of the launch window", target, float(sun_planned.el_deg[0]), "deg",
                        limit2, diff, "PASS" if abs(diff) < limit2 else "FAIL", "planned landing 1972-04-20 20:39:00 UTC, 5 h 44 min 35 s before the actual landing"))
        slip = float(sun_actual.el_deg[0] - sun_planned.el_deg[0])
        out.append(_row("apollo16_slip_effect", "reported", "Change of the Sun elevation caused by the landing delay", round(row["sun_alt_deg"] - target, 2), slip, "deg",
                        difference=slip - (row["sun_alt_deg"] - target), note=f"Sun elevation at the actual landing time and site: {float(sun_actual.el_deg[0]):.2f} deg; the table of SP-4029 still lists the targeted {target} deg."))
    return out


# --------------------------------------------------------------------------- Blue Ghost


def blue_ghost(case: dict, rules: dict) -> list:
    site_p = _published(case, "landing_site")
    site = d.Site(site_p["lon_deg"], site_p["lat_deg"], site_p["height_m"] / 1000.0)
    landing = d.utc_to_et(_published(case, "landing_time"))
    daylight_end = landing + 3600.0 * _published(case, "daylight_hours")
    allowance = 3600.0 * rules["R4_one_sided_physical_bound"]["rounding_allowance_hours"]
    start, stop = d.utc_to_et("2025-03-15T00:00:00"), d.utc_to_et("2025-03-18T00:00:00")
    table = d.direction_table(start - 3600.0 + 3600.0 * np.arange(int((stop - start) / 3600.0) + 4))
    local_radius_m = (d.MOON_RADIUS_KM + site.height_km) * 1000.0
    dip = np.degrees(np.arccos(local_radius_m / (local_radius_m + OBSERVER_HEIGHT_M)))
    horizon = ev.Horizon(0.0, 1.0, np.full(360, -dip))
    direction = ev.site_direction(site, table, "SUN")
    result = ev.find_events(direction, horizon, start, stop, thresholds=("upper_limb", "center", "lower_limb"))
    sets = {e.threshold: e.et_s for e in result.events if e.type == "set"}
    last_light = sets["upper_limb"]

    window = (d.utc_to_et("2025-03-16T05:00:00"), d.utc_to_et("2025-03-17T05:00:00"))
    out = [
        _row("blue_ghost_sunset_day", "pass_fail", "Day of the lunar sunset (last light on the smooth local sphere)", "2025-03-16 (US Central Daylight Time)", d.et_to_utc_z(last_light), "UTC",
             "inside 2025-03-16T05:00Z to 2025-03-17T05:00Z", None, "PASS" if window[0] <= last_light <= window[1] else "FAIL"),
        _row("blue_ghost_daylight_not_after_last_light", "pass_fail", "Recorded daylight must end before geometric last light", d.et_to_utc_z(daylight_end) + " (landing + 346 h)", d.et_to_utc_z(last_light), "UTC",
             "last light not earlier than landing + 346 h - 0.5 h", (last_light - (daylight_end - allowance)) / 3600.0, "PASS" if last_light >= daylight_end - allowance else "FAIL",
             "difference: hours by which the inequality is satisfied"),
    ]
    spot = d.topocentric_exact(site, np.array([daylight_end, landing]), "SUN")
    az, el, radius = spot.az_deg, spot.el_deg, spot.angular_radius_deg
    final_minus_night = d.utc_to_et(_published(case, "final_data")) - 3600.0 * _published(case, "night_operation")
    out.append(_row("blue_ghost_end_of_daylight", "reported", "End of recorded daylight against smooth-sphere sunset",
                    {"landing_plus_346h": d.et_to_utc_z(daylight_end), "final_data_minus_5h": d.et_to_utc_z(final_minus_night) + " or earlier ('just over 5 hours')"},
                    {"lower_limb_touches_horizon": d.et_to_utc_z(sets["lower_limb"]), "centre_on_horizon": d.et_to_utc_z(sets["center"]), "last_light": d.et_to_utc_z(last_light),
                     "sun_upper_limb_elevation_at_landing_plus_346h_deg": float(el[0] + radius[0]), "sun_centre_elevation_at_landing_deg": float(el[1]), "sun_azimuth_at_landing_plus_346h_deg": float(az[0])},
                    "UTC", difference=(last_light - daylight_end) / 3600.0,
                    note="difference: hours from the end of recorded daylight to geometric last light; a local horizon as high as the Sun's upper limb at that moment, or the operator's definition of night, would account for it"))
    return out


# --------------------------------------------------------------------------- Chandrayaan-3


def chandrayaan3(case: dict, rules: dict) -> list:
    from lsncore.dem import open_lola
    from lsncore.horizon import HorizonSettings, compute_horizon

    site_p = _published(case, "landing_site")
    terrain = open_lola()
    result = compute_horizon(terrain, site_p["lat_deg"], site_p["lon_deg"], [OBSERVER_HEIGHT_M], 0.25, 300000.0, HorizonSettings())
    elevation = np.asarray(result.elevation_deg[0], dtype=np.float64)
    if not np.all(np.isfinite(elevation)):
        raise RuntimeError("terrain horizon has gaps at this site")
    site = d.Site(site_p["lon_deg"], site_p["lat_deg"], result.surface_height_m / 1000.0)
    start, stop = d.utc_to_et("2023-08-24T00:00:00"), d.utc_to_et("2023-10-05T00:00:00")
    table = d.direction_table(start - 3600.0 + 3600.0 * np.arange(int((stop - start) / 3600.0) + 4))
    direction = ev.site_direction(site, table, "SUN")
    sleep_date = d.utc_to_et("2023-09-03T18:30:00")  # start of 4 September in Indian Standard Time

    def night(horizon):
        found = ev.find_events(direction, horizon, start, stop, thresholds=("upper_limb",))
        sets = [e for e in found.events if e.type == "set"]
        rises = [e for e in found.events if e.type == "rise" and e.et_s > sleep_date]
        return found, sets, rises

    profile = ev.Horizon(0.0, result.azimuth_step_deg, elevation, np.asarray(result.distance_m[0], dtype=np.float64))
    found, sets, rises = night(profile)
    _, sphere_sets, sphere_rises = night(ev.Horizon.smooth_sphere(OBSERVER_HEIGHT_M))
    sunrise = rises[0]
    deadline = d.utc_to_et("2023-09-22T18:30:00")
    day = np.linspace(d.utc_to_et("2023-09-21T18:30:00"), deadline, 49)
    _, el, _ = direction(day)
    margin_h = (deadline - sunrise.et_s) / 3600.0
    out = [
        _row("chandrayaan3_sun_up_by_expected_awakening", "pass_fail", "Sunrise over the terrain horizon must precede the end of the expected wake-up day", "2023-09-22 (Indian Standard Time), 'around'", d.et_to_utc_z(sunrise.et_s), "UTC",
             "not later than 2023-09-22T18:30:00Z", margin_h, "PASS" if sunrise.et_s <= deadline else "FAIL", "difference: hours by which the inequality is satisfied"),
        _row("chandrayaan3_night", "reported", "Lunar night at the landing site",
             {"sleep_status_date": "2023-09-04 (IST)", "expected_awakening": "around 2023-09-22 (IST)"},
             {
                 "sunset_last_light_terrain": [d.et_to_utc_z(e.et_s) for e in sets],
                 "sunrise_first_light_terrain": d.et_to_utc_z(sunrise.et_s),
                 "sunrise_azimuth_deg": sunrise.center_azimuth_deg,
                 "sunrise_horizon_elevation_deg": float(profile.elevation_at(sunrise.azimuth_deg)),
                 "sunrise_obstacle_distance_km": sunrise.obstacle_distance_m / 1000.0,
                 "sunset_last_light_smooth_sphere": [d.et_to_utc_z(e.et_s) for e in sphere_sets],
                 "sunrise_first_light_smooth_sphere": d.et_to_utc_z(sphere_rises[0].et_s),
                 "terrain_delay_of_sunrise_h": (sunrise.et_s - sphere_rises[0].et_s) / 3600.0,
                 "sun_centre_elevation_on_2023-09-22_IST_deg": [float(el.min()), float(el.max())],
                 "all_sun_events_terrain": [[e.type, d.et_to_utc_z(e.et_s)] for e in found.events],
                 "dem_surface_height_m": result.surface_height_m,
                 "lroc_elevation_m": site_p["height_m"],
                 "dem_set": terrain.describe()["dem_set_id"],
                 "horizon_coverage_complete": bool(result.coverage_complete),
             },
             "UTC", difference=(d.utc_to_et("2023-09-21T18:30:00") - sunrise.et_s) / 86400.0,
             note="difference: days from computed sunrise to the start of 22 September 2023 (IST)"),
    ]
    return out


# --------------------------------------------------------------------------- report


RUNNERS = {"apollo11": apollo, "apollo16": apollo, "blue_ghost_m1": blue_ghost, "chandrayaan3": chandrayaan3}


def terrain_available() -> bool:
    """True if the LOLA terrain of the data stream can be opened on this machine."""
    try:
        from lsncore.dem import open_lola

        open_lola()
        return True
    except Exception:
        return False


def run(include_terrain_case: bool | None = None) -> dict:
    """Recompute every case. Without terrain data the Chandrayaan-3 rows are taken from the
    stored result file and marked as such."""
    kernels.load()
    cases, rules = load()
    if include_terrain_case is None:
        include_terrain_case = terrain_available()
    out = []
    for case in cases["cases"]:
        if case["id"] == "chandrayaan3" and not include_terrain_case:
            stored = json.loads((RESULTS / "validation_table.json").read_text(encoding="utf-8"))
            kept = next(c for c in stored["cases"] if c["id"] == "chandrayaan3")
            kept["recomputed"] = False
            out.append(kept)
            continue
        rows = RUNNERS[case["id"]](case, rules)
        expected = [check["id"] for check in case["checks"]]
        assert [row["id"] for row in rows] == expected or sorted(row["id"] for row in rows) == sorted(expected), (case["id"], [row["id"] for row in rows], expected)
        out.append({"id": case["id"], "mission": case["mission"], "terrain": case["terrain"], "recomputed": True, "rows": rows})
    judged = [row for case in out for row in case["rows"] if row["kind"] == "pass_fail"]
    return {
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "core": {"frame": d.FRAME, "aberration_correction": d.ABCORR, "kernel_set_id": kernels.kernel_set_id()},
        "summary": {"pass_fail_checks": len(judged), "passed": sum(r["status"] == "PASS" for r in judged), "failed": sum(r["status"] == "FAIL" for r in judged),
                    "reported_without_verdict": sum(row["kind"] == "reported" for case in out for row in case["rows"])},
        "cases": out,
    }


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    if isinstance(value, dict):
        return "; ".join(f"{k.replace('_', ' ')}: {_fmt(v)}" for k, v in value.items())
    if isinstance(value, list):
        return ", ".join(_fmt(v) for v in value)
    return str(value)


def to_markdown(report: dict, cases: dict) -> str:
    s = report["summary"]
    lines = [
        "# Validation table: core versus published records of real lunar landers",
        "",
        f"Generated {report['generated_utc']} by `validation/landers/compare.py`. Do not edit by hand.",
        "",
        f"**{s['passed']} of {s['pass_fail_checks']} pass/fail checks pass; {s['failed']} fail; {s['reported_without_verdict']} comparisons are reported without a verdict.**",
        "Published values, sources, precision and thresholds are in `cases.json` and `thresholds.json`, committed before the first run (commit eaf5634). The test is not blind: see the disclosure in `thresholds.json`.",
        "",
    ]
    for case in report["cases"]:
        lines += [f"## {case['mission']}", "", f"Terrain: {case['terrain'].rstrip('.')}.", "", "| Quantity | Published | Computed | Difference | Threshold | Result |", "|---|---|---|---|---|---|"]
        details = []
        for row in case["rows"]:
            diff = "" if row["difference"] is None else f"{row['difference']:+.3f}"
            threshold = "" if row["threshold"] is None else (f"< {row['threshold']} {row['unit']}" if isinstance(row["threshold"], float) else str(row["threshold"]))
            status = f"**{row['status']}**" if row["status"] else "reported"
            published, computed = row["published"], row["computed"]
            if isinstance(published, dict) or isinstance(computed, dict):
                details.append(row)
                published = _fmt(published) if not isinstance(published, dict) else "see below"
                computed = "see below"
            lines.append(f"| {row['quantity']} | {_fmt(published)} | {_fmt(computed)} | {diff} | {threshold} | {status} |")
        lines.append("")
        for row in case["rows"]:
            if row["note"]:
                lines.append(f"- *{row['quantity']}*: {row['note']}.")
        for row in details:
            lines.append(f"- *{row['quantity']}*, published:")
            lines += [f"  - {key.replace('_', ' ')}: {_fmt(value)}" for key, value in (row["published"].items() if isinstance(row["published"], dict) else [("value", row["published"])])]
            lines.append(f"- *{row['quantity']}*, computed:")
            lines += [f"  - {key.replace('_', ' ')}: {_fmt(value)}" for key, value in row["computed"].items()]
        lines.append("")
    lines += ["## Sources", ""]
    for key, src in cases["sources"].items():
        lines.append(f"- `{key}`: {src['title']}. {src['url']} (retrieved {src['retrieved_utc']})")
    return "\n".join(lines) + "\n"


def main() -> None:
    report = run()
    cases, _ = load()
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "validation_table.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (RESULTS / "validation_table.md").write_text(to_markdown(report, cases), encoding="utf-8")
    for case in report["cases"]:
        for row in case["rows"]:
            diff = "" if row["difference"] is None else f"{row['difference']:+.4f}"
            print(f"{row['id']:44s} {row['kind']:9s} {str(row['status']):5s} diff {diff:10s} computed {_fmt(row['computed'])[:150]}")
    print(report["summary"])


if __name__ == "__main__":
    main()
