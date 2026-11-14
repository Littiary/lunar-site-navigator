"""Supplementary check to checkpoint 2 (criterion: data/checkpoints/thresholds_supplementary.json,
committed before the first measurement). Output: data/checkpoints/supplementary_report.json."""

from __future__ import annotations

import json

import numpy as np

from . import checkpoints as c
from . import manifest as mf
from .georef import lonlat_to_xy
from .paths import data_root, repo_data_dir

CRATERS = ("Shackleton", "Shoemaker", "Faustini", "Cabeus", "de Gerlache", "Haworth")
SHIFTS = np.arange(-4000.0, 4000.1, 100.0)


def _densify(x: np.ndarray, y: np.ndarray, step: float = 250.0):
    xs, ys = [], []
    n = len(x)
    for i in range(n):
        j = (i + 1) % n
        L = np.hypot(x[j] - x[i], y[j] - y[i])
        k = max(int(np.ceil(L / step)), 1)
        t = np.arange(k) / k
        xs.append(x[i] + t * (x[j] - x[i]))
        ys.append(y[i] + t * (y[j] - y[i]))
    return np.concatenate(xs), np.concatenate(ys)


def fit_crater(dem, feat: dict, rng: np.random.Generator) -> dict:
    det = c._best_outline(feat)
    pts = np.array(det["outline_lon_lat_deg"], dtype=float)
    if np.allclose(pts[0], pts[-1]):
        pts = pts[:-1]
    vx, vy = lonlat_to_xy(pts[:, 0], pts[:, 1], dem.grid0.radius_m, dem.grid0.pole)
    cx, cy = vx.mean(), vy.mean()
    px, py = _densify(vx, vy)
    nx, ny = px - cx, py - cy
    nn = np.hypot(nx, ny)
    nx, ny = nx / nn, ny / nn
    d = 0.02 * det["diameter_km"] * 1000.0
    N = len(px)
    S = np.empty((N, len(SHIFTS), len(SHIFTS)), dtype=np.float32)
    for iy, dy in enumerate(SHIFTS):
        for ix, dx in enumerate(SHIFTS):
            qx, qy = px + dx, py + dy
            h0 = dem.height_xy(qx, qy)
            hp = dem.height_xy(qx + d * nx, qy + d * ny)
            hm = dem.height_xy(qx - d * nx, qy - d * ny)
            S[:, iy, ix] = h0 - 0.5 * (hp + hm)
    S = np.nan_to_num(S, nan=0.0)
    mean = S.mean(axis=0)
    iy, ix = np.unravel_index(np.argmax(mean), mean.shape)
    flat = S.reshape(N, -1)
    bx, by = [], []
    for _ in range(200):
        idx = rng.integers(0, N, N)
        k = np.argmax(flat[idx].mean(axis=0))
        by.append(SHIFTS[k // len(SHIFTS)])
        bx.append(SHIFTS[k % len(SHIFTS)])
    z = len(SHIFTS) // 2
    return {
        "outline_points": int(N),
        "contrast_distance_m": d,
        "dx_m": float(SHIFTS[ix]),
        "dy_m": float(SHIFTS[iy]),
        "bootstrap_sd_dx_m": float(np.std(bx)),
        "bootstrap_sd_dy_m": float(np.std(by)),
        "objective_best": float(mean[iy, ix]),
        "objective_at_zero_shift": float(mean[z, z]),
        "centroid_x_m": float(cx),
        "centroid_y_m": float(cy),
        "centroid_distance_from_pole_km": float(np.hypot(cx, cy) / 1000.0),
    }


def evaluate(fits: dict) -> dict:
    T = np.array([[f["dx_m"], f["dy_m"]] for f in fits.values()])
    R = np.array([[f["centroid_x_m"], f["centroid_y_m"]] for f in fits.values()])
    n = len(T)
    m = T.mean(axis=0)
    S = float(np.sqrt(np.mean(np.sum((T - m) ** 2, axis=1))))
    SE = S / np.sqrt(n)
    mlen = float(np.hypot(*m))
    u = m / mlen if mlen > 0 else np.array([1.0, 0.0])
    along = T @ u
    common = bool(mlen >= 500.0 and mlen >= 2 * SE and int(np.sum(along > 0)) >= 5)
    resultant = float(np.hypot(*T.sum(axis=0)) / np.sum(np.hypot(T[:, 0], T[:, 1])))
    # rotation and scale: t_i = T0 + delta * (-y_i, x_i) + eps * (x_i, y_i)
    A = np.zeros((2 * n, 4))
    b = np.zeros(2 * n)
    for i in range(n):
        A[2 * i] = [1, 0, -R[i, 1], R[i, 0]]
        A[2 * i + 1] = [0, 1, R[i, 0], R[i, 1]]
        b[2 * i], b[2 * i + 1] = T[i]
    p, res, *_ = np.linalg.lstsq(A, b, rcond=None)
    rss = float(np.sum((A @ p - b) ** 2))
    sigma2 = rss / (2 * n - 4)
    cov = sigma2 * np.linalg.inv(A.T @ A)
    se = np.sqrt(np.diag(cov))
    rmax = float(np.max(np.hypot(R[:, 0], R[:, 1])))
    delta, eps = float(p[2]), float(p[3])
    rot_flag = bool(abs(delta) * rmax >= 500 and abs(delta) >= 2 * se[2])
    scale_flag = bool(abs(eps) * rmax >= 500 and abs(eps) >= 2 * se[3])
    return {
        "vectors_m": {k: [float(v[0]), float(v[1])] for k, v in zip(fits, T)},
        "mean_vector_m": [float(m[0]), float(m[1])],
        "mean_length_m": mlen,
        "scatter_S_m": S,
        "standard_error_m": float(SE),
        "vectors_with_positive_component_along_mean": int(np.sum(along > 0)),
        "resultant_length_ratio": resultant,
        "common_shift_flagged": common,
        "rotation_deg": float(np.degrees(delta)),
        "rotation_se_deg": float(np.degrees(se[2])),
        "rotation_effect_at_rmax_m": abs(delta) * rmax,
        "rotation_flagged": rot_flag,
        "radial_scale_eps": eps,
        "radial_scale_se": float(se[3]),
        "scale_effect_at_rmax_m": abs(eps) * rmax,
        "scale_flagged": scale_flag,
        "fit_translation_term_m": [float(p[0]), float(p[1])],
        "any_flagged": bool(common or rot_flag or scale_flag),
    }


def post_hoc(fits: dict) -> dict:
    """Not part of the criterion: tangential/radial split of each vector and leave-one-out rotation."""
    comp = {}
    for n, v in fits.items():
        x, y = v["centroid_x_m"], v["centroid_y_m"]
        r = float(np.hypot(x, y))
        comp[n] = {
            "distance_from_pole_km": r / 1000.0,
            "tangential_m_ccw_positive": float((v["dx_m"] * -y + v["dy_m"] * x) / r),
            "radial_m_outward_positive": float((v["dx_m"] * x + v["dy_m"] * y) / r),
        }
    loo = {}
    for n in fits:
        e = evaluate({k: v for k, v in fits.items() if k != n})
        loo[n] = {"rotation_deg": e["rotation_deg"], "rotation_se_deg": e["rotation_se_deg"], "rotation_flagged": e["rotation_flagged"], "common_shift_flagged": e["common_shift_flagged"]}
    return {"components": comp, "leave_one_out_without": loo}


def run(root=None) -> dict:
    root = root or data_root()
    d20, _ = c.open_products(root)
    feats = c.features()
    rng = np.random.default_rng(20261114)
    fits = {n: fit_crater(d20, feats[n], rng) for n in CRATERS}
    return {
        "generated_utc": mf.utc_now(),
        "criterion": "data/checkpoints/thresholds_supplementary.json",
        "per_crater": fits,
        "evaluation": evaluate(fits),
        "post_hoc_not_part_of_criterion": post_hoc(fits),
    }


def main() -> None:
    rep = run()
    out = repo_data_dir() / "checkpoints" / "supplementary_report.json"
    out.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(rep["evaluation"], indent=1))
    print(out)


if __name__ == "__main__":
    main()
