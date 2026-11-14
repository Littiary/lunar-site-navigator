"""Turning results into packages. No science here: only layout, units and method cards."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from . import SCIENCE_VERSION
from .contract import PackageWriter
from .geometry import site_frame
from .results import HorizonResult, TimelineResult
from .scenario import canonical_heights, canonical_site

# Method card ids used by the package builder. The computing modules supply the cards.
M_SITE_GEOMETRY = "site.geometry"
M_SITE_HEIGHT = "site.surface_height"
M_HORIZON = "horizon.elevation"
M_OBSTACLE = "horizon.obstacle"
M_DIRECTION = "timeline.direction"
M_MARGIN = "timeline.margin"
M_FRACTION = "timeline.visible_fraction"
M_EVENTS = "timeline.events"
M_WINDOWS = "timeline.windows"
M_METRICS = "timeline.metrics"
M_DIRTAB_POSITIONS = "dirtab.positions"
M_DIRTAB_RADII = "dirtab.body_radii"
M_DIRTAB_INTERP = "dirtab.interpolation"


def method_card(
    title: str,
    definition: str,
    algorithm: str,
    frame: str,
    time_scale: str,
    data: list[str],
    parameters: dict,
    status: str,
    evidence: list[str],
    limits: list[str],
) -> dict:
    return {
        "title": title,
        "definition": definition,
        "algorithm": algorithm,
        "frame": frame,
        "time_scale": time_scale,
        "data": data,
        "parameters": parameters,
        "validation": {"status": status, "evidence": evidence},
        "limits": limits,
    }


def _quantity(value, unit: str, method: str) -> dict:
    return {"value": None if value is None else float(value), "unit": unit, "method": method}


def _used_methods(node, found: set[str]) -> set[str]:
    if isinstance(node, dict):
        if isinstance(node.get("method"), str):
            found.add(node["method"])
        for value in node.values():
            _used_methods(value, found)
    elif isinstance(node, list):
        for value in node:
            _used_methods(value, found)
    return found


def site_request(site: dict, horizon: HorizonResult, timeline_request: dict | None) -> dict:
    """Canonical request of a site package (the part of the input that defines its id)."""
    return {
        "site": canonical_site(site),
        "observer_heights_m": canonical_heights(horizon.observer_heights_m),
        "horizon": {
            "azimuth_step_deg": float(horizon.azimuth_step_deg),
            "max_range_m": float(horizon.max_range_m),
        },
        "timeline": timeline_request,
    }


def build_site_package(
    out_root: Path | str,
    *,
    site: dict,
    frame_name: str,
    dem_input: dict,
    horizon: HorizonResult,
    methods: dict,
    synthetic: bool,
    synthetic_notice: str | None = None,
    timeline: TimelineResult | None = None,
    timeline_request: dict | None = None,
    default_height_m: float | None = None,
    scenario_id: str | None = None,
    timings_s: dict | None = None,
    status: str = "ok",
    warnings: list[str] | None = None,
) -> Path:
    """Write one site package and return its directory."""
    request = site_request(site, horizon, timeline_request)
    csite = request["site"]
    heights = request["observer_heights_m"]
    if heights != [float(h) for h in horizon.observer_heights_m]:
        raise ValueError("observer heights must be sorted, unique and rounded to the millimetre")
    n_az = int(round(360.0 / horizon.azimuth_step_deg))
    shape = (len(heights), n_az)
    if horizon.elevation_deg.shape != shape or horizon.distance_m.shape != shape:
        raise ValueError(f"horizon arrays must have shape {shape}")

    inputs = {
        "science_version": SCIENCE_VERSION,
        "dem": dem_input,
        "direction_table": None,
    }
    if timeline is not None:
        inputs["direction_table"] = {
            "package_id": timeline.direction_table_id,
            "content_sha256": timeline.direction_table_sha256,
        }

    writer = PackageWriter("site")

    east, north, up = site_frame(csite["lat_deg"], csite["lon_deg"])
    radius_m = horizon.reference_radius_m + horizon.surface_height_m
    site_block = {
        "site_id": csite["site_id"],
        "name": csite["name"],
        "body": "MOON",
        "lat_deg": csite["lat_deg"],
        "lon_deg": csite["lon_deg"],
        "frame": frame_name,
        "reference_radius_m": _quantity(horizon.reference_radius_m, "m", M_SITE_GEOMETRY),
        "surface_height_m": _quantity(horizon.surface_height_m, "m", M_SITE_HEIGHT),
        "radius_m": _quantity(radius_m, "m", M_SITE_GEOMETRY),
        "position_km": [float(x) for x in up * (radius_m / 1000.0)],
        "enu": {
            "east": [float(x) for x in east],
            "north": [float(x) for x in north],
            "up": [float(x) for x in up],
        },
    }
    if horizon.dem_pixel is not None:
        site_block["dem_pixel"] = horizon.dem_pixel

    default_index = 0
    if default_height_m is not None:
        default_index = int(np.argmin(np.abs(np.asarray(heights) - default_height_m)))

    horizon_block = {
        "azimuth": {"start_deg": 0, "step_deg": float(horizon.azimuth_step_deg), "count": n_az},
        "observer_heights_m": heights,
        "default_height_index": default_index,
        "max_range_m": _quantity(horizon.max_range_m, "m", M_HORIZON),
        "elevation_deg": writer.array("horizon_elevation_deg", horizon.elevation_deg, "<f4", "deg", M_HORIZON),
        "distance_m": writer.array("horizon_distance_m", horizon.distance_m, "<f4", "m", M_OBSTACLE),
    }
    optional = (
        ("obstacle_height_m", horizon.obstacle_height_m, "<f4", "m"),
        ("obstacle_lat_deg", horizon.obstacle_lat_deg, "<f8", "deg"),
        ("obstacle_lon_deg", horizon.obstacle_lon_deg, "<f8", "deg"),
    )
    for name, values, dtype, unit in optional:
        if values is not None:
            horizon_block[name] = writer.array(f"horizon_{name}", values, dtype, unit, M_OBSTACLE)
    if horizon.error_bounds:
        horizon_block["error_bounds"] = {
            name: _quantity(value, unit, method)
            for name, (value, unit, method) in horizon.error_bounds.items()
        }
    horizon_block["flags"] = {
        "coverage_complete": bool(horizon.coverage_complete),
        "truncated_at_data_edge": bool(horizon.truncated_at_data_edge),
        "nodata_fraction": float(horizon.nodata_fraction),
    }

    sections = {"site": site_block, "horizon": horizon_block}

    if timeline is not None:
        series = {}
        for body in timeline.bodies:
            s = timeline.series[body]
            tag = body.lower()
            block = {
                "azimuth_deg": writer.array(f"series_{tag}_azimuth_deg", s.azimuth_deg, "<f4", "deg", M_DIRECTION),
                "elevation_deg": writer.array(f"series_{tag}_elevation_deg", s.elevation_deg, "<f4", "deg", M_DIRECTION),
            }
            if s.angular_radius_deg is not None:
                block["angular_radius_deg"] = writer.array(
                    f"series_{tag}_angular_radius_deg", s.angular_radius_deg, "<f4", "deg", M_DIRECTION
                )
            block["margin_deg"] = writer.array(f"series_{tag}_margin_deg", s.margin_deg, "<f4", "deg", M_MARGIN)
            block["visible_fraction"] = writer.array(
                f"series_{tag}_visible_fraction", s.visible_fraction, "<f4", "1", M_FRACTION
            )
            series[body] = block
        sections["timeline"] = {
            "direction_table_id": timeline.direction_table_id,
            "time": timeline.time,
            "bodies": list(timeline.bodies),
            "series": series,
            "events": timeline.events,
            "windows": timeline.windows,
            "metrics": timeline.metrics,
        }

    used = _used_methods(sections, set())
    missing = used - methods.keys()
    if missing:
        raise ValueError(f"method cards missing for: {sorted(missing)}")

    return writer.write(
        Path(out_root),
        csite["site_id"],
        status=status,
        synthetic=synthetic,
        synthetic_notice=synthetic_notice,
        warnings=(warnings or []) + list(horizon.warnings),
        request=request,
        inputs=inputs,
        methods={k: methods[k] for k in sorted(used)},
        sections=sections,
        scenario_id=scenario_id,
        timings_s=timings_s,
    )


def build_direction_table_package(
    out_root: Path | str,
    *,
    time: dict,
    frame_name: str,
    aberration_correction: str,
    bodies: list[str],
    positions_km: np.ndarray,
    body_radii_km: dict[str, float],
    interpolation: str,
    interpolation_max_error_km: float | None,
    interpolation_max_error_arcsec: float | None,
    kernel_set_id: str,
    kernels: list[dict],
    methods: dict,
    synthetic: bool,
    synthetic_notice: str | None = None,
    scenario_id: str | None = None,
    timings_s: dict | None = None,
    warnings: list[str] | None = None,
) -> Path:
    """Write one direction-table package (site independent) and return its directory."""
    positions_km = np.asarray(positions_km, dtype=np.float64)
    if positions_km.shape != (time["count"], len(bodies), 3):
        raise ValueError("positions_km must have shape [time.count, len(bodies), 3]")
    request = {
        "start_et_s": float(time["start_et_s"]),
        "step_s": float(time["step_s"]),
        "count": int(time["count"]),
        "bodies": list(bodies),
        "frame": frame_name,
        "center": "MOON",
        "aberration_correction": aberration_correction,
    }
    inputs = {
        "science_version": SCIENCE_VERSION,
        "kernel_set_id": kernel_set_id,
        "kernels": kernels,
    }
    writer = PackageWriter("direction_table")
    sections = {
        "frame": frame_name,
        "center": "MOON",
        "aberration_correction": aberration_correction,
        "bodies": list(bodies),
        "time": time,
        "positions_km": writer.array("positions_km", positions_km, "<f8", "km", M_DIRTAB_POSITIONS),
        "body_radii_km": {b: _quantity(body_radii_km[b], "km", M_DIRTAB_RADII) for b in bodies},
        "interpolation": {
            "recommended": interpolation,
            "max_error_km": _quantity(interpolation_max_error_km, "km", M_DIRTAB_INTERP),
            "max_error_arcsec": _quantity(interpolation_max_error_arcsec, "arcsec", M_DIRTAB_INTERP),
        },
    }
    used = _used_methods(sections, set())
    missing = used - methods.keys()
    if missing:
        raise ValueError(f"method cards missing for: {sorted(missing)}")
    return writer.write(
        Path(out_root),
        None,
        status="ok",
        synthetic=synthetic,
        synthetic_notice=synthetic_notice,
        warnings=warnings or [],
        request=request,
        inputs=inputs,
        methods={k: methods[k] for k in sorted(used)},
        sections=sections,
        scenario_id=scenario_id,
        timings_s=timings_s,
    )
