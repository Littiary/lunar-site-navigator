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
from ..ephem import kernels
from ..ephem import stations
from ..ephem import table as tb
from ..results import BodySeries, HorizonResult, TimelineResult
from ..scenario import canonical_site
from ..timeline import IntervalSet, TimeGrid
from . import eclipse, finder, links

DEFAULT_THRESHOLDS = {
    "SUN": {"quantity": "visible_fraction", "op": ">", "value": 0.0},
    "EARTH": {"quantity": "margin_deg", "op": ">", "value": 0.0},
}
_ANY_PART = {"quantity": "visible_fraction", "op": ">", "value": 0.0}
_FULL_DISC = {"quantity": "visible_fraction", "op": ">=", "value": 1.0}
_NAMES = {"SUN": "Sun", "EARTH": "Earth"}
_RATE_HALF_SPAN_S = 30.0
M_STATION_LINKS = "timeline.station_links"
_STATION_TABLES: dict = {}


def _station_table(domain: tuple) -> stations.StationTable:
    """Station table for a time range; computed once and shared by all sites of a run."""
    if domain not in _STATION_TABLES:
        _STATION_TABLES.clear()
        _STATION_TABLES[domain] = stations.station_table(domain[0], domain[1])
    return _STATION_TABLES[domain]


def _describe(threshold: dict) -> str:
    return f"{threshold['quantity']} {threshold['op']} {threshold['value']:g}"


def _window(wid: str, subject: str, h: int, definition: str, intervals: IntervalSet, threshold: dict | None, method: str = pk.M_WINDOWS) -> dict:
    out = {
        "id": wid,
        "subject": subject,
        "height_index": h,
        "definition": definition,
        "intervals_et_s": intervals.as_list(),
        "intervals_utc": [[d.et_to_utc_z(a), d.et_to_utc_z(b)] for a, b in intervals.intervals],
        "clipped_start": bool(intervals.clipped_start),
        "clipped_end": bool(intervals.clipped_end),
        "method": method,
    }
    if threshold is not None:
        out["threshold"] = threshold
    return out


# Metrics that are counted from the reference instant of the timeline.
COUNTDOWN_SUFFIXES = ("_visible_at_reference", "_time_to_set_s", "_time_to_set_is_lower_bound", "_time_to_rise_s", "_time_to_rise_is_lower_bound")


