"""The 5 m/pixel site DEMs (Barker et al. 2021) against our 20 m product, and the near-field layer's seam.

Criterion: data/checkpoints/thresholds_near_field.json (committed before the first comparison).
Output: data/checkpoints/near_field_report.json (``python -m lsn_data.near_field``).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import catalog, checkpoints as cp, geotiff as gt, independent as ind, manifest as mf, site_dems
from .dem import PolarDEM, Terrain
from .fetch import read_ranges
from .georef import xy_to_lonlat
from .height_error import SLOPE_CLASSES, _q
from .paths import data_root, manifest_path, repo_data_dir

LDEC_URLS = [
    "https://imbrium.mit.edu/DATA/LOLA_GDR/POLAR/IMG/LDEC_80S_20M.IMG",
    "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/img/ldec_80s_20m.img",
]


WHAT_IT_SHOWS = (
    "Both products are made from the same LOLA laser returns. The 5 m product re-adjusts the tracks (orbit errors "
    "reduced more than tenfold, page of PGDA product 78) and grids them at 5 m with its own interpolation; the 20 m "
    "product uses the original geolocation and GMT gridding at 20 m. CAN show: (1) differences in georeferencing "
    "between the two (the translation fit), (2) how much the 20 m gridding and interpolation depart from the better "
    "controlled 5 m surface, in particular at 20 m pixels without returns where the 5 m pixel has returns (class "
    "20m_interpolated__5m_constrained: the closest we have to a measurement of the 20 m interpolation error), (3) "
    "what the 20 m product cannot resolve below 20 m. CANNOT show: errors common to both (LOLA radial error, residual "
    "orbit error after adjustment, returns edited out of both), and in pixels interpolated in both products it "
    "compares two interpolations of the same returns, not a surface with the truth. The 5 m RMS error maps are the "
    "producers' model estimate (fractal clone ensemble, Barker et al. 2021), not a measurement against independent data."
)


def thresholds() -> dict:
    return json.loads((repo_data_dir() / "checkpoints" / "thresholds_near_field.json").read_text(encoding="utf-8"))


def ldec20_window(d20: PolarDEM, x0, y0, x1, y1) -> tuple[np.ndarray, int, int, int]:
    """Counts of LDEC_80S_20M over a box (by multipart byte ranges; every 50th row also read from PDS)."""
    g = d20.grid0
    c0 = int(np.floor((x0 - g.x_ul_m) / g.pixel_m))
    c1 = int(np.ceil((x1 - g.x_ul_m) / g.pixel_m))
    r0 = int(np.floor((g.y_ul_m - y0) / g.pixel_m))
    r1 = int(np.ceil((g.y_ul_m - y1) / g.pixel_m))
    rg = [(r * g.n_cols + c0, r * g.n_cols + c1 - 1) for r in range(r0, r1)]
    rows = read_ranges(LDEC_URLS[0], rg)
    check = rg[::50]
    other = read_ranges(LDEC_URLS[1], check)
    mine = rows[::50]
    if other != mine:
        raise ValueError("LDEC_80S_20M: the two mirrors disagree")
    return np.array([np.frombuffer(b, dtype=np.uint8) for b in rows]), r0, c0, len(check)


def _box_mean(a: np.ndarray, k: int) -> np.ndarray:
    """k x k moving mean (same shape, NaN at the border)."""
    c = np.nancumsum(np.nancumsum(np.pad(a, ((1, 0), (1, 0))), 0), 1)
    out = np.full(a.shape, np.nan)
    h = k // 2
    s = (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)
    out[h : h + s.shape[0], h : h + s.shape[1]] = s
    return out


def compare_site(d20: PolarDEM, d5: PolarDEM, count5: np.ndarray, err5: np.ndarray, site_xy, th: dict) -> dict:
    g5 = d5.grid0
    a5 = np.asarray(d5._array(0, "mean"), dtype=np.float64)
    rows = np.arange(2, g5.n_rows - 2, 4)
    cols = np.arange(2, g5.n_cols - 2, 4)
    R, C = np.meshgrid(rows, cols, indexing="ij")
    x, y = g5.rowcol_to_xy(R, C)
    h5 = a5[R, C]
    h20 = d20.height_xy(x, y)
    d = h20 - h5
    sm = _box_mean(a5, 4)
    gx = (sm[R, np.minimum(C + 4, g5.n_cols - 1)] - sm[R, np.maximum(C - 4, 0)]) / 40.0
    gy = (sm[np.maximum(R - 4, 0), C] - sm[np.minimum(R + 4, g5.n_rows - 1), C]) / 40.0
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    lon, lat = xy_to_lonlat(x, y, g5.radius_m, g5.pole)
    from .georef import lonlat_to_xy

    xm, ym = lonlat_to_xy(-lon, lat, g5.radius_m, g5.pole)
    dm = d20.height_xy(xm, ym) - h5
    ok = np.isfinite(d) & np.isfinite(gx) & np.isfinite(gy)
    st = ind._stats(d[ok])
    fit = _fit(d[ok], np.column_stack([gx[ok], gy[ok]]), np.column_stack([x[ok], y[ok]]))
    mirror = float(np.sqrt(np.nanmean(dm**2)))
    # counts: the 20 m pixel containing each point, and any 5 m return inside that 20 m pixel
    g20 = d20.grid0
    r20 = np.floor((g20.y_ul_m - y) / g20.pixel_m).astype(int)
    c20 = np.floor((x - g20.x_ul_m) / g20.pixel_m).astype(int)
    x0, y0, x1, y1 = g5.x_ul_m, g5.y_ul_m, g5.x_lr_m, g5.y_lr_m
    if getattr(d20, "_q_count", None) is not None:
        n20 = np.asarray(d20._q_count[r20, c20]).astype(int)
        n_checked = "full LDEC_80S_20M file (manifest SHA-256)"
    else:
        ldec, rr0, cc0, n_checked = ldec20_window(d20, x0, y0, x1, y1)
        n20 = ldec[r20 - rr0, c20 - cc0]
    # 5 m pixels of that 20 m pixel: 20 m pixel edges are multiples of 20 m from the 20 m corner (aligned with 5 m)
    xe = g20.x_ul_m + c20 * g20.pixel_m
    ye = g20.y_ul_m - r20 * g20.pixel_m
    c5 = np.round((xe - g5.x_ul_m) / g5.pixel_m).astype(int)
    r5 = np.round((g5.y_ul_m - ye) / g5.pixel_m).astype(int)
    has5 = np.zeros(R.shape, dtype=bool)
    for dr in range(4):
        for dc in range(4):
            rr = np.clip(r5 + dr, 0, g5.n_rows - 1)
            cc = np.clip(c5 + dc, 0, g5.n_cols - 1)
            has5 |= count5[rr, cc] > 0
    classes = {
        "count20_ge1": ok & (n20 >= 1),
        "count20_0": ok & (n20 == 0),
        "count20_0_and_5m_returns_present": ok & (n20 == 0) & has5,
        "count20_0_and_no_5m_returns": ok & (n20 == 0) & ~has5,
    }
    split = {}
    for name, m in classes.items():
        split[name] = {"all": _q(d[m]), **{f"slope_{lo}_{hi}_deg": _q(d[m & (slope >= lo) & (slope < hi)]) for lo, hi in SLOPE_CLASSES}}
    # post hoc (requested after the criterion was written): 2 x 2 by the status of each product's own pixel
    c5 = count5[R, C] > 0
    both = {
        "20m_constrained__5m_constrained": ok & (n20 >= 1) & c5,
        "20m_constrained__5m_interpolated": ok & (n20 >= 1) & ~c5,
        "20m_interpolated__5m_constrained": ok & (n20 == 0) & c5,
        "20m_interpolated__5m_interpolated": ok & (n20 == 0) & ~c5,
    }
    split_pixels = {k: {"all": _q(d[m]), **{f"slope_{lo}_{hi}_deg": _q(d[m & (slope >= lo) & (slope < hi)]) for lo, hi in SLOPE_CLASSES}}
                    for k, m in both.items()}
    # 5 m product's own RMS error within 1 km of the site record
    sx, sy = site_xy
    rr, cc = np.mgrid[0 : g5.n_rows : 2, 0 : g5.n_cols : 2]
    ex, ey = g5.rowcol_to_xy(rr, cc)
    dist = np.hypot(ex - sx, ey - sy)
    near = dist <= 1000.0
    e_near = err5[rr[near], cc[near]]
    err_rings = {}
    for rad in (500.0, 1000.0, 2000.0):
        m = dist <= rad
        e = np.asarray(err5[rr[m], cc[m]], dtype=float)
        k = np.asarray(count5[rr[m], cc[m]]) > 0
        err_rings[f"within_{int(rad)}_m"] = {
            "pixels": int(m.sum()), "fraction_constrained": float(k.mean()),
            "median_m": float(np.nanmedian(e)), "p95_m": float(np.nanpercentile(e, 95)),
            "median_m_constrained": float(np.nanmedian(e[k])) if k.any() else None,
            "median_m_interpolated": float(np.nanmedian(e[~k])) if (~k).any() else None,
            "inside_extent": bool(rad <= min(sx - x0, x1 - sx, y0 - sy, sy - y1)),
        }
    crit2 = th["checkpoint_2_georeferencing"]
    crit3 = th["checkpoint_3_values"]["pass_if"]
    checks = {
        "translation_x": abs(fit["translation_x_m"]) <= crit2["pass_if"]["abs_translation_component_m"],
        "translation_y": abs(fit["translation_y_m"]) <= crit2["pass_if"]["abs_translation_component_m"],
        "rotation": abs(fit["rotation_deg"]) <= crit2["pass_if"]["abs_rotation_deg"],
        "mirror": mirror / st["rms_d_m"] >= crit2["mirror_rms_ratio_at_least"],
        "abs_mean_d_m": abs(st["mean_d_m"]) <= crit3["abs_mean_d_m"],
        "median_abs_d_m": st["median_abs_d_m"] <= crit3["median_abs_d_m"],
    }
    return {
        "product": d5.product_id,
        "extent_m": {"x": [x0, x1], "y": [y1, y0]},
        "points": int(ok.sum()),
        "d_is": "h(LDEM_80S_20M, bilinear) - h(5 m pixel)",
        "stats": st,
        "fit": fit,
        "mirror_rms_m": mirror,
        "mirror_rms_ratio": mirror / st["rms_d_m"],
        "checks": checks,
        "passed": bool(all(checks.values())),
        "fraction_of_points_in_20m_pixels_without_returns": float(np.mean(n20[ok] == 0)),
        "fraction_of_5m_pixels_with_returns": float(np.mean(count5 > 0)),
        "ldec20_rows_compared_between_mirrors": n_checked,
        "split_by_counts": split,
        "split_by_each_products_pixel_post_hoc": split_pixels,
        "rms_error_map_near_site": err_rings,
        "own_rms_error_within_1km_of_site": {"median_m": float(np.nanmedian(e_near)), "p95_m": float(np.nanpercentile(e_near, 95)),
                                             "two_sigma_m": 2.0 * float(np.nanmedian(e_near))},
    }


def _fit(d, g, r):
    """Displacement fit with this criterion's limits (|d| <= 30 m, 0.02 <= |g| <= 0.7, 1 km blocks)."""
    return ind.fit_displacement(d, g, r, block_m=1000.0, d_max=30.0, g_min=0.02, g_max=0.7)


