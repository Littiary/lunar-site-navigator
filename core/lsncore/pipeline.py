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
from .terrain_patch import DEFAULT_PATCHES, canonical_patches, compute_patches, patch_warnings
from .timeline import IntervalSet, TimeGrid
from .uncertainty import (
    add_uncertainty_to_timeline, band_from_windows, ellipse_points, height_error_for_points, horizon_error_profile, terrain_slope_deg, window_job,
)

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
        "first_point_m": min(px * settings.first_sample_px, settings.first_sample_max_m),
        "ground_at_the_site": (
            "not offered to the observer at 0 m: its horizon is that of the terrain from first_point_m outward, the convention of pixel-based illumination maps"
            if settings.ground_from_first_point
            else "searched for every observer height: for an observer at 0 m the slope of the ground at the site is part of its horizon"
        ),
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
        "Observer height 0 is the surface point itself, and the slope of the ground at the site is part of its horizon: uphill, the horizon of a 0 m observer is at least that slope. The elevation model does not resolve the ground below its pixel, so this slope is that of the interpolated surface; a 0 m result depends on it far more than a result at 1 m and above, where the ground at the site reached no horizon on LOLA data.",
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
            "Great-circle rays on a sphere. Exact triangle observer - terrain point - centre of the Moon, tan(e) = (r_t cos g - r_o) / (r_t sin g), evaluated in a cancellation-free form; curvature is contained in the formula. Each ray is covered by a lattice of points half a pixel apart; its first point is one pixel from the site and never farther than 20 m (first_point_m). The ground in front of that point is searched as well, down to about 2 cm from the site (parameter ground_at_the_site). Near the site every lattice point is evaluated on the finest data. Farther out the lattice is grouped into cells; a cell is skipped only if the block maximum of the terrain over the cell proves that nothing in it can reach the horizon already found, otherwise it is walked point by point on the finest data. Crossings of the ray with the lines through pixel centres (the creases of the bilinear surface) are evaluated as well, and the leading points are refined by nested sampling. All observer heights share the same terrain evaluations.",
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
        "core/tests/test_brute_force_lola.py::test_limiting_terrain_point_of_the_sun_against_brute_force: on LOLA terrain, 24 instants at one site, the limiting terrain point recomputed straight from the elevation data without a stored profile; horizon elevation on the named ray within 0.003 deg (tolerance -0.002 to +0.02 deg), limiting azimuth within 0.13 deg (tolerance 0.25 deg), hidden or visible the same at all 24.",
        "That check compares the code with the elevation model. It does not compare the elevation model with the Moon, and the lost time has not been compared with a published product.",
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
                "Time lost to obstacles closer than about 1 km (flagged near_field) is bounded by the 20 m pixel of the elevation model: at a 2 m observer height a shift of the site by one pixel changed the Sun-visible time of a 30-day window by up to 82 h at one site record. Such a number supports an order of magnitude, not its digits; docs/method/obstacles.md, section 4.",
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
        "core/tests/test_uncertainty.py::test_horizon_error_from_a_terrain_height_error: per-azimuth error against atan(error / distance)",
        "core/tests/test_near_field.py::test_height_error_follows_the_stated_model and ::test_slope_of_a_tilted_plane (0.1 deg): the height error per limiting point after a stated model; ::test_package_says_what_fed_the_band_of_every_event",
        "core/tests/test_brute_force_lola.py::test_extreme_points_of_the_de_gerlache_ellipse_against_brute_force: the best and the worst point of one surveyed ellipse on LOLA terrain recomputed straight from the elevation data; horizon within 0.013 deg (tolerance -0.002 to +0.02 deg), Sun-visible time 721 of 721 and 0 of 721 hourly samples against 720.0 h and 0.0 h (tolerance 2 h).",
        "The stated error and the stated ellipse are inputs. Whether they describe the real elevation model or the real landing accuracy has not been checked.",
    ]
    cards = {}
    model = stated.get("dem_height_error_model")
    if "horizon_error_deg" in stated or "dem_height_error_m" in stated or model:
        cards[pk.M_HORIZON_ERROR] = pk.method_card(
            "Band for a stated horizon error",
            "visible_certain: the times at which the body is visible even if the terrain horizon is higher than computed by the stated angle. visible_possible: the times at which it is visible if the horizon is lower by that angle. visible_uncertain: possible and not certain. For every rise and set, earliest and latest give the interval of the uncertain set that contains the event.",
            "The event finder is run on the horizon profile raised and lowered by the stated error: a common angle at every azimuth (horizon_error_deg), and/or atan(dem_height_error_m / distance of the limiting terrain) per azimuth, which is wide for near terrain and narrow for far terrain. Raising a horizon can only hide and lowering it can only reveal, so certain lies inside the nominal window and the nominal window inside possible.",
            local,
            "TDB",
            data,
            {**{key: stated[key] for key in ("horizon_error_deg", "dem_height_error_m") if key in stated}, **({"dem_height_error_model": model.get("id", "unnamed")} if model else {})},
            "analytic-test-passed",
            evidence,
            [
                "The same sign is assumed at every azimuth. Real errors differ from azimuth to azimuth; the band is the unfavourable case for one event and says little about how errors along the profile combine.",
                "For a height error only the limiting terrain point is moved. visible_possible is an outer bound: with lower terrain the horizon is at least the lowered limiting point. visible_certain is not a guarantee: if the terrain in front of the limiting point were higher by the same amount, it could set a horizon above the raised profile (for 1 m at three site records: in 9 to 30 % of the azimuths, by up to 0.4 to 0.7 deg). The band is the response to the stated error at the limiting point.",
                *(([f"Stated height-error model: {model.get('label', '')}. Source: {model.get('source', 'not stated')}"]) if model else []),
                "Where a product's own error map feeds the band, that map is the producers' model estimate, not a test against independent data. Every elevation product used here is built from LOLA returns: a finer product is independent of the gridding of a coarser one, not of LOLA, and errors common to all of them are not in the band.",
                "terrain_quality of an event names the horizon sample at the azimuth of the body at the event; for a limb condition the sample that actually limits the disc can be one sample away.",
                "The height error applies to the limiting terrain point as the elevation model has it. Terrain the model does not contain at all (relief smaller than its pixels) is outside any band.",
                "The stated numbers are inputs, not estimates of the elevation model's accuracy.",
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
                "A spread that comes from points whose horizon is set by terrain a few pixels away is a statement about the resolution of the 20 m elevation model, not about the site: at one site record a point 82 m from the centre had no Sun in 30 days at 2 m and the Sun throughout at 20 m; docs/method/uncertainty.md, section 4.",
            ],
        )
    return cards


