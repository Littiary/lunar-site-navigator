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
from .contract import write_index
from .dem import Terrain
from .horizon import M_FAR_FIELD, HorizonSettings, compute_horizon
from .obstacles import ABS_TOL_M, NEAR_FIELD_M, REL_TOL
from .scenario import DEFAULT_HEIGHT_M, canonical_heights, canonical_site
from .synthetic import run_synthetic_scenario
from .timeline import IntervalSet, TimeGrid

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
    "Self-convergence on LOLA data: a four times finer search changes no value by more than 0.0005 deg (51 840 values)",
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
    if wanted != actual:
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
                timeline_request=timeline_request if timeline is not None else None,
                default_height_m=scenario.get("default_height_m", DEFAULT_HEIGHT_M),
                scenario_id=scenario_id,
                timings_s={"horizon": t1 - t0, "timeline": t2 - t1},
                status=status,
                warnings=warnings,
            )
        )
    write_index(out_root, scenario_id)
    return written
