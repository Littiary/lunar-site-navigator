"""From a scenario to packages: the one function every front end calls.

No science here. The horizon comes from lsncore.horizon, the direction table and the
timeline from the ephemeris modules (lsncore.ephem, lsncore.events) when they are
installed; without them a site package holds the horizon only and says so.
"""

from __future__ import annotations

import time as _time
from pathlib import Path

import numpy as np

from . import packaging as pk
from .blocking import add_blocking_to_timeline
from .calendar import add_calendar_to_timeline
from .contract import read_package
from .contract import write_index
from .dem import Terrain
from .horizon import M_FAR_FIELD, HorizonSettings, compute_horizon
from .obstacles import ABS_TOL_M, NEAR_FIELD_M, REL_TOL
from .pairs import build_pairs_package
from .trade import add_height_trade_to_timeline
from .scenario import DEFAULT_HEIGHT_M, canonical_heights, canonical_site
from .synthetic import run_synthetic_scenario
from .timeline import IntervalSet, TimeGrid
from .uncertainty import add_uncertainty_to_timeline, ellipse_points, horizon_error_band, visibility_window

# Body-fixed frame of the LOLA elevation products and of the direction table: the lunar
# mean-Earth / polar-axis frame, as named in the frame kernel the ephemeris stream loads.
BODY_FIXED_FRAME = "MOON_ME_DE440_ME421"

SYNTHETIC_TERRAIN_NOTICE = (
    "SYNTHETIC TERRAIN. The horizon in this package was computed by the real algorithm, but "
    "from an invented test surface, not from lunar elevation data. It describes no real "
    "place. Do not use it, quote it or present it as a result."
)

# Measured on the analytic cases of core/tests/test_horizon.py (see docs/method/horizon.md).
_EVIDENCE = [
    "core/tests/test_horizon.py::test_smooth_sphere_horizon_depression: largest error 3.0e-12 deg (threshold 0.0005 deg), 6 sites incl. both poles and the longitude seam",
    "core/tests/test_horizon.py::test_crater_rim_at_known_distance_and_height: largest error 2e-13 deg (threshold 0.001 deg)",
    "core/tests/test_horizon.py::test_hill_appears_at_its_bearing_with_the_right_elevation: largest error 3.4e-8 deg against an independent 1-D solution (threshold 0.002 deg)",
    "core/tests/test_horizon.py::test_nothing_is_missed_on_a_rough_gridded_surface: never below an exhaustive 1 m reference scan on a spiked synthetic raster (threshold 0.002 deg, 144 comparisons)",
    "core/tests/test_horizon.py::test_nothing_is_missed_on_lola_data: never below an exhaustive 1 m reference scan on the LOLA 20 m and 60 m south-polar products (threshold 0.002 deg; 648 comparisons at 6 test points measured by script)",
    "Self-convergence on LOLA data: a four times finer search changes no value by more than 0.0006 deg (51 840 values)",
    "No comparison with an independent horizon product has been made yet.",
]