def limiting_quality(terrain, horizon, height_index: int, model: dict) -> dict:
    """Stated height error of the terrain point that sets the horizon in every azimuth, with
    its source, the product it lies on and whether its pixel holds a laser return."""
    lat, lon = horizon.obstacle_lat_deg[height_index], horizon.obstacle_lon_deg[height_index]
    n = lat.size
    out = {"error_m": np.full(n, np.nan), "source": np.full(n, "", dtype=object), "constrained": np.full(n, -1, dtype=np.int64), "product_id": np.full(n, "", dtype=object)}
    known = np.isfinite(lat) & np.isfinite(lon)
    if known.any():
        q = terrain.quality_at(lon[known], lat[known])
        slope = terrain_slope_deg(terrain, lon[known], lat[known], np.where(np.isfinite(q["pixel_m"]), q["pixel_m"], terrain.finest_pixel_m))
        out["error_m"][known], out["source"][known] = height_error_for_points(model, q["product_id"], q["height_rms_error_m"], slope)
        out["constrained"][known], out["product_id"][known] = q["constrained"], q["product_id"]
    return out


def _uncertainty_inputs(csite, terrain, horizon, table_dir, timeline, thresholds, stated, hd, az_step, max_range, settings, workers: int = 1):
    """Bands for a stated horizon error and windows at the sample points of a stated ellipse.

    workers: processes that share the event searches (two per body and height for the
    band, one per body and sample point for the ellipse). The result is the same for any
    number of them."""
    grid = TimeGrid.from_contract(timeline.time)
    domain = (grid.start_et_s, grid.end_et_s)
    heights = horizon.observer_heights_m
    notes = []
    tasks = []  # (what the window is for, arguments of window_job)
    errors = None

    bands, applied, quality = None, None, None
    model = stated.get("dem_height_error_model") or ({"constant_m": float(stated["dem_height_error_m"])} if stated.get("dem_height_error_m") else None)
    if stated.get("horizon_error_deg") or model:
        bands = {}
        if model:
            quality = [limiting_quality(terrain, horizon, h, model) for h in range(len(heights))]
            horizon.obstacle_height_error_m = np.stack([q["error_m"] for q in quality])
            horizon.obstacle_constrained = np.stack([q["constrained"] for q in quality])
        errors = [
            horizon_error_profile(horizon.distance_m[h], stated.get("horizon_error_deg"), quality[h]["error_m"] if quality else None)
            for h in range(len(heights))
        ]
        applied = {"min": float(errors[hd].min()), "median": float(np.median(errors[hd])), "max": float(errors[hd].max())}
        here = (csite["lon_deg"], csite["lat_deg"], horizon.surface_height_m / 1000.0)
        for body in timeline.bodies:
            for h in range(len(heights)):
                for sign in (1.0, -1.0):  # the horizon raised, then lowered
                    tasks.append((("band", body, h, sign), (*here, str(table_dir), body, horizon.elevation_deg[h] + sign * errors[h], az_step, domain, thresholds[body])))

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
            for body in timeline.bodies:
                if k == 0:
                    sets[body].append(timeline.window(f"{body.lower()}_visible", hd))
                else:
                    sets[body].append(None)  # filled in below
                    tasks.append((("point", body, len(sets[body]) - 1, 0.0), (float(lon), float(lat), ground_height / 1000.0, str(table_dir), body, profile, az_step, domain, thresholds[body])))
        ellipse = {"spec": spec, "height_index": hd, "points": points, "surface_height_m": ground_heights, "sets": sets}

    # Every task is one event search over the whole range; they are independent of each other.
    if workers > 1 and len(tasks) > 1:
        from concurrent.futures import ProcessPoolExecutor

        with ProcessPoolExecutor(max_workers=min(int(workers), len(tasks))) as pool:
            found = list(pool.map(window_job, *zip(*(arguments for _, arguments in tasks))))
    else:
        found = [window_job(*arguments) for _, arguments in tasks]
    raised = {}
    for (kind, body, where, sign), intervals in zip((key for key, _ in tasks), found):
        result = IntervalSet(intervals, domain)
        if kind == "point":
            sets[body][where] = result
        elif sign > 0.0:
            raised[(body, where)] = result
        else:
            bands[(body, where)] = band_from_windows(timeline.window(f"{body.lower()}_visible", where), raised[(body, where)], result, float(errors[where].max()))
    return bands, ellipse, notes, applied, quality