def _metric(mid: str, label: str, value, unit: str, h: int | None, method: str = pk.M_METRICS) -> dict:
    return {"id": mid, "label": label, "value": None if value is None else float(value), "unit": unit, "height_index": h, "method": method}


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
    any_part: dict[tuple[str, int], IntervalSet] = {}

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
            any_part[(body, h)] = sets["any_part"]

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

    if "SUN" in bodies:
        # Eclipses of the Sun by the Earth: the same for every observer height.
        found = eclipse.find_eclipses(eclipse.site_geometry(ground, table), domain[0], domain[1], scan_step_s, tol_s)
        partial = IntervalSet([(e.partial_start_et_s, e.partial_end_et_s) for e in found], domain)
        total = IntervalSet([(e.total_start_et_s, e.total_end_et_s) for e in found if e.total_start_et_s is not None], domain)
        for h in range(len(heights)):
            windows.append(_window("sun_eclipsed_by_earth", "SUN", h, "Part or all of the Sun's disc is hidden by the Earth (opaque Earth disc, no atmosphere), whether or not the Sun is above the terrain horizon", partial, None))
            windows.append(_window("sun_totally_eclipsed_by_earth", "SUN", h, "The whole disc of the Sun is hidden by the Earth (opaque Earth disc, no atmosphere)", total, None))
            lit = any_part[("SUN", h)].intersection(total.complement())
            windows.append(_window("sun_lit", "SUN", h, "Some part of the Sun's disc is above the terrain horizon and the Sun is not totally eclipsed by the Earth", lit, None))
        # Lit fraction of the Sun: the visible fraction, reduced at the samples at which the
        # Earth covers part of the disc. Outside an eclipse the two are the same numbers.
        sun = series["SUN"]
        lit_series = sun.visible_fraction.copy()
        eclipsed = np.zeros(t.size, dtype=bool)
        for e in found:
            eclipsed |= (t >= e.partial_start_et_s) & (t <= e.partial_end_et_s)
        if eclipsed.any():
            for h in range(len(heights)):
                profile = finder.Horizon(0.0, step_deg, np.asarray(horizon.elevation_deg[h], dtype=np.float64), np.asarray(horizon.distance_m[h], dtype=np.float64))
                lit_series[h, eclipsed] = np.clip(eclipse.power_line(ground, table, profile, t[eclipsed], n_strips), 0.0, sun.visible_fraction[h, eclipsed])
            # Between the second and the third contact the whole disc is hidden: exactly zero, not the rounding residue of the quadrature.
            for e in found:
                if e.total_start_et_s is not None:
                    lit_series[:, (t >= e.total_start_et_s) & (t <= e.total_end_et_s)] = 0.0
        sun.lit_fraction = lit_series

        totals = [e.total_end_et_s - e.total_start_et_s for e in found if e.total_start_et_s is not None]
        metrics.append(_metric("sun_eclipse_count", "Number of eclipses of the Sun by the Earth in the window (partial or total at the site)", len(found), "1", None))
        metrics.append(_metric("sun_eclipse_total_count", "Number of those eclipses that are total at the site", len(totals), "1", None))
        metrics.append(_metric("sun_eclipse_longest_totality_s", "Longest time with the whole Sun hidden by the Earth", max(totals) if totals else 0.0, "s", None))
        metrics.append(_metric("sun_eclipse_max_covered_fraction", "Largest fraction of the Sun's disc hidden by the Earth in the window", max((e.max_covered_fraction for e in found), default=0.0), "1", None))

    if "EARTH" in bodies and kernels.stations_available():
        # Direct-to-Earth windows per ground station. Absent when the station kernels are not installed.
        geometry = stations.site_link_geometry(ground, _station_table(domain))
        span = domain[1] - domain[0]
        transmit, receive = stations.TRANSMIT_MASK_DEG, stations.RECEIVE_MASK_DEG
        for h in range(len(heights)):
            profile = finder.Horizon(0.0, step_deg, np.asarray(horizon.elevation_deg[h], dtype=np.float64), np.asarray(horizon.distance_m[h], dtype=np.float64))
            two_way = links.find_link_windows(geometry, profile, domain[0], domain[1], transmit)
            listen = links.find_link_windows(geometry, profile, domain[0], domain[1], receive)
            for station, found in zip(stations.DSN_STATIONS, two_way.station_windows):
                iv = IntervalSet(found, domain)
                windows.append(_window(f"earth_station_{station.window_id}", "EARTH", h, f"Direct two-way link with {station.place} is geometrically possible: the station is above the terrain horizon of the site and the site is at least {transmit:g} deg above the station's horizon", iv, None, M_STATION_LINKS))
                metrics.append(_metric(f"dte_station_{station.window_id}_share", f"Share of the window with a possible two-way link to {station.place}", iv.total_s() / span, "1", h, M_STATION_LINKS))
            network = IntervalSet(two_way.network_windows, domain)
            windows.append(_window("earth_network_dsn", "EARTH", h, f"Direct two-way link with at least one of the three Deep Space Network complexes is geometrically possible (station mask {transmit:g} deg)", network, None, M_STATION_LINKS))
            windows.append(_window("earth_network_dsn_receive", "EARTH", h, f"At least one of the three Deep Space Network complexes can receive from the site (station mask {receive:g} deg)", IntervalSet(listen.network_windows, domain), None, M_STATION_LINKS))
            windows.append(_window("earth_stations_hidden_by_terrain", "EARTH", h, "No Deep Space Network station is above the terrain horizon of the site: a direct link is impossible whatever the station", IntervalSet(two_way.terrain_outages, domain), None, M_STATION_LINKS))
            level = two_way.relay_need_level
            metrics.append(_metric("dte_relay_need_level", "Relay need, 0 to 3: 0 = direct link possible at all times; 1 = interrupted only by station gaps on the Earth; 2 = interrupted by lunar terrain for part of the time (relay or waiting needed); 3 = no station is ever above the lunar terrain (relay required). Value for this window: " + links.RELAY_NEED_LABELS[level], level, "1", h, M_STATION_LINKS))
            metrics.append(_metric("dte_network_share", "Share of the window with a possible two-way link to the Deep Space Network", two_way.network_share(), "1", h, M_STATION_LINKS))
            metrics.append(_metric("dte_network_receive_share", "Share of the window in which the Deep Space Network can receive from the site", listen.network_share(), "1", h, M_STATION_LINKS))
            metrics.append(_metric("dte_longest_outage_s", "Longest time without a possible two-way link to the Deep Space Network", two_way.longest_outage_s(), "s", h, M_STATION_LINKS))
            metrics.append(_metric("dte_longest_terrain_outage_s", "Longest time with every station hidden by the lunar terrain", two_way.longest_terrain_outage_s(), "s", h, M_STATION_LINKS))

    # The countdown metrics count from one instant. It is stated with each of them, so that a
    # reader need not take it from the label (contract 0.10).
    reference = {
        "utc": reference_label,
        "et_s": float(reference_et),
        "time_scale": "TDB",
        "is": "start of the time window" if reference_et == domain[0] else ("stated reference time" if reference_utc else "planned landing of the site"),
    }
    for metric in metrics:
        if metric["id"].endswith(COUNTDOWN_SUFFIXES):
            metric["reference"] = reference
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
    station_card = {}
    if kernels.stations_available():
        manifest = kernels.read_manifest()["station_kernels"]
        station_card[M_STATION_LINKS] = pk.method_card(
            title="Direct-to-Earth windows per ground station and relay need",
            definition="A two-way link with a station is geometrically possible when the station (a point on the Earth) is above the terrain horizon of the site and the site is at least 10 deg above the station's horizon; 'receive' uses 6 deg. The network window is the union over the three Deep Space Network complexes, each represented by its 70 m antenna. Relay need: 0 direct link possible at all times; 1 interrupted only by station gaps; 2 interrupted by lunar terrain for part of the time; 3 no station ever above the lunar terrain.",
            algorithm=f"Station positions and local verticals relative to the Moon's centre, tabulated every {stations.TABLE_STEP_S:g} s in the Moon body-fixed frame (SPICE, LT+S) and interpolated; both conditions sampled every {links.DEFAULT_SCAN_STEP_S:g} s; changes located by bisection to {links.DEFAULT_TOL_S:g} s. {horizon_note}",
            frame=local,
            time_scale="TDB",
            data=data + [f"{entry['name']} (sha256 {entry['sha256'][:12]})" for entry in manifest],
            parameters={"transmit_mask_deg": stations.TRANSMIT_MASK_DEG, "receive_mask_deg": stations.RECEIVE_MASK_DEG, "lunar_end_mask_deg": 0.0, "mask_source": stations.MASK_SOURCE,
                        "stations": [s.name for s in stations.DSN_STATIONS], "scan_step_s": links.DEFAULT_SCAN_STEP_S},
            status="analytic-test-passed",
            evidence=[
                "core/tests/events/test_stations.py: window logic on cases with a known answer; fast path against direct SPICE.",
                "validation/stations: both ends of the link against JPL Horizons, 12 queries, 3468 rows: lunar site seen from the station within 0.42 arcsec, station seen from the lunar site within 0.21 arcsec (threshold 1 arcsec). The windows themselves have not been compared with an external source.",
            ],
            limits=[
                "Geometry only: no link budget, antenna pattern, frequency, weather or station scheduling.",
                "Station masks are single elevation limits; the azimuth-dependent horizon masks of the stations, the 13.5 deg limit for high-power transmit and the keyhole near the zenith are not modelled.",
                "Only the three Deep Space Network complexes; other networks would shorten the station gaps but cannot remove an outage caused by lunar terrain.",
                "Near the lunar horizon a real link suffers from multipath; the lunar-end mask is 0 deg here.",
                terrain_limit,
            ],
        )
    return {
        **station_card,
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
            limits=[terrain_limit, "The horizon profile must be sampled finer than the disc radius (0.26 deg for the Sun) for the fraction to be meaningful.", "This fraction is cut by the terrain only. Eclipses of the Sun by the Earth are in the channel 'lit_fraction' of the Sun and in the windows 'sun_eclipsed_by_earth' and 'sun_totally_eclipsed_by_earth'."],
        ),
        pk.M_LIT: pk.method_card(
            title="Lit fraction of the Sun's disc",
            definition="Fraction of the area of the Sun's disc that is above the terrain horizon and not hidden by the Earth, 0 to 1. Outside an eclipse of the Sun by the Earth it equals the visible fraction. Stored for the Sun only.",
            algorithm=f"At the samples inside an eclipse (between the first and the last contact at the site) the part of the disc hidden by the Earth is subtracted from the visible fraction: in each of the {n_strips} strips, the overlap of the Earth's disc with what the horizon left visible, integrated on 511 finer strips because the Earth's limb is steep where it crosses the Sun. The Earth is an opaque disc of its equatorial radius, without atmosphere. {horizon_note}",
            frame=local,
            time_scale="TDB",
            data=data,
            parameters={"disc_strips": int(n_strips), "earth_strips": 511},
            status="analytic-test-passed",
            evidence=[
                "core/tests/events/test_eclipse.py: within 0.002 of the closed form for two overlapping discs at Sun elevations from 1 to 85 deg and every position angle of the Earth (measured 0.00007); with terrain and the Earth together within 0.003 of pixel counting; the eclipse contacts from the table agree with exact SPICE geometry within 1 s.",
                "core/tests/events/test_site_timeline.py::test_lit_fraction_drops_during_the_eclipse_of_march_2025: zero in totality, equal to the visible fraction outside the eclipse.",
                "validation/eclipse: the contacts of the eclipse of 14 March 2025 at a lander site are within 0.9 min of the operator's predicted times. No measured power curve of a lander was compared.",
            ],
            limits=[
                terrain_limit,
                "Uniform disc (no limb darkening) and an opaque Earth without atmosphere: the light that the Earth's atmosphere refracts into the shadow is not modelled, and the real edge of the shadow is soft over about a minute.",
                "This is a fraction of disc area, not electrical power: panel orientation, temperature and the spectrum are not part of it.",
                "Sampled at the step of the series; the contacts themselves are in the windows 'sun_eclipsed_by_earth' and 'sun_totally_eclipsed_by_earth'.",
            ],
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
                "No published sunrise or sunset clock time of a real lander was found to compare with; the operational records of two landers bound the computed events from one side only (validation/landers).",
            ],
        ),
        pk.M_WINDOWS: pk.method_card(
            title="Visibility windows",
            definition="Intervals during which the stated condition holds. '*_visible' uses the scenario threshold; '*_any_part_visible' and '*_full_disc_visible' bracket the partial phase: between them the disc is partly hidden and 'visible_fraction' says how much. 'sun_eclipsed_by_earth' and 'sun_totally_eclipsed_by_earth' are eclipses of the Sun by the Earth seen from the site; 'sun_lit' is 'sun_any_part_visible' without the total eclipses.",
            algorithm="Built from the refined event times; 'sun_and_earth_visible' is the intersection of the two '*_visible' sets. Eclipse contacts: the separation of the Sun and the Earth seen from the site equals the sum (partial) or the difference (total) of their angular radii; Earth as an opaque disc of its equatorial radius without atmosphere; located by bisection like the events. A window that touches the start or the end of the computed range is marked clipped.",
            frame=local,
            time_scale="TDB",
            data=data,
            parameters=params,
            status="analytic-test-passed",
            evidence=[
                "core/tests/events/test_events.py::test_windows_and_countdown; core/tests/test_timeline.py (interval arithmetic).",
                "validation/pgda: the long-term share of time with any part of the Sun, and of the Earth, above the terrain horizon agrees with the published LOLA illumination maps at 100 points on terrain of the same 60 m resolution (median absolute difference 0.0006 and 0.0004; permanent shadow agrees at all 98 points compared). This checks long-term shares, not individual window edges.",
                "validation/lro_images: sunlit or shadowed state against two dated LROC images. The shadowed state of the south pole on 18 May 2022 agrees. Along an image strip of 13 December 2010 the agreement is 89.3 % of 298 points against a registered criterion of 90 %: a failed check, in which every disagreement is ground this method calls sunlit at grazing incidence and the image rule reads as shadow.",
                "Eclipse contacts: core/tests/events/test_eclipse.py (analytic pass within 1 s) and validation/eclipse (eclipse of 14 March 2025 at a lander site: within 0.9 min of the operator's predicted contacts, inside NASA's whole-Moon contacts).",
            ],
            limits=[terrain_limit, "Eclipses: the Earth's atmosphere is not modelled; the real edge of the shadow is soft over about a minute and totality is dim, not black."],
        ),
        pk.M_METRICS: pk.method_card(
            title="Window statistics and countdowns",
            definition="Share of the window, longest visibility and longest outage per body; time from the reference instant to the next set and the next rise. A countdown with its 'is_lower_bound' flag set to 1 means that no such event lies inside the computed range. 'sun_eclipse_*' count and measure the eclipses of the Sun by the Earth; they do not depend on the observer height.",
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