def horizon_methods(terrain: Terrain, azimuth_step_deg: float, max_range_m: float, settings: HorizonSettings) -> dict:
    """Method cards of the site geometry and the terrain horizon."""
    dem = terrain.describe()
    data = [dem["dem_set_id"]]
    body_frame = f"{BODY_FIXED_FRAME} (Moon body-fixed, mean Earth / polar axis); sphere of the DEM reference radius"
    local = "local East/North/Up at the site; up is the outward radial direction of the reference sphere"
    px = terrain.finest_pixel_m
    params = {
        "azimuth_step_deg": azimuth_step_deg,
        "max_range_m": max_range_m,
        "finest_pixel_m": px,
        "first_point_m": px * settings.first_sample_px,
        "lattice_step_m": px * settings.fine_step_px,
        "inner_lattice_step_m": px * settings.inner_step_px,
        "inner_zone_m": px * settings.inner_zone_px,
        "cell_growth": settings.cell_growth,
        "max_cell_m": px * settings.fine_step_px * settings.max_cell_points,
        "creases": "every crossing of an evaluated stretch of ray with a line through pixel centres is evaluated",
        "refinement": f"{settings.refine_rounds} rounds of {settings.refine_points} points around the leading points of each azimuth",
        "interpolation": "bilinear between pixel centres, finest product that covers the point",
        "skipping": "a cell of a ray is skipped only if the block maximum of the terrain over the cell proves that nothing in it reaches the horizon already found",
    }
    limits = [
        "The terrain is the bilinear surface through the DEM pixels: relief smaller than a pixel is absent, and a crest between pixels is cut. Within about 1 km of the site this, not the algorithm, limits the accuracy.",
        f"Azimuth sampling is {azimuth_step_deg} deg; an obstacle narrower than that between two rays is not seen.",
        "Single high pixels of the DEM are taken at face value, whether they are terrain or noise.",
        "Terrain beyond the search radius or beyond the data is not seen; error_bounds.far_field_max_deg states how much it could add.",
        "The observer is a point at the given height above the DEM surface on the radial through the site; the lander body, local rocks and regolith relief are not modelled.",
    ]
    status = "analytic-test-passed"

    def card(title, definition, algorithm, frame, parameters, extra_limits=()):
        return pk.method_card(title, definition, algorithm, frame, "none", data, parameters, status, _EVIDENCE, limits + list(extra_limits))

    return {
        pk.M_SITE_GEOMETRY: card(
            "Site geometry on the reference sphere",
            "reference_radius_m is the radius of the sphere the DEM heights refer to, read from the DEM product. radius_m is that radius plus the terrain height at the site.",
            "Sum of the reference radius and the bilinear DEM height at the site coordinates.",
            body_frame,
            {},
        ),
        pk.M_SITE_HEIGHT: card(
            "Terrain height at the site",
            "Height of the DEM surface above the reference sphere at the site coordinates, in metres.",
            "Bilinear interpolation of the finest DEM layer that covers the site.",
            body_frame,
            {"interpolation": "bilinear between pixel centres"},
        ),
        pk.M_HORIZON: card(
            "Terrain horizon elevation",
            "For each azimuth and observer height: the largest elevation angle, above the plane perpendicular to the radial direction at the site, of the straight line from the observer to any terrain point along the great circle of that azimuth, out to the search radius. Negative when the terrain horizon lies below the horizontal.",
            "Great-circle rays on a sphere. Exact triangle observer - terrain point - centre of the Moon, tan(e) = (r_t cos g - r_o) / (r_t sin g), evaluated in a cancellation-free form; curvature is contained in the formula. Each ray is covered by a lattice of points half a pixel apart. Near the site every lattice point is evaluated on the finest data. Farther out the lattice is grouped into cells; a cell is skipped only if the block maximum of the terrain over the cell proves that nothing in it can reach the horizon already found, otherwise it is walked point by point on the finest data. Crossings of the ray with the lines through pixel centres (the creases of the bilinear surface) are evaluated as well, and the leading points are refined by nested sampling. All observer heights share the same terrain evaluations.",
            local,
            params,
        ),
        pk.M_OBSTACLE: card(
            "Terrain point that sets the horizon",
            "distance_m: arc length along the reference sphere from the site to the terrain point whose line of sight has the largest elevation angle. obstacle_height_m: DEM height of that point. obstacle_lat_deg, obstacle_lon_deg: its coordinates.",
            "Location of the maximum found by the horizon search, after refinement; coordinates from the great circle of the azimuth.",
            body_frame,
            params,
            ["Where two obstacles reach nearly the same elevation the reported point can jump between them from one azimuth or observer height to the next."],
        ),
        pk.M_OBSTACLES: card(
            "Obstacles of the horizon profile",
            "An obstacle is a run of neighbouring azimuths whose horizon is set by the same piece of terrain. obstacle_id gives, per observer height and azimuth, the index of the obstacle in the obstacles list (-1 where the horizon has no data). Each obstacle lists its azimuth range, the range of distances of its limiting points, and its peak: the azimuth at which its horizon elevation is largest, with the distance, coordinates and height of the limiting point there.",
            f"Two neighbouring azimuths belong to the same obstacle if the distances of their limiting points differ by no more than {REL_TOL:.0%} of the smaller one or by no more than {ABS_TOL_M:g} m. The profile is treated as periodic. near_field marks a peak closer than {NEAR_FIELD_M:g} m.",
            local,
            {"relative_tolerance": REL_TOL, "absolute_tolerance_m": ABS_TOL_M, "near_field_m": NEAR_FIELD_M},
            ["The grouping looks at distance only. It does not identify named features, and one ridge can be split where the limiting point jumps along it."],
        ),
        M_FAR_FIELD: card(
            "Bound on unseen far terrain",
            "far_field_max_deg: the largest amount, over all azimuths and observer heights, by which terrain beyond the reach of the rays could still raise the horizon, if no such terrain is higher than ceiling_height_m. 0 means the search radius is proven sufficient under that assumption. far_field_open_azimuth_fraction: share of azimuths with a non-zero bound. shortest_reach_m: shortest ray reach (search radius, or the edge of the data).",
            "A point of height H at central angle g from an observer at radius r_o is seen at elevation atan2((R+H) cos g - r_o, (R+H) sin g), which grows with H and, beyond the tangent point, falls with g. The bound is that elevation for H = ceiling at the end of each ray, minus the horizon found, floored at zero.",
            local,
            {"max_range_m": max_range_m, "ceiling_source": "highest terrain in the DEM products" if terrain.ceiling_height_m is not None else "highest terrain met inside the search radius (assumption)"},
        ),
    }