RESOLUTION_CLASSES = "fine: pixel at the site up to 30 m; medium: up to 120 m; coarse: larger"


def resolution_class(pixel_m: float) -> str:
    return "fine" if pixel_m <= 30.0 else "medium" if pixel_m <= 120.0 else "coarse"


def terrain_source(terrain, csite: dict, horizon, height_index: int) -> tuple[dict | None, list[str]]:
    """Which elevation product served the site and the horizon, and what its pixel allows.

    Returns the block for the package and the warnings that go with it.
    """
    site_id, info = terrain.source_at(csite["lon_deg"], csite["lat_deg"])
    site_id = str(np.asarray(site_id).ravel()[0])
    if not site_id or horizon.obstacle_lat_deg is None:
        return None, []
    lat, lon = horizon.obstacle_lat_deg[height_index], horizon.obstacle_lon_deg[height_index]
    known = np.isfinite(lat) & np.isfinite(lon)
    ids, more = terrain.source_at(lon[known], lat[known])
    info = {**more, **info}
    products = []
    for pid in sorted(set(ids.ravel()) - {""}):
        products.append({"product_id": str(pid), "pixel_m": float(info[pid]["pixel_m"]), "projection": info[pid]["projection"], "azimuth_share": float(np.mean(ids == pid))})
    products.sort(key=lambda p: -p["azimuth_share"])
    pixel = float(info[site_id]["pixel_m"])
    block = {
        "at_site": {"product_id": site_id, "pixel_m": pixel, "projection": info[site_id]["projection"]},
        "resolution_class": resolution_class(pixel),
        "classes": RESOLUTION_CLASSES,
        "products": products,
    }
    notes = []
    if block["resolution_class"] != "fine":
        notes.append(
            f"terrain: the site is served by {site_id} with {pixel:.0f} m pixels (resolution class {block['resolution_class']}); "
            f"relief narrower than about {2.0 * pixel:.0f} m is not in the horizon, and nearby obstacles of that size cannot be shown"
        )
    return block, notes


