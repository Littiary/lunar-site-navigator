"""Exports real terrain heights around the sites of a package root, for drawing only.

The Unreal scene cannot call the data stream's Python reader, so this script samples it
once per site on the polar layout of the scene's terrain mesh and writes the samples as
plain files next to the imported packages. Nothing is computed here apart from where the
sample points lie: the heights are what ``lsn_data`` returns for those points on its
finest data (bilinear, the same surface the science core uses).

Layout of the samples: for every azimuth sample of the package horizon and for a fixed
list of ring distances (arc length along the reference sphere from the site), the height
of the terrain above the reference sphere. Shape [A, R], float32, little-endian, NaN
where the data reader has no data.

This is a viewer-side cache, not part of the package contract. It is not under version
control. Each grid records the package it was sampled for and the terrain files behind it.

Usage (in the Python environment that has the data stream's reader installed):
    python export_terrain.py <package root> [--out <folder>] [--rings 320]
The default output folder is unreal/Content/LsnTerrain.

Near the three project sites the data stream also serves NASA's 5 m site models
(open_terrain(near_field=True)). They are sampled only for a package that was itself computed
on them (its horizon.terrain_source says so), so that the drawn ground and the package
horizon are the same data; --near-field yes forces them for a preview.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
from pathlib import Path

import numpy as np

FORMAT = {"name": "lsn-unreal-terrain-grid", "version": "1"}
NEAREST_RING_M = 1.0


def ring_distances(max_range_m: float, count: int) -> np.ndarray:
    """Ring distances from 1 m to the search radius, growing by a constant factor."""
    return np.geomspace(NEAREST_RING_M, max_range_m, count)


def destinations(site: dict, azimuth_deg: np.ndarray, arc_m: np.ndarray, radius_m: float):
    """Latitude and east longitude of the points reached from the site along great circles.

    Uses the site frame the package gives (site.enu), so the sample points lie exactly in
    the azimuths of the package.
    """
    east, north, up = (np.asarray(site["enu"][k], dtype=np.float64) for k in ("east", "north", "up"))
    az = np.deg2rad(azimuth_deg)[:, None]
    arc = (arc_m / radius_m)[None, :]
    heading = np.sin(az)[..., None] * east + np.cos(az)[..., None] * north  # [A, 1, 3]
    p = np.cos(arc)[..., None] * up + np.sin(arc)[..., None] * heading  # [A, R, 3]
    lat = np.rad2deg(np.arctan2(p[..., 2], np.hypot(p[..., 0], p[..., 1])))
    lon = np.rad2deg(np.arctan2(p[..., 1], p[..., 0]))
    return lat, lon


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("package_root")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "Content" / "LsnTerrain"))
    parser.add_argument("--rings", type=int, default=480)
    parser.add_argument("--near-field", choices=("auto", "yes", "no"), default="auto",
                        help="sample the 5 m site models near the site. auto (default): only for a package whose own "
                             "terrain_source names a product of 5 m or finer, so that the drawn ground is the data the "
                             "package was computed on; yes: always (a preview: the ground may then differ from the "
                             "package horizon); no: never")
    args = parser.parse_args()

    import lsn_data  # the data stream's reader

    terrains = {}

    def open_terrain(near_field: bool):
        if near_field not in terrains:
            terrains[near_field] = lsn_data.open_terrain(near_field=True) if near_field else lsn_data.open_terrain()
        return terrains[near_field]

    def package_rests_on_fine_data(manifest: dict) -> bool:
        source = manifest["horizon"].get("terrain_source") or {}
        pixels = [p.get("pixel_m", 1e9) for p in source.get("products", [])] + [source.get("at_site", {}).get("pixel_m", 1e9)]
        return min(pixels) <= 5.0

    root = Path(args.package_root)
    out = Path(args.out)
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    written = []
    for entry in index["packages"]:
        if entry["kind"] != "site":
            continue
        manifest = json.loads((root / entry["path"] / "manifest.json").read_text(encoding="utf-8"))
        if manifest["synthetic"]:
            print(f"skip {entry['site_id']}: a synthetic package has no terrain")
            continue
        site, horizon = manifest["site"], manifest["horizon"]
        near_field = args.near_field == "yes" or (args.near_field == "auto" and package_rests_on_fine_data(manifest))
        terrain = open_terrain(near_field)
        radius_m = site["reference_radius_m"]["value"]
        if abs(radius_m - terrain.reference_radius_m) > 1e-6:
            raise SystemExit(f"{entry['site_id']}: package sphere {radius_m} m, terrain sphere {terrain.reference_radius_m} m")
        az = horizon["azimuth"]
        azimuth_deg = az["start_deg"] + az["step_deg"] * np.arange(az["count"])
        rings = ring_distances(horizon["max_range_m"]["value"], args.rings)
        lat, lon = destinations(site, azimuth_deg, rings, radius_m)
        heights = np.asarray(terrain.height_m(lon, lat), dtype="<f4")

        folder = out / site["site_id"]
        folder.mkdir(parents=True, exist_ok=True)
        data = heights.tobytes()
        (folder / "heights_m.f4").write_bytes(data)
        meta = {
            "format": FORMAT,
            "note": "Viewer-side cache for drawing. Not part of the package contract.",
            "site_id": site["site_id"],
            "package_id": manifest["package_id"],
            "frame": site["frame"],
            "reference_radius_m": radius_m,
            "azimuth": az,
            "ring_distance_m": [float(r) for r in rings],
            "heights": {"file": "heights_m.f4", "dtype": "<f4", "shape": [int(az["count"]), int(rings.size)], "unit": "m",
                        "sha256": hashlib.sha256(data).hexdigest(), "nan_count": int(np.isnan(heights).sum())},
            "definition": "Height of the terrain above the reference sphere at the point reached from the site along the great circle of the azimuth after the ring distance (arc length on the reference sphere).",
            "sampling": "lsn_data.Terrain.height_m(lon, lat): finest data, bilinear, statistic 'mean'",
            "near_field": bool(near_field),
            "near_field_note": ("5 m site models sampled where they cover the place" + ("" if package_rests_on_fine_data(manifest) else
                                "; PREVIEW: the package was computed on coarser data, so this ground may differ from its horizon")) if near_field else "not used",
            "dem": manifest["inputs"]["dem"],
            "created_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        (folder / "terrain.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        written.append(site["site_id"])
        print(f"{site['site_id']}: {heights.shape[0]} azimuths x {heights.shape[1]} rings, "
              f"{'5 m near field, ' if near_field else ''}{meta['heights']['nan_count']} without data, heights {np.nanmin(heights):.0f} to {np.nanmax(heights):.0f} m -> {folder}")
    (out / "index.json").write_text(json.dumps({"format": FORMAT, "sites": written}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