def blocking_methods(dem_set_id: str, azimuth_step_deg: float, series_step_s: float, direction_table_id: str) -> dict:
    """Method cards of the comparison with a smooth sphere and of the blockers."""
    local = "local East/North/Up at the site; up is the outward radial direction of the reference sphere"
    data = [dem_set_id, direction_table_id]
    evidence = [
        "core/tests/test_obstacles.py::test_hours_lost_to_a_ridge_against_the_closed_form: lost time 0.9 s off the closed-form value of 45.7 h (threshold 5 s)",
        "core/tests/test_obstacles.py::test_lost_time_is_split_between_obstacles_without_loss: the shares add up to the lost time (threshold 1e-6 s)",
        "core/tests/test_obstacles.py::test_limiting_azimuth_on_a_sloping_horizon",
        "Not yet compared with an independent computation on real terrain.",
    ]
    return {
        pk.M_SMOOTH_SPHERE: pk.method_card(
            "Visibility over a smooth sphere",
            "The visibility condition of the body evaluated as if the Moon were a smooth sphere through the ground point of the site: the horizon is a circle below the horizontal by the dip angle acos(r / (r + m)), r being the distance of the site from the centre and m the observer height. Same direction table, same condition and same event finder as the terrain windows.",
            "Event finder (lsncore.events.finder) on a flat horizon profile at minus the dip angle.",
            local,
            "TDB",
            [direction_table_id],
            {"condition": "the scenario threshold of the body"},
            "analytic-test-passed",
            evidence,
            ["This is a reference for comparison, not a prediction: no site sits on a smooth sphere."],
        ),
        pk.M_BLOCKING: pk.method_card(
            "Time lost to terrain and the obstacle that causes it",
            "lost_to_terrain: the times at which the body is visible over a smooth sphere and not visible over the terrain. gained_from_terrain: visible over the terrain and not over a smooth sphere (terrain below the smooth horizon). blocker_azimuth_index: for every sample of the series, the index of the horizon sample that limits the view of the disc; for a hidden disc under the 'any part visible' condition it is where the disc is closest to showing. blockers: the lost time split between the obstacles of the horizon, each with the intervals in which it is the limiting obstacle.",
            "Interval algebra on the visibility windows (lost = smooth AND NOT terrain). For the split, each sample of the series stands for the half step before and after it, and its time goes to the obstacle at its limiting horizon sample.",
            local,
            "TDB",
            data,
            {"series_step_s": series_step_s, "azimuth_step_deg": azimuth_step_deg},
            "analytic-test-passed",
            evidence,
            [
                f"The totals have the accuracy of the event finder; the split between obstacles is resolved to the series step ({series_step_s:g} s).",
                "One obstacle is named per instant: the one at the limiting azimuth. Other terrain under the disc may hide parts of it at the same time.",
                "Obstacles are runs of the horizon profile, not named terrain features; see the obstacle card.",
                "The horizon limits of docs/method/horizon.md apply: near terrain depends on single DEM pixels.",
            ],
        ),
    }