def terrain_source_methods(dem_set_id: str) -> dict:
    return {
        pk.M_TERRAIN_SOURCE: pk.method_card(
            "Elevation product that served the site",
            "at_site: the product the terrain height at the site was read from, with its pixel size. resolution_class: fine (pixel up to 30 m), medium (up to 120 m) or coarse (larger). products: every product that set the horizon in at least one azimuth at the default observer height, with the share of the azimuths whose limiting terrain point was read from it.",
            "The data reader names the product for a place: a polar product where its square covers the place, the finest installed simple-cylindrical mosaic elsewhere. Asked at the site and at the limiting terrain point of every azimuth.",
            "none",
            "none",
            [dem_set_id],
            {"classes": RESOLUTION_CLASSES},
            "analytic-test-passed",
            [
                "core/tests/test_moon_terrain.py::test_a_site_outside_the_polar_products_gets_a_package_that_says_so",
                "core/tests/test_moon_terrain.py::test_south_polar_sites_are_served_exactly_as_before",
            ],
            [
                "The class describes the grid of the product, not its accuracy. Relief narrower than about two pixels is not in a horizon computed from it.",
                "For a simple-cylindrical product pixel_m is the north-south pixel; the east-west pixel is smaller by the cosine of the latitude.",
            ],
        )
    }


