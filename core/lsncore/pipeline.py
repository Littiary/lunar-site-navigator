"""From a scenario to packages: the one function every front end calls.

No science here. The horizon comes from lsncore.horizon, the direction table and the
timeline from the ephemeris modules (lsncore.ephem, lsncore.events) when they are
installed; without them a site package holds the horizon only and says so.
"""

from __future__ import annotations

import time as _time
from pathlib import Path

from . import packaging as pk
from .contract import write_index
from .dem import Terrain
from .horizon import M_FAR_FIELD, HorizonSettings, compute_horizon
from .scenario import DEFAULT_HEIGHT_M, canonical_heights, canonical_site
from .synthetic import run_synthetic_scenario

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
        M_FAR_FIELD: card(
            "Bound on unseen far terrain",
            "far_field_max_deg: the largest amount, over all azimuths and observer heights, by which terrain beyond the reach of the rays could still raise the horizon, if no such terrain is higher than ceiling_height_m. 0 means the search radius is proven sufficient under that assumption. far_field_open_azimuth_fraction: share of azimuths with a non-zero bound. shortest_reach_m: shortest ray reach (search radius, or the edge of the data).",
            "A point of height H at central angle g from an observer at radius r_o is seen at elevation atan2((R+H) cos g - r_o, (R+H) sin g), which grows with H and, beyond the tangent point, falls with g. The bound is that elevation for H = ceiling at the end of each ray, minus the horizon found, floored at zero.",
            local,
            {"max_range_m": max_range_m, "ceiling_source": "highest terrain in the DEM products" if terrain.ceiling_height_m is not None else "highest terrain met inside the search radius (assumption)"},
        ),
    }


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
            timeline = timeline_mod.compute_timeline(site, horizon, table_dir, window, bodies, thresholds)
            methods.update(timeline_mod.timeline_methods(table_dir, horizon_is_terrain=True))
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