def uncertainty_methods(dem_set_id: str, direction_table_id: str, stated: dict) -> dict:
    """Method cards of the horizon-error band and of the landing-ellipse survey."""
    local = "local East/North/Up at each point; up is the outward radial direction of the reference sphere"
    data = [dem_set_id, direction_table_id]
    evidence = [
        "core/tests/test_uncertainty.py::test_band_of_a_rising_body_against_the_closed_form: band edges against delta / rate (threshold 2 s)",
        "core/tests/test_uncertainty.py::test_window_of_a_displaced_point_follows_from_its_own_local_frame: window edges of nine displaced points against a 1 s brute-force scan (threshold 2 s)",
        "core/tests/test_uncertainty.py::test_ellipse_points_fill_the_ellipse_evenly (threshold 0.5 m)",
        "The stated error and the stated ellipse are inputs. Whether they describe the real elevation model or the real landing accuracy has not been checked.",
    ]
    cards = {}
    if "horizon_error_deg" in stated:
        cards[pk.M_HORIZON_ERROR] = pk.method_card(
            "Band for a stated horizon error",
            "visible_certain: the times at which the body is visible even if the terrain horizon is higher than computed by the stated angle. visible_possible: the times at which it is visible if the horizon is lower by that angle. visible_uncertain: possible and not certain. For every rise and set, earliest and latest give the interval of the uncertain set that contains the event.",
            "The event finder is run on the horizon profile raised and lowered by the stated angle (one common shift of the whole profile). Raising a horizon can only hide and lowering it can only reveal, so certain lies inside the nominal window and the nominal window inside possible.",
            local,
            "TDB",
            data,
            {"horizon_error_deg": stated["horizon_error_deg"]},
            "analytic-test-passed",
            evidence,
            [
                "One common shift is assumed. Real horizon errors differ from azimuth to azimuth and with the distance of the limiting terrain (a height error of the elevation model matters more for near terrain); the band does not model that.",
                "The stated angle is an input, not an estimate of the elevation model's accuracy.",
                "Ephemeris, landing position and observer height are not in this band.",
                "Where the body grazes the horizon, a small angle moves an event by many hours; events can appear or disappear inside the band, and then the nominal event keeps its own time as both bounds.",
            ],
        )
    if "landing_ellipse" in stated:
        cards[pk.M_ELLIPSE] = pk.method_card(
            "Survey of the stated landing ellipse",
            "visible_all_points / visible_any_point: the times at which the body is visible at every sample point of the ellipse / at one point at least. ellipse_visible_share: at every sample of the series, the share of the points at which it is visible. points: the sample points with their terrain height and visible time; visible_s: visible time at the centre, and the least, median and largest over the points.",
            "Sample points fill the ellipse evenly in area (sunflower pattern, the centre first, deterministic). For every point the terrain horizon is computed with the same settings as for the site, and the event finder is run with the direction of the body from that point.",
            local,
            "TDB",
            data,
            dict(stated["landing_ellipse"]),
            "analytic-test-passed",
            evidence,
            [
                "A survey, not a probability: no landing-dispersion distribution is assumed. With few points, a small part of the ellipse with different lighting can be missed.",
                "Computed for the default observer height only.",
                "Not combined with the horizon error.",
                "Each point's horizon has the limits of docs/method/horizon.md; neighbouring points can differ strongly where near terrain sets the horizon.",
            ],
        )
    return cards


