"""First-screen summary of a published package set, written at build time.

The comparison page should show something useful before the large site packages arrive. The
build therefore writes, next to the packages:

    summary/index.json       one entry per site of packages/index.json: identity, terrain
                             class, observer heights, and the file and SHA-256 of its summary
    summary/<site_id>.json   the fields the first screen needs, in the layout of the site
                             manifest (SPEC 5), copied from it unchanged: the Sun and Earth
                             visibility windows, the Sun and Earth rise and set events, the
                             landing opportunities and requirements, the countdown metrics with
                             their reference, and the method statuses of those fields

Nothing is computed: every value is a value of the manifest named in `summary_of`, which also
records that manifest's package id and content digest. The viewer checks the SHA-256 of each
summary file against the catalogue before it uses it, and replaces the summary by the full
package as soon as that is loaded (whose arrays it checks as before).

The validation note of the pages is taken from the validation card in the same way.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

KIND = "lsn-web-summary"
VERSION = 1
# Windows of the first screen: status cards and chips of the comparison panes.
WINDOWS = ("sun_visible", "earth_visible", "sun_and_earth_visible", "earth_network_dsn", "sun_eclipsed_by_earth")
# Event fields of the first screen (status cards); the other event fields, terrain_quality among
# them, are shown once the full manifest is loaded.
EVENT_FIELDS = ("type", "body", "height_index", "et_s", "utc", "method")
# Opportunity fields left out of the summary (the calendar reads them from the full manifest).
OPPORTUNITY_LEFT_OUT = ("landing_windows_utc", "feasible_s_per_period")
COUNTDOWN = ("_at_reference", "_time_to_set_s", "_time_to_rise_s", "_is_lower_bound")


def _dumps(obj) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def site_summary(manifest: dict, path: str) -> dict:
    """The first-screen fields of one site manifest, unchanged."""
    t = manifest.get("timeline") or {}
    used_methods = set()

    def keep(record, fields=None):
        out = {k: v for k, v in record.items() if fields is None or k in fields}
        if out.get("method"):
            used_methods.add(out["method"])
        return out

    windows = [keep(w, ("id", "subject", "height_index", "definition", "intervals_et_s", "method"))
               for w in t.get("windows", []) if w.get("id") in WINDOWS]
    events = [keep(e, EVENT_FIELDS) for e in t.get("events", []) if e.get("body") in ("SUN", "EARTH")]
    opportunities = [keep(o, [k for k in o if k not in OPPORTUNITY_LEFT_OUT]) for o in t.get("opportunities", [])]
    metrics = [keep(m) for m in t.get("metrics", []) if any(m.get("id", "").endswith(s) for s in COUNTDOWN)]
    horizon = manifest.get("horizon") or {}
    if horizon.get("terrain_source", {}).get("method"):
        used_methods.add(horizon["terrain_source"]["method"])
    if t:
        used_methods.add("timeline.windows")
    site = manifest.get("site") or {}
    return {
        "kind": KIND, "version": VERSION, "partial": True,
        "summary_of": {"package_id": manifest.get("package_id"), "content_sha256": manifest.get("content_sha256"), "path": path},
        "contract": manifest.get("contract"), "package_id": manifest.get("package_id"), "status": manifest.get("status"),
        "synthetic": manifest.get("synthetic"), "warnings": manifest.get("warnings", []),
        "site": {k: site[k] for k in ("site_id", "name", "programme", "category", "lat_deg", "lon_deg") if k in site},
        "request": {"timeline": {k: v for k, v in ((manifest.get("request") or {}).get("timeline") or {}).items()
                                 if k in ("requirements", "landing_utc")}},
        # The horizon axis and the array references (file, shape, dtype, SHA-256) of the horizon
        # and of the Sun and Earth series, so that the first chart can be fetched, and checked,
        # before the large manifest arrives.
        "horizon": {k: horizon[k] for k in ("observer_heights_m", "default_height_index", "terrain_source", "azimuth",
                                            "elevation_deg", "distance_m") if k in horizon},
        "timeline": ({"time": t.get("time"), "direction_table_id": t.get("direction_table_id"), "series": t.get("series"),
                      "windows": windows, "events": events, "opportunities": opportunities, "metrics": metrics} if t else None),
        "methods": {k: {"validation": {"status": (v.get("validation") or {}).get("status")}}
                    for k, v in (manifest.get("methods") or {}).items() if k in used_methods},
    }


def write_summaries(index_path: Path, out: Path) -> list[Path]:
    """Write summary/index.json and one summary per site of the copied package index."""
    root = index_path.parent
    index = json.loads(index_path.read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    written, entries = [], []
    for entry in index["packages"]:
        if entry["kind"] != "site":
            continue
        manifest = json.loads((root / entry["path"] / "manifest.json").read_text(encoding="utf-8"))
        data = _dumps(site_summary(manifest, entry["path"]))
        name = f"{entry['site_id']}.json"
        (out / name).write_bytes(data)
        written.append(out / name)
        ts = (manifest.get("horizon") or {}).get("terrain_source") or {}
        at = ts.get("at_site") or {}
        horizon = manifest.get("horizon") or {}
        entries.append({
            "site_id": entry["site_id"], "name": entry.get("name"), "programme": entry.get("programme"), "category": entry.get("category"),
            "package_id": entry["package_id"], "file": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "terrain": {"resolution_class": ts.get("resolution_class"), "product_id": at.get("product_id"), "pixel_m": at.get("pixel_m")},
            "observer_heights_m": horizon.get("observer_heights_m"), "default_height_index": horizon.get("default_height_index"),
        })
    catalogue = {"kind": KIND, "version": VERSION, "index_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
                 "note": "Every value is copied unchanged from the site manifest named in each summary; nothing is computed.",
                 "sites": entries}
    (out / "index.json").write_bytes(_dumps(catalogue))
    written.append(out / "index.json")
    return written


def validation_note(card_path: Path | None) -> dict | None:
    """Counts and open items of the validation card, for the short note of the pages."""
    if not card_path or not Path(card_path).is_file():
        return None
    card = json.loads(Path(card_path).read_text(encoding="utf-8"))
    s = card.get("summary") or {}
    return {"checks": s.get("checks"), "passed": s.get("passed"), "failed": s.get("failed"), "failed_ids": s.get("failed_ids", []),
            "not_validated": [{"item": x.get("item"), "state": x.get("state")} for x in card.get("not_validated", [])],
            "generated_utc": card.get("generated_utc")}
