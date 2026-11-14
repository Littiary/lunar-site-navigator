"""Validation of contract documents and of whole package directories.

Two layers:
1. the JSON Schema (structure, types, required fields);
2. checks a schema cannot express: array files exist with the stated size, digest and NaN
   count; every 'method' points at a method card; array shapes agree with the axes; the
   package id and the content digest can be recomputed; synthetic data is labelled.
"""

from __future__ import annotations

import functools
import hashlib
import json
from pathlib import Path
from typing import Any, Iterator

import numpy as np
from jsonschema import Draft202012Validator

from .io import (
    CONTRACT_VERSION,
    compute_content_sha256,
    compute_package_id,
    contract_dir,
)

KINDS = ("site", "direction_table", "site_pairs", "scenario", "index")


class ContractError(ValueError):
    """Raised when a document or a package does not satisfy the contract."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("contract violation:\n  " + "\n  ".join(errors))


@functools.lru_cache(maxsize=1)
def load_schema() -> dict:
    path = contract_dir() / "schemas" / "lsn-contract.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=None)
def _validator(kind: str) -> Draft202012Validator:
    schema = load_schema()
    sub = {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": f"#/$defs/{kind}"}
    Draft202012Validator.check_schema(sub)
    return Draft202012Validator(sub)


def _schema_errors(doc: Any) -> list[str]:
    if not isinstance(doc, dict) or doc.get("kind") not in KINDS:
        return [f"'kind' must be one of {KINDS}"]
    errors = []
    for err in sorted(_validator(doc["kind"]).iter_errors(doc), key=lambda e: list(e.absolute_path)):
        where = "/".join(str(p) for p in err.absolute_path) or "<root>"
        errors.append(f"{where}: {err.message}")
    version = str(doc.get("contract", {}).get("version"))
    try:
        found = tuple(int(part) for part in version.split("."))
        mine = tuple(int(part) for part in CONTRACT_VERSION.split("."))
        readable = len(found) == 2 and found[0] == mine[0] and found[1] <= mine[1]
    except ValueError:
        readable = False
    if not readable:
        errors.append(f"contract/version: found {version!r}, this reader implements {CONTRACT_VERSION!r} and older minor versions")
    return errors


def validate_document(doc: Any) -> None:
    """Validate a JSON document (manifest, scenario or index) against the schema only."""
    errors = _schema_errors(doc)
    if errors:
        raise ContractError(errors)


def _walk(node: Any, path: str = "") -> Iterator[tuple[str, dict]]:
    if isinstance(node, dict):
        yield path, node
        for key, value in node.items():
            yield from _walk(value, f"{path}/{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _walk(value, f"{path}/{i}")


def _is_array_ref(node: dict) -> bool:
    return {"file", "dtype", "shape", "sha256"} <= node.keys()


def _check_arrays(path: Path, manifest: dict, errors: list[str]) -> None:
    seen: set[str] = set()
    for where, node in _walk(manifest):
        if not _is_array_ref(node):
            continue
        file = node["file"]
        if file in seen:
            errors.append(f"{where}: file {file} is referenced more than once")
        seen.add(file)
        fpath = path / file
        if not fpath.is_file():
            errors.append(f"{where}: missing array file {file}")
            continue
        dtype = np.dtype(node["dtype"])
        expected = int(np.prod(node["shape"])) * dtype.itemsize
        data = fpath.read_bytes()
        if len(data) != expected:
            errors.append(f"{where}: {file} has {len(data)} bytes, shape and dtype need {expected}")
            continue
        if hashlib.sha256(data).hexdigest() != node["sha256"]:
            errors.append(f"{where}: sha256 of {file} does not match the manifest")
        if dtype.kind == "f":
            nan_count = int(np.isnan(np.frombuffer(data, dtype=dtype)).sum())
            if nan_count != node["nan_count"]:
                errors.append(f"{where}: {file} holds {nan_count} NaN, manifest says {node['nan_count']}")
    stray = {p.name for p in path.iterdir() if p.is_file()} - seen - {"manifest.json"}
    if stray:
        errors.append(f"files not referenced by the manifest: {sorted(stray)}")


def _check_methods(manifest: dict, errors: list[str]) -> None:
    cards = manifest.get("methods", {})
    used: set[str] = set()
    for where, node in _walk(manifest):
        if where.startswith("/methods"):
            continue
        method = node.get("method")
        if isinstance(method, str):
            used.add(method)
            if method not in cards:
                errors.append(f"{where}: method card '{method}' is not defined in 'methods'")
    for unused in sorted(set(cards) - used):
        errors.append(f"methods/{unused}: card is not referenced by any number")
    if manifest.get("synthetic"):
        for name, card in cards.items():
            if card["validation"]["status"] != "synthetic":
                errors.append(f"methods/{name}: synthetic package, validation status must be 'synthetic'")
    else:
        for name, card in cards.items():
            if card["validation"]["status"] == "synthetic":
                errors.append(f"methods/{name}: status 'synthetic' in a package not marked synthetic")


def _expect_shape(ref: dict | None, shape: list[int], where: str, errors: list[str]) -> None:
    if ref is not None and ref["shape"] != shape:
        errors.append(f"{where}: shape {ref['shape']} but the axes require {shape}")


def _check_site(manifest: dict, errors: list[str]) -> None:
    hz = manifest["horizon"]
    az = hz["azimuth"]
    if abs(az["count"] * az["step_deg"] - 360.0) > 1e-9:
        errors.append("horizon/azimuth: count * step_deg must equal 360")
    heights = hz["observer_heights_m"]
    if heights != manifest["request"]["observer_heights_m"]:
        errors.append("horizon/observer_heights_m differs from request/observer_heights_m")
    if heights != sorted(set(heights)):
        errors.append("horizon/observer_heights_m must be strictly increasing")
    if hz["default_height_index"] >= len(heights):
        errors.append("horizon/default_height_index is out of range")
    shape = [len(heights), az["count"]]
    for name in (
        "elevation_deg", "distance_m", "obstacle_height_m", "obstacle_lat_deg",
        "obstacle_lon_deg", "obstacle_dem_layer", "elevation_sigma_deg", "obstacle_height_error_m", "obstacle_constrained",
        "elevation_lower_deg", "elevation_upper_deg",
    ):
        _expect_shape(hz.get(name), shape, f"horizon/{name}", errors)

    _expect_shape(hz.get("obstacle_id"), shape, "horizon/obstacle_id", errors)
    if ("obstacle_id" in hz) != ("obstacles" in hz):
        errors.append("horizon: obstacle_id and obstacles must be given together")
    for k, ob in enumerate(hz.get("obstacles", [])):
        if ob["id"] != k:
            errors.append(f"horizon/obstacles/{k}: id must equal the position in the list")
        if ob["height_index"] >= len(heights) or ob["azimuth_start_index"] >= az["count"] or ob["azimuth_count"] > az["count"]:
            errors.append(f"horizon/obstacles/{k}: index out of range")

    site = manifest["site"]
    req_site = manifest["request"]["site"]
    for key in ("site_id", "lat_deg", "lon_deg"):
        if site[key] != req_site[key]:
            errors.append(f"site/{key} differs from request/site/{key}")

    tl = manifest.get("timeline")
    if tl is None:
        return
    trade = tl.get("height_trade")
    if trade is not None:
        if trade["observer_heights_m"] != heights:
            errors.append("timeline/height_trade: observer_heights_m differs from the horizon")
        for quantity in trade["quantities"]:
            if len(quantity["values"]) != len(heights) or len(quantity["change_s"]) != len(heights):
                errors.append(f"timeline/height_trade/{quantity['id']}: one value per observer height is required")
    n = tl["time"]["count"]
    dt_input = manifest["inputs"]["direction_table"]
    if dt_input is None or dt_input["package_id"] != tl["direction_table_id"]:
        errors.append("timeline/direction_table_id must match inputs/direction_table/package_id")
    for body in tl["bodies"]:
        series = tl["series"].get(body)
        if series is None:
            errors.append(f"timeline/series/{body}: missing series for a listed body")
            continue
        for name in ("azimuth_deg", "elevation_deg", "angular_radius_deg", "ellipse_visible_share"):
            _expect_shape(series.get(name), [n], f"timeline/series/{body}/{name}", errors)
        for name in ("margin_deg", "visible_fraction", "lit_fraction", "blocker_azimuth_index"):
            _expect_shape(series.get(name), [len(heights), n], f"timeline/series/{body}/{name}", errors)
    calendar = tl.get("calendar")
    n_periods = None
    if calendar is not None:
        n_periods = len(calendar["periods"])
        for k, period in enumerate(calendar["periods"]):
            if period["index"] != k or not period["start_et_s"] < period["end_et_s"]:
                errors.append(f"timeline/calendar/periods/{k}: index or time order is wrong")
            if k and period["start_et_s"] != calendar["periods"][k - 1]["end_et_s"]:
                errors.append(f"timeline/calendar/periods/{k}: periods must follow each other without gaps")
        for quantity in calendar["quantities"]:
            rows = quantity["values"]
            if len(rows) != len(heights) or any(len(row) != n_periods for row in rows):
                errors.append(f"timeline/calendar/quantities/{quantity['id']}: values must be [heights][periods]")
    stated = {r["id"] for r in (manifest["request"]["timeline"] or {}).get("requirements", [])}
    for i, opportunity in enumerate(tl.get("opportunities", [])):
        if opportunity["requirement_id"] not in stated:
            errors.append(f"timeline/opportunities/{i}: requirement_id is not in request/timeline/requirements")
        if opportunity["height_index"] >= len(heights):
            errors.append(f"timeline/opportunities/{i}: height_index out of range")
        if len(opportunity["landing_windows_et_s"]) != len(opportunity["landing_windows_utc"]):
            errors.append(f"timeline/opportunities/{i}: landing windows differ in length")
        if n_periods is not None and len(opportunity["feasible_s_per_period"]) != n_periods:
            errors.append(f"timeline/opportunities/{i}: feasible_s_per_period must have one value per calendar period")
    n_obstacles = len(hz.get("obstacles", []))
    for i, blocker in enumerate(tl.get("blockers", [])):
        if blocker["height_index"] >= len(heights) or blocker["body"] not in tl["bodies"]:
            errors.append(f"timeline/blockers/{i}: body or height_index not in this package")
        if blocker["obstacle_id"] >= n_obstacles:
            errors.append(f"timeline/blockers/{i}: obstacle_id is not in horizon/obstacles")
        if len(blocker["intervals_et_s"]) != len(blocker["intervals_utc"]):
            errors.append(f"timeline/blockers/{i}: intervals_et_s and intervals_utc differ in length")
    t0 = tl["time"]["start_et_s"]
    t1 = t0 + (n - 1) * tl["time"]["step_s"]
    last = None
    for i, ev in enumerate(tl["events"]):
        if ev["height_index"] >= len(heights):
            errors.append(f"timeline/events/{i}: height_index out of range")
        if not (t0 <= ev["et_s"] <= t1):
            errors.append(f"timeline/events/{i}: et_s outside the time grid")
        if "earliest_et_s" in ev and not ev["earliest_et_s"] <= ev["et_s"] <= ev["latest_et_s"]:
            errors.append(f"timeline/events/{i}: the event must lie between its earliest and latest time")
        if last is not None and ev["et_s"] < last:
            errors.append(f"timeline/events/{i}: events must be sorted by et_s")
        last = ev["et_s"]
    for i, win in enumerate(tl["windows"]):
        if win["height_index"] >= len(heights):
            errors.append(f"timeline/windows/{i}: height_index out of range")
        if len(win["intervals_et_s"]) != len(win["intervals_utc"]):
            errors.append(f"timeline/windows/{i}: intervals_et_s and intervals_utc differ in length")
        prev_end = None
        for a, b in win["intervals_et_s"]:
            if not a < b or (prev_end is not None and a <= prev_end):
                errors.append(f"timeline/windows/{i}: intervals must be non-empty, sorted and disjoint")
                break
            prev_end = b


def _check_terrain(manifest: dict, errors: list[str]) -> None:
    block = manifest.get("terrain")
    stated = manifest["request"].get("terrain_patches")
    if block is None:
        if stated:
            errors.append("request/terrain_patches is stated but the package has no terrain block")
        return
    patches = block["patches"]
    ids = [p["id"] for p in patches]
    if len(set(ids)) != len(ids):
        errors.append("terrain/patches: ids must be unique")
    spacings = [p["spacing_m"] for p in patches]
    if spacings != sorted(spacings):
        errors.append("terrain/patches must be listed finest first")
    if stated != [{"id": p["id"], "half_width_m": p["half_width_m"], "spacing_m": p["spacing_m"]} for p in patches]:
        errors.append("terrain/patches differ from request/terrain_patches")
    for i, p in enumerate(patches):
        where = f"terrain/patches/{i}"
        cells = p["half_width_m"] / p["spacing_m"]
        count = 2 * int(round(cells)) + 1
        if abs(cells - round(cells)) > 1e-9 or p["count_east"] != count or p["count_north"] != count:
            errors.append(f"{where}: count_east and count_north must be 2 * half_width_m / spacing_m + 1 = {count}")
        _expect_shape(p["up_m"], [p["count_north"], p["count_east"]], f"{where}/up_m", errors)
        if p["up_m"]["dtype"] != "<f4" or p["up_m"]["unit"] != "m":
            errors.append(f"{where}/up_m must be float32 in metres")
        if p["up_m"]["method"] != block["method"]:
            errors.append(f"{where}/up_m: method differs from terrain/method")
        if p["east_min_m"] != -p["half_width_m"] or p["north_min_m"] != -p["half_width_m"]:
            errors.append(f"{where}: east_min_m and north_min_m must be -half_width_m (the grid is centred on the site)")
        if p["sources"] and abs(sum(s["node_share"] for s in p["sources"]) - 1.0) > 1e-6:
            errors.append(f"{where}/sources: node_share must add up to 1")


def _check_direction_table(manifest: dict, errors: list[str]) -> None:
    n = manifest["time"]["count"]
    bodies = manifest["bodies"]
    _expect_shape(manifest["positions_km"], [n, len(bodies), 3], "positions_km", errors)
    if manifest["positions_km"]["dtype"] != "<f8":
        errors.append("positions_km: dtype must be <f8")
    for body in bodies:
        if body not in manifest["body_radii_km"]:
            errors.append(f"body_radii_km: missing radius for {body}")
    req = manifest["request"]
    for key in ("frame", "center", "aberration_correction", "bodies"):
        if manifest[key] != req[key]:
            errors.append(f"{key} differs from request/{key}")
    for key in ("start_et_s", "step_s", "count"):
        if manifest["time"][key] != req[key]:
            errors.append(f"time/{key} differs from request/{key}")
    view = manifest.get("earth_view")
    if (view is not None) != bool(req.get("earth_view")):
        errors.append("earth_view: the block and request/earth_view must both be present or both be absent")
    if view is not None:
        for name in ("sub_lunar_lat_deg", "sub_lunar_lon_deg", "north_pole_angle_deg"):
            _expect_shape(view[name], [n], f"earth_view/{name}", errors)
            if view[name]["dtype"] != "<f4" or view[name]["unit"] != "deg" or view[name]["method"] != view["method"]:
                errors.append(f"earth_view/{name} must be float32 in degrees with the method of the block")


def _check_site_pairs(manifest: dict, errors: list[str]) -> None:
    known = [s["site_id"] for s in manifest["sites"]]
    if len(set(known)) != len(known):
        errors.append("sites: site_id values must be unique")
    if [s["package_id"] for s in manifest["sites"]] != manifest["request"]["site_package_ids"]:
        errors.append("sites: package ids differ from request/site_package_ids")
    if len(manifest["pairs"]) != len(known) * (len(known) - 1) // 2:
        errors.append("pairs: there must be one entry for every pair of sites")
    total = (manifest["time"]["count"] - 1) * manifest["time"]["step_s"]
    for i, pair in enumerate(manifest["pairs"]):
        if pair["site_a"] not in known or pair["site_b"] not in known or pair["site_a"] == pair["site_b"]:
            errors.append(f"pairs/{i}: site ids must be two different sites of this package")
        for row in pair["windows"]:
            if abs(row["either_s"] + row["neither_s"] - total) > 1e-3:
                errors.append(f"pairs/{i}/{row['window']}: either_s + neither_s must equal the length of the time range")
            if len(row["neither_intervals_et_s"]) != len(row["neither_intervals_utc"]):
                errors.append(f"pairs/{i}/{row['window']}: neither intervals differ in length")


def validate_package(path: Path | str) -> dict:
    """Validate a package directory completely. Returns the manifest; raises ContractError."""
    path = Path(path)
    manifest_path = path / "manifest.json"
    if not manifest_path.is_file():
        raise ContractError([f"{path}: manifest.json not found"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = _schema_errors(manifest)
    if errors:
        raise ContractError(errors)
    if manifest["kind"] not in ("site", "direction_table", "site_pairs"):
        raise ContractError([f"kind '{manifest['kind']}' is a document, not a package"])

    _check_arrays(path, manifest, errors)
    _check_methods(manifest, errors)
    if manifest["kind"] == "site":
        _check_site(manifest, errors)
        _check_terrain(manifest, errors)
    elif manifest["kind"] == "site_pairs":
        _check_site_pairs(manifest, errors)
    else:
        _check_direction_table(manifest, errors)

    expected_id = compute_package_id(
        manifest["kind"], manifest["synthetic"], manifest["request"], manifest["inputs"]
    )
    if manifest["package_id"] != expected_id:
        errors.append(f"package_id is {manifest['package_id']}, request and inputs give {expected_id}")
    if manifest["content_sha256"] != compute_content_sha256(manifest):
        errors.append("content_sha256 does not match the manifest content")
    if path.name != manifest["package_id"]:
        errors.append(f"directory name '{path.name}' differs from package_id")
    if errors:
        raise ContractError(errors)
    return manifest
