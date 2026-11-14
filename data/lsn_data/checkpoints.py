"""The three data checkpoints. Thresholds come from ``data/checkpoints/thresholds.json``.

1. checksums: files on disk equal the manifest (and the second-source cross-check matched);
2. georeferencing: published crater outlines (IAU Gazetteer) fall on the DEM's rim crests;
3. values and reference radius: label min/max, the Shackleton numbers of Zuber et al. 2012,
   consistency between the 20 m and 60 m products, and the independent 16 ppd cylindrical product.

``run_all`` returns a plain dict (written to ``data/checkpoints/report.json`` by the CLI).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import manifest as mf
from .dem import PolarDEM
from .georef import lonlat_to_xy
from .paths import data_root, derived_dir, manifest_path, raw_dir, repo_data_dir
from .pdslabel import parse_label

CHK_DIR = repo_data_dir() / "checkpoints"


def thresholds() -> dict:
    return json.loads((CHK_DIR / "thresholds.json").read_text(encoding="utf-8"))


def features() -> dict[str, dict]:
    d = json.loads((CHK_DIR / "features.json").read_text(encoding="utf-8"))
    return {f["name"]: f for f in d["features"]}


# --------------------------------------------------------------------------------------------
def checkpoint_1(root: Path | None = None) -> dict:
    root = root or data_root()
    m = mf.load(manifest_path())
    problems = mf.verify(m, root)
    big_unchecked = []
    cross_failed = []
    for rel, rec in m["files"].items():
        if rec["size_bytes"] > 10_000_000 or rec["equivalent_urls"]:
            ok = [c for c in rec.get("cross_checks", []) if c["matches"]]
            bad = [c for c in rec.get("cross_checks", []) if not c["matches"]]
            if bad:
                cross_failed.append(rel)
            if not ok and rec["role"] == "data":
                big_unchecked.append(rel)
    return {
        "files_in_manifest": len(m["files"]),
        "total_bytes": sum(r["size_bytes"] for r in m["files"].values()),
        "problems": problems,
        "cross_check_failed": cross_failed,
        "data_files_without_matching_cross_check": big_unchecked,
        "passed": not problems and not cross_failed and not big_unchecked,
    }


# --------------------------------------------------------------------------------------------
def _best_outline(feat: dict) -> dict:
    d = max(feat["determinations"], key=lambda b: len(b["outline_lon_lat_deg"]))
    if len(d["outline_lon_lat_deg"]) < 5:
        raise ValueError(f"{feat['name']}: no outline")
    return d


def crest_metrics(dem: PolarDEM, det: dict, th2: dict) -> dict:
    pts = np.array(det["outline_lon_lat_deg"], dtype=float)
    if np.allclose(pts[0], pts[-1]):
        pts = pts[:-1]
    sel = np.unique(np.linspace(0, len(pts) - 1, min(60, len(pts))).round().astype(int))
    pts = pts[sel]
    x, y = lonlat_to_xy(pts[:, 0], pts[:, 1], dem.grid0.radius_m, dem.grid0.pole)
    cx, cy = x.mean(), y.mean()
    ux, uy = x - cx, y - cy
    n = np.hypot(ux, uy)
    ux, uy = ux / n, uy / n
    s = np.arange(-1500.0, 1500.0 + 1, 20.0)
    px = x[:, None] + s[None, :] * ux[:, None]
    py = y[:, None] + s[None, :] * uy[:, None]
    h = dem.height_xy(px, py)
    k = np.nanargmax(h, axis=1)
    crest_h = h[np.arange(len(k)), k]
    offset = np.abs(s[k])
    inside = th2["inside_distance_is_fraction_of_diameter"] * det["diameter_km"] * 1000.0
    ix = px[np.arange(len(k)), k] - inside * ux
    iy = py[np.arange(len(k)), k] - inside * uy
    drop = crest_h - dem.height_xy(ix, iy)
    return {
        "vertices_used": int(len(k)),
        "median_crest_offset_m": float(np.median(offset)),
        "fraction_offset_le_1000m": float(np.mean(offset <= 1000.0)),
        "median_drop_crest_to_inside_m": float(np.median(drop)),
        "mean_crest_height_m": float(np.mean(crest_h)),
    }


def checkpoint_2(dem20: PolarDEM) -> dict:
    th = thresholds()["checkpoint_2_georeferencing"]
    feats = features()
    out = {}
    for name in ("Shackleton", "Shoemaker", "Faustini", "Cabeus", "de Gerlache", "Haworth"):
        det = _best_outline(feats[name])
        m = crest_metrics(dem20, det, th)
        m["gazetteer_feature_id"] = feats[name]["feature_id"]
        m["outline_diameter_km"] = det["diameter_km"]
        m["passed"] = bool(
            m["median_crest_offset_m"] <= th["per_crater_median_crest_offset_m_max"]
            and m["fraction_offset_le_1000m"] >= th["per_crater_fraction_of_vertices_with_offset_le_1000m_min"]
            and m["median_drop_crest_to_inside_m"] >= th["per_crater_median_drop_from_crest_to_inside_m_min"]
        )
        out[name] = m
    return {"craters": out, "passed": all(v["passed"] for v in out.values())}


# --------------------------------------------------------------------------------------------
def _label_min_max(dem: PolarDEM) -> dict:
    mn, mx = 32767, -32768
    arr = dem._array(0, "mean")
    for i in range(0, arr.shape[0], 1024):
        blk = np.asarray(arr[i : i + 1024])
        mn, mx = min(mn, int(blk.min())), max(mx, int(blk.max()))
    return {
        "measured_min_dn": mn,
        "measured_max_dn": mx,
        "label_min_dn": int(dem.label["DERIVED_MINIMUM"]),
        "label_max_dn": int(dem.label["DERIVED_MAXIMUM"]),
        "passed": mn == int(dem.label["DERIVED_MINIMUM"]) and mx == int(dem.label["DERIVED_MAXIMUM"]),
        "min_m": mn * dem.scale,
        "max_m": mx * dem.scale,
    }


def _overlap(d20: PolarDEM, d60: PolarDEM) -> dict:
    g20, g60 = d20.grid0, d60.grid0
    a20, a60 = d20._array(0, "mean"), d60._array(0, "mean")
    # 60 m pixels whose whole 3x3 block of 20 m pixels lies inside the 20 m raster
    f = round(g60.pixel_m / g20.pixel_m)
    left0 = (g60.x_ul_m - g20.x_ul_m) / g20.pixel_m  # 20 m column of the left edge of 60 m column 0
    top0 = (g20.y_ul_m - g60.y_ul_m) / g20.pixel_m
    assert abs(left0 - round(left0)) < 1e-9 and abs(top0 - round(top0)) < 1e-9, "grids are not aligned"
    j_lo = int(np.ceil(-left0 / f))
    j_hi = int(np.floor((g20.n_cols - left0) / f))  # exclusive
    i_lo = int(np.ceil(-top0 / f))
    i_hi = int(np.floor((g20.n_rows - top0) / f))
    j = np.arange(j_lo, j_hi)
    diffs = []
    step = 64
    for i0 in range(i_lo, i_hi, step):
        i1 = min(i0 + step, i_hi)
        r20 = int(round(top0 + i0 * f))
        c20 = int(round(left0 + j_lo * f))
        blk = np.asarray(a20[r20 : r20 + (i1 - i0) * f, c20 : c20 + (j_hi - j_lo) * f]).astype(np.float32)
        mean20 = blk.reshape(i1 - i0, f, j_hi - j_lo, f).mean(axis=(1, 3)) * d20.scale
        v60 = np.asarray(a60[i0:i1, j_lo:j_hi]).astype(np.float32) * d60.scale
        diffs.append((v60 - mean20).ravel())
    d = np.concatenate(diffs)
    return {
        "pixels_compared": int(d.size),
        "mean_difference_m": float(d.mean()),
        "median_abs_difference_m": float(np.median(np.abs(d))),
        "p99_abs_difference_m": float(np.percentile(np.abs(d), 99)),
    }


def _ldem16_vs_polar(dem20: PolarDEM, root: Path) -> dict:
    lbl = parse_label(raw_dir(root) / "LDEM_16" / "ldem_16.lbl")
    n_rows, n_cols = int(lbl["LINES"]), int(lbl["LINE_SAMPLES"])
    assert lbl["MAP_PROJECTION_TYPE"] == "SIMPLE CYLINDRICAL" and lbl["MAP_RESOLUTION"] == 16
    arr = np.fromfile(raw_dir(root) / "LDEM_16" / "ldem_16.img", dtype="<i2").reshape(n_rows, n_cols)
    ppd = float(lbl["MAP_RESOLUTION"])
    lat_off, lon_off = float(lbl["LINE_PROJECTION_OFFSET"]), float(lbl["SAMPLE_PROJECTION_OFFSET"])
    clon = float(lbl["CENTER_LONGITUDE"])
    rows = np.arange(n_rows)
    lat = (lat_off - rows) / ppd  # pixel-centre latitude of each row (pole-ward rows have lat < 0)
    sel_rows = rows[lat <= -80.5]
    cols = np.arange(n_cols)
    lon = (clon + (cols - lon_off) / ppd) % 360.0
    LON, LAT = np.meshgrid(lon, lat[sel_rows])
    v16 = arr[sel_rows, :].astype(np.float64) * float(lbl["SCALING_FACTOR"])
    level = dem20.level_for_pixel(1900.0)
    v_polar = dem20.height_m(LON, LAT, level=level)
    ok = np.isfinite(v_polar)
    d = (v_polar - v16)[ok]
    return {
        "ldem16_pixels_compared": int(d.size),
        "polar_level_used": level,
        "polar_pixel_m_used": dem20.pixel_m(level),
        "mean_difference_m": float(d.mean()),
        "median_abs_difference_m": float(np.median(np.abs(d))),
        "p95_abs_difference_m": float(np.percentile(np.abs(d), 95)),
        "rmse_m": float(np.sqrt(np.mean(d**2))),
        "correlation": float(np.corrcoef(v_polar[ok], v16[ok])[0, 1]),
    }


def checkpoint_3(dem20: PolarDEM, dem60: PolarDEM, root: Path, c2: dict | None = None) -> dict:
    th = thresholds()["checkpoint_3_values_and_reference_radius"]
    out: dict = {}
    out["label_min_max"] = {dem.product_id: _label_min_max(dem) for dem in (dem20, dem60)}
    out["label_min_max"]["passed"] = all(v["passed"] for v in out["label_min_max"].values())

    z = th["shackleton_reference"]
    w = dem20.window_around(z["centre_lon_deg"], z["centre_lat_deg"], z["floor_disc_radius_m"])
    r, c = np.mgrid[0 : w.heights_m.shape[0], 0 : w.heights_m.shape[1]]
    x, y = w.grid.rowcol_to_xy(r, c)
    cx, cy = lonlat_to_xy(z["centre_lon_deg"], z["centre_lat_deg"], dem20.grid0.radius_m, dem20.grid0.pole)
    disc = np.hypot(x - cx, y - cy) <= z["floor_disc_radius_m"]
    floor_h = float(np.nanmean(w.heights_m[disc]))
    floor_radius_km = (floor_h + dem20.reference_radius_m) / 1000.0
    th2 = thresholds()["checkpoint_2_georeferencing"]
    rim = crest_metrics(dem20, _best_outline(features()["Shackleton"]), th2)["mean_crest_height_m"]
    depth = rim - floor_h
    out["shackleton"] = {
        "floor_mean_height_m": floor_h,
        "floor_radius_km": floor_radius_km,
        "floor_radius_km_published": z["floor_radius_km_expected"],
        "rim_mean_crest_height_m": rim,
        "rim_height_m_published": z["rim_height_m_expected"],
        "depth_m": depth,
        "depth_m_published": z["depth_m_expected"],
        "passed": bool(
            abs(floor_radius_km - z["floor_radius_km_expected"]) * 1000 <= z["floor_radius_tolerance_m"]
            and abs(rim - z["rim_height_m_expected"]) <= z["rim_height_tolerance_m"]
            and abs(depth - z["depth_m_expected"]) <= z["depth_tolerance_m"]
        ),
    }

    o = _overlap(dem20, dem60)
    t = th["overlap_20m_vs_60m"]
    o["passed"] = bool(abs(o["mean_difference_m"]) <= t["abs_mean_difference_m_max"] and o["median_abs_difference_m"] <= t["median_abs_difference_m_max"])
    out["overlap_20m_vs_60m"] = o

    cy16 = _ldem16_vs_polar(dem20, root)
    t = th["cylindrical_16ppd_vs_polar"]
    cy16["passed"] = bool(
        abs(cy16["mean_difference_m"]) <= t["abs_mean_difference_m_max"]
        and cy16["median_abs_difference_m"] <= t["median_abs_difference_m_max"]
        and cy16["p95_abs_difference_m"] <= t["p95_abs_difference_m_max"]
    )
    out["cylindrical_16ppd_vs_polar"] = cy16
    out["passed"] = all(out[k]["passed"] for k in ("label_min_max", "shackleton", "overlap_20m_vs_60m", "cylindrical_16ppd_vs_polar"))
    return out


def open_products(root: Path) -> tuple[PolarDEM, PolarDEM]:
    d20 = PolarDEM(raw_dir(root) / "LDEM_80S_20M" / "ldem_80s_20m.lbl", pyramid_dir=derived_dir(root) / "LDEM_80S_20M")
    d60 = PolarDEM(raw_dir(root) / "LDEM_60S_60M" / "ldem_60s_60m.lbl", pyramid_dir=derived_dir(root) / "LDEM_60S_60M")
    return d20, d60


def run_all(root: Path | None = None) -> dict:
    root = root or data_root()
    d20, d60 = open_products(root)
    c1 = checkpoint_1(root)
    c2 = checkpoint_2(d20)
    c3 = checkpoint_3(d20, d60, root, c2)
    return {
        "generated_utc": mf.utc_now(),
        "data_root": str(root),
        "checkpoint_1_checksums": c1,
        "checkpoint_2_georeferencing": c2,
        "checkpoint_3_values_and_reference_radius": c3,
        "all_passed": bool(c1["passed"] and c2["passed"] and c3["passed"]),
    }