def terrain_patch_methods(dem_set_id: str) -> dict:
    """Method card of the terrain patches."""
    return {
        pk.M_TERRAIN_PATCH: pk.method_card(
            "Terrain patch for drawing",
            "up_m: the up coordinate, in the site's local East/North/Up frame and measured from the ground point of the site, of the surface point whose east and north coordinates are those of the grid node. The curvature of the sphere is in the values: on a smooth sphere they fall off as -(east^2 + north^2) / (2 r). NaN where the elevation data ends.",
            "For every node the surface point is found whose position in the site frame has the node's east and north coordinates: its distance from the centre is the reference radius plus the terrain height at its latitude and longitude, settled by iteration to 0.1 mm. The terrain is read by bilinear interpolation from the block-average level of the elevation product whose pixel is the coarsest not larger than the grid spacing (sources lists product, level and checksum).",
            "local East/North/Up at the site; up is the outward radial direction of the reference sphere; origin at the ground point of the site",
            "none",
            [dem_set_id],
            {},
            "analytic-test-passed",
            [
                "core/tests/test_terrain_patch.py::test_patch_of_a_smooth_sphere_is_the_spherical_cap (threshold 0.002 m)",
                "core/tests/test_terrain_patch.py::test_patch_nodes_lie_on_the_surface: every node turned back into latitude, longitude and height with frame vectors written out in the test (threshold 0.05 m)",
                "core/tests/test_terrain_patch.py::test_east_is_east_and_north_is_north: a hill at a known bearing and distance (threshold one grid spacing)",
                "core/tests/test_terrain_patch.py::test_near_patch_reproduces_the_elevation_data and ::test_coarser_patches_reproduce_their_overview_level: on LOLA terrain at three site records against the data reader, 0.0002 m at the nodes (threshold 0.05 m)",
                "core/tests/test_terrain_patch.py::test_horizon_drawn_from_the_patches_agrees_with_the_package_horizon: on LOLA terrain at three site records the horizon of the drawn surface is inside the tolerance (a height of 15 % of the grid spacing at the limiting terrain, plus 0.02 deg) at 99.9 to 100 % of the azimuths (required 95 %); in angle 0.03 to 0.04 deg in the median, 0.46 deg at most",
                "NOT MET: core/tests/test_terrain_patch.py::test_near_patch_between_its_nodes_stays_within_half_a_metre asked for 0.5 m at 95 % of random places between the nodes of the near patch; measured 0.83, 0.55 and 0.49 m at the three site records (docs/method/terrain_patch.md, section 3)",
            ],
            [
                "For drawing only. The horizon, the windows and the event times of the package are computed on the finest elevation data; a viewer must not derive visibility from this surface.",
                "A coarse patch shows ground averaged over its grid cells: ridge crests are lower and narrow gaps are filled. Measured at three site records, the horizon of the drawn surface differs from the package horizon by up to 0.46 deg (terrain within 500 m of the site) and by up to 0.22 deg for terrain beyond 500 m; where they differ, the package horizon is right.",
                "The grid is regular in the tangent plane of the site, not on the sphere: 32 km away a cell covers 0.02 % more ground than at the site. Overhangs cannot be represented.",
                "Terrain beyond the largest patch is not in the package as a surface; its silhouette is in the horizon profile with the distance of the limiting terrain.",
            ],
        )
    }


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


def find_direction_table(roots, start_utc: str, end_utc: str, bodies=("SUN", "EARTH")) -> Path | None:
    """A direction table under one of the package roots that can serve the window, or None.

    It must come from the kernel set installed here and from this science version, have
    the step a new table would have, not be synthetic, reach one record beyond the window
    on both sides (as a table written for the window does) and pass the contract
    validator. If the kernels for the orientation of the Earth are installed, a table
    without that orientation is passed over. Among several, the shortest is taken.
    """
    import json

    from .contract import ContractError, validate_package
    from .contract.io import CONTRACT_VERSION
    from .ephem import directions as ephem_directions
    from .ephem import kernels
    from .ephem import table as ephem_table
    from .packaging import SCIENCE_VERSION

    kernels.load()
    start, end = float(ephem_directions.utc_to_et(start_utc)), float(ephem_directions.utc_to_et(end_utc))
    kernel_set, earth_wanted = kernels.kernel_set_id(), kernels.stations_available()
    major = CONTRACT_VERSION.split(".")[0]
    candidates = []
    for root in roots:
        for manifest_path in sorted(Path(root).glob("direction_table/*/manifest.json")):
            try:
                m = json.loads(manifest_path.read_text(encoding="utf-8"))
                grid, inputs = m["time"], m["inputs"]
                step = float(grid["step_s"])
                first = float(grid["start_et_s"])
                last = first + step * (int(grid["count"]) - 1)
                usable = (
                    m["kind"] == "direction_table"
                    and not m["synthetic"]
                    and m["status"] == "ok"
                    and str(m["contract"]["version"]).split(".")[0] == major
                    and inputs["kernel_set_id"] == kernel_set
                    and inputs["science_version"] == SCIENCE_VERSION
                    and step == ephem_table.DEFAULT_STEP_S
                    and set(bodies) <= set(m["bodies"])
                    and first + step <= start + 1e-6
                    and last - step >= end - 1e-6
                    and ("earth_view" in m or not earth_wanted)
                )
            except (OSError, ValueError, KeyError, TypeError):
                continue
            if usable:
                candidates.append((int(grid["count"]), manifest_path.parent))
    for _, path in sorted(candidates, key=lambda item: (item[0], item[1].as_posix())):
        try:
            validate_package(path)
        except ContractError:
            continue
        return path
    return None