def _uncertainty_inputs(csite, terrain, horizon, table_dir, timeline, thresholds, stated, hd, az_step, max_range, settings):
    """Bands for a stated horizon error and windows at the sample points of a stated ellipse."""
    from .ephem import directions as d
    from .ephem import table as ephem_table
    from .events import finder

    table = ephem_table.load_table(table_dir)
    grid = TimeGrid.from_contract(timeline.time)
    domain = (grid.start_et_s, grid.end_et_s)
    heights = horizon.observer_heights_m
    rules = {body: finder.threshold_from_contract(thresholds[body], "visible") for body in timeline.bodies}
    notes = []

    bands = None
    error_deg = stated.get("horizon_error_deg")
    if error_deg:
        bands = {}
        ground = d.Site(csite["lon_deg"], csite["lat_deg"], horizon.surface_height_m / 1000.0)
        for body in timeline.bodies:
            direction = finder.site_direction(ground, table, body)
            for h in range(len(heights)):
                nominal = timeline.window(f"{body.lower()}_visible", h)
                bands[(body, h)] = horizon_error_band(direction, horizon.elevation_deg[h], az_step, domain, rules[body], error_deg, nominal)

    ellipse = None
    spec = stated.get("landing_ellipse")
    if spec:
        r_site = horizon.reference_radius_m + horizon.surface_height_m
        points = ellipse_points(csite["lat_deg"], csite["lon_deg"], spec["semi_major_m"], spec["semi_minor_m"], spec["azimuth_deg"], spec["points"], r_site)
        sets = {body: [] for body in timeline.bodies}
        ground_heights = []
        for k, (lat, lon) in enumerate(points):
            if k == 0:  # the centre is the site itself
                profile, ground_height = horizon.elevation_deg[hd], horizon.surface_height_m
            else:
                try:
                    here = compute_horizon(terrain, float(lat), float(lon), [heights[hd]], az_step, max_range, settings)
                    profile, ground_height = here.elevation_deg[0], here.surface_height_m
                except ValueError:
                    profile, ground_height = None, None
            if profile is None or not np.all(np.isfinite(profile)):
                notes.append(f"landing ellipse: sample point {k} has no complete terrain horizon and was left out")
                ground_heights.append(ground_height)
                for body in timeline.bodies:
                    sets[body].append(None)
                continue
            ground_heights.append(ground_height)
            place = d.Site(float(lon), float(lat), ground_height / 1000.0)
            for body in timeline.bodies:
                if k == 0:
                    sets[body].append(timeline.window(f"{body.lower()}_visible", hd))
                else:
                    sets[body].append(visibility_window(finder.site_direction(place, table, body), profile, az_step, domain, rules[body]))
        ellipse = {"spec": spec, "height_index": hd, "points": points, "surface_height_m": ground_heights, "sets": sets}
    return bands, ellipse, notes


