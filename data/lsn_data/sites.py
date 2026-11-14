"""Site records for the three Stage 1 south-polar candidate sites.

Each record is anchored on an IAU Gazetteer feature (primary source, with URL and retrieval time in
``data/sites/gazetteer_records.json``) and located on the LOLA 20 m DEM by a stated, repeatable rule:

* ``shackleton_rim_crest`` and ``de_gerlache_rim_crest``: the highest crest point found along radial lines
  (+-1500 m) through the vertices of the Gazetteer outline, as in checkpoint 2;
* ``malapert_massif_summit``: the highest DEM pixel inside the Gazetteer outline of Mons Malapert.

NASA's August 2022 candidate regions (Peak Near Shackleton, Connecting Ridge, de Gerlache Rim 1 and 2,
Malapert Massif and others) are in the same neighbourhoods, but NASA's pages do not publish coordinates for
them, so these records are the project's own sites and are not NASA landing sites.
"""

from __future__ import annotations

import json

import numpy as np

from . import manifest as mf
from .dem import PolarDEM
from .georef import lonlat_to_xy, xy_to_lonlat
from .paths import data_root, derived_dir, manifest_path, raw_dir, repo_data_dir

SITES_DIR = repo_data_dir() / "sites"
NASA_RELEASE = "https://www.nasa.gov/news-release/nasa-identifies-candidate-regions-for-landing-next-americans-on-Moon/"


def _inside(poly_xy: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Even-odd ray casting point-in-polygon, vectorised over points."""
    px, py = poly_xy[:, 0], poly_xy[:, 1]
    inside = np.zeros(x.shape, dtype=bool)
    j = len(px) - 1
    for i in range(len(px)):
        cond = ((py[i] > y) != (py[j] > y)) & (x < (px[j] - px[i]) * (y - py[i]) / (py[j] - py[i] + 1e-300) + px[i])
        inside ^= cond
        j = i
    return inside


def _best_outline(feat: dict) -> dict:
    return max(feat["determinations"], key=lambda b: len(b["outline_lon_lat_deg"]))


def _crest_site(dem: PolarDEM, feat: dict) -> tuple[float, float, dict]:
    det = _best_outline(feat)
    pts = np.array(det["outline_lon_lat_deg"])
    if np.allclose(pts[0], pts[-1]):
        pts = pts[:-1]
    x, y = lonlat_to_xy(pts[:, 0], pts[:, 1], dem.grid0.radius_m, dem.grid0.pole)
    cx, cy = x.mean(), y.mean()
    ux, uy = x - cx, y - cy
    n = np.hypot(ux, uy)
    ux, uy = ux / n, uy / n
    s = np.arange(-1500.0, 1500.0 + 1, 20.0)
    px = x[:, None] + s * ux[:, None]
    py = y[:, None] + s * uy[:, None]
    h = dem.height_xy(px, py)
    i, k = np.unravel_index(np.nanargmax(h), h.shape)
    return float(px[i, k]), float(py[i, k]), {
        "rule": "highest DEM point on radial lines +-1500 m (20 m step, bilinear) through the vertices of the IAU outline",
        "outline_vertices": int(len(pts)),
        "outline_determination_diameter_km": det["diameter_km"],
    }


def _summit_site(dem: PolarDEM, feat: dict) -> tuple[float, float, dict]:
    det = _best_outline(feat)
    pts = np.array(det["outline_lon_lat_deg"])
    x, y = lonlat_to_xy(pts[:, 0], pts[:, 1], dem.grid0.radius_m, dem.grid0.pole)
    w = dem.window_xy(x.min(), y.min(), x.max(), y.max())
    r, c = np.mgrid[0 : w.heights_m.shape[0], 0 : w.heights_m.shape[1]]
    gx, gy = w.grid.rowcol_to_xy(r, c)
    mask = _inside(np.column_stack([x, y]), gx, gy) & np.isfinite(w.heights_m)
    hh = np.where(mask, w.heights_m, -np.inf)
    i, j = np.unravel_index(np.argmax(hh), hh.shape)
    return float(gx[i, j]), float(gy[i, j]), {
        "rule": "highest 20 m DEM pixel whose centre lies inside the IAU outline polygon",
        "outline_vertices": int(len(pts)),
        "pixels_inside_outline": int(mask.sum()),
    }


def build(root=None) -> dict:
    root = root or data_root()
    dem = PolarDEM(raw_dir(root) / "LDEM_80S_20M" / "ldem_80s_20m.lbl", pyramid_dir=derived_dir(root) / "LDEM_80S_20M")
    m = mf.load(manifest_path())
    img = m["files"]["raw/lola/LDEM_80S_20M/ldem_80s_20m.img"]
    gaz = json.loads((SITES_DIR / "gazetteer_records.json").read_text(encoding="utf-8"))
    feats = {f["feature_id"]: f for f in gaz["features"]}
    spec = [
        ("shackleton_rim_crest", "Shackleton crater rim crest", 5450, _crest_site),
        ("de_gerlache_rim_crest", "de Gerlache crater rim crest", 1439, _crest_site),
        ("malapert_massif_summit", "Mons Malapert (Malapert massif) summit", 16338, _summit_site),
    ]
    sites = []
    for sid, name, fid, fn in spec:
        f = feats[fid]
        x, y, how = fn(dem, f)
        lon, lat = xy_to_lonlat(x, y, dem.grid0.radius_m, dem.grid0.pole)
        h = float(dem.height_xy(x, y))
        sites.append(
            {
                "site_id": sid,
                "name": name,
                "lon_deg_east": round(float(lon), 5),
                "lat_deg": round(float(lat), 5),
                "polar_stereographic_x_m": round(x, 1),
                "polar_stereographic_y_m": round(y, 1),
                "ground_height_m_above_1737.4km_sphere": round(h, 1),
                "ground_radius_m": round(h + dem.reference_radius_m, 1),
                "reference_frame": "Moon body-fixed, mean Earth/polar axis (label COORDINATE_SYSTEM_NAME 'MEAN EARTH/POLAR AXIS OF DE421'); "
                "planetocentric latitude, longitude positive east; sphere of radius 1737.4 km (LOLA GDR reference radius)",
                "location_method": how,
                "anchor": {
                    "source": "IAU Gazetteer of Planetary Nomenclature (USGS)",
                    "feature": f["name"],
                    "feature_id": fid,
                    "url": f["source_url"],
                    "retrieved_utc": f["retrieved_utc"],
                    "gazetteer_coordinate_system": f["coordinate_system"],
                    "iau_status": f["iau_status"],
                },
                "terrain_product": {
                    "product_id": "LDEM_80S_20M",
                    "product_version": img["product_version"],
                    "file": img["path"],
                    "sha256": img["sha256"],
                    "source_url": img["source_url"],
                },
                "status": "project candidate site derived from LOLA and the IAU outline; not an official landing site",
                "nasa_candidate_regions_in_the_neighbourhood": {
                    "note": "named in NASA's release; NASA published no coordinates for them, so the match is by name only and is unverified",
                    "url": NASA_RELEASE,
                },
                "unverified": ["relation to the NASA candidate regions"],
            }
        )
    return {
        "schema": "lunar-site-navigator site records v0",
        "generated_utc": mf.utc_now(),
        "sites": sites,
    }


def main() -> None:
    out = SITES_DIR / "sites.json"
    out.write_text(json.dumps(build(), indent=1) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
