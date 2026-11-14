"""Checkpoints of the whole-Moon products and of the seams between products.

Criterion: data/checkpoints/thresholds_moon.json (committed before the first run).
Output: data/checkpoints/moon_report.json (``python -m lsn_data.moon_check``).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from . import catalog, checkpoints as cp, independent as ind, manifest as mf, open_moon
from .cylindrical import CylDEM, CylMosaic
from .dem import PolarDEM
from .paths import data_root, manifest_path, raw_dir, repo_data_dir

R_MOON = 1_737_400.0


def thresholds() -> dict:
    return json.loads((repo_data_dir() / "checkpoints" / "thresholds_moon.json").read_text(encoding="utf-8"))


# -- checkpoint 1 ---------------------------------------------------------------------------------
def checkpoint_1(root: Path, product_ids: list[str]) -> dict:
    m = mf.load(manifest_path())
    recs = {k: v for k, v in m["files"].items() if v["product_id"] and any(v["path"].split("/")[-2] == p for p in product_ids)}
    sub = {"files": recs}
    problems = mf.verify(sub, root)
    no_cross = [k for k, v in recs.items() if v["role"] == "data" and not any(c["matches"] for c in v.get("cross_checks", []))]
    bad = [k for k, v in recs.items() if any(not c["matches"] for c in v.get("cross_checks", []))]
    return {
        "files": sorted(recs),
        "problems": problems,
        "cross_check_failed": bad,
        "data_files_without_matching_cross_check": no_cross,
        "passed": bool(recs) and not problems and not bad and not no_cross,
    }


# -- checkpoint 2: cylindrical against laser returns ------------------------------------------------
def compare_rdr_cyl(mosaic: CylMosaic, files: list[Path], lat_lo: float, lat_hi: float, max_points=2_000_000, seed=ind.SEED) -> dict:
    lon, lat, rad = [], [], []
    for f in files:
        s = ind.read_rdr(f)
        ok = (s["flag"] == 0) & (s["lat"] >= lat_lo) & (s["lat"] <= lat_hi) & (s["radius_m"] > 1.7e6)
        lon.append(s["lon"][ok]); lat.append(s["lat"][ok]); rad.append(s["radius_m"][ok])
    lon, lat, rad = np.concatenate(lon), np.concatenate(lat), np.concatenate(rad)
    n_all = lon.size
    if n_all > max_points:
        pick = np.random.default_rng(seed).choice(n_all, max_points, replace=False)
        lon, lat, rad = lon[pick], lat[pick], rad[pick]
    px = mosaic.pixel_m(0)
    dlat = math.degrees(px / R_MOON)
    dlon = dlat / np.cos(np.radians(lat))
    h = mosaic.height_m(lon, lat)
    ge = (mosaic.height_m(lon + dlon, lat) - mosaic.height_m(lon - dlon, lat)) / (2 * px)
    gn = (mosaic.height_m(lon, lat + dlat) - mosaic.height_m(lon, lat - dlat)) / (2 * px)
    d = (rad - mosaic.reference_radius_m) - h
    dm = (rad - mosaic.reference_radius_m) - mosaic.height_m(-lon, lat)
    st = ind._stats(d)
    gl = np.hypot(ge, gn)
    d_max = 10.0 * px if mosaic.product_id == "LDEM_128" else 50.0
    use = np.isfinite(d) & (np.abs(d) <= d_max) & (gl >= 0.02) & (gl <= 0.5)
    A = np.column_stack([np.ones(use.sum()), ge[use], gn[use]])
    p, *_ = np.linalg.lstsq(A, d[use], rcond=None)
    blk = (np.floor(lat[use]).astype(np.int64) + 90) * 400 + np.floor(lon[use]).astype(np.int64)
    _, inv = np.unique(blk, return_inverse=True)
    nb = inv.max() + 1
    AtA = np.zeros((nb, 3, 3)); Atb = np.zeros((nb, 3))
    np.add.at(AtA, inv, A[:, :, None] * A[:, None, :])
    np.add.at(Atb, inv, A * d[use][:, None])
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(500):
        k = rng.integers(0, nb, nb)
        try:
            boots.append(np.linalg.solve(AtA[k].sum(0), Atb[k].sum(0)))
        except np.linalg.LinAlgError:
            pass
    se = np.array(boots).std(axis=0)
    mirror_rms = float(np.sqrt(np.nanmean(dm**2)))
    return {
        "ours": mosaic.product_id, "pixel_m": px, "latitude_band": [lat_lo, lat_hi],
        "spots_in_band": int(n_all), "spots_compared": int(lon.size), "stats": st,
        "fit": {"points_used": int(use.sum()), "blocks": int(nb), "height_offset_m": float(p[0]),
                "translation_east_m": float(p[1]), "translation_north_m": float(p[2]),
                "se": {"height_offset_m": float(se[0]), "translation_east_m": float(se[1]), "translation_north_m": float(se[2])}},
        "mirror_rms_m": mirror_rms, "mirror_rms_ratio": mirror_rms / st["rms_d_m"],
    }


def _judge_cyl(r: dict, crit: dict) -> dict:
    px = r["pixel_m"]
    checks = {
        "abs_mean_d_m": abs(r["stats"]["mean_d_m"]) <= crit["abs_mean_d_m"],
        "median_abs_d_m": r["stats"]["median_abs_d_m"] <= 0.1 * px + crit["median_abs_d_m_is_at_most_0.1_px_plus_m"],
        "translation_east": abs(r["fit"]["translation_east_m"]) <= crit["abs_translation_component_px"] * px,
        "translation_north": abs(r["fit"]["translation_north_m"]) <= crit["abs_translation_component_px"] * px,
        "mirror": r["mirror_rms_ratio"] >= crit["mirror_rms_ratio_at_least"],
    }
    return {"checks": checks, "passed": bool(all(checks.values()))}


# -- checkpoint 3 ---------------------------------------------------------------------------------
def _cyl_range(t: CylDEM) -> dict:
    arr = t._array(0, "mean")
    mn, mx = np.inf, -np.inf
    for i in range(0, arr.shape[0], 512):
        b = np.asarray(arr[i : i + 512])
        mn, mx = min(mn, float(b.min())), max(mx, float(b.max()))
    lab_min, lab_max = float(t.label["MINIMUM"]), float(t.label["MAXIMUM"])
    return {"measured_min": mn, "measured_max": mx, "label_minimum": lab_min, "label_maximum": lab_max,
            "measured_min_m": mn * t.scale, "measured_max_m": mx * t.scale,
            "passed": bool(lab_min - 1e-9 <= mn and mx <= lab_max + 1e-9),
            "max_abs_difference_to_label_m": float(max(abs(mn - lab_min), abs(mx - lab_max)) * t.scale),
            "note": "reported only: SLDEM2015 labels give MINIMUM/MAXIMUM rounded to 0.001 km, so up to 0.5 m outside is rounding"}


def _radius_ok(lab: dict) -> dict:
    unit = str(lab.get("UNIT", "METER")).upper()
    off_km = float(lab["OFFSET"]) / (1.0 if unit == "KILOMETER" else 1000.0)
    axes = [float(lab[k]) for k in ("A_AXIS_RADIUS", "B_AXIS_RADIUS", "C_AXIS_RADIUS")]
    return {"offset_km": off_km, "axes_km": axes, "passed": bool(all(abs(a - 1737.4) < 1e-9 for a in axes) and abs(off_km - 1737.4) < 1e-9)}


# -- seams ----------------------------------------------------------------------------------------
def _cyl_cell_means(mosaic: CylMosaic, lon_c, lat_c, dlat_deg, step_m=None):
    step_m = step_m or mosaic.pixel_m(0) / 2
    cell_h = math.radians(dlat_deg) * R_MOON
    n_lat = max(2, int(math.ceil(cell_h / step_m)))
    fl = (np.arange(n_lat) + 0.5) / n_lat - 0.5
    w = cell_h * np.cos(np.radians(lat_c))
    n_lon = np.maximum(2, np.ceil(w / step_m).astype(int))
    out = np.empty(lon_c.shape)
    for n in np.unique(n_lon):
        sel = np.nonzero(n_lon == n)[0]
        fo = (np.arange(n) + 0.5) / n - 0.5
        la = lat_c[sel, None, None] + fl[None, :, None] * dlat_deg
        lo = lon_c[sel, None, None] + fo[None, None, :] * dlat_deg
        la, lo = np.broadcast_arrays(la, lo)
        out[sel] = mosaic.height_m(lo, la).reshape(len(sel), -1).mean(axis=1)
    return out


def sldem_vs_ldem128(sldem: CylMosaic, l128: CylDEM, n=20_000, seed=ind.SEED) -> dict:
    g = l128.grid0
    rng = np.random.default_rng(seed)
    rows = np.arange(g.n_rows)
    _, lat_rows = g.rowcol_to_lonlat(rows, np.zeros_like(rows))
    rows = rows[np.abs(lat_rows) <= 55.0]
    _, lat_rows = g.rowcol_to_lonlat(rows, np.zeros_like(rows))
    p = np.cos(np.radians(lat_rows))
    r = rng.choice(rows, size=n, p=p / p.sum())
    c = rng.integers(0, g.n_cols, n)
    lon_c, lat_c = g.rowcol_to_lonlat(r, c)
    d = l128.values_at(r, c, 0, "mean") - _cyl_cell_means(sldem, lon_c, lat_c, 1.0 / g.res_ppd)
    return {"ours": sldem.product_id, "reference": l128.product_id, "cells": n, "stats": ind._stats(d)}


def _square_edge_points(dem: PolarDEM, n=2000, seed=ind.SEED):
    """Points on the outer edge of a polar square, with the outward normal (x, y metres)."""
    g = dem.grid0
    rng = np.random.default_rng(seed)
    side = rng.integers(0, 4, n)
    t = rng.uniform(g.x_ul_m, g.x_lr_m, n)
    x = np.where(side == 0, g.x_lr_m, np.where(side == 1, g.x_ul_m, t))
    y = np.where(side == 2, g.y_ul_m, np.where(side == 3, g.y_lr_m, t))
    nx = np.where(side == 0, 1.0, np.where(side == 1, -1.0, 0.0))
    ny = np.where(side == 2, 1.0, np.where(side == 3, -1.0, 0.0))
    return x, y, nx, ny


def continuity(moon, crit: dict) -> dict:
    from .georef import xy_to_lonlat

    out = {}
    for t in moon.polar:
        for dem in t.products:
            x, y, nx, ny = _square_edge_points(dem)
            li, ai = xy_to_lonlat(x - 0.5 * nx, y - 0.5 * ny, dem.grid0.radius_m, dem.grid0.pole)
            lo, ao = xy_to_lonlat(x + 0.5 * nx, y + 0.5 * ny, dem.grid0.radius_m, dem.grid0.pole)
            hi, ho = moon.height_m(li, ai), moon.height_m(lo, ao)
            si, so = moon.source(li, ai)[0], moon.source(lo, ao)[0]
            jump = np.abs(ho - hi)
            ok = np.isfinite(jump)
            out[f"edge_of_{dem.product_id}"] = {
                "points": int(ok.sum()), "inside_source": sorted(set(si)), "outside_source": sorted(set(so)),
                "median_abs_jump_m": float(np.median(jump[ok])), "p95_abs_jump_m": float(np.percentile(jump[ok], 95)),
                "passed": bool(np.median(jump[ok]) <= crit["median_abs_jump_m"] and np.percentile(jump[ok], 95) <= crit["p95_abs_jump_m"]),
            }
    for c in moon.cylindrical:
        if len(c.tiles) > 1:
            jumps = []
            rng = np.random.default_rng(ind.SEED)
            for t in c.tiles:
                g = t.grid0
                lat = rng.uniform(g.south_lat, g.north_lat, 500)
                for lon_e in (g.west_lon, g.east_lon):
                    d = np.degrees(0.5 / (R_MOON * np.cos(np.radians(lat))))
                    jumps.append(np.abs(c.height_m(lon_e + d, lat) - c.height_m(lon_e - d, lat)))
                lon = rng.uniform(g.west_lon, g.east_lon, 500)
                dd = math.degrees(0.5 / R_MOON)
                for lat_e in (g.south_lat, g.north_lat):
                    if abs(lat_e) < 59.99:
                        jumps.append(np.abs(c.height_m(lon, lat_e + dd) - c.height_m(lon, lat_e - dd)))
            j = np.concatenate(jumps)
            j = j[np.isfinite(j)]
            out[f"tile_seams_of_{c.product_id}"] = {"points": int(j.size), "max_abs_jump_m": float(j.max()), "passed": bool(j.max() <= 1.0)}
        # the outer +-60 deg edge of a 60S..60N mosaic
        lats = [t.grid0.south_lat for t in c.tiles] + [t.grid0.north_lat for t in c.tiles]
        if max(lats) < 89.0:
            rng = np.random.default_rng(ind.SEED + 1)
            lon = rng.uniform(0, 360, 2000)
            dd = math.degrees(0.5 / R_MOON)
            res = {}
            for edge in (min(lats), max(lats)):
                inner = edge + dd if edge < 0 else edge - dd
                outer = edge - dd if edge < 0 else edge + dd
                hi, ho = moon.height_m(lon, inner), moon.height_m(lon, outer)
                jump = np.abs(ho - hi)
                ok = np.isfinite(jump)
                res[f"{edge:+.0f}"] = {"points": int(ok.sum()), "outside_source": sorted(set(moon.source(lon, outer)[0])),
                                        "median_abs_jump_m": float(np.median(jump[ok])), "p95_abs_jump_m": float(np.percentile(jump[ok], 95))}
            res["passed"] = all(v["median_abs_jump_m"] <= crit["median_abs_jump_m"] and v["p95_abs_jump_m"] <= crit["p95_abs_jump_m"] for v in res.values())
            out[f"outer_edge_of_{c.product_id}"] = res
    return out


# -- all --------------------------------------------------------------------------------------------
def run(root: Path | None = None, candidates: tuple[str, ...] = ()) -> dict:
    """All whole-Moon checkpoints. ``candidates``: unapproved mosaics to include (they are evaluated, not approved)."""
    root = root or data_root()
    th = thresholds()
    moon = open_moon(root, candidates=tuple(candidates))
    rdr = [Path(root) / "raw" / "lola_rdr" / n / f"{n.lower()}.dat" for n in catalog.RDR_SAMPLE]
    # Deviation from thresholds_moon.json (criteria unchanged): the LRO_SM_06 files have no valid returns north of
    # 80.5 N and only ~3400 in 60.5-79.5 N, so the north-polar products are compared with the LRO_SM_06 files plus
    # 14 files of LRO_NO_08 (2010, near-circular orbit).
    rdr_north = rdr + [Path(root) / "raw" / "lola_rdr" / n / f"{n.lower()}.dat" for n in catalog.RDR_NORTH
                       if (Path(root) / "raw" / "lola_rdr" / n / f"{n.lower()}.dat").exists()]
    rep = {"generated_utc": mf.utc_now(), "criterion": "data/checkpoints/thresholds_moon.json", "coverage": moon.coverage(),
           "candidates_not_yet_approved": list(candidates)}
    north_ids = [p.product_id for t in moon.polar if t.pole > 0 for p in t.products]
    tile_ids = [t.product_id for c in moon.cylindrical for t in c.tiles]
    rep["checkpoint_1"] = checkpoint_1(root, north_ids + tile_ids + list(catalog.RDR_SAMPLE) + list(catalog.RDR_NORTH))
    rep["deviation"] = ("north-polar products compared with LRO_SM_06 plus LRO_NO_08 returns, selected with the validity rule "
                        "of LOLARDR.FMT (least significant byte of SHOT_FLAG = 0, bit 10 clear) instead of SHOT_FLAG = 0, "
                        "which leaves no returns north of 80.5 N; criteria unchanged")

    c2 = {}
    try:
        north = moon.polar_terrain(1)
    except KeyError:
        north = None
    if north is not None:
        crit = th["checkpoint_2_georeferencing"]["polar_north"]
        for dem in north.products:
            band = crit["regions"].get(dem.product_id)
            if band:
                r = ind.compare_rdr(dem, rdr_north, *band, rule="documented")
                r["judgement"] = ind._judge(r["stats"], r["fit"], r["mirror_rms_ratio"], crit["pass_if"])
                c2[dem.product_id] = r
    crit_c = th["checkpoint_2_georeferencing"]["cylindrical"]["pass_if_in_pixels"]
    for c in moon.cylindrical:
        r = compare_rdr_cyl(c, rdr, -59.5, 59.5)
        r["judgement"] = _judge_cyl(r, crit_c)
        c2[c.product_id] = r
        if c.product_id == "LDEM_128":
            r2 = compare_rdr_cyl(c, rdr, -89.5, 89.5)
            r2["judgement"] = {"reported_only": True, **_judge_cyl(r2, crit_c)}
            c2["LDEM_128_all_latitudes"] = r2
    rep["checkpoint_2"] = c2

    c3 = {"label_min_max": {}, "reference_radius": {}}
    for p in moon.products:
        files = p.tiles if isinstance(p, CylMosaic) else [p]
        for f in files:
            c3["reference_radius"][f.product_id] = _radius_ok(f.label)
            if isinstance(f, CylDEM):
                c3["label_min_max"][f.product_id] = _cyl_range(f)
            elif f.grid0.pole > 0:
                c3["label_min_max"][f.product_id] = cp._label_min_max(f)
    if north is not None and len(north.products) == 2:
        o = cp._overlap(*north.products)
        t = th["checkpoint_3_values_and_reference_radius"]["north_overlap_20m_vs_60m"]
        o["passed"] = bool(abs(o["mean_difference_m"]) <= t["abs_mean_difference_m_max"] and o["median_abs_difference_m"] <= t["median_abs_difference_m_max"])
        c3["north_overlap_20m_vs_60m"] = o
    sh = {c.product_id: c.height_m for c in moon.cylindrical}
    try:
        sh["LDEM_60S_60M"] = moon.product("LDEM_60S_60M").height_m
    except KeyError:
        pass
    sh["LDEM_16"] = CylMosaic([CylDEM(raw_dir(root) / "LDEM_16" / "ldem_16.lbl")]).height_m
    c3["published_spot_heights"] = ind.spot_heights(sh)
    rep["checkpoint_3"] = c3

    seams = {}
    l128 = next((t for c in moon.cylindrical if c.product_id == "LDEM_128" for t in c.tiles), None)
    if l128 is not None:
        crit = th["seams"]["polar_60m_vs_LDEM_128"]
        for pid, band in crit["bands"].items():
            try:
                dem = moon.product(pid)
            except KeyError:
                continue
            r = ind.compare_cylindrical(dem, l128, *band)
            r["judgement"] = ind._judge(r["stats"], r["fit"], r["mirror_rms_ratio"], crit["pass_if"])
            seams[f"{pid}_vs_LDEM_128"] = r
        for c in moon.cylindrical:
            if c.product_id.startswith("SLDEM"):
                r = sldem_vs_ldem128(c, l128)
                t = th["seams"]["SLDEM_vs_LDEM_128"]["pass_if"]
                r["passed"] = bool(abs(r["stats"]["mean_d_m"]) <= t["abs_mean_d_m"] and r["stats"]["median_abs_d_m"] <= t["median_abs_d_m"] and r["stats"]["p95_abs_d_m"] <= t["p95_abs_d_m"])
                seams[f"{c.product_id}_vs_LDEM_128"] = r
    seams["moon_terrain_continuity"] = continuity(moon, th["seams"]["moon_terrain_continuity"]["pass_if"])
    rep["seams"] = seams
    return rep


def main(argv: list[str] | None = None) -> None:
    import argparse

    ap = argparse.ArgumentParser(description="whole-Moon checkpoints (thresholds_moon.json)")
    ap.add_argument("--candidate", action="append", default=[], help="also evaluate this unapproved mosaic id; "
                    "the report then goes to moon_report_<id>.json and moon_report.json is left as it is")
    a = ap.parse_args(argv)
    rep = run(candidates=tuple(a.candidate))
    name = "moon_report.json" if not a.candidate else f"moon_report_{'_'.join(a.candidate)}.json"
    out = repo_data_dir() / "checkpoints" / name
    out.write_text(json.dumps(rep, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps(rep, indent=1, default=str)[:20000])


if __name__ == "__main__":
    main()