def seam(t: Terrain, d5: PolarDEM, crit: dict, n=2000) -> dict:
    from .moon_check import _square_edge_points

    x, y, nx, ny = _square_edge_points(d5, n)
    li, ai = xy_to_lonlat(x - 0.5 * nx, y - 0.5 * ny, d5.grid0.radius_m, d5.grid0.pole)
    lo, ao = xy_to_lonlat(x + 0.5 * nx, y + 0.5 * ny, d5.grid0.radius_m, d5.grid0.pole)
    hi, ho = t.height_m(li, ai), t.height_m(lo, ao)
    si, so = t.source(li, ai)[0], t.source(lo, ao)[0]
    j = np.abs(ho - hi)
    ok = np.isfinite(j)
    return {"points": int(ok.sum()), "inside_sources": sorted(set(si)), "outside_sources": sorted(set(so)),
            "median_abs_jump_m": float(np.median(j[ok])), "p95_abs_jump_m": float(np.percentile(j[ok], 95)),
            "passed": bool(np.median(j[ok]) <= crit["median_abs_jump_m"] and np.percentile(j[ok], 95) <= crit["p95_abs_jump_m"])}


def checkpoint_1(root: Path) -> dict:
    m = mf.load(manifest_path())
    recs = {k: v for k, v in m["files"].items() if "/lola_5mpp/" in "/" + k}
    problems = mf.verify({"files": recs}, root)
    return {"files": sorted(recs), "problems": problems, "second_source": "none exists (PGDA is the only host); ETag and Last-Modified recorded",
            "etags": {k: v.get("http_etag") for k, v in recs.items()}, "passed": bool(recs) and not problems}


