"""Build the validation card: every check of the ephemeris, time and event layer in one table.

Each row says what was compared, against which source, the threshold and where it was
fixed, the measured difference and pass or fail, and every check carries its main limit
in one sentence. Every measured value is recomputed here from the stored reference data
and the current code, or read from a stored result table where the computation needs the
terrain data; nothing is typed in by hand. A check that fails is shown as failed.

Writes ``validation_card.json`` and ``validation_card.md`` next to this file.

Usage (from the repository root)::

    python -m validation.card.build
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import re
import subprocess
from pathlib import Path

import numpy as np

from lsncore import events as ev
from lsncore.ephem import directions as d
from lsncore.ephem import kernels
from validation.horizons import compare as horizons
from validation.horizons_rts import compare as horizons_rts
from validation.eclipse import compare as eclipse_check
from validation.landers import compare as landers
from validation.stations import compare as station_check

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

    # The two files this script writes do not count as uncommitted changes of the code and data behind them.
    own = [f":(exclude)validation/card/{name}" for name in ("validation_card.json", "validation_card.md")]
    return {"commit": git("rev-parse", "--short", "HEAD"), "uncommitted_changes": bool(git("status", "--porcelain", "--", ".", *own))}


def _check(cid, group, quantity, against, threshold, unit, fixed_how, fixed_where, measured, evidence, cases, limits, comparison="<"):
    passed = {"<=": measured <= threshold, ">=": measured >= threshold}.get(comparison, measured < threshold)
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

    lander = landers.run()
    lander_rows = {row["id"]: row for case in lander["cases"] for row in case["rows"]}
    lander_rules = landers.load()[1]
    r1 = lander_rules["R1_angle_same_inputs"]["threshold_deg"]
    alsj = [row for row in lander_rows.values() if row["kind"] == "pass_fail" and row["unit"] == "deg" and row["threshold"] == r1]
    bounds = [lander_rows[k] for k in ("blue_ghost_sunset_day", "blue_ghost_daylight_not_after_last_light", "chandrayaan3_sun_up_by_expected_awakening")]
    lander_where = "validation/landers/thresholds.json and cases.json (commit eaf5634); second batch cases_second_batch.json (commit af10faa)"
    lander_how = (
        "committed on its own before the core was run on these cases; not blind (earlier research had compared some of the published "
        "values with Horizons), so the thresholds follow fixed rules from the printed precision of each source"
    )
    lander_evidence = "validation/landers/results/validation_table.md; test validation/tests/test_landers.py"
    recomputed = all(case.get("recomputed", True) for case in lander["cases"])
    stored_note = "" if recomputed else " (stored result: terrain data not present on this machine)"

    ecl = eclipse_check.run()
    ecl_rows = {row["id"]: row for row in ecl["rows"]}
    ecl_rules = eclipse_check.load()[1]
    ecl_where = "validation/eclipse/thresholds.json and cases.json (commit a8bbc5a)"
    ecl_how = (
        "committed on its own before the eclipse code was run on this eclipse; not blind (earlier research had computed these contacts "
        "with Horizons), so the thresholds follow fixed rules from the printed precision of each source"
    )
    ecl_evidence = "validation/eclipse/results/validation_table.md; test validation/tests/test_eclipse_validation.py"
    ecl_contacts = [ecl_rows[k] for k in ("eclipse_partial_start", "eclipse_totality_start", "eclipse_partial_end")]
    ecl_nesting = [ecl_rows[k] for k in ("eclipse_c1_after_p1", "eclipse_c2_between_u1_and_u2", "eclipse_c3_between_u3_and_u4", "eclipse_c4_before_p4")]

    stn = station_check.run()
    stn_limit, stn_sum = stn["thresholds"], stn["summary"]
    stn_where = "validation/stations/thresholds.json (commit 6f74153)"
    stn_evidence = "validation/stations/results/validation_table.md; test validation/tests/test_stations_validation.py"
    stn_cases = f"{stn_sum['cases'] // 2} queries, {stn_sum['rows'] // 2} rows: 3 Deep Space Network stations, a south-polar and an equatorial lunar site, 14-16 Nov 2026 at 10 min"
    stn_source = f"JPL Horizons observer tables ({HORIZONS_URL}), retrieved 2026-11-14"
    stn_limits = ["No terrain at either end.", "Both sides use JPL ephemerides and Earth orientation data of the same origin."]

    pgda = json.loads((REPO / "validation" / "pgda" / "results" / "validation_table.json").read_text(encoding="utf-8"))
    pgda_limit = json.loads((REPO / "validation" / "pgda" / "thresholds.json").read_text(encoding="utf-8"))["thresholds_run_A"]
    pg = {key: pgda["distribution"][f"run_A/0m/{key}"]["all"] for key in ("sun", "earth")}
    pg_b = {key: pgda["distribution"][f"run_B/0m/{key}"]["all"] for key in ("sun", "earth")}
    pgda_where = "validation/pgda/thresholds.json and points.json (commit d044186)"
    pgda_how = "committed on its own before any value of the published maps was downloaded or read"
    pgda_evidence = "validation/pgda/results/validation_table.md; test validation/tests/test_pgda.py (stored result; recomputed by validation/pgda/compute.py and compare.py)"
    pgda_source = "LOLA illumination maps of the south pole, 60 m (AVGVISIB_85S_060M_201608, _EARTH, LPSR_85S_060M_201608), LOLA Science Team, NASA GSFC, PGDA product 69 (https://pgda.gsfc.nasa.gov/products/69), retrieved 2026-11-14"
    pgda_cases = "100 points fixed beforehand (33 ridges and rims, 33 floors, 31 plains and slopes, 3 site records); one nodal cycle of 18.6 years at hourly steps; terrain of the same 60 m resolution as the maps"
    pgda_limits = ["Both sides rest on LOLA elevation data: this validates the method on given terrain, not the terrain itself.",
                   "Long-term shares only; individual rise and set times are not tested by these maps."]

    lro = json.loads((REPO / "validation" / "lro_images" / "results" / "validation_table.json").read_text(encoding="utf-8"))
    lro_checks = {check["id"]: check for check in lro["checks"]}
    # The two thresholds of the image rows are read from the criteria of the committed cases, not typed here.
    lro_criteria = {check["id"]: check["criterion"] for case in json.loads((REPO / "validation" / "lro_images" / "cases.json").read_text(encoding="utf-8"))["cases"] for check in case["checks"]}
    strip_threshold = float(re.search(r"at least (\d+(?:\.\d+)?) percent", lro_criteria["nadir_2010_agreement"]).group(1)) / 100.0
    sub_solar_thresholds = {float(re.search(r"less than (\d+(?:\.\d+)?) degree", lro_criteria[key]).group(1)) for key in ("pole_2022_sub_solar_point", "nadir_2010_sub_solar_point")}
    if len(sub_solar_thresholds) != 1:
        raise ValueError(f"the two sub-solar criteria state different thresholds: {sorted(sub_solar_thresholds)}")
    sub_solar_threshold = sub_solar_thresholds.pop()
    lro_where = "validation/lro_images/cases.json (commit fb05da0)"
    lro_how = "committed on its own before any computation for these cases and before the image was downloaded"
    lro_evidence = "validation/lro_images/results/validation_table.md; test validation/tests/test_lro_images.py (stored result; recomputed by validation/lro_images/compare.py)"
    strip = lro_checks["nadir_2010_agreement"]
    strip_cause, strip_limit = [], "One lossy browse image georeferenced from four corners printed to 300 m: it tests broad sunlit and shadowed areas, not the position of a shadow edge."
    disputed = lro["exploratory_after_the_result"]["image_shadow_ours_sunlit"]
    strip_not_blind = ("The horizon of the core was changed after this check had first failed (266 of 298 judged points, 89.3 %) and after the strip point row+700_along11500 had been examined: "
                       "since contract 0.12 the ground between the site and the first pixel is in the horizon of an observer at 0 m. For that point the comparison is therefore no longer blind. "
                       "It is the one strip point whose state changed with the new horizon (sunlit to shadow); the reading rule and the criterion are unchanged.")
    if strip["status"] == "FAIL" and disputed:
        low, _, high = disputed["our_centre_margin_deg_min_median_max"]
        strip_limit = (f"Fails as registered ({100 * strip['computed']:.1f} % against 90 %): all {disputed['points']} disagreements are ground the core calls sunlit with the centre of the Sun only {low:.2f} to {high:.2f} deg above the terrain horizon and the image rule reads as shadow, "
                       "which fits either a single brightness threshold that reads dimly lit ground as shadow or a terrain horizon of the core that is too low there by that amount, and the data do not decide between the two; "
                       "the rule and the criterion were not changed after the result.")
        strip_cause = [strip_limit, "The cause was looked for after the result (validation/lro_images/results/validation_table.md); that analysis is not a criterion."]

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
        _check("terrain_sun_share_difference", "Independent computation on terrain", "Share of time with any part of the Sun above the LOLA terrain horizon: median absolute difference to the published map",
               pgda_source, pgda_limit["sun"]["median_absolute_difference_max"], "share of time", pgda_how, pgda_where, pg["sun"]["median_absolute"], pgda_evidence, pgda_cases,
               pgda_limits + [f"With the 20 m terrain the tool uses, crests are less lit than on the 60 m maps: mean difference {pg_b['sun']['mean_signed']:+.3f}, largest {pg_b['sun']['max_absolute']:.2f}."], comparison="<="),
        _check("terrain_earth_share_difference", "Independent computation on terrain", "Share of time with any part of the Earth above the LOLA terrain horizon: median absolute difference to the published map",
               pgda_source, pgda_limit["earth"]["median_absolute_difference_max"], "share of time", pgda_how, pgda_where, pg["earth"]["median_absolute"], pgda_evidence, pgda_cases,
               pgda_limits + [f"With the 20 m terrain the largest difference at a single point is {pg_b['earth']['max_absolute']:.2f}."], comparison="<="),
        _check("terrain_share_correlation", "Independent computation on terrain", "Correlation of our shares with the published maps over the points (the smaller of Sun and Earth)",
               pgda_source, pgda_limit["sun"]["pearson_r_min"], "correlation", pgda_how, pgda_where, min(pg["sun"]["pearson_r"], pg["earth"]["pearson_r"]), pgda_evidence, pgda_cases,
               ["A correlation over points that range from permanent shadow to well-lit ridges is high almost by construction; the difference rows are the sharper test."], comparison=">="),
        _check("terrain_share_bias", "Independent computation on terrain", "Median signed difference of our shares to the published maps (the larger of Sun and Earth, absolute value)",
               pgda_source, pgda_limit["sun"]["median_signed_difference_abs_max"], "share of time", pgda_how, pgda_where, max(abs(pg["sun"]["median_signed"]), abs(pg["earth"]["median_signed"])), pgda_evidence, pgda_cases,
               ["A shift would show a different definition of 'lit'; none is seen.", f"A median hides the tails: {pg['sun']['beyond_0.05']} of {pg['sun']['points']} points differ by more than 0.05 in the Sun share (largest {pg['sun']['max_absolute']:.3f}); their cause was not traced."], comparison="<="),
        _check("terrain_permanent_shadow", "Independent computation on terrain", "Agreement on permanent shadow: never lit in our period against the published permanent-shadow map",
               pgda_source, pgda_limit["sun"]["permanent_shadow_agreement_min"], "share of points", pgda_how, pgda_where, pgda["permanent_shadow"]["agreement"], pgda_evidence,
               f"{pgda['permanent_shadow']['points_compared']} points ({pgda['permanent_shadow']['points_left_out_as_boundary']} boundary points left out), {pgda['permanent_shadow']['published_shadow_and_ours_never_lit']} of them in permanent shadow",
               ["One nodal cycle; a point lit for less than one hourly step in 18.6 years would count as never lit."], comparison=">="),
        _check("image_pole_state", "Dated image", "Sunlit or shadowed state of the south pole on 18 May 2022, 14:40:49 UTC, against the camera team's reading of NAC image M1407524099 (states that differ)",
               "LROC featured image 'Where is the South Pole?' (https://lroc.im-ldi.com/images/1276) and the LROC data page of the image, retrieved 2026-11-14",
               0, "states that differ", lro_how, lro_where, 0 if lro_checks["pole_2022_state"]["status"] == "PASS" else 1, lro_evidence, "1 point, 1 image",
               [f"The terrain that hides the Sun at the pole is only {lro_checks['pole_2022_state']['detail']['obstacle_distance_m'] / 1000.0:.2f} km away, so the state depends on where the pole falls on the 20 m elevation grid to about that distance.",
                "The state is the camera team's statement about its image, not a measurement by us."], comparison="<="),
    ] + ([
        _check("image_strip_agreement", "Dated image", "Sunlit or shadowed state along a nadir NAC strip of 13 December 2010, read from the image by a fixed rule: share of judged points that agree",
               "LROC NAC image M146846913L, calibrated browse product (https://pds.lroc.im-ldi.com/), retrieved 2026-11-14",
               strip_threshold, "share of points", lro_how, lro_where, strip["computed"], lro_evidence,
               f"{strip['detail']['judged']} judged points of {strip['detail']['points']} along the strip ({strip['detail']['mixed_or_outside']} near a shadow edge or outside were not judged)",
               ["Corner-based georeferencing (corners printed to 300 m) of a lossy browse image: it tests broad sunlit and shadowed areas, not the position of a shadow edge.", "One image, near Shackleton crater."] + strip_cause + [strip_not_blind], comparison=">="),
    ] if strip["status"] in ("PASS", "FAIL") else []) + [
        _check("image_sub_solar_points", "Dated image", "Sub-solar latitude and longitude at the two image times against the values printed on the LROC data pages (largest difference)",
               "LROC data pages of NAC images M1407524099LE and M146846913LE, retrieved 2026-11-14",
               sub_solar_threshold, "deg", lro_how, lro_where, max(abs(v) for key in ("pole_2022_sub_solar_point", "nadir_2010_sub_solar_point") for v in lro_checks[key]["difference_deg"]), lro_evidence, "2 images, 4 angles printed to 0.01 deg",
               ["An ephemeris check, independent of terrain."]),
        _check("station_earth_end", "Independent source", "Earth end of a direct link: direction of a lunar site seen from a ground station (observer at the station)", stn_source,
               stn_limit["earth_end_direction_arcsec_max"], "arcsec", SEPARATE_COMMIT, stn_where, stn_sum["earth_end_exact_arcsec_max"], stn_evidence, stn_cases, stn_limits),
        _check("station_moon_end", "Independent source", "Moon end of a direct link: direction of a ground station seen from a lunar site (observer at the site)", stn_source,
               stn_limit["moon_end_direction_arcsec_max"], "arcsec", SEPARATE_COMMIT, stn_where, stn_sum["moon_end_exact_arcsec_max"], stn_evidence, stn_cases, stn_limits),
        _check("station_fast_path_earth_end", "Independent source", "Elevation of the lunar site at the station through the fast path that the link windows use", stn_source,
               stn_limit["fast_path_earth_end_deg_max"], "deg", SEPARATE_COMMIT, stn_where, stn_sum["earth_end_fast_elevation_deg_max"], stn_evidence, stn_cases,
               stn_limits + ["The fast path evaluates both ends at one instant."]),
        _check("station_fast_path_moon_end", "Independent source", "Direction of the station seen from the lunar site through the fast path that the link windows use", stn_source,
               stn_limit["fast_path_moon_end_arcsec_max"], "arcsec", SEPARATE_COMMIT, stn_where, stn_sum["moon_end_fast_arcsec_max"], stn_evidence, stn_cases, stn_limits),
        _check("apollo_landing_angles", "Published mission record",
               "Sun and Earth altitude, azimuth and sub-points at the six Apollo landings, at the published landing times",
               "Apollo Lunar Surface Journal table computed from the Nautical Almanac (https://www.nasa.gov/wp-content/uploads/static/history/alsj/Scotti_AltAz.txt), retrieved 2026-11-14",
               r1, "deg", lander_how, lander_where,
               max(abs(row["difference"]) for row in alsj), lander_evidence, f"{len(alsj)} published angles, {len(alsj) // 8} landings",
               ["The published angles are themselves computed (1960s almanac), not measured; the landing times and places are the mission record.",
                "Smooth sphere; the site coordinates and the no-parallax definition of the source are used."]),
        _check("apollo16_targeted_sun_angle", "Published mission record",
               "Sun elevation at the planned Apollo 16 landing time against the targeted angle of the launch window (the landing then slipped by 5 h 45 min, which raised the Sun by 2.88 deg)",
               "NASA SP-2000-4029, Apollo by the Numbers, tables 'Launch Windows' and 'LM Lunar Landing', retrieved 2026-11-14",
               lander_rules["R2_targeted_sun_angle"]["threshold_deg"], "deg", lander_how, lander_where,
               abs(lander_rows["apollo16_targeted_sun_at_planned_time"]["difference"]), lander_evidence, "1 published angle and 2 published times",
               ["The planned landing time is derived from two published values."]),
        _check("lander_operational_bounds", "Published mission record",
               "Physical bounds from operational records that are violated: Blue Ghost Mission 1 (sunset day; recorded daylight must end before geometric last light) and Chandrayaan-3 (sunrise over the terrain horizon must precede the expected wake-up day)",
               "Firefly Aerospace press release of 17 March 2025; ISRO Chandrayaan-3 mission updates; LROC landing coordinates; retrieved 2026-11-14",
               0, "bounds violated", lander_how, lander_where,
               sum(row["status"] != "PASS" for row in bounds), lander_evidence,
               f"3 bounds; Blue Ghost on a smooth sphere, Chandrayaan-3 with the LOLA terrain horizon{stored_note}",
               ["One-sided checks: they can show the core wrong, they do not confirm an event time.",
                "Blue Ghost recorded 346 h of daylight, ending 2.3 h before smooth-sphere last light; local terrain is not in the project data for that site.",
                "ISRO expected the wake-up about 1.8 days after the computed sunrise; ISRO published no sunrise time."], comparison="<="),
        _check("eclipse_contact_times", "Published mission record",
               "Eclipse of the Sun by the Earth on 14 March 2025 at the Blue Ghost landing point: start of the partial phase, start of totality, end of the partial phase",
               "Contact times predicted by the operator, Firefly Aerospace, printed to the minute (https://fireflyspace.com/news/blue-ghost-mission-1-live-updates/), retrieved 2026-11-14",
               ecl_rules["E1_contact_time_at_the_site"]["threshold_minutes"], "min", ecl_how, ecl_where,
               max(abs(row["difference"]) for row in ecl_contacts), ecl_evidence, "3 contact times at one site",
               ["Opaque Earth without atmosphere; the real edge of the shadow is soft over about a minute.",
                "The operator's times are predictions, not measurements; its images of the eclipse are timed only to about half an hour.",
                "The operator labels the times CST; they are read as local Texas time (UTC-5), which the NASA chart confirms independently."]),
        _check("eclipse_totality_duration", "Published mission record",
               "Duration of totality at the Blue Ghost landing point, 14 March 2025 (the operator: approximately 2 hours and 16 minutes)",
               "Firefly Aerospace, Blue Ghost Mission 1 live updates, retrieved 2026-11-14",
               ecl_rules["E2_duration_of_totality"]["threshold_minutes"], "min", ecl_how, ecl_where,
               abs(ecl_rows["eclipse_totality_duration"]["difference"]), ecl_evidence, "1 duration",
               ["Called approximate by the source."]),
        _check("eclipse_inside_whole_moon_contacts", "Independent source",
               "Contacts at the site that fall outside the whole-Moon contacts of the same eclipse (a point of the Moon cannot enter the shadow before the Moon does or leave it after)",
               "NASA GSFC eclipse chart, F. Espenak, 'Total Lunar Eclipse of 2025 Mar 14' (https://eclipse.gsfc.nasa.gov/LEplot/LEplot2001/LE2025Mar14T.pdf), retrieved 2026-11-14",
               0, "contacts outside", ecl_how, ecl_where,
               sum(row["status"] != "PASS" for row in ecl_nesting), ecl_evidence, "4 inequalities, allowance 2 min for NASA's enlarged shadow",
               ["One-sided: the margins are 9 to 63 min, so this only excludes gross errors."], comparison="<="),
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

    same_family = "Both sides use JPL ephemerides of the same family (DE440 and DE441) and neither has terrain, so an error common to both would not show."
    station_limit = "No terrain at either end, and both sides use JPL ephemerides and Earth orientation data of the same origin."
    one_sentence = {
        "direction_exact": same_family,
        "direction_table": "As in the row above; what is measured here is that the table applies light time and stellar aberration for the Moon's centre instead of the site.",
        "angular_diameter": "Equatorial width only: the flattening of the Earth's disc (0.3 %) is not modelled.",
        "range": same_family,
        "tdb_minus_utc": "For dates after the last announced leap second both sides assume that no further leap second is introduced.",
        "sun_rise_set_time": "Smooth sphere and Sun only, and the reference resolves one minute, so agreement cannot be shown more finely than that.",
        "sun_rise_set_unmatched": "Smooth sphere and Sun only, over two months at four points.",
        "terrain_sun_share_difference": f"Both sides rest on LOLA elevation data at 60 m, so this validates the method on given terrain, not the terrain itself and not single event times; with the 20 m terrain the tool uses, crests come out less lit (mean difference {pg_b['sun']['mean_signed']:+.3f}, largest {pg_b['sun']['max_absolute']:.2f}).",
        "terrain_earth_share_difference": f"As for the Sun: the method on given 60 m terrain, not the terrain and not single event times; with the 20 m terrain the largest difference at a single point is {pg_b['earth']['max_absolute']:.2f}.",
        "terrain_share_correlation": "A correlation over points that range from permanent shadow to well-lit ridges is high almost by construction; the difference rows are the sharper test.",
        "terrain_share_bias": f"A median hides the tails: {pg['sun']['beyond_0.05']} of {pg['sun']['points']} points differ by more than 0.05 in the Sun share (largest {pg['sun']['max_absolute']:.3f}), and their cause was not traced.",
        "terrain_permanent_shadow": f"One nodal cycle at hourly steps, so a point lit for less than an hour in 18.6 years counts as never lit; {pgda['permanent_shadow']['points_left_out_as_boundary']} points on a boundary of the published map were left out.",
        "image_pole_state": f"One point in one image, read by the camera team and not by us, where the terrain that hides the Sun is only {lro_checks['pole_2022_state']['detail']['obstacle_distance_m'] / 1000.0:.2f} km away, so the state depends on the pole's position on the 20 m elevation grid.",
        "image_strip_agreement": strip_limit,
        "image_sub_solar_points": "An ephemeris check against values printed to 0.01 deg; it does not involve terrain.",
        "station_earth_end": station_limit,
        "station_moon_end": station_limit,
        "station_fast_path_earth_end": "As for the station rows above; in addition the fast path evaluates both ends of the link at one instant.",
        "station_fast_path_moon_end": "As for the station rows above; in addition the fast path evaluates both ends of the link at one instant.",
        "apollo_landing_angles": "The published angles are themselves computed from a 1960s almanac, not measured, and involve no terrain: the six landings test directions at a known time and place, not event times.",
        "apollo16_targeted_sun_angle": "The target is a planned angle, and the planned landing time is derived from two published values.",
        "lander_operational_bounds": "One-sided: these records can show the core wrong, but they cannot confirm an event time.",
        "eclipse_contact_times": "The operator's times are predictions printed to the minute, not measurements, and the Earth is modelled as opaque and without atmosphere.",
        "eclipse_totality_duration": "One duration, which the source itself calls approximate.",
        "eclipse_inside_whole_moon_contacts": "One-sided, with margins of 9 to 63 min, so it only excludes gross errors.",
        "projection_vs_azlcpo": "Checks the projection only: ephemeris, frame and kernels are shared by both sides.",
        "table_shortcut": "Internal: both paths use the same kernels and frames.",
        "table_interpolation": "Internal, and valid only inside the time span of the table.",
        "visible_fraction": "A uniform disc without limb darkening, cut by a straight horizon.",
        "event_time_analytic": "Numerical accuracy for a given horizon profile, not the physical accuracy of an event time on real terrain.",
        "event_time_sphere": "Internal and without terrain.",
        "scan_completeness": "An invented horizon profile, not terrain; pairs of crossings closer than 60 s are not reported by the default scan.",
    }
    for check in checks:
        check["limit"] = one_sentence[check["id"]]
    failed = [check for check in checks if check["status"] == "FAIL"]

    return {
        "title": "Validation card: ephemeris, time and event finding",
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_from": _commit(),
        "core": {"frame": d.FRAME, "aberration_correction": d.ABCORR, "reference_radius_km": d.MOON_RADIUS_KM, "kernel_set_id": kernels.kernel_set_id(), "kernels": [k["name"] for k in kernels.read_manifest()["kernels"]]},
        "summary": {"checks": len(checks), "passed": sum(c["status"] == "PASS" for c in checks), "failed": len(failed), "failed_ids": [c["id"] for c in failed]},
        "checks": checks,
        "not_validated": [
            {"item": "Individual rise and set times on real terrain", "state": "not validated", "reason": "The long-term shares of lit and Earth-visible time agree with the published LOLA maps on terrain of the same resolution; of the two checks against dated images one agrees and one fails its criterion; and no independent source gives the time of a sunrise or sunset at a point on real terrain. Where an event is set by terrain closer than about 1 km, the elevation grid limits its accuracy."},
            {"item": "The elevation model itself", "state": "not validated here", "reason": "Every terrain check on this card uses LOLA elevation data on both sides. The data stream checks the georeferencing of the LOLA files separately."},
            {"item": "Exact rise and set times at a real lander", "state": "not available", "reason": "No source examined for Blue Ghost Mission 1, Chandrayaan-3, SLIM, IM-1 or IM-2 prints a sunrise or sunset clock time for the landing site. Operational records (hours of daylight, expected wake-up date) only bound the computed events from one side."},
            {"item": "Direct-to-Earth windows", "state": "geometry validated, windows not", "reason": "Both ends of the link geometry agree with Horizons. The windows built from them, the station elevation limits as single numbers (no azimuth-dependent masks), and anything about link budget, multipath or scheduling have not been compared with an external source."},
            {"item": "Earth rise and set against an independent source", "state": "not done", "reason": "Horizons does not state which point of the Earth's disc its rise and set refer to; only the Earth's direction and size are validated."},
            {"item": "Sunlight during an eclipse", "state": "partly modelled", "reason": "Eclipses of the Sun by the Earth are computed for an opaque Earth without atmosphere and checked against one published eclipse. The light that the Earth's atmosphere refracts into the shadow, and any measured power curve of a lander, are not modelled or compared."},
        ],
        "limits": [
            "Near the lunar poles the terrain horizon, not the ephemeris, sets the accuracy of an event time: a horizon error of 0.01 deg can move an event by many minutes. The terrain checks on this card test long-term shares and two dated images, not event times.",
            "The external reference (Horizons) and the core use JPL ephemerides of the same family; an error common to both would not show.",
            "Thresholds marked as written in the acceptance test were committed in the same commit as the code they test; the thresholds of the comparisons with external sources have commits of their own that predate the data or the computation, as listed above.",
            "The lander and eclipse comparisons are not blind: earlier research had compared some of the published values with Horizons.",
            "Row 14 is not blind for one of its points. " + strip_not_blind,
            "Rows 8 to 12 were recomputed on 15 November 2026 with the horizon the packages use, in which the ground between the point and the first pixel counts for an observer at 0 m. "
            "That this default is the one judged, and not the convention of pixel-based maps, was decided before the result was seen; the thresholds were not changed. "
            "The first result, of 14 November, searched from one pixel outward (Sun correlation 0.9973, permanent-shadow agreement 100 %).",
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
    numbers = [str(number) for number, c in enumerate(card["checks"], start=1) if c["status"] == "FAIL"]
    verdict = "." if not numbers else f"; {s['failed']} fail{'s' if s['failed'] == 1 else ''} (row {', '.join(numbers)}). A failed check is shown as it is: no threshold, rule or reference was changed after a result."
    lines = [
        f"# {card['title']}",
        "",
        f"Generated {card['generated_utc']} by `validation/card/build.py` from commit `{card['generated_from']['commit']}`{' with uncommitted changes' if card['generated_from']['uncommitted_changes'] else ''}; "
        "every measured value is recomputed from the stored reference data and the code or, for the terrain and image checks, read from their stored result tables. Do not edit by hand.",
        "",
        f"**{s['passed']} of {s['checks']} checks pass{verdict}** Core: SPICE, frame `{core['frame']}`, correction `{core['aberration_correction']}`, sphere {core['reference_radius_km']} km, kernel set `{core['kernel_set_id']}`.",
        "",
        "| # | What was compared | Against | Cases | Threshold | Measured | Result |",
        "|---|---|---|---|---|---|---|",
    ]
    for number, c in enumerate(card["checks"], start=1):
        op = {"<=": "≤", ">=": "≥"}.get(c["threshold"]["comparison"], "<")
        lines.append(
            f"| {number} | {c['quantity']} | {c['compared_against']} | {c['cases']} | {op} {_number(c['threshold']['value'])} {c['threshold']['unit']} | "
            f"{_number(c['measured']['value'])} {c['measured']['unit']} | **{c['status']}** |"
        )
    lines += ["", "## The main limit of each check, in one sentence", "", "Numbers as in the table above.", ""]
    lines += [f"{number}. {c['limit']}" for number, c in enumerate(card["checks"], start=1)]
    lines += ["", "## Where each threshold was fixed", ""]
    seen = []
    for c in card["checks"]:
        entry = f"- {c['threshold_fixed']['where']}: {c['threshold_fixed']['how']}."
        if entry not in seen:
            seen.append(entry)
    lines += seen
    lines += ["", "## Not validated", ""]
    lines += [f"- **{item['item']}** ({item['state']}). {item['reason']}" for item in card["not_validated"]]
    lines += ["", "## Limits of the card as a whole", ""]
    lines += [f"- {limit}" for limit in card["limits"]]
    lines += ["", "Reference: Giorgini, JD and JPL Solar System Dynamics Group, NASA/JPL Horizons On-Line Ephemeris System, https://ssd.jpl.nasa.gov/horizons/, data retrieved 2026-Nov-14."]
    return "\n".join(lines) + "\n"


def main() -> None:
    card = build()
    (HERE / "validation_card.json").write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    (HERE / "validation_card.md").write_text(to_markdown(card), encoding="utf-8")
    for c in card["checks"]:
        print(f"{c['id']:34s} threshold {c['threshold']['value']:<8g} measured {c['measured']['value']:<12.6g} {c['measured']['unit']:22s} {c['status']}")
    print(card["summary"])


if __name__ == "__main__":
    main()
