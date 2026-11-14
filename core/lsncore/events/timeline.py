"""Per-site timeline in contract form: series, events, windows and countdown metrics.

``compute_timeline`` has the same signature as the synthetic stand-in
(``lsncore.synthetic.synthetic_timeline``) and returns the same result object, but every
number comes from the real direction table and the event finder.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .. import packaging as pk
from ..contract import read_package
from ..ephem import directions as d
from ..ephem import table as tb
from ..results import BodySeries, HorizonResult, TimelineResult
from ..scenario import canonical_site
from ..timeline import IntervalSet, TimeGrid
from . import finder

DEFAULT_THRESHOLDS = {
    "SUN": {"quantity": "visible_fraction", "op": ">", "value": 0.0},
    "EARTH": {"quantity": "margin_deg", "op": ">", "value": 0.0},
}
_ANY_PART = {"quantity": "visible_fraction", "op": ">", "value": 0.0}
_FULL_DISC = {"quantity": "visible_fraction", "op": ">=", "value": 1.0}
_NAMES = {"SUN": "Sun", "EARTH": "Earth"}
_RATE_HALF_SPAN_S = 30.0


def _describe(threshold: dict) -> str:
    return f"{threshold['quantity']} {threshold['op']} {threshold['value']:g}"


def _window(wid: str, subject: str, h: int, definition: str, intervals: IntervalSet, threshold: dict | None) -> dict:
    out = {
        "id": wid,
        "subject": subject,
        "height_index": h,
        "definition": definition,
        "intervals_et_s": intervals.as_list(),
        "intervals_utc": [[d.et_to_utc_z(a), d.et_to_utc_z(b)] for a, b in intervals.intervals],
        "clipped_start": bool(intervals.clipped_start),
        "clipped_end": bool(intervals.clipped_end),
        "method": pk.M_WINDOWS,
    }
    if threshold is not None:
        out["threshold"] = threshold
    return out


def _metric(mid: str, label: str, value, unit: str, h: int) -> dict:
    return {"id": mid, "label": label, "value": None if value is None else float(value), "unit": unit, "height_index": h, "method": pk.M_METRICS}


def _nearest(values: np.ndarray | None, h: int, azimuth_deg: float, step_deg: float):
    if values is None:
        return None
    value = float(values[h, int(round(azimuth_deg / step_deg)) % values.shape[1]])
    return value if np.isfinite(value) else None


def compute_timeline(
    site: dict,
    horizon: HorizonResult,
    table_dir: Path | str,
    window: dict,
    bodies: list[str],
    thresholds: dict[str, dict] | None = None,
    scan_step_s: float = finder.DEFAULT_SCAN_STEP_S,
    tol_s: float = finder.DEFAULT_TOL_S,
    n_strips: int = finder.DEFAULT_STRIPS,
    reference_utc: str | None = None,
) -> TimelineResult:
    """Series, events, windows and metrics of one site from a direction table and a horizon.

    ``window`` is ``{"start_utc", "end_utc", "step_s"}`` (the step is that of the stored
    series; events are located independently of it, see ``lsncore.events.finder``).
    ``reference_utc`` is the instant the countdown metrics count from; the default is the
    site's ``landing_utc`` if it lies inside the window, otherwise the start of the window.
    """
    thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    table_package = read_package(table_dir)
    table = tb.load_table(table_dir)
    csite = canonical_site(site)

    start = d.utc_to_et(window["start_utc"])
    count = int(np.floor((d.utc_to_et(window["end_utc"]) - start) / window["step_s"] + 1e-6)) + 1
    grid = TimeGrid(start, float(window["step_s"]), count)
    t = grid.times()
    if t[0] < table.et[0] or t[-1] > table.et[-1]:
        raise ValueError("time window lies outside the direction table")
    domain = (float(t[0]), float(t[-1]))

    reference_et = domain[0]
    candidate = reference_utc or site.get("landing_utc")
    if candidate:
        candidate_et = d.utc_to_et(candidate)
        if domain[0] <= candidate_et <= domain[1]:
            reference_et = candidate_et
        elif reference_utc:
            raise ValueError("reference_utc lies outside the time window")
    reference_label = d.et_to_utc_z(reference_et)

    # Ground point of the site. Observer heights of metres change the direction of the Earth
    # by less than 0.01 arcsec; they act through the horizon profile, not through parallax.
    ground = d.Site(csite["lon_deg"], csite["lat_deg"], horizon.surface_height_m / 1000.0)
    heights = list(horizon.observer_heights_m)
    step_deg = horizon.azimuth_step_deg

    series: dict[str, BodySeries] = {}
    events: list[dict] = []
    windows: list[dict] = []
    metrics: list[dict] = []
    visible: dict[tuple[str, int], IntervalSet] = {}

    for body in bodies:
        name, tag = _NAMES[body], body.lower()
        direction = finder.site_direction(ground, table, body)
        az, el, radius = direction(t)
        margin = np.empty((len(heights), t.size))
        fraction = np.empty((len(heights), t.size))
        threshold = thresholds[body]
        rules = {
            "visible": finder.threshold_from_contract(threshold, "visible"),
            "any_part": finder.threshold_from_contract(_ANY_PART, "any_part"),
            "full_disc": finder.threshold_from_contract(_FULL_DISC, "full_disc"),
        }

        for h in range(len(heights)):
            profile = finder.Horizon(0.0, step_deg, np.asarray(horizon.elevation_deg[h], dtype=np.float64), np.asarray(horizon.distance_m[h], dtype=np.float64))
            sampled = finder.disc_signals(az, el, radius, profile, n_strips)
            margin[h], fraction[h] = sampled.center_margin_deg, sampled.visible_fraction

            result = finder.find_events(direction, profile, domain[0], domain[1], scan_step_s, tol_s, rules, n_strips)
            sets = {}
            for label in rules:
                found = finder.windows(result, label)
                sets[label] = IntervalSet(found.intervals_et_s, domain)
            visible[(body, h)] = sets["visible"]

            windows.append(_window(f"{tag}_visible", body, h, f"{name} visible: {_describe(threshold)}", sets["visible"], threshold))
            windows.append(_window(f"{tag}_any_part_visible", body, h, f"Any part of the {name}'s disc is above the horizon", sets["any_part"], _ANY_PART))
            windows.append(_window(f"{tag}_full_disc_visible", body, h, f"The whole disc of the {name} is above the horizon", sets["full_disc"], _FULL_DISC))

            rule = rules["visible"]
            for event in result.events:
                if event.threshold != "visible":
                    continue
                around = np.array([event.et_s - _RATE_HALF_SPAN_S, event.et_s + _RATE_HALF_SPAN_S])
                around = np.clip(around, domain[0], domain[1])
                near = rule.margin(finder.disc_signals(*direction(around), profile, n_strips))
                rate = float((near[1] - near[0]) / (around[1] - around[0]) * 3600.0)
                record = {
                    "type": event.type,
                    "body": body,
                    "height_index": h,
                    "et_s": event.et_s,
                    "utc": d.et_to_utc_z(event.et_s),
                    "azimuth_deg": event.center_azimuth_deg % 360.0,
                    "horizon_elevation_deg": float(profile.elevation_at(event.azimuth_deg)),
                    "obstacle_distance_m": event.obstacle_distance_m if np.isfinite(event.obstacle_distance_m) else None,
                    "threshold": threshold,
                    "method": pk.M_EVENTS,
                    "closing_rate_deg_per_h": rate,
                }
                lat = _nearest(horizon.obstacle_lat_deg, h, event.azimuth_deg, step_deg)
                lon = _nearest(horizon.obstacle_lon_deg, h, event.azimuth_deg, step_deg)
                if lat is not None and lon is not None:
                    record["obstacle_lat_deg"], record["obstacle_lon_deg"] = lat, lon
                events.append(record)

            iv = sets["visible"]
            metrics.append(_metric(f"{tag}_visible_fraction_of_time", f"Share of the window with the {name} visible", iv.fraction(), "1", h))
            metrics.append(_metric(f"{tag}_longest_visible_s", f"Longest continuous {name} visibility", iv.longest_s(), "s", h))
            metrics.append(_metric(f"{tag}_longest_outage_s", f"Longest continuous interval without the {name}", iv.complement().longest_s(), "s", h))

            down = finder.countdown(result, "visible", reference_et)
            to_set, set_bound = _time_to(result, "set", reference_et)
            to_rise, rise_bound = (None, None) if down.visible_now else _time_to(result, "rise", reference_et)
            metrics.append(_metric(f"{tag}_visible_at_reference", f"1 if the {name} is visible ({_describe(threshold)}) at {reference_label}, else 0", 1.0 if down.visible_now else 0.0, "1", h))
            metrics.append(_metric(f"{tag}_time_to_set_s", f"Time from {reference_label} until the {name} next sets ({_describe(threshold)} stops holding); if no set lies inside the computed range, the time to the end of the range", to_set, "s", h))
            metrics.append(_metric(f"{tag}_time_to_set_is_lower_bound", f"1 if no {name} set lies inside the computed range, so that the time to set is only a lower bound, else 0", 1.0 if set_bound else 0.0, "1", h))
            metrics.append(_metric(f"{tag}_time_to_rise_s", f"Time from {reference_label} until the {name} next rises; null while the {name} is visible", to_rise, "s", h))
            if to_rise is not None:
                metrics.append(_metric(f"{tag}_time_to_rise_is_lower_bound", f"1 if no {name} rise lies inside the computed range, else 0", 1.0 if rise_bound else 0.0, "1", h))

        series[body] = BodySeries(az, el, margin, fraction, radius)

    if set(bodies) >= {"SUN", "EARTH"}:
        for h in range(len(heights)):
            both = visible[("SUN", h)].intersection(visible[("EARTH", h)])
            windows.append(_window("sun_and_earth_visible", "COMBINED", h, "Sun visible and Earth visible at the same time", both, None))

    events.sort(key=lambda event: (event["et_s"], event["body"], event["height_index"]))
    return TimelineResult(
        direction_table_id=table_package.package_id,
        direction_table_sha256=table_package.manifest["content_sha256"],
        time=grid.to_contract(d.et_to_utc_z(t[0]), d.et_to_utc_z(t[-1]), d.leap_seconds_between(t[0], t[-1])),
        bodies=list(bodies),
        series=series,
        events=events,
        windows=windows,
        metrics=metrics,
        thresholds=thresholds,
    )


def _time_to(result: finder.EventResult, kind: str, reference_et: float):
    """Seconds from the reference instant to the next event of a kind; (remaining range, True) if none."""
    for event in result.events:
        if event.threshold == "visible" and event.type == kind and event.et_s > reference_et:
            return event.et_s - reference_et, False
    return result.stop_et_s - reference_et, True


# --------------------------------------------------------------------------- method cards


def timeline_methods(
    table_dir: Path | str,
    horizon_is_terrain: bool,
    scan_step_s: float = finder.DEFAULT_SCAN_STEP_S,
    tol_s: float = finder.DEFAULT_TOL_S,
    n_strips: int = finder.DEFAULT_STRIPS,
) -> dict:
    """Method cards for the timeline section of a site package."""
    table = read_package(table_dir).manifest
    data = [f"direction table {table['package_id']} (kernel set {table['inputs']['kernel_set_id']})"]
    local = "local East/North/Up of the site; Up is the normal of the reference sphere; azimuth clockwise from north"
    horizon_note = (
        "The horizon is the terrain horizon profile of this package, linearly interpolated in azimuth."
        if horizon_is_terrain
        else "The horizon is the edge of a smooth sphere (no terrain)."
    )
    terrain_limit = (
        "The accuracy of event times is set by the terrain horizon, not by the ephemeris: near the poles a horizon error of 0.01 deg can move an event by many minutes."
        if horizon_is_terrain
        else "No terrain: times are those of a smooth sphere and are not valid for a real site."
    )
    direction_evidence = table["methods"][pk.M_DIRTAB_POSITIONS]["validation"]["evidence"]
    params = {"scan_step_s": float(scan_step_s), "bisection_tolerance_s": float(tol_s), "disc_strips": int(n_strips)}
    return {
        pk.M_DIRECTION: pk.method_card(
            title="Direction and apparent size of the body",
            definition="Azimuth and elevation of the centre of the disc and its angular radius, seen from the ground point of the site. Elevation is measured from the local horizontal plane, not from the visible horizon.",
            algorithm="Direction-table vectors interpolated to the sample time (4-point Lagrange), minus the site position vector, projected on East, North, Up; angular radius = asin(body radius / distance).",
            frame=local,
            time_scale="TDB",
            data=data,
            parameters={"aberration_correction": table["aberration_correction"], "body_frame": table["frame"]},
            status="externally-validated",
            evidence=direction_evidence,
            limits=["Stored as 32-bit floats: azimuth resolution about 0.1 arcsec.", "Observer height above the ground is not applied to the direction (below 0.01 arcsec for heights of metres)."],
        ),
        pk.M_MARGIN: pk.method_card(
            title="Margin of the disc centre above the horizon",
            definition="Elevation of the disc centre minus the horizon elevation at the azimuth of the centre, for each observer height.",
            algorithm=horizon_note,
            frame=local,
            time_scale="TDB",
            data=data,
            parameters={},
            status="analytic-test-passed",
            evidence=["core/tests/events/test_events.py (horizon interpolation, ordering of margins)."],
            limits=[terrain_limit],
        ),
        pk.M_FRACTION: pk.method_card(
            title="Visible fraction of the disc",
            definition="Fraction of the area of the disc that is above the horizon, 0 to 1. The disc is uniform (no limb darkening).",
            algorithm=f"The disc is cut into {n_strips} vertical strips (Gauss-Chebyshev nodes of the second kind); in each strip the part above the horizon at the strip's azimuth is taken exactly; the strips are summed with their area weights. {horizon_note}",
            frame=local,
            time_scale="TDB",
            data=data,
            parameters={"disc_strips": int(n_strips)},
            status="analytic-test-passed",
            evidence=["core/tests/events/test_events.py::test_visible_fraction_matches_closed_form_on_flat_horizon: within 0.002 of the closed form for a straight horizon (measured 0.00006)."],
            limits=[terrain_limit, "The horizon profile must be sampled finer than the disc radius (0.26 deg for the Sun) for the fraction to be meaningful.", "Eclipses of the Sun by the Earth are not included."],
        ),
        pk.M_EVENTS: pk.method_card(
            title="Rise and set events",
            definition="Instants at which the visibility condition of the body (the 'threshold' of the event) starts or stops holding. 'visible_fraction > 0' means the first or last part of the disc (upper limb); 'margin_deg > 0' means the centre of the disc.",
            algorithm=f"The governing signal (upper-limb margin, centre margin, lower-limb margin or visible fraction) is sampled every {scan_step_s:g} s; every change of sign is located by bisection until the bracket is at most {tol_s:g} s wide; the middle of the bracket is reported. The closing rate is the change of the governing margin over +/-{_RATE_HALF_SPAN_S:g} s. {horizon_note}",
            frame=local,
            time_scale="TDB",
            data=data,
            parameters=params,
            status="analytic-test-passed",
            evidence=[
                "core/tests/events/test_events.py: analytic cases (linear motion, diurnal arc, terrain ramp, short occultation, grazing pass) within 1 s.",
                "core/tests/events/test_site_timeline.py::test_sun_events_match_direct_spice_crossings: smooth-sphere events within 1 s of direct SPICE.",
            ],
            limits=[
                f"Numerical accuracy 0.25 s for the given inputs; two crossings closer together than {scan_step_s:g} s can be missed.",
                terrain_limit,
                "Not yet compared with published event times of real landers.",
            ],
        ),
        pk.M_WINDOWS: pk.method_card(
            title="Visibility windows",
            definition="Intervals during which the stated condition holds. '*_visible' uses the scenario threshold; '*_any_part_visible' and '*_full_disc_visible' bracket the partial phase: between them the disc is partly hidden and 'visible_fraction' says how much.",
            algorithm="Built from the refined event times; 'sun_and_earth_visible' is the intersection of the two '*_visible' sets. A window that touches the start or the end of the computed range is marked clipped.",
            frame=local,
            time_scale="TDB",
            data=data,
            parameters=params,
            status="analytic-test-passed",
            evidence=["core/tests/events/test_events.py::test_windows_and_countdown; core/tests/test_timeline.py (interval arithmetic)."],
            limits=[terrain_limit],
        ),
        pk.M_METRICS: pk.method_card(
            title="Window statistics and countdowns",
            definition="Share of the window, longest visibility and longest outage per body; time from the reference instant to the next set and the next rise. A countdown with its 'is_lower_bound' flag set to 1 means that no such event lies inside the computed range.",
            algorithm="Derived from the visibility windows and the event list.",
            frame=local,
            time_scale="TDB",
            data=data,
            parameters=params,
            status="analytic-test-passed",
            evidence=["core/tests/events/test_site_timeline.py::test_countdown_metrics."],
            limits=[terrain_limit, "Statistics describe the computed window only, not a long-term average."],
        ),
    }


def smooth_sphere_methods() -> dict:
    """Method cards for the site and horizon sections when no terrain is used."""
    frame = f"{d.FRAME} (site position); local East/North/Up (angles)"
    note = ["No terrain. Not valid for a real site; use only for tests and as a stand-in."]
    passed = ["core/tests/events/test_site_timeline.py::test_smooth_sphere_horizon_result"]
    return {
        pk.M_SITE_GEOMETRY: pk.method_card("Site geometry", "Reference sphere radius and distance of the site from the centre of the Moon.", "Sphere of the LOLA reference radius; the site is on the sphere.", frame, "none", [], {"reference_radius_m": 1737400.0}, "analytic-test-passed", passed, note),
        pk.M_SITE_HEIGHT: pk.method_card("Surface height", "Height of the surface above the reference sphere at the site.", "Set to zero: smooth sphere.", frame, "none", [], {}, "analytic-test-passed", passed, note),
        pk.M_HORIZON: pk.method_card("Smooth-sphere horizon", "Elevation of the edge of the reference sphere seen from each observer height: minus the dip angle arccos(R / (R + h)).", "Closed form.", frame, "none", [], {}, "analytic-test-passed", passed, note),
        pk.M_OBSTACLE: pk.method_card("Horizon distance", "Arc length from the site to the horizon point of the smooth sphere: R * arccos(R / (R + h)).", "Closed form.", frame, "none", [], {}, "analytic-test-passed", passed, note),
    }
