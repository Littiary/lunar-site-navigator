"""Georeferencing check against the Robbins crater catalogue.

Criterion: data/checkpoints/thresholds_catalogue.json (committed before the first measurement).
Output: data/checkpoints/catalogue_report.json. The catalogue was measured on LROC, LOLA and Kaguya TC
products in a LOLA control net, so this tests our reading of the files, not the absolute frame.
"""

from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path

import numpy as np

from . import checkpoints as c
from . import manifest as mf
from .georef import lonlat_to_xy
from .paths import data_root, repo_data_dir

CSV_IN_ZIP = "lunar_crater_database_robbins_2018_bundle/data/lunar_crater_database_robbins_2018.csv"


def thresholds() -> dict:
    return json.loads((repo_data_dir() / "checkpoints" / "thresholds_catalogue.json").read_text(encoding="utf-8"))


def load_selection(root: Path, th: dict) -> list[dict]:
    zpath = root / "raw" / "catalogs" / "ROBBINS_2018" / "lunar_crater_database_robbins_2018.zip"
    out = []
    with zipfile.ZipFile(zpath) as z, z.open(CSV_IN_ZIP) as raw:
        rd = csv.DictReader((line.decode("ascii") for line in raw))
        for d in rd:
            lat = float(d["LAT_CIRC_IMG"])
            if lat > -80.5:
                continue
            D = float(d["DIAM_CIRC_IMG"])
            if not (2.0 <= D < 16.0):
                continue
            if float(d["DIAM_ELLI_ELLIP_IMG"]) > 1.1 or float(d["ARC_IMG"]) < 0.8 or float(d["DIAM_CIRC_SD_IMG"]) / D > 0.03:
                continue
            out.append({"id": d["CRATER_ID"], "lat": lat, "lon": float(d["LON_CIRC_IMG"]), "D_km": D})
    return out


def _circle_fit(x, y):
    A = np.column_stack([2 * x, 2 * y, np.ones_like(x)])
    b = x**2 + y**2
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy = sol[0], sol[1]
    r = np.sqrt(max(sol[2] + cx**2 + cy**2, 0.0))
    return cx, cy, r


def fit_crater(dem, cr: dict) -> dict | None:
    x0, y0 = lonlat_to_xy(cr["lon"], cr["lat"], dem.grid0.radius_m, dem.grid0.pole)
    x0, y0 = float(x0), float(y0)
    colat = np.radians(90.0 + cr["lat"])
    k = 1.0 / np.cos(colat / 2.0) ** 2
    a = cr["D_km"] * 500.0 * k
    dist = np.hypot(x0, y0)
    if dist + 1.5 * a > 300_000.0:
        return None
    az = np.radians(np.arange(0, 360, 5.0))
    s = np.arange(0.75 * a, 1.25 * a + 1e-9, 10.0)
    px = x0 + np.cos(az)[:, None] * s[None, :]
    py = y0 + np.sin(az)[:, None] * s[None, :]
    h = dem.height_xy(px, py)
    if not np.isfinite(h).all():
        return None
    i = np.argmax(h, axis=1)
    cx_, cy_ = px[np.arange(len(az)), i], py[np.arange(len(az)), i]
    fx, fy, fr = _circle_fit(cx_, cy_)
    res = np.hypot(cx_ - fx, cy_ - fy) - fr
    mad = 1.4826 * np.median(np.abs(res - np.median(res)))
    keep = np.abs(res) <= 3 * mad if mad > 0 else np.ones_like(res, dtype=bool)
    if keep.sum() >= 3:
        fx, fy, fr = _circle_fit(cx_[keep], cy_[keep])
        res = np.hypot(cx_ - fx, cy_ - fy) - fr
    rms = float(np.sqrt(np.mean(res[keep] ** 2)))
    ok = bool(keep.sum() >= 50 and abs(fr - a) <= 0.15 * a and rms <= 0.06 * a)
    return {
        "id": cr["id"],
        "x_m": x0,
        "y_m": y0,
        "dx_m": float(fx - x0),
        "dy_m": float(fy - y0),
        "D_km": cr["D_km"],
        "lon": cr["lon"],
        "lat": cr["lat"],
        "rays_kept": int(keep.sum()),
        "radius_ratio": float(fr / a),
        "rms_over_a": rms / a,
        "accepted": ok,
    }


def _solve(T, R, w=None):
    n = len(T)
    A = np.zeros((2 * n, 4))
    b = np.zeros(2 * n)
    A[0::2, 0] = 1
    A[0::2, 2] = -R[:, 1]
    A[0::2, 3] = R[:, 0]
    A[1::2, 1] = 1
    A[1::2, 2] = R[:, 0]
    A[1::2, 3] = R[:, 1]
    b[0::2], b[1::2] = T[:, 0], T[:, 1]
    p, *_ = np.linalg.lstsq(A, b, rcond=None)
    res = (A @ p - b).reshape(n, 2)
    return p, res