def trade_methods(dem_set_id: str, direction_table_id: str) -> dict:
    """Method cards of the mast-height trade and of the site pairs."""
    local = "local East/North/Up at each site; up is the outward radial direction of the reference sphere"
    data = [dem_set_id, direction_table_id]
    evidence = [
        "core/tests/test_trade_pairs.py::test_mast_height_in_a_crater_against_the_closed_form: visible time for five observer heights against the closed-form rim elevation (threshold 5 s)",
        "core/tests/test_trade_pairs.py::test_pair_identities_hold_for_random_windows (threshold 1e-6 s)",
        "Both are arithmetic on the visibility windows and inherit their accuracy and their limits.",
    ]
    return {
        pk.M_HEIGHT_TRADE: pk.method_card(
            "Mast-height trade",
            "For every observer height of the package: the total time a visibility window holds and the longest continuous time it does not, over the computed range, and the change of each against the lowest height. sun_least_lunar_day_s: Sun-visible time in the least sunlit complete lunar day.",
            "The horizon is computed for all observer heights in one pass and the event finder runs for each; the table is read off the resulting windows.",
            local,
            "TDB",
            data,
            {},
            "analytic-test-passed",
            evidence,
            [
                "Only the listed heights are computed; nothing is interpolated between them.",
                "A mast changes the view of near terrain most. Where the gain is large, the horizon is set by terrain within about 1 km, which depends on single pixels of the elevation model: the gain is then as uncertain as that terrain.",
                "The observer is a point on the radial through the site; a real mast, its base and the lander are not modelled.",
            ],
        ),
        pk.M_PAIRS: pk.method_card(
            "Complementary site pairs",
            "For every pair of sites and each compared window: a_s and b_s are the times the window holds at each site; either_s at one of them at least; both_s at both; neither_s at neither, with its longest stretch and its intervals. gain_over_better_s is either_s minus the larger of a_s and b_s; covered_share_of_better_outage is that gain divided by the time the better site lacks. distance_m is the great-circle distance on the reference sphere.",
            "Union, intersection and complement of the visibility windows of the site packages, each taken at its default observer height. The packages must share one time range.",
            local,
            "TDB",
            data,
            {},
            "analytic-test-passed",
            evidence,
            [
                "The comparison says when at least one site sees the body. It says nothing about moving power or data between the sites: no line of sight between them, no cable, no relay is computed.",
                "Each site's windows carry the limits of its own horizon.",
            ],
        ),
    }


def calendar_methods(dem_set_id: str, direction_table_id: str) -> dict:
    """Method cards of the lunar-day calendar and of the landing windows."""
    local = "local East/North/Up at the site; up is the outward radial direction of the reference sphere"
    data = [dem_set_id, direction_table_id]
    evidence = [
        "core/tests/test_calendar.py::test_lunar_days_begin_when_the_sun_crosses_the_far_side_meridian: boundaries 0.004 s off the closed form (threshold 5 s)",
        "core/tests/test_calendar.py::test_calendar_totals_add_up_to_the_window_totals (threshold 1e-6 s)",
        "core/tests/test_calendar.py::test_exact_landing_windows_agree_with_a_brute_force_scan: 25 random cases, 1 s scan (threshold 2 s)",
        "core/tests/test_calendar.py::test_slip_tolerance_of_a_planned_landing",
        "The calendar and the landing windows are arithmetic on the visibility windows; they inherit the accuracy and the limits of those windows.",
    ]
    return {
        pk.M_CALENDAR: pk.method_card(
            "Visible time per lunar day",
            "For every lunar day inside the computed range and every observer height: the time for which a visibility window holds (seconds), or the longest stretch inside the lunar day for which it does not. A lunar day begins when the Sun crosses the 180 degree meridian of the body-fixed frame; the periods are the same for every site.",
            "Subsolar longitude from the direction table, crossings located by linear interpolation between hourly records; intersection of the visibility windows with each period.",
            local,
            "TDB",
            data,
            {"period_boundary": "subsolar longitude 180 deg"},
            "analytic-test-passed",
            evidence,
            [
                "The first and the last period are cut by the ends of the computed range (complete = false); their totals cannot be compared with full lunar days.",
                "A stretch without the Sun that continues across a period boundary is cut there; the longest outage of the whole range is in the metrics.",
            ],
        ),
        pk.M_OPPORTUNITY: pk.method_card(
            "Landing windows of a stated requirement and slip tolerance",
            "landing_windows: the set of landing times for which every condition of the requirement holds. slip_tolerance_s: how long the planned landing can be delayed while the requirement keeps holding (0 if the planned time is not feasible); early_tolerance_s: how much earlier it can be. wait_s: time from an infeasible planned landing to the next landing window. feasible_s_per_period: feasible landing time inside each lunar day.",
            "Exact interval arithmetic on the visibility windows: erosion of the windows for 'continuous from landing', a piecewise-linear cumulative measure for 'total in mission', intersection of all conditions. No sampling of dates.",
            local,
            "TDB",
            data,
            {"requirement": "request.timeline.requirements"},
            "analytic-test-passed",
            evidence,
            [
                "The requirement is the one stated in the scenario; the tool does not know whether it is the right requirement for a mission.",
                "Nothing is assumed about the time after the computed range: a landing whose requirement cannot be checked inside the range counts as not feasible, and a tolerance that ends at the edge of the range is a lower bound.",
                "A landing window is as reliable as the visibility windows it is built from: near-field obstacles and DEM errors move its edges (docs/method/horizon.md).",
            ],
        ),
    }