def run(root=None) -> dict:
    root = Path(root or data_root())
    th = thresholds()
    d20, d60 = cp.open_products(root)
    sites = {s["site_id"]: (s["polar_stereographic_x_m"], s["polar_stereographic_y_m"])
             for s in json.loads((repo_data_dir() / "sites" / "sites.json").read_text(encoding="utf-8"))["sites"]}
    which = {"LOLA5MPP_SITE04": "shackleton_rim_crest", "LOLA5MPP_SITE11": "de_gerlache_rim_crest", "LOLA5MPP_SITE23": "malapert_massif_summit"}
    from . import attach_counts

    attach_counts(d20, root)
    rep = {"generated_utc": mf.utc_now(), "criterion": "data/checkpoints/thresholds_near_field.json",
           "checkpoint_1": checkpoint_1(root), "sites": {},
           "what_this_can_and_cannot_show": WHAT_IT_SHOWS}
    dems = site_dems(root, include_unapproved=True)  # the check evaluates every layer, approved or not
    t = Terrain([d20, d60] + dems)
    for d5 in dems:
        site = d5.product_id.split("_", 1)[1].capitalize()
        base = root / "raw" / "lola_5mpp" / d5.product_id
        cnt = gt.open_array(base / f"{site}_final_adj_5mpp_ldec.tif")
        err = gt.open_array(base / f"{site}_final_adj_5mpp_toterr.tif")
        for name, f in (("ldec", base / f"{site}_final_adj_5mpp_ldec.tif"), ("toterr", base / f"{site}_final_adj_5mpp_toterr.tif")):
            gi = gt.read_header(f)
            if (gi.width, gi.height, gi.tiepoint, gi.pixel_scale) != (d5.grid0.n_cols, d5.grid0.n_rows, gt.read_header(d5.data_path).tiepoint, gt.read_header(d5.data_path).pixel_scale):
                raise ValueError(f"{f.name} is not on the grid of the height file")
        r = compare_site(d20, d5, np.asarray(cnt), np.asarray(err), sites[which[d5.product_id]], th)
        r["site_record"] = which[d5.product_id]
        r["nan_pixels"] = int(np.isnan(np.asarray(d5._array(0, "mean"))).sum())
        r["seam"] = seam(t, d5, th["seam"]["pass_if"])
        rep["sites"][d5.product_id] = r
    rep["all_passed"] = bool(rep["sites"]) and all(v["passed"] and v["seam"]["passed"] for v in rep["sites"].values())
    return rep


def main() -> None:
    rep = run()
    out = repo_data_dir() / "checkpoints" / "near_field_report.json"
    out.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(rep, indent=1)[:6000])


if __name__ == "__main__":
    main()