def estimate(T: np.ndarray, R: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    p, res = _solve(T, R)
    L = np.hypot(res[:, 0], res[:, 1])
    mad = 1.4826 * np.median(np.abs(L - np.median(L)))
    keep = L <= np.median(L) + 3 * mad if mad > 0 else np.ones(len(L), dtype=bool)
    p2, _ = _solve(T[keep], R[keep])
    return p2, keep


def classify(est: float, se: float, level: float, same_sign: bool) -> str:
    detected = abs(est) >= 3 * se and same_sign
    if detected and abs(est) >= level:
        return "confirmed_and_matters"
    if detected:
        return "detected_but_small"
    if abs(est) + 1.96 * se < level:
        return "ruled_out_to_matter_level"
    return "undecided"


def run(root=None) -> dict:
    root = root or data_root()
    th = thresholds()
    d20, _ = c.open_products(root)
    sel = load_selection(root, th)
    fits = [f for f in (fit_crater(d20, cr) for cr in sel) if f is not None]
    acc = [f for f in fits if f["accepted"]]
    T = np.array([[f["dx_m"], f["dy_m"]] for f in acc])
    R = np.array([[f["x_m"], f["y_m"]] for f in acc])
    p, keep = estimate(T, R)
    Tk, Rk, accK = T[keep], R[keep], [f for f, k in zip(acc, keep) if k]
    n = len(Tk)
    rng = np.random.default_rng(20261114)
    boots = np.array([_solve(Tk[i], Rk[i])[0] for i in (rng.integers(0, n, n) for _ in range(1000))])
    se = boots.std(axis=0)

    def sub(mask):
        return _solve(Tk[mask], Rk[mask])[0]

    lon = np.array([f["lon"] for f in accK])
    dist = np.hypot(Rk[:, 0], Rk[:, 1])
    halves = {
        "lon_lt_180": sub(lon < 180),
        "lon_ge_180": sub(lon >= 180),
        "nearer_than_median": sub(dist < np.median(dist)),
        "farther_than_median": sub(dist >= np.median(dist)),
    }
    # leave-one-out: largest change of each parameter (every 5th crater to bound the run time, all if n < 400)
    step = 1 if n < 400 else 5
    loo = np.array([_solve(np.delete(Tk, i, 0), np.delete(Rk, i, 0))[0] for i in range(0, n, step)])
    loo_max = np.abs(loo - p).max(axis=0)

    names = ["Tx_m", "Ty_m", "rotation_rad", "radial_scale"]
    lev = th["what_matters_for_horizons"]
    same = {
        "Tx_m": all(np.sign(h[0]) == np.sign(p[0]) for h in halves.values()),
        "Ty_m": all(np.sign(h[1]) == np.sign(p[1]) for h in halves.values()),
        "rotation_rad": all(np.sign(h[2]) == np.sign(p[2]) for h in halves.values()),
        "radial_scale": all(np.sign(h[3]) == np.sign(p[3]) for h in halves.values()),
    }
    trans_len = float(np.hypot(p[0], p[1]))
    # translation: classify each component against the level with the component's own SE; also the length
    cls = {
        "translation_x": classify(p[0], se[0], lev["translation_m"], same["Tx_m"]),
        "translation_y": classify(p[1], se[1], lev["translation_m"], same["Ty_m"]),
        "rotation": classify(np.degrees(p[2]), np.degrees(se[2]), lev["rotation_deg"], same["rotation_rad"]),
        "radial_scale": classify(p[3], se[3], lev["radial_scale"], same["radial_scale"]),
    }
    return {
        "generated_utc": mf.utc_now(),
        "criterion": "data/checkpoints/thresholds_catalogue.json",
        "catalogue_file_sha256": mf.load(repo_data_dir() / "manifest" / "manifest.json")["files"]["raw/catalogs/ROBBINS_2018/lunar_crater_database_robbins_2018.zip"]["sha256"],
        "craters_selected_by_catalogue_flags": len(sel),
        "craters_with_a_complete_window": len(fits),
        "craters_accepted_by_rim_fit": len(acc),
        "craters_used_after_outlier_rejection": int(n),
        "estimates": {
            "translation_x_m": float(p[0]),
            "translation_y_m": float(p[1]),
            "translation_length_m": trans_len,
            "rotation_deg": float(np.degrees(p[2])),
            "radial_scale": float(p[3]),
        },
        "bootstrap_se": {
            "translation_x_m": float(se[0]),
            "translation_y_m": float(se[1]),
            "rotation_deg": float(np.degrees(se[2])),
            "radial_scale": float(se[3]),
        },
        "effect_at_150_km_m": {
            "rotation": float(abs(p[2]) * 150_000.0),
            "radial_scale": float(abs(p[3]) * 150_000.0),
        },
        "subsets": {k: {"translation_x_m": float(v[0]), "translation_y_m": float(v[1]), "rotation_deg": float(np.degrees(v[2])), "radial_scale": float(v[3])} for k, v in halves.items()},
        "leave_one_out_max_change": {
            "translation_x_m": float(loo_max[0]),
            "translation_y_m": float(loo_max[1]),
            "rotation_deg": float(np.degrees(loo_max[2])),
            "radial_scale": float(loo_max[3]),
            "craters_tested": int(len(loo)),
        },
        "classification": cls,
        "median_abs_offset_m": float(np.median(np.hypot(Tk[:, 0], Tk[:, 1]))),
        "offsets": [{k: f[k] for k in ("id", "dx_m", "dy_m", "D_km", "lat", "lon")} for f in accK][:0],
    }


def main() -> None:
    rep = run()
    out = repo_data_dir() / "checkpoints" / "catalogue_report.json"
    out.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
