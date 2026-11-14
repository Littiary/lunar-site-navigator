"""The direction-table package: Sun and Earth positions over time, independent of any site.

Writes and reads the ``direction_table`` package kind of the contract
(docs/contract/SPEC.md, section 6) with real SPICE values.
"""

from __future__ import annotations

import json
import time as _time
from pathlib import Path

import numpy as np
import spiceypy as spice

from .. import packaging as pk
from ..contract import read_package
from ..timeline import TimeGrid
from . import directions as d
from . import kernels

INTERPOLATION_NAME = "lagrange-4-point"
DEFAULT_STEP_S = 3600.0
_ERROR_SAMPLES = 4000
_ARCSEC = 3600.0


def _angle_arcsec(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    cross = np.linalg.norm(np.cross(a, b), axis=1)
    return np.degrees(np.arctan2(cross, np.sum(a * b, axis=1))) * _ARCSEC


def interpolation_error(table: d.DirectionTable, query_et: np.ndarray) -> dict:
    """Largest difference between the interpolated table and direct SPICE at the given epochs."""
    interpolated = d.interpolate_table(table, query_et)
    direct = d.direction_table(query_et)
    km, arcsec = 0.0, 0.0
    for body in d.BODIES:
        a, b = interpolated.vectors(body), direct.vectors(body)
        km = max(km, float(np.linalg.norm(a - b, axis=1).max()))
        arcsec = max(arcsec, float(_angle_arcsec(a, b).max()))
    return {"max_error_km": km, "max_error_arcsec": arcsec}


def _horizons_evidence() -> list[str]:
    """Evidence lines from the stored Horizons comparison, if the report is present."""
    report = kernels.REPO_ROOT / "validation" / "horizons" / "results" / "validation_table.json"
    lines = ["Test validation/tests/test_horizons.py (comparison with JPL Horizons, thresholds fixed beforehand in validation/horizons/thresholds.json)."]
    if report.exists():
        cases = [row for row in json.loads(report.read_text(encoding="utf-8"))["cases"] if "exact" in row]
        if cases:
            lines.append(
                f"{len(cases)} Horizons cases, {sum(row['rows'] for row in cases)} rows: largest direction difference "
                f"{max(row['table']['direction_arcsec_max'] for row in cases):.3f} arcsec through this table, "
                f"{max(row['exact']['direction_arcsec_max'] for row in cases):.3f} arcsec with the observer at the site "
                "(threshold 1 arcsec). Report: validation/horizons/results/validation_table.md."
            )
    return lines


def dirtab_methods(step_s: float, error: dict) -> dict:
    """Method cards of the direction-table package."""
    manifest = kernels.read_manifest()["kernels"]
    data = [f"{entry['name']} (sha256 {entry['sha256'][:12]})" for entry in manifest]
    frame = f"{d.FRAME}: lunar mean-Earth/polar-axis frame, DE440 orientation aligned with the DE421 mean-Earth frame (the frame of the LOLA elevation products)"
    return {
        pk.M_DIRTAB_POSITIONS: pk.method_card(
            title="Apparent positions of the Sun and the Earth",
            definition="Position of the centre of each body relative to the centre of the Moon, in the Moon body-fixed frame, as seen at the record time: corrected for one-way light time and stellar aberration (reception).",
            algorithm=f"SPICE spkpos(target, et, '{d.FRAME}', '{d.ABCORR}', 'MOON') at every record. A site direction is obtained by subtracting the site position vector and projecting on East, North, Up.",
            frame=frame,
            time_scale="TDB",
            data=data,
            parameters={"aberration_correction": d.ABCORR, "observer": "centre of the Moon", "step_s": float(step_s), "spice_toolkit": spice.tkvrsn("TOOLKIT")},
            status="externally-validated",
            evidence=_horizons_evidence(),
            limits=[
                "Light time and stellar aberration are evaluated for the centre of the Moon, not for the site: up to 0.1 arcsec for the Earth, 0.005 arcsec for the Sun.",
                "No terrain and no light bending; directions only.",
                "UTC labels after the last announced leap second assume that no further leap second is introduced.",
            ],
        ),
        pk.M_DIRTAB_RADII: pk.method_card(
            title="Body radii used for the discs",
            definition="Radius that defines the apparent disc of each body: angular radius = asin(radius / distance).",
            algorithm="Read from the planetary constants kernel: Sun radius; Earth equatorial radius (the largest half-width of its slightly flattened disc).",
            frame="none",
            time_scale="none",
            data=["pck00011.tpc"],
            parameters={"earth_polar_radius_km": float(spice.bodvrd("EARTH", "RADII", 3)[1][2])},
            status="externally-validated",
            evidence=["Angular diameters agree with JPL Horizons to 0.001 arcsec (validation/horizons/results/validation_table.md)."],
            limits=["The flattening of the Earth's disc (0.3 %) is not modelled.", "No limb darkening, no atmosphere of the Earth."],
        ),
        pk.M_DIRTAB_INTERP: pk.method_card(
            title="Interpolation error of the table",
            definition="Largest difference between positions interpolated from the table and positions computed directly, in km and as an angle seen from the centre of the Moon.",
            algorithm=(
                "Recommended interpolation 'lagrange-4-point': for a time between records i and i+1, with u = (t - t_i) / step, each vector component is "
                "w(-1) p[i-1] + w(0) p[i] + w(1) p[i+1] + w(2) p[i+2], where w(-1) = -u(u-1)(u-2)/6, w(0) = (u+1)(u-1)(u-2)/2, "
                "w(1) = -(u+1)u(u-2)/2, w(2) = (u+1)u(u-1)/6; at the two ends of the table the nearest complete stencil is used. "
                f"The error is measured at {_ERROR_SAMPLES} pseudo-random epochs inside the table against direct SPICE."
            ),
            frame=frame,
            time_scale="TDB",
            data=data,
            parameters={"samples": _ERROR_SAMPLES, "seed": 20261114, "linear_max_error_arcsec": error.get("linear_max_error_arcsec")},
            status="analytic-test-passed",
            evidence=["Tests core/tests/events/test_events.py::test_table_interpolation_error_is_below_threshold and core/tests/events/test_site_timeline.py::test_stated_interpolation_error_is_measured_and_small."],
            limits=["Valid inside the table only. Interpolate vectors, never angles."],
        ),
    }


def _linear_error_arcsec(table: d.DirectionTable, query: np.ndarray) -> float:
    direct = d.direction_table(query)
    worst = 0.0
    for body in d.BODIES:
        vectors = table.vectors(body)
        linear = np.stack([np.interp(query, table.et, vectors[:, k]) for k in range(3)], axis=-1)
        worst = max(worst, float(_angle_arcsec(linear, direct.vectors(body)).max()))
    return worst


def write_direction_table(
    out_root: Path | str,
    start_utc: str,
    end_utc: str,
    step_s: float = DEFAULT_STEP_S,
    scenario_id: str | None = None,
) -> Path:
    """Compute the table for a UTC window and write it as a package. Returns the package directory.

    The grid starts one record before ``start_utc`` and ends at least one record after
    ``end_utc``, so that the 4-point stencil is centred everywhere inside the window.
    """
    kernels.load()
    t0 = _time.perf_counter()
    start = d.utc_to_et(start_utc) - step_s
    count = int(np.ceil((d.utc_to_et(end_utc) - start) / step_s)) + 2
    grid = TimeGrid(start, float(step_s), count)
    table = d.direction_table(grid.times())
    positions = np.stack([table.vectors(body) for body in d.BODIES], axis=1)

    rng = np.random.default_rng(20261114)
    query = np.sort(rng.uniform(table.et[0], table.et[-1], _ERROR_SAMPLES))
    error = interpolation_error(table, query)
    error["linear_max_error_arcsec"] = _linear_error_arcsec(table, query)

    manifest = kernels.read_manifest()["kernels"]
    kernel_list = [
        {"name": entry["name"], "bytes": int(entry["bytes"]), "sha256": entry["sha256"], "source_url": entry["url"], "load_order": order}
        for order, entry in enumerate(manifest)
    ]
    return pk.build_direction_table_package(
        out_root,
        time=grid.to_contract(d.et_to_utc_z(grid.start_et_s), d.et_to_utc_z(grid.end_et_s), d.leap_seconds_between(grid.start_et_s, grid.end_et_s)),
        frame_name=d.FRAME,
        aberration_correction=d.ABCORR,
        bodies=list(d.BODIES),
        positions_km=positions,
        body_radii_km=dict(table.radii_km),
        interpolation=INTERPOLATION_NAME,
        interpolation_max_error_km=error["max_error_km"],
        interpolation_max_error_arcsec=error["max_error_arcsec"],
        kernel_set_id=kernels.kernel_set_id(),
        kernels=kernel_list,
        methods=dirtab_methods(step_s, error),
        synthetic=False,
        scenario_id=scenario_id,
        timings_s={"direction_table": _time.perf_counter() - t0},
    )


def load_table(table_dir: Path | str) -> d.DirectionTable:
    """Read a direction-table package back into a ``DirectionTable``."""
    package = read_package(table_dir)
    manifest = package.manifest
    if manifest["kind"] != "direction_table":
        raise ValueError("not a direction-table package")
    positions = package.array(manifest["positions_km"])
    bodies = manifest["bodies"]
    return d.DirectionTable(
        et=TimeGrid.from_contract(manifest["time"]).times(),
        sun_km=np.ascontiguousarray(positions[:, bodies.index("SUN")]),
        earth_km=np.ascontiguousarray(positions[:, bodies.index("EARTH")]),
        frame=manifest["frame"],
        abcorr=manifest["aberration_correction"],
        observer=manifest["center"],
        kernel_set_id=manifest["inputs"]["kernel_set_id"],
        radii_km={body: manifest["body_radii_km"][body]["value"] for body in bodies},
    )
