"""The scenario file: the single input of the tool (contract decision 5)."""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

from .contract import contract_dir, contract_header, validate_document
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


# Descriptive labels of a site, for the site list of a viewer. They are passed through
# unchanged; no number depends on them and they are not part of the canonical request.
SITE_LABELS = ("programme", "category")


def site_labels(site: dict) -> dict:
    """The descriptive labels a site states, as they are."""
    return {label: site[label] for label in SITE_LABELS if label in site}


def slug(text: str) -> str:
    """Lower-case identifier with hyphens, as the contract wants a site id."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:64] or "site"


_UTC = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?)?Z?$")


def parse_utc(text: str) -> _dt.datetime:
    """A UTC date (YYYY-MM-DD) or date and time (YYYY-MM-DDTHH:MM[:SS[.mmm]], with or
    without the final Z). Other time zones are not read."""
    match = _UTC.match(str(text).strip())
    if not match:
        raise ValueError(f"'{text}' is not a UTC date (YYYY-MM-DD) or date and time (YYYY-MM-DDTHH:MM[:SS]Z)")
    year, month, day, hour, minute, second, fraction = match.groups()
    return _dt.datetime(
        int(year), int(month), int(day), int(hour or 0), int(minute or 0), int(second or 0),
        int((fraction or "0").ljust(3, "0")) * 1000, tzinfo=_dt.timezone.utc,
    )


def format_utc(moment: _dt.datetime) -> str:
    """UTC as the contract writes it, to the millisecond."""
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


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


def custom_site_scenario(
    lat_deg: float,
    lon_deg: float,
    start,
    *,
    days: float = 30.0,
    step_s: float = 3600.0,
    name: str | None = None,
    site_id: str | None = None,
    landing_utc: str | None = None,
    requirement_ids=None,
    band: bool = True,
    synthetic: bool = False,
    heights_m=None,
    azimuth_step_deg: float = DEFAULT_AZIMUTH_STEP_DEG,
    max_range_m: float = DEFAULT_MAX_RANGE_M,
) -> dict:
    """Scenario for one site given by coordinates and a start date: everything a viewer shows.

    The window runs for ``days`` from ``start`` (UTC). It states the example requirements
    of the contract (all of them, or those named in ``requirement_ids``), so that the
    package holds landing windows and the slip tolerance, and, with ``band``, the default
    height-error model, so that it holds the uncertainty band. No landing ellipse.
    """
    lat_deg, lon_deg, days = float(lat_deg), float(lon_deg), float(days)
    if not -90.0 <= lat_deg <= 90.0:
        raise ValueError(f"latitude {lat_deg} is outside -90 to 90 degrees")
    if not -180.0 <= lon_deg <= 360.0:
        raise ValueError(f"east longitude {lon_deg} is outside -180 to 360 degrees")
    if not days > 0.0:
        raise ValueError(f"the length of the window must be positive, not {days} days")
    try:
        begin = parse_utc(start)
    except ValueError as err:
        raise ValueError(f"start: {err}") from err
    if name is None:
        # The default id follows the canonical coordinates (1e-7 deg, a few millimetres), so that
        # two places the package tells apart never share an id; the name is good to 0.3 m.
        north, east = round(lat_deg, 7), round(canonical_lon(lon_deg), 7)
        name = f"Custom site {abs(north):.5f} {'S' if north < 0 else 'N'}, {abs(east):.5f} {'W' if east < 0 else 'E'}"
        default_id = f"custom-{abs(north):.7f}{'s' if north < 0 else 'n'}-{abs(east):.7f}{'w' if east < 0 else 'e'}"
    else:
        default_id = name
    site = {"site_id": site_id or slug(default_id), "name": name, "lat_deg": lat_deg, "lon_deg": lon_deg}
    if landing_utc:
        try:
            site["landing_utc"] = format_utc(parse_utc(landing_utc))
        except ValueError as err:
            raise ValueError(f"landing time: {err}") from err
    scenario = {
        "contract": contract_header(),
        "kind": "scenario",
        "scenario_id": site["site_id"],
        "title": name,
        "synthetic": bool(synthetic),
        "sites": [site],
        "observer_heights_m": list(heights_m or DEFAULT_OBSERVER_HEIGHTS_M),
        "default_height_m": DEFAULT_HEIGHT_M,
        "horizon": {"azimuth_step_deg": float(azimuth_step_deg), "max_range_m": float(max_range_m)},
        "time_window": {"start_utc": format_utc(begin), "end_utc": format_utc(begin + _dt.timedelta(days=days)), "step_s": float(step_s)},
        "bodies": ["SUN", "EARTH"],
        "data": {"dem_set_id": "any", "kernel_set_id": None},
    }
    presets = requirement_presets()
    wanted = list(presets) if requirement_ids is None else list(requirement_ids)
    unknown = [rid for rid in wanted if rid not in presets]
    if unknown:
        raise ValueError(f"unknown requirement preset {unknown}; available: {sorted(presets)}")
    if wanted:
        scenario["requirements"] = [presets[rid] for rid in wanted]
    if band:
        models = height_error_presets()
        scenario["uncertainty"] = {"dem_height_error_model": models["models"][models["default"]]}
    validate_document(scenario)
    return scenario


def height_error_presets() -> dict:
    """The stated height-error models shipped with the contract: {"default": id, "models": {id: model}}."""
    return json.loads((contract_dir() / "presets" / "terrain_height_error.json").read_text(encoding="utf-8"))


def requirement_presets() -> dict:
    """The example requirements shipped with the contract, by id.

    They are examples chosen by the team (docs/contract/presets/README.md); a scenario
    may state any other requirement.
    """
    path = contract_dir() / "presets" / "requirements.json"
    return {r["id"]: r for r in json.loads(path.read_text(encoding="utf-8"))["requirements"]}
