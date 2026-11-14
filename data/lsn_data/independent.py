"""Independent checks of the polar products and of the mapping in :mod:`lsn_data.georef`.

Criterion: data/checkpoints/thresholds_independent.json (committed before the first run).
Output: data/checkpoints/independent_report.json.

A. Cylindrical grids (LDEM_128, LDEM_16): another LOLA product in another projection, whose mapping is a linear
   function of latitude and longitude. Each cylindrical cell is compared with the mean of our polar product over the
   same latitude/longitude cell.
B. LOLA RDR laser returns: individual measurements with their own latitude, longitude and radius.

Both fit the displacement model d = c + g . (T + delta z x r + eps r) described in the criterion file.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from . import catalog, checkpoints as cp, manifest as mf
from .cylindrical import CylDEM, CylMosaic
from .dem import PolarDEM
from .georef import lonlat_to_xy
from .paths import data_root, raw_dir, repo_data_dir

SEED = 20261114


def thresholds() -> dict:
    return json.loads((repo_data_dir() / "checkpoints" / "thresholds_independent.json").read_text(encoding="utf-8"))


# -- displacement fit -------------------------------------------------------------------------------
def _design(g, r):
    gx, gy = g[:, 0], g[:, 1]
    x, y = r[:, 0], r[:, 1]
    return np.column_stack([np.ones_like(gx), gx, gy, gx * (-y) + gy * x, gx * x + gy * y])


def fit_displacement(d, g, r, block_m=10_000.0, n_boot=500, seed=SEED, d_max=50.0, g_min=0.02, g_max=0.5) -> dict:
    """Least squares of d = c + g.(T + delta z x r + eps r) with block-bootstrap standard errors."""
    gl = np.hypot(g[:, 0], g[:, 1])
    use = np.isfinite(d) & np.isfinite(gl) & (np.abs(d) <= d_max) & (gl >= g_min) & (gl <= g_max)
    d, g, r = d[use], g[use], r[use]
    A = _design(g, r)
    p, *_ = np.linalg.lstsq(A, d, rcond=None)
    bx = np.floor(r[:, 0] / block_m).astype(np.int64)
    by = np.floor(r[:, 1] / block_m).astype(np.int64)
    _, blk = np.unique(bx * 1_000_003 + by, return_inverse=True)
    nb = blk.max() + 1
    order = np.argsort(blk, kind="stable")
    starts = np.searchsorted(blk[order], np.arange(nb))
    ends = np.append(starts[1:], len(blk))
    # per-block normal equations, so that each bootstrap resample is a sum of blocks
    AtA = np.zeros((nb, 5, 5))
    Atb = np.zeros((nb, 5))
    for i in range(nb):
        idx = order[starts[i] : ends[i]]
        Ai = A[idx]
        AtA[i] = Ai.T @ Ai
        Atb[i] = Ai.T @ d[idx]
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        pick = rng.integers(0, nb, nb)
        try:
            boots.append(np.linalg.solve(AtA[pick].sum(0), Atb[pick].sum(0)))
        except np.linalg.LinAlgError:
            continue
    se = np.array(boots).std(axis=0)
    res = d - A @ p
    return {
        "points_used": int(use.sum()),
        "blocks": int(nb),
        "height_offset_m": float(p[0]),
        "translation_x_m": float(p[1]),
        "translation_y_m": float(p[2]),
        "rotation_deg": float(np.degrees(p[3])),
        "radial_scale": float(p[4]),
        "se": {
            "height_offset_m": float(se[0]),
            "translation_x_m": float(se[1]),
            "translation_y_m": float(se[2]),
            "rotation_deg": float(np.degrees(se[3])),
            "radial_scale": float(se[4]),
        },
        "residual_rms_m": float(np.sqrt(np.mean(res**2))),
    }


def _stats(d) -> dict:
    a = np.abs(d[np.isfinite(d)])
    return {
        "n": int(a.size),
        "mean_d_m": float(np.nanmean(d)),
        "median_abs_d_m": float(np.median(a)),
        "p95_abs_d_m": float(np.percentile(a, 95)),
        "rms_d_m": float(np.sqrt(np.mean(a**2))),
    }


def _judge(stats: dict, fit: dict, mirror_ratio: float, crit: dict | None) -> dict:
    if not crit:
        return {"criterion": None, "passed": None}
    checks = {
        "abs_mean_d_m": abs(stats["mean_d_m"]) <= crit["abs_mean_d_m"],
        "median_abs_d_m": stats["median_abs_d_m"] <= crit["median_abs_d_m"],
        "translation_x": abs(fit["translation_x_m"]) <= crit["abs_translation_component_m"],
        "translation_y": abs(fit["translation_y_m"]) <= crit["abs_translation_component_m"],
        "rotation": abs(fit["rotation_deg"]) <= crit["abs_rotation_deg"],
        "radial_scale": abs(fit["radial_scale"]) <= crit["abs_radial_scale"],
        "radial_scale_se": fit["se"]["radial_scale"] <= crit["radial_scale_se_at_most"],
        "mirror": mirror_ratio >= crit["mirror_rms_ratio_at_least"],
    }
    if "p95_abs_d_m" in crit:
        checks["p95_abs_d_m"] = stats["p95_abs_d_m"] <= crit["p95_abs_d_m"]
    return {"criterion": crit, "checks": checks, "passed": bool(all(checks.values()))}


# -- A: cylindrical cells ---------------------------------------------------------------------------
def _cell_means(dem: PolarDEM, lon_c, lat_c, dlat_deg, step_m=10.0, shift_xy=(0.0, 0.0), mirror=False):
    """Mean of our product over each latitude/longitude cell (centre lon_c, lat_c, size dlat_deg square in degrees)."""
    R = dem.grid0.radius_m
    cell_h = math.radians(dlat_deg) * R
    n_lat = max(2, int(math.ceil(cell_h / step_m)))
    out = np.empty(lon_c.shape)
    # group by number of longitude sub-samples (depends on latitude)
    w = cell_h * np.cos(np.radians(lat_c))
    n_lon = np.maximum(2, np.ceil(w / step_m).astype(int))
    fl = (np.arange(n_lat) + 0.5) / n_lat - 0.5
    for n in np.unique(n_lon):
        sel = np.nonzero(n_lon == n)[0]
        fo = (np.arange(n) + 0.5) / n - 0.5
        la = lat_c[sel, None, None] + fl[None, :, None] * dlat_deg
        lo = lon_c[sel, None, None] + fo[None, None, :] * dlat_deg
        la, lo = np.broadcast_arrays(la, lo)
        if mirror:
            lo = -lo
        x, y = lonlat_to_xy(lo, la, R, dem.grid0.pole)
        h = dem.height_xy(x + shift_xy[0], y + shift_xy[1])
        out[sel] = h.reshape(len(sel), -1).mean(axis=1)
    return out


def compare_cylindrical(dem: PolarDEM, cyl: CylDEM, lat_lo: float, lat_hi: float, n: int = 20_000, seed=SEED) -> dict:
    g = cyl.grid0
    rng = np.random.default_rng(seed)
    # rows whose centre latitude lies inside [lat_lo, lat_hi]; draw with probability proportional to cos(lat)
    rows = np.arange(g.n_rows)
    _, lat_rows = g.rowcol_to_lonlat(rows, np.zeros_like(rows))
    rows = rows[(lat_rows >= lat_lo) & (lat_rows <= lat_hi)]
    _, lat_rows = g.rowcol_to_lonlat(rows, np.zeros_like(rows))
    p = np.cos(np.radians(lat_rows))
    r = rng.choice(rows, size=n, p=p / p.sum())
    c = rng.integers(0, g.n_cols, n)
    lon_c, lat_c = g.rowcol_to_lonlat(r, c)
    h_ref = cyl.values_at(r, c, 0, "mean")
    dlat = 1.0 / g.res_ppd
    ours = _cell_means(dem, lon_c, lat_c, dlat)
    px = dem.grid0.pixel_m
    gx = (_cell_means(dem, lon_c, lat_c, dlat, shift_xy=(px, 0)) - _cell_means(dem, lon_c, lat_c, dlat, shift_xy=(-px, 0))) / (2 * px)
    gy = (_cell_means(dem, lon_c, lat_c, dlat, shift_xy=(0, px)) - _cell_means(dem, lon_c, lat_c, dlat, shift_xy=(0, -px))) / (2 * px)
    mir = _cell_means(dem, lon_c, lat_c, dlat, mirror=True)
    d = h_ref - ours
    xy = np.column_stack(lonlat_to_xy(lon_c, lat_c, dem.grid0.radius_m, dem.grid0.pole))
    st = _stats(d)
    fit = fit_displacement(d, np.column_stack([gx, gy]), xy)
    dm = h_ref - mir
    mirror_rms = float(np.sqrt(np.nanmean(dm**2)))
    return {
        "ours": dem.product_id,
        "reference": cyl.product_id,
        "reference_version": cyl.product_version,
        "latitude_band": [lat_lo, lat_hi],
        "cells": n,
        "stats": st,
        "fit": fit,
        "mirror_rms_m": mirror_rms,
        "mirror_rms_ratio": mirror_rms / st["rms_d_m"],
    }


# -- B: LOLA RDR shots ------------------------------------------------------------------------------
def read_rdr(path: Path) -> dict:
    """Spots of one LOLA RDR file (LOLARDR.FMT: 256-byte records, 5 spots of 40 bytes from byte 41)."""
    raw = np.fromfile(path, dtype=np.uint8)
    if raw.size % 256:
        raise ValueError(f"{path.name}: size is not a multiple of 256")
    rec = raw.reshape(-1, 256)
    lon, lat, rad, flag = [], [], [], []
    for k in range(5):
        o = 40 + 40 * k
        lon.append(rec[:, o : o + 4].copy().view("<i4")[:, 0])
        lat.append(rec[:, o + 4 : o + 8].copy().view("<i4")[:, 0])
        rad.append(rec[:, o + 8 : o + 12].copy().view("<i4")[:, 0])
        flag.append(rec[:, o + 36 : o + 40].copy().view("<u4")[:, 0])
    lon = np.concatenate(lon) * 1e-7
    lat = np.concatenate(lat) * 1e-7
    rad = np.concatenate(rad) * 1e-3
    flag = np.concatenate(flag)
    return {"lon": np.mod(lon, 360.0), "lat": lat, "radius_m": rad, "flag": flag}


def compare_rdr(dem: PolarDEM, files: list[Path], lat_lo: float, lat_hi: float, max_points: int = 2_000_000, seed=SEED) -> dict:
    lon, lat, rad = [], [], []
    for f in files:
        s = read_rdr(f)
        ok = (s["flag"] == 0) & (s["lat"] >= lat_lo) & (s["lat"] <= lat_hi) & (s["radius_m"] > 1.7e6)
        lon.append(s["lon"][ok])
        lat.append(s["lat"][ok])
        rad.append(s["radius_m"][ok])
    lon, lat, rad = np.concatenate(lon), np.concatenate(lat), np.concatenate(rad)
    n_all = lon.size
    if n_all < 100:
        raise ValueError(f"only {n_all} valid returns in {lat_lo}..{lat_hi} for {dem.product_id}")
    if n_all > max_points:
        pick = np.random.default_rng(seed).choice(n_all, max_points, replace=False)
        lon, lat, rad = lon[pick], lat[pick], rad[pick]
    R = dem.grid0.radius_m
    x, y = lonlat_to_xy(lon, lat, R, dem.grid0.pole)
    h = dem.height_xy(x, y)
    px = dem.grid0.pixel_m
    gx = (dem.height_xy(x + px, y) - dem.height_xy(x - px, y)) / (2 * px)
    gy = (dem.height_xy(x, y + px) - dem.height_xy(x, y - px)) / (2 * px)
    xm, ym = lonlat_to_xy(-lon, lat, R, dem.grid0.pole)
    hm = dem.height_xy(xm, ym)
    d = (rad - dem.reference_radius_m) - h
    st = _stats(d)
    fit = fit_displacement(d, np.column_stack([gx, gy]), np.column_stack([x, y]))
    dm = (rad - dem.reference_radius_m) - hm
    mirror_rms = float(np.sqrt(np.nanmean(dm**2)))
    return {
        "ours": dem.product_id,
        "reference": "LOLA RDR returns, " + ", ".join(f.stem.upper() for f in files),
        "latitude_band": [lat_lo, lat_hi],
        "spots_in_band": int(n_all),
        "spots_compared": int(lon.size),
        "stats": st,
        "fit": fit,
        "mirror_rms_m": mirror_rms,
        "mirror_rms_ratio": mirror_rms / st["rms_d_m"],
    }


def run(root: Path | None = None) -> dict:
    root = root or data_root()
    th = thresholds()
    d20, d60 = cp.open_products(root)
    out = {"generated_utc": mf.utc_now(), "criterion": "data/checkpoints/thresholds_independent.json", "results": {}}
    have128 = (raw_dir(root) / "LDEM_128" / "ldem_128.img").exists()
    l128 = CylDEM(raw_dir(root) / "LDEM_128" / "ldem_128.lbl") if have128 else None
    l16 = CylDEM(raw_dir(root) / "LDEM_16" / "ldem_16.lbl")
    crit_a = th["A_cylindrical_LDEM_128"]["pass_if"]
    for name, dem, cyl, band, crit in (
        ("A_LDEM_80S_20M_vs_LDEM_128", d20, l128, (-89.5, -80.5), crit_a),
        ("A_LDEM_60S_60M_vs_LDEM_128", d60, l128, (-79.5, -60.5), crit_a),
        ("A2_LDEM_80S_20M_vs_LDEM_16", d20, l16, (-89.5, -80.5), None),
        ("A2_LDEM_60S_60M_vs_LDEM_16", d60, l16, (-79.5, -60.5), None),
    ):
        if cyl is None:
            out["results"][name] = {"pending": "LDEM_128 is not downloaded yet", "judgement": {"criterion": crit, "passed": None}}
            continue
        # A2 (LDEM_16, reported only): 5 000 cells instead of 20 000, because a 1.9 km cell needs ~40x more samples
        r = compare_cylindrical(dem, cyl, *band, n=20_000 if crit else 5_000)
        r["judgement"] = _judge(r["stats"], r["fit"], r["mirror_rms_ratio"], crit)
        out["results"][name] = r
    rdr = [Path(root) / "raw" / "lola_rdr" / n / f"{n.lower()}.dat" for n in catalog.RDR_SAMPLE]
    crit_b = th["B_lola_rdr_shots"]["pass_if"]
    for name, dem, band in (("B_LDEM_80S_20M_vs_RDR", d20, (-89.8, -80.5)), ("B_LDEM_60S_60M_vs_RDR", d60, (-79.5, -60.5))):
        r = compare_rdr(dem, rdr, *band)
        r["judgement"] = _judge(r["stats"], r["fit"], r["mirror_rms_ratio"], crit_b)
        out["results"][name] = r
    sh = {"LDEM_16": CylMosaic([l16]).height_m, "LDEM_60S_60M": d60.height_m}
    if l128 is not None:
        sh["LDEM_128"] = CylMosaic([l128]).height_m
    out["spot_heights"] = spot_heights(sh)
    judged = [v["judgement"]["passed"] for v in out["results"].values() if v["judgement"]["criterion"] is not None]
    out["complete"] = None not in judged
    out["all_with_criterion_passed"] = bool(all(j for j in judged if j is not None)) and out["spot_heights"]["passed"]
    return out




# -- C: published spot heights -------------------------------------------------------------------
def _disc_lonlat(lon0, lat0, radius_km=5.0, step_m=250.0, R=1_737_400.0):
    """Points of a 250 m grid within ``radius_km`` of (lon0, lat0) on the sphere (local east/north metres)."""
    n = int(radius_km * 1000 // step_m)
    e, nn = np.meshgrid(np.arange(-n, n + 1) * step_m, np.arange(-n, n + 1) * step_m)
    keep = np.hypot(e, nn) <= radius_km * 1000
    e, nn = e[keep], nn[keep]
    lat = lat0 + np.degrees(nn / R)
    lon = lon0 + np.degrees(e / (R * np.cos(np.radians(lat0))))
    return lon, lat, np.hypot(e, nn)


def spot_heights(products: dict) -> dict:
    """``products``: {name: callable(lon, lat) -> heights in m}. Criterion: thresholds_spot_heights.json."""
    th = json.loads((repo_data_dir() / "checkpoints" / "thresholds_spot_heights.json").read_text(encoding="utf-8"))
    crit = th["pass_if"]
    out = {"criterion": "data/checkpoints/thresholds_spot_heights.json", "points": []}
    for pt in th["points"]:
        lon0, lat0, h0 = pt["lon_deg_east"], pt["lat_deg"], pt["height_m"]
        lon, lat, dist = _disc_lonlat(lon0, lat0)
        res = {"name": pt["name"], "published_m": h0, "products": {}}
        for name, f in products.items():
            hp = float(np.asarray(f(lon0, lat0)))
            if not np.isfinite(hp):
                continue
            h = np.asarray(f(lon, lat), dtype=float)
            i = int(np.nanargmax(h) if pt["extremum"] == "max" else np.nanargmin(h))
            r = {
                "at_point_m": hp,
                "point_difference_m": hp - h0,
                "extreme_m": float(h[i]),
                "extreme_difference_m": float(h[i] - h0),
                "extreme_distance_km": float(dist[i] / 1000),
            }
            r["passed"] = bool(
                abs(r["extreme_difference_m"]) <= crit["abs_extreme_difference_m"]
                and r["extreme_distance_km"] <= crit["extreme_within_km"]
                and abs(r["point_difference_m"]) <= crit["abs_point_difference_m"]
            )
            res["products"][name] = r
        out["points"].append(res)
    out["passed"] = all(r["passed"] for p in out["points"] for r in p["products"].values())
    return out


def main() -> None:
    rep = run()
    path = repo_data_dir() / "checkpoints" / "independent_report.json"
    path.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
