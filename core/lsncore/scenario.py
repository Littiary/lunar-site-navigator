"""The scenario file: the single input of the tool (contract decision 5)."""

from __future__ import annotations

import json
from pathlib import Path

from .contract import contract_header, validate_document
from .geometry import canonical_lon

# Defaults chosen by the team; a scenario may override every one of them.
DEFAULT_OBSERVER_HEIGHTS_M = [0.0, 1.0, 2.0, 5.0, 10.0, 20.0]
DEFAULT_HEIGHT_M = 2.0
DEFAULT_AZIMUTH_STEP_DEG = 0.25
DEFAULT_MAX_RANGE_M = 300_000.0


def canonical_site(site: dict) -> dict:
    """Site in canonical form: longitude wrapped to (-180, 180], angles rounded to 1e-7 deg."""
    return {
        "site_id": site["site_id"],
        "name": site["name"],
        "lat_deg": round(float(site["lat_deg"]), 7),
        "lon_deg": round(canonical_lon(site["lon_deg"]), 7),
    }


def canonical_heights(heights) -> list[float]:
    """Observer heights rounded to the millimetre, sorted, without duplicates."""
    return sorted({round(float(h), 3) for h in heights})


def load_scenario(path: Path | str) -> dict:
    """Read a scenario file and check it against the contract."""
    scenario = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_document(scenario)
    ids = [s["site_id"] for s in scenario["sites"]]
    if len(ids) != len(set(ids)):
        raise ValueError("scenario: site_id values must be unique")
    return scenario


def single_site_scenario(
    site_id: str,
    name: str,
    lat_deg: float,
    lon_deg: float,
    *,
    dem_set_id: str,
    synthetic: bool,
    heights_m=None,
    azimuth_step_deg: float = DEFAULT_AZIMUTH_STEP_DEG,
    max_range_m: float = DEFAULT_MAX_RANGE_M,
) -> dict:
    """Scenario for one site with no time window (horizon only)."""
    scenario = {
        "contract": contract_header(),
        "kind": "scenario",
        "scenario_id": site_id,
        "title": name,
        "synthetic": synthetic,
        "sites": [{"site_id": site_id, "name": name, "lat_deg": lat_deg, "lon_deg": lon_deg}],
        "observer_heights_m": list(heights_m or DEFAULT_OBSERVER_HEIGHTS_M),
        "default_height_m": DEFAULT_HEIGHT_M,
        "horizon": {"azimuth_step_deg": azimuth_step_deg, "max_range_m": max_range_m},
        "time_window": None,
        "bodies": ["SUN", "EARTH"],
        "data": {"dem_set_id": dem_set_id, "kernel_set_id": None},
    }
    validate_document(scenario)
    return scenario