def _smooth_sphere_windows(csite: dict, horizon, table_dir, timeline, thresholds: dict) -> dict:
    """Visibility windows of every body and observer height over a smooth sphere through the site."""
    from .ephem import directions as d
    from .ephem import table as ephem_table
    from .events import finder

    table = ephem_table.load_table(table_dir)
    grid = TimeGrid.from_contract(timeline.time)
    domain = (grid.start_et_s, grid.end_et_s)
    ground = d.Site(csite["lon_deg"], csite["lat_deg"], horizon.surface_height_m / 1000.0)
    r_site = horizon.reference_radius_m + horizon.surface_height_m
    out = {}
    for body in timeline.bodies:
        direction = finder.site_direction(ground, table, body)
        rule = {"visible": finder.threshold_from_contract(thresholds[body], "visible")}
        for h, m in enumerate(horizon.observer_heights_m):
            dip = float(np.degrees(np.arccos(r_site / (r_site + m))))
            flat = finder.Horizon(0.0, 1.0, np.full(360, -dip))
            result = finder.find_events(direction, flat, domain[0], domain[1], thresholds=rule)
            out[(body, h)] = IntervalSet(finder.windows(result, "visible").intervals_et_s, domain)
    return out


def _mark_synthetic(methods: dict) -> dict:
    out = {}
    for name, card in methods.items():
        out[name] = {**card, "validation": {"status": "synthetic", "evidence": ["Computed from a synthetic test surface."]}}
    return out