def _adopt_table(table: Path, out_root: Path) -> Path:
    """The table inside the package root: as it is if it lies there, otherwise a copy."""
    import shutil

    home = Path(out_root) / "direction_table" / table.name
    if home.resolve() == table.resolve() or (home / "manifest.json").exists():
        return home
    home.parent.mkdir(parents=True, exist_ok=True)
    tmp = home.parent / f".tmp-{table.name}-copy"
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(table, tmp)
    tmp.rename(home)
    return home


def _site_job(scenario: dict, index: int, out_root: str, table_dir: str | None, terrain_factory, synthetic: bool, settings, inner: int = 1) -> str:
    """One site of a scenario in a worker process: its own terrain, the shared direction table."""
    one = {**scenario, "sites": [scenario["sites"][index]]}
    paths = run_scenario(one, out_root, terrain_factory(), synthetic, settings, jobs=inner, _table_dir=table_dir or "", _finish=False)
    return str(paths[-1])


def run_scenario(
    scenario: dict,
    out_root: Path | str,
    terrain: Terrain | None = None,
    terrain_is_synthetic: bool = False,
    settings: HorizonSettings = HorizonSettings(),
    *,
    jobs: int = 1,
    terrain_factory=None,
    direction_table: Path | str | None = None,
    progress=None,
    _table_dir: str | None = None,
    _finish: bool = True,
) -> list[Path]:
    """Compute every site of a scenario and write the packages. Returns their directories.

    direction_table: a direction-table package that covers the time window (see
    find_direction_table). It is used instead of computing one, and copied into the
    package root if it lies elsewhere, so that the root stays complete.

    progress: called with the name of a stage when it begins ("horizon", "timeline",
    "uncertainty", "package"), for a caller that shows what is going on. Sites computed
    in other processes do not report.

    jobs: processes the run may use. Sites are computed side by side, each in its own
    process; that needs terrain_factory, a picklable callable without arguments that
    opens the terrain in a worker. What is left over is shared inside each site among the
    event searches of the uncertainty band and the landing ellipse. The packages are the
    same whatever the number of jobs.
    """
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
    patch_specs = canonical_patches(scenario.get("terrain_patches", DEFAULT_PATCHES))
    written: list[Path] = []
    extra_warnings: list[str] = []

    wanted = scenario["data"]["dem_set_id"]
    whole_terrain = terrain  # a terrain for any place hands each site the products that serve it

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
            if _table_dir:  # a worker: the table was written by the process that started it
                table_dir = Path(_table_dir)
            elif direction_table is not None:
                table_dir = _adopt_table(Path(direction_table), out_root)
                written.append(table_dir)
            else:
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

    sites = list(scenario["sites"])
    if jobs > 1 and terrain_factory is not None and len(sites) > 1 and not (window is not None and table_dir is None):
        from concurrent.futures import ProcessPoolExecutor

        at_once = min(int(jobs), len(sites))
        with ProcessPoolExecutor(max_workers=at_once) as pool:
            futures = [
                pool.submit(_site_job, scenario, k, str(out_root), str(table_dir) if table_dir else None, terrain_factory, synthetic, settings, int(jobs) // at_once)
                for k in range(len(sites))
            ]
            written.extend(Path(future.result()) for future in futures)
        sites = []

    tell = progress or (lambda stage: None)
    for site in sites:
        csite = canonical_site(site)
        terrain = whole_terrain.for_site(csite["lat_deg"], csite["lon_deg"], max_range) if hasattr(whole_terrain, "for_site") else whole_terrain
        tell("horizon")
        t0 = _time.perf_counter()
        horizon = compute_horizon(terrain, csite["lat_deg"], csite["lon_deg"], heights, az_step, max_range, settings)
        t1 = _time.perf_counter()
        methods = horizon_methods(terrain, az_step, max_range, settings)
        timeline = None
        status = "ok"
        warnings = list(extra_warnings)
        actual = terrain.describe()["dem_set_id"]
        if wanted not in ("any", actual):
            warnings.append(f"data: the scenario asks for DEM set '{wanted}', the run used '{actual}'")
        default_index = int(np.argmin(np.abs(np.asarray(heights) - scenario.get("default_height_m", DEFAULT_HEIGHT_M))))
        horizon.terrain_source, notes = terrain_source(terrain, csite, horizon, default_index)
        warnings.extend(notes)
        warnings.extend(getattr(terrain, "site_notes", []))
        if horizon.terrain_source is not None:
            methods.update(terrain_source_methods(actual))
        if window is not None and table_dir is None:
            status = "partial"
        if table_dir is not None:
            from .ephem import directions as ephem_directions

            tell("timeline")
            timeline = timeline_mod.compute_timeline(site, horizon, table_dir, window, bodies, thresholds)
            methods.update(timeline_mod.timeline_methods(table_dir, horizon_is_terrain=True))
            smooth = _smooth_sphere_windows(csite, horizon, table_dir, timeline, thresholds)
            add_blocking_to_timeline(timeline, horizon, smooth, ephem_directions.et_to_utc_z)
            methods.update(
                blocking_methods(terrain.describe()["dem_set_id"], az_step, float(window["step_s"]), timeline.direction_table_id)
            )
            stated = scenario.get("uncertainty") or {}
            if stated:
                tell("uncertainty")
                default_height = scenario.get("default_height_m", DEFAULT_HEIGHT_M)
                hd = int(np.argmin(np.abs(np.asarray(heights) - default_height)))
                bands, ellipse, notes, applied, quality = _uncertainty_inputs(
                    csite, terrain, horizon, table_dir, timeline, thresholds, stated, hd, az_step, max_range, settings,
                    workers=max(1, int(jobs)),
                )
                warnings.extend(notes)
                add_uncertainty_to_timeline(timeline, stated, bands, ellipse, ephem_directions.et_to_utc_z, applied, quality, az_step, hd)
                methods.update(uncertainty_methods(terrain.describe()["dem_set_id"], timeline.direction_table_id, stated))
            landing = site.get("landing_utc")
            warnings.extend(
                add_calendar_to_timeline(
                    timeline, read_package(table_dir), len(heights), scenario.get("requirements"),
                    float(ephem_directions.utc_to_et(landing)) if landing else None, ephem_directions.et_to_utc_z,
                )
            )
            methods.update(calendar_methods(terrain.describe()["dem_set_id"], timeline.direction_table_id))
            add_height_trade_to_timeline(timeline, heights)
            methods.update(trade_methods(terrain.describe()["dem_set_id"], timeline.direction_table_id))
        t2 = _time.perf_counter()
        tell("package")
        patches = None
        if patch_specs:
            patches = compute_patches(terrain, csite["lat_deg"], csite["lon_deg"], horizon.surface_height_m, patch_specs)
            methods.update(terrain_patch_methods(terrain.describe()["dem_set_id"]))
            warnings.extend(patch_warnings(patches))
        t3 = _time.perf_counter()
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
                timings_s={"horizon": t1 - t0, "timeline": t2 - t1, "terrain_patches": t3 - t2},
                status=status,
                warnings=warnings,
                terrain_patches=patches,
            )
        )
    if not _finish:
        return written
    dem_sets = sorted({read_package(p).manifest["inputs"]["dem"]["dem_set_id"] for p in written if p.name.startswith("site-")})
    pair_methods = trade_methods(" and ".join(dem_sets), "the direction table of the site packages")
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
