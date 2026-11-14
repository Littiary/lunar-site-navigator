"""Build the validation card: every check of the ephemeris, time and event layer in one table.

Each row says what was compared, against which source, the threshold and where it was
fixed, the measured difference and pass or fail. Every measured value is recomputed here
from the stored reference data and the current code; nothing is typed in by hand.

Writes ``validation_card.json`` and ``validation_card.md`` next to this file.

Usage (from the repository root)::

    python -m validation.card.build
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import subprocess
from pathlib import Path

import numpy as np

from lsncore import events as ev
from lsncore.ephem import directions as d
from lsncore.ephem import kernels
from validation.horizons import compare as horizons
from validation.horizons_rts import compare as horizons_rts

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
ARCSEC = 3600.0
HORIZONS_URL = "https://ssd.jpl.nasa.gov/horizons/"

SEPARATE_COMMIT = "committed on its own before the reference data was fetched or compared"
WITH_TEST = "written in the acceptance test before the implementation was run; committed together with it"


def _load(path: str):
    spec = importlib.util.spec_from_file_location(Path(path).stem, REPO / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _commit() -> dict:
    def git(*args):
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout.strip()

    return {"commit": git("rev-parse", "--short", "HEAD"), "uncommitted_changes": bool(git("status", "--porcelain"))}


def _check(cid, group, quantity, against, threshold, unit, fixed_how, fixed_where, measured, evidence, cases, limits, comparison="<"):
    passed = measured <= threshold if comparison == "<=" else measured < threshold
    return {
        "id": cid,
        "group": group,
        "quantity": quantity,
        "compared_against": against,
        "cases": cases,
        "threshold": {"value": threshold, "unit": unit, "comparison": comparison},
        "threshold_fixed": {"how": fixed_how, "where": fixed_where},
        "measured": {"value": float(measured), "unit": unit},
        "status": "PASS" if passed else "FAIL",
        "evidence": evidence,
        "limits": limits,
    }


# --------------------------------------------------------------------------- measurements


def _measure_internal_directions(t) -> dict:
    """SPICE azlcpo and the table shortcut, on the sites and epochs of the acceptance test."""
    start = d.utc_to_et("2026-11-01T00:00:00")
    epochs = start + np.arange(0, 60 * 86400.0, 5.5 * 3600.0)
    table = d.direction_table(epochs)
    azlcpo, shortcut = 0.0, 0.0
    for site in t.SITES:
        from_table = d.topocentric_from_table(site, table)
        for body in d.BODIES:
            exact = d.topocentric_exact(site, epochs, body)
            az, el, _ = d.topocentric_azlcpo(site, epochs, body)
            azlcpo = max(azlcpo, float(d.angular_separation_deg(exact.az_deg, exact.el_deg, az, el).max()))
            got = from_table[body]
            shortcut = max(shortcut, float(d.angular_separation_deg(got.az_deg, got.el_deg, exact.az_deg, exact.el_deg).max()) * ARCSEC)
    return {"azlcpo_deg": azlcpo, "table_vs_exact_arcsec": shortcut, "rows": int(len(t.SITES) * 2 * epochs.size)}


def _measure_interpolation() -> dict:
    start = d.utc_to_et("2026-11-01T00:00:00")
    grid = start + 3600.0 * np.arange(0, 24 * 90 + 1)
    table = d.direction_table(grid)
    query = np.sort(np.random.default_rng(11).uniform(grid[0], grid[-1], 10000))
    direct, interpolated = d.direction_table(query), d.interpolate_table(table, query)
    worst = 0.0
    for body in d.BODIES:
        a, b = interpolated.vectors(body), direct.vectors(body)
        angle = np.degrees(np.arctan2(np.linalg.norm(np.cross(a, b), axis=1), np.sum(a * b, axis=1))) * ARCSEC
        worst = max(worst, float(angle.max()))
    return {"arcsec": worst, "rows": 20000}


def _measure_fraction(t) -> float:
    radius = 0.266
    x = np.linspace(-1.2, 1.2, 481)
    signals = ev.disc_signals(np.full(x.shape, 123.0), x * radius, np.full(x.shape, radius), t.flat_horizon(0.0))
    xc = np.clip(x, -1.0, 1.0)
    closed_form = (np.arccos(-xc) + xc * np.sqrt(1.0 - xc * xc)) / np.pi
    return float(np.abs(signals.visible_fraction - closed_form).max())


def _measure_analytic_events(t) -> dict:
    """Largest time error over the analytic cases of core/tests/events/test_events.py."""
    errors = []
    # 1. Disc sinking linearly through a flat horizon: three limb/centre thresholds and half disc.
    radius, rate, el0 = 0.25, -0.5 / 3600.0, 1.0
    result = ev.find_events(t.linear_body(200.0, el0, rate, radius), t.flat_horizon(), 0.0, 4 * 3600.0)
    expected = {"lower_limb": (el0 - radius) / -rate, "center": el0 / -rate, "half_disc": el0 / -rate, "upper_limb": (el0 + radius) / -rate}
    for name, time in expected.items():
        errors += [abs(event.et_s - time) for event in t.by_threshold(result, name)]
    # 2. Diurnal arc of spherical astronomy.
    phi, dec, radius, period = np.radians(40.0), np.radians(10.0), 0.3, 86400.0
    omega = 2.0 * np.pi / period

    def direction(et):
        h = omega * (np.asarray(et, dtype=float) - period / 2.0)
        el = np.arcsin(np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.cos(h))
        az = np.arctan2(-np.cos(dec) * np.sin(h), np.sin(dec) * np.cos(phi) - np.cos(dec) * np.sin(phi) * np.cos(h))
        return np.degrees(az) % 360.0, np.degrees(el), np.full(h.shape, radius)

    result = ev.find_events(direction, t.flat_horizon(), 0.0, period)
    for name, elevation in (("center", 0.0), ("upper_limb", -radius), ("lower_limb", radius)):
        h0 = np.arccos((np.sin(np.radians(elevation)) - np.sin(phi) * np.sin(dec)) / (np.cos(phi) * np.cos(dec)))
        found = t.by_threshold(result, name)
        errors += [abs(found[0].et_s - (period / 2.0 - h0 / omega)), abs(found[1].et_s - (period / 2.0 + h0 / omega))]
    # 3. Point body crossing a linear terrain ramp.
    step = 0.5
    az_grid = np.arange(0.0, 360.0, step)
    profile = np.interp(az_grid, [0.0, 100.0, 110.0, 120.0, 360.0], [0.0, 0.0, 2.0, 0.0, 0.0])
    rate = 1.0 / 3600.0
    result = ev.find_events(t.linear_body(90.0, 1.0, 0.0, 1e-4, az_rate_deg_per_s=rate), ev.Horizon(0.0, step, profile), 0.0, 40 * 3600.0)
    found = t.by_threshold(result, "center")
    errors += [abs(found[0].et_s - 15.0 * 3600.0), abs(found[1].et_s - 25.0 * 3600.0)]
    # 4. Occultation by a narrow spike, a few minutes long.
    step = 0.01
    az_grid = np.arange(0.0, 360.0, step)
    profile = np.where((az_grid >= 50.0) & (az_grid <= 50.04), 5.0, 0.0)
    rate = 0.5 / 3600.0
    result = ev.find_events(t.linear_body(49.0, 1.0, 0.0, 1e-5, az_rate_deg_per_s=rate), ev.Horizon(0.0, step, profile), 0.0, 6 * 3600.0)
    found = t.by_threshold(result, "center")
    errors += [abs(found[0].et_s - 0.992 / rate), abs(found[1].et_s - 1.048 / rate)]
    return {"max_s": float(max(errors)), "events": len(errors)}


def _measure_sphere_events() -> dict:
    """Smooth-sphere Sun events from the interpolated table against direct SPICE crossings."""
    site = d.Site(lon_deg=15.0, lat_deg=2.0, height_km=0.0)
    start = d.utc_to_et("2026-11-01T00:00:00")
    stop = start + 45 * 86400.0
    table = d.direction_table(start + 3600.0 * np.arange(0, 45 * 24 + 1))
    horizon = ev.Horizon.smooth_sphere(observer_height_m=2.0)
    result = ev.find_events(ev.site_direction(site, table, "SUN"), horizon, start, stop)
    dip = horizon.elevation_deg[0]
    errors = []
    for name, sign in (("upper_limb", 1.0), ("center", 0.0), ("lower_limb", -1.0)):
        for event in [e for e in result.events if e.threshold == name]:
            et = np.array([event.et_s - 2.0, event.et_s + 2.0])
            exact = d.topocentric_exact(site, et, "SUN")
            signal = exact.el_deg + sign * exact.angular_radius_deg - dip
            crossing = et[0] - signal[0] * (et[1] - et[0]) / (signal[1] - signal[0])
            errors.append(abs(crossing - event.et_s))
    return {"max_s": float(max(errors)), "events": len(errors)}


def _measure_scan_completeness() -> dict:
    """Events of a 5 s scan that the default 60 s scan misses, on the rough polar test profile."""
    rng = np.random.default_rng(2026)
    count = 1440
    k = np.fft.rfftfreq(count, d=1.0 / count)
    spectrum = (rng.normal(size=k.size) + 1j * rng.normal(size=k.size)) / np.maximum(k, 1.0) ** 0.9
    spectrum[0] = 0.0
    profile = np.fft.irfft(spectrum, count)
    profile = 1.2 + 1.5 * profile / np.abs(profile).max()
    horizon = ev.Horizon(0.0, 0.25, profile)
    site = d.Site(lon_deg=-135.0, lat_deg=-89.5, height_km=0.0)
    start = d.utc_to_et("2026-11-14T00:00:00")
    stop = start + 30 * 86400.0
    table = d.direction_table(start - 3600.0 + 3600.0 * np.arange(30 * 24 + 4))
    direction = ev.site_direction(site, table, "SUN")
    coarse = ev.find_events(direction, horizon, start, stop, scan_step_s=60.0)
    fine = ev.find_events(direction, horizon, start, stop, scan_step_s=5.0)
    unexplained, short_pairs, shift = 0, 0, 0.0
    for name in ev.THRESHOLDS:
        a = np.array([e.et_s for e in coarse.events if e.threshold == name])
        b = [e for e in fine.events if e.threshold == name]
        tb = np.array([e.et_s for e in b])
        shift = max(shift, float(max(np.abs(tb - t).min() for t in a)))
        missed = [e for e in b if np.abs(a - e.et_s).min() >= 1.0]
        pairs = list(zip(missed[::2], missed[1::2]))
        ok = len(missed) % 2 == 0 and all(x.type != y.type and 0.0 < y.et_s - x.et_s < 60.0 for x, y in pairs)
        short_pairs += len(pairs) if ok else 0
        unexplained += 0 if ok else len(missed)
    return {"unexplained": unexplained, "short_pairs": short_pairs, "events": len(fine.events), "max_shift_s": shift}


# --------------------------------------------------------------------------- card


def build() -> dict:
    kernels.load()
    t_dir = _load("core/tests/ephem/test_directions.py")
    t_ev = _load("core/tests/events/test_events.py")

    hz = horizons.run()
    hz_cases = [row for row in hz["cases"] if "exact" in row]
    hz_rows = sum(row["rows"] for row in hz_cases)
    hz_limit = hz["thresholds"]
    hz_where = "validation/horizons/thresholds.json (commit f25145f)"
    hz_evidence = "validation/horizons/results/validation_table.md; test validation/tests/test_horizons.py"
    hz_cases_text = f"{len(hz_cases)} queries, {hz_rows} rows: 7 lunar surface points (3 south-polar), Sun and Earth, 14-16 Nov 2026 at 10 min and 2026-11-01 to 2045-07-01 at 25 h"
    hz_source = f"JPL Horizons observer tables, DE441 ({HORIZONS_URL}), retrieved 2026-11-14"
    hz_limits = ["No terrain on either side.", "Both sides use JPL ephemerides of the same family (DE440, DE441)."]

    rts = horizons_rts.run()
    rts_pairs = [pair for case in rts["cases"] for pair in case["events"]]
    rts_diffs = [abs(pair["horizons_minus_core_s"]) for pair in rts_pairs if pair["horizons_minus_core_s"] is not None]
    rts_where = "validation/horizons_rts/thresholds.json (commit 48afcd5)"
    rts_cases_text = f"{len(rts_pairs)} sunrise and sunset events: 4 lunar surface points (one 1 km above the sphere), 2026-11-01 to 2026-12-31"
    rts_source = f"JPL Horizons rise/transit/set search, 1-minute step ({HORIZONS_URL}), retrieved 2026-11-14"

    internal = _measure_internal_directions(t_dir)
    interpolation = _measure_interpolation()
    analytic = _measure_analytic_events(t_ev)
    sphere = _measure_sphere_events()
    scan = _measure_scan_completeness()

    checks = [
        _check("direction_exact", "Independent source", "Direction of the Sun and the Earth from a lunar surface point (observer at the site)", hz_source,
               hz_limit["direction_arcsec_max"], "arcsec", SEPARATE_COMMIT, hz_where,
               max(r["exact"]["direction_arcsec_max"] for r in hz_cases), hz_evidence, hz_cases_text, hz_limits),
        _check("direction_table", "Independent source", "Same direction through the site-independent direction table that viewers read", hz_source,
               hz_limit["direction_arcsec_max"], "arcsec", SEPARATE_COMMIT, hz_where,
               max(r["table"]["direction_arcsec_max"] for r in hz_cases), hz_evidence, hz_cases_text,
               hz_limits + ["The table applies light time and stellar aberration for the Moon's centre; that is the measured difference."]),
        _check("angular_diameter", "Independent source", "Apparent angular diameter of the Sun and the Earth", hz_source,
               hz_limit["angular_diameter_arcsec_max"], "arcsec", SEPARATE_COMMIT, hz_where,
               max(r["exact"]["angular_diameter_arcsec_max_abs"] for r in hz_cases), hz_evidence, hz_cases_text,
               ["Equatorial width; the flattening of the Earth's disc (0.3 %) is not modelled."]),
        _check("range", "Independent source", "Distance from the site to the Sun and to the Earth", hz_source,
               hz_limit["range_km_max"], "km", SEPARATE_COMMIT, hz_where,
               max(r["exact"]["range_km_max_abs"] for r in hz_cases), hz_evidence, hz_cases_text, []),
        _check("tdb_minus_utc", "Independent source", "Time scales: TDB minus UTC", hz_source,
               hz_limit["tdb_minus_ut_seconds_max"], "s", SEPARATE_COMMIT, hz_where,
               max(r["tdb_minus_ut_seconds_max_abs"] for r in hz_cases), hz_evidence, hz_cases_text,
               ["For dates after the last announced leap second both sides assume that no further leap second is introduced."]),
        _check("sun_rise_set_time", "Independent source", "Sunrise and sunset times on a smooth sphere (upper limb, with the dip of the horizon)", rts_source,
               rts["thresholds"]["event_time_seconds_max"], "s", SEPARATE_COMMIT, rts_where,
               max(rts_diffs), "validation/horizons_rts/results/validation_table.md; test validation/tests/test_horizons_rts.py", rts_cases_text,
               ["No terrain.", "The reference resolves one minute: a Horizons row is the first search step after the event, so 0 to 60 s is what agreement looks like.", "Sun only."]),
        _check("sun_rise_set_unmatched", "Independent source", "Sunrise and sunset events without a counterpart on the other side", rts_source,
               rts["thresholds"]["unmatched_events_max"], "events", SEPARATE_COMMIT, rts_where,
               sum(case["unmatched"] for case in rts["cases"]), "validation/horizons_rts/results/validation_table.md", rts_cases_text, [], comparison="<="),
        _check("projection_vs_azlcpo", "Independent implementation", "East-North-Up projection of the core against the SPICE routine azlcpo (same kernels, separate code)", "NAIF SPICE Toolkit N0067, routine azlcpo",
               t_dir.TOL_AZLCPO_DEG, "deg", WITH_TEST, "core/tests/ephem/test_directions.py (commit aa86a5a)",
               internal["azlcpo_deg"], "test core/tests/ephem/test_directions.py::test_exact_path_matches_azlcpo", f"{internal['rows']} rows: 7 points, Sun and Earth, 60 days", ["Checks the projection only; ephemeris and frame are shared."]),
        _check("table_shortcut", "Internal consistency", "Direction table (observer at the Moon's centre, site vector subtracted) against the observer at the site", "the core's own exact path (SPICE spkcpo)",
               t_dir.TOL_TABLE_VS_EXACT_ARCSEC, "arcsec", WITH_TEST, "core/tests/ephem/test_directions.py (commit aa86a5a)",
               internal["table_vs_exact_arcsec"], "test core/tests/ephem/test_directions.py::test_table_path_matches_exact_path", f"{internal['rows']} rows: 7 points, Sun and Earth, 60 days", []),
        _check("table_interpolation", "Internal consistency", "Hourly direction table, 4-point interpolation, against direct SPICE at random times", "direct SPICE evaluation",
               t_ev.TOL_INTERPOLATION_ARCSEC, "arcsec", WITH_TEST, "core/tests/events/test_events.py (commit 5a14bcb)",
               interpolation["arcsec"], "test core/tests/events/test_events.py::test_table_interpolation_error_is_below_threshold", f"{interpolation['rows']} vectors over 90 days", ["Valid inside the table only."]),
        _check("visible_fraction", "Closed form", "Visible fraction of a disc cut by a straight horizon", "area of a circular segment (closed form)",
               t_ev.TOL_FRACTION, "fraction of the disc", WITH_TEST, "core/tests/events/test_events.py (commit 5a14bcb)",
               _measure_fraction(t_ev), "test core/tests/events/test_events.py::test_visible_fraction_matches_closed_form_on_flat_horizon", "481 disc positions from fully hidden to fully visible", ["Uniform disc: no limb darkening."]),
        _check("event_time_analytic", "Closed form", "Rise and set times in cases with a known answer (linear motion, diurnal arc, terrain ramp, short occultation)", "closed-form event times",
               t_ev.TOL_EVENT_S, "s", WITH_TEST, "core/tests/events/test_events.py (commit 5a14bcb)",
               analytic["max_s"], "tests core/tests/events/test_events.py (analytic cases)", f"{analytic['events']} events in 4 cases", ["Numerical accuracy for a given horizon profile; not the physical accuracy of an event time on real terrain."]),
        _check("event_time_sphere", "Internal consistency", "Sun events on a smooth sphere from the interpolated table against the zero crossing of the exact SPICE elevation", "direct SPICE evaluation at the site",
               t_ev.TOL_EVENT_S, "s", WITH_TEST, "core/tests/events/test_events.py (commit 5a14bcb)",
               sphere["max_s"], "test core/tests/events/test_events.py::test_smooth_sphere_events_match_direct_spice_crossings", f"{sphere['events']} events, three thresholds, 45 days", ["No terrain."]),
        _check("scan_completeness", "Internal consistency", "Events found by a 5 s scan but not by the default 60 s scan, other than pairs of opposite crossings closer than 60 s (the stated limit)", "the same finder with a 5 s scan step",
               0, "events", "stated limit of the finder (two crossings closer than the scan step can be missed), written in the module before the test", "core/lsncore/events/finder.py (commit 5a14bcb); test added in commit d93504e",
               scan["unexplained"], "test core/tests/events/test_events.py::test_scan_step_does_not_lose_events_on_a_rough_polar_horizon",
               f"{scan['events']} events on an invented rough polar horizon, 30 days; {scan['short_pairs']} pair(s) closer than 60 s were not reported by the default scan",
               ["Invented profile, not terrain.", "Pairs of crossings closer than 60 s are not reported by the default scan."], comparison="<="),
    ]

    return {
        "title": "Validation card: ephemeris, time and event finding",
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_from": _commit(),
        "core": {"frame": d.FRAME, "aberration_correction": d.ABCORR, "reference_radius_km": d.MOON_RADIUS_KM, "kernel_set_id": kernels.kernel_set_id(), "kernels": [k["name"] for k in kernels.read_manifest()["kernels"]]},
        "summary": {"checks": len(checks), "passed": sum(c["status"] == "PASS" for c in checks), "failed": sum(c["status"] == "FAIL" for c in checks)},
        "checks": checks,
        "not_validated": [
            {"item": "Event times and visibility shares on real terrain", "state": "unverified", "reason": "No independent illumination product or mission record has been compared yet. The terrain horizon has passed analytic tests of the core stream only (docs/method/horizon.md)."},
            {"item": "Published event times of real landers", "state": "not done yet", "reason": "Planned as the next validation step."},
            {"item": "Earth rise and set against an independent source", "state": "not done", "reason": "Horizons does not state which point of the Earth's disc its rise and set refer to; only the Earth's direction and size are validated."},
            {"item": "Eclipses of the Sun by the Earth", "state": "not modelled", "reason": "The visible fraction of the Sun does not include occultation by the Earth."},
        ],
        "limits": [
            "Every check on this card is terrain-free. Near the lunar poles the terrain horizon, not the ephemeris, sets the accuracy of an event time: a horizon error of 0.01 deg can move an event by many minutes.",
            "The external reference (Horizons) and the core use JPL ephemerides of the same family; an error common to both would not show.",
            "Thresholds marked as written in the acceptance test were committed in the same commit as the code they test; only the Horizons thresholds have a commit of their own that predates the data.",
        ],
    }


def _number(value: float) -> str:
    if value == 0:
        return "0"
    if abs(value) >= 100 or float(value).is_integer():
        return f"{value:g}"
    return f"{value:.2g}" if abs(value) < 0.01 else f"{value:.3g}"


def to_markdown(card: dict) -> str:
    core = card["core"]
    s = card["summary"]
    lines = [
        f"# {card['title']}",
        "",
        f"Generated {card['generated_utc']} by `validation/card/build.py`; every measured value is recomputed from the stored reference data and the code. Do not edit by hand.",
        "",
        f"**{s['passed']} of {s['checks']} checks pass.** Core: SPICE, frame `{core['frame']}`, correction `{core['aberration_correction']}`, sphere {core['reference_radius_km']} km, kernel set `{core['kernel_set_id']}`.",
        "",
        "| What was compared | Against | Cases | Threshold | Measured | Result |",
        "|---|---|---|---|---|---|",
    ]
    for c in card["checks"]:
        op = "≤" if c["threshold"]["comparison"] == "<=" else "<"
        lines.append(
            f"| {c['quantity']} | {c['compared_against']} | {c['cases']} | {op} {_number(c['threshold']['value'])} {c['threshold']['unit']} | "
            f"{_number(c['measured']['value'])} {c['measured']['unit']} | **{c['status']}** |"
        )
    lines += ["", "## Where each threshold was fixed", ""]
    seen = []
    for c in card["checks"]:
        entry = f"- {c['threshold_fixed']['where']}: {c['threshold_fixed']['how']}."
        if entry not in seen:
            seen.append(entry)
    lines += seen
    lines += ["", "## Not validated", ""]
    lines += [f"- **{item['item']}** ({item['state']}). {item['reason']}" for item in card["not_validated"]]
    lines += ["", "## Limits", ""]
    lines += [f"- {limit}" for limit in card["limits"]]
    lines += ["", "Reference: Giorgini, JD and JPL Solar System Dynamics Group, NASA/JPL Horizons On-Line Ephemeris System, https://ssd.jpl.nasa.gov/horizons/, data retrieved 2026-Nov-14."]
    return "\n".join(lines) + "\n"


def main() -> None:
    card = build()
    (HERE / "validation_card.json").write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    (HERE / "validation_card.md").write_text(to_markdown(card), encoding="utf-8")
    for c in card["checks"]:
        print(f"{c['id']:24s} threshold {c['threshold']['value']:<8g} measured {c['measured']['value']:<12.6g} {c['measured']['unit']:22s} {c['status']}")
    print(card["summary"])


if __name__ == "__main__":
    main()