def run_scenario(
    scenario: dict,
    out_root: Path | str,
    terrain: Terrain | None = None,
    terrain_is_synthetic: bool = False,
    settings: HorizonSettings = HorizonSettings(),
) -> list[Path]:
    """Compute every site of a scenario and write the packages. Returns their directories."""
    if scenario["synthetic"] and terrain is None:
        return run_synthetic_scenario(scenario, out_root)
    if terrain is None:
        raise ValueError("a terrain source is required for a scenario that is not synthetic")

    out_root = Path(out_root)
    scenario_id = scenario["scenario_id"]
    synthetic = bool(terrain_is_synthetic)
    heights = canonical_heights(scenario["observer_heights_m"])
    az_step = float(scenario["horizon"]["azimuth_step_deg"])
    max_range = float(scenario["horizon"]["max_range_m"])
    window = scenario.get("time_window")
    bodies = list(scenario["bodies"])
    written: list[Path] = []
    extra_warnings: list[str] = []

    wanted = scenario["data"]["dem_set_id"]
    actual = terrain.describe()["dem_set_id"]
    if wanted not in ("any", actual):
        extra_warnings.append(f"data: the scenario asks for DEM set '{wanted}', the run used '{actual}'")

    # Direction table and timeline: provided by the ephemeris modules when present.
    table_dir = None
    timeline_mod = None
    timeline_request = None
    thresholds = None
    if window is not None:
        try:
            from .ephem import table as ephem_table
            from .events import timeline as timeline_mod
            from .synthetic import DEFAULT_THRESHOLDS

            thresholds = {**DEFAULT_THRESHOLDS, **scenario.get("thresholds", {})}
            table_dir = ephem_table.write_direction_table(
                out_root, window["start_utc"], window["end_utc"], scenario_id=scenario_id
            )
            written.append(Path(table_dir))
            timeline_request = {
                "start_utc": window["start_utc"],
                "end_utc": window["end_utc"],
                "step_s": float(window["step_s"]),
                "bodies": bodies,
                "thresholds": {b: thresholds[b] for b in bodies},
            }
            if scenario.get("requirements"):
                timeline_request["requirements"] = scenario["requirements"]
            if scenario.get("uncertainty"):
                timeline_request["uncertainty"] = scenario["uncertainty"]
        except ImportError:
            extra_warnings.append(
                "timeline: the ephemeris modules are not installed; this package holds the horizon only"
            )

    for site in scenario["sites"]:
        csite = canonical_site(site)
        t0 = _time.perf_counter()
        horizon = compute_horizon(terrain, csite["lat_deg"], csite["lon_deg"], heights, az_step, max_range, settings)
        t1 = _time.perf_counter()
        methods = horizon_methods(terrain, az_step, max_range, settings)
        timeline = None
        status = "ok"
        warnings = list(extra_warnings)
        if window is not None and table_dir is None:
            status = "partial"
        if table_dir is not None:
            from .ephem import directions as ephem_directions

            timeline = timeline_mod.compute_timeline(site, horizon, table_dir, window, bodies, thresholds)
            methods.update(timeline_mod.timeline_methods(table_dir, horizon_is_terrain=True))
            smooth = _smooth_sphere_windows(csite, horizon, table_dir, timeline, thresholds)
            add_blocking_to_timeline(timeline, horizon, smooth, ephem_directions.et_to_utc_z)
            methods.update(
                blocking_methods(terrain.describe()["dem_set_id"], az_step, float(window["step_s"]), timeline.direction_table_id)
            )
            stated = scenario.get("uncertainty") or {}
            if stated:
                default_height = scenario.get("default_height_m", DEFAULT_HEIGHT_M)
                hd = int(np.argmin(np.abs(np.asarray(heights) - default_height)))
                bands, ellipse, notes = _uncertainty_inputs(
                    csite, terrain, horizon, table_dir, timeline, thresholds, stated, hd, az_step, max_range, settings
                )
                warnings.extend(notes)
                add_uncertainty_to_timeline(timeline, stated.get("horizon_error_deg"), bands, ellipse, ephem_directions.et_to_utc_z)
                methods.update(uncertainty_methods(terrain.describe()["dem_set_id"], timeline.direction_table_id, stated))
            landing = site.get("landing_utc")
            add_calendar_to_timeline(
                timeline, read_package(table_dir), len(heights), scenario.get("requirements"),
                float(ephem_directions.utc_to_et(landing)) if landing else None, ephem_directions.et_to_utc_z,
            )
            methods.update(calendar_methods(terrain.describe()["dem_set_id"], timeline.direction_table_id))
            add_height_trade_to_timeline(timeline, heights)
            methods.update(trade_methods(terrain.describe()["dem_set_id"], timeline.direction_table_id))
        t2 = _time.perf_counter()
        if not horizon.coverage_complete:
            status = "partial"
        if synthetic:
            methods = _mark_synthetic(methods)
        written.append(
            pk.build_site_package(
                out_root,
                site=site,
                frame_name=BODY_FIXED_FRAME,
                dem_input=terrain.describe(),
                horizon=horizon,
                methods=methods,
                synthetic=synthetic,
                synthetic_notice=SYNTHETIC_TERRAIN_NOTICE if synthetic else None,
                timeline=timeline,
                timeline_request={**timeline_request, "landing_utc": site.get("landing_utc")} if timeline is not None else None,
                default_height_m=scenario.get("default_height_m", DEFAULT_HEIGHT_M),
                scenario_id=scenario_id,
                timings_s={"horizon": t1 - t0, "timeline": t2 - t1},
                status=status,
                warnings=warnings,
            )
        )
    pair_methods = trade_methods(terrain.describe()["dem_set_id"], "the direction table of the site packages")
    pairs = build_pairs_package(
        out_root,
        written,  # it picks the site packages with a timeline
        _mark_synthetic(pair_methods) if synthetic else pair_methods,
        scenario_id=scenario_id,
    )
    if pairs is not None:
        written.append(pairs)
    write_index(out_root, scenario_id)
    return written
