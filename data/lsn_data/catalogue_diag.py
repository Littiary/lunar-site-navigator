"""Diagnosis of the radial scale found by the crater-catalogue check (post hoc, not a pass/fail rule).

The catalogue check (lsn_data.catalogue_check) fits t_i = T + delta (z x r_i) + eps r_i to the offsets between the rim
circles fitted on our 20 m DEM and the catalogue centres. This module asks where eps = -3.6e-4 comes from:

1. Bias of our own rim detector: on a regional slope the highest point of each ray moves uphill, so the fitted circle
   moves uphill. Measured by adding beta * a * grad(h) to the model (grad from a plane fitted to an annulus
   1.4 a .. 2.4 a outside the search band) and, separately, by repeating the rim fit on the DEM with that plane removed.
2. Alternatives that cannot be told apart with 192 craters: a constant radial offset b, or a radial offset
   proportional to the crater diameter.

Output: data/checkpoints/radial_scale_diagnosis.json.
"""

from __future__ import annotations

import json

import numpy as np

from . import catalogue_check as cc, checkpoints as cp, manifest as mf
from .paths import data_root, repo_data_dir


def _regional_and_detrended(dem, f: dict, cr: dict) -> dict:
    x0, y0 = f["x_m"], f["y_m"]
    a = cr["D_km"] * 500.0 / np.cos(np.radians(90.0 + cr["lat"]) / 2) ** 2
    az = np.radians(np.arange(0, 360, 5.0))
    rr = np.linspace(1.4 * a, 2.4 * a, 11)
    px = x0 + np.cos(az)[:, None] * rr
    py = y0 + np.sin(az)[:, None] * rr
    h = dem.height_xy(px, py)
    ok = np.isfinite(h)
    A = np.column_stack([np.ones(ok.sum()), px[ok] - x0, py[ok] - y0])
    co, *_ = np.linalg.lstsq(A, h[ok], rcond=None)
    gx, gy = float(co[1]), float(co[2])
    s = np.arange(0.75 * a, 1.25 * a + 1e-9, 10.0)
    qx = x0 + np.cos(az)[:, None] * s
    qy = y0 + np.sin(az)[:, None] * s
    hq = dem.height_xy(qx, qy) - (gx * (qx - x0) + gy * (qy - y0))
    i = np.argmax(hq, axis=1)
    cx_, cy_ = qx[np.arange(len(az)), i], qy[np.arange(len(az)), i]
    fx, fy, _ = cc._circle_fit(cx_, cy_)
    res = np.hypot(cx_ - fx, cy_ - fy) - _
    mad = 1.4826 * np.median(np.abs(res - np.median(res)))
    keep = np.abs(res) <= 3 * mad if mad > 0 else np.ones(len(az), bool)
    fx, fy, _ = cc._circle_fit(cx_[keep], cy_[keep])
    return {"a_m": float(a), "gx": gx, "gy": gy, "dx_detrended_m": float(fx - x0), "dy_detrended_m": float(fy - y0)}


def _ols(M, b, names):
    co, *_ = np.linalg.lstsq(M, b, rcond=None)
    r = b - M @ co
    cov = np.linalg.inv(M.T @ M) * (r @ r) / (len(b) - M.shape[1])
    se = np.sqrt(np.diag(cov))
    return {n: {"estimate": float(c), "se": float(s)} for n, c, s in zip(names, co, se)}


def run(root=None) -> dict:
    root = root or data_root()
    d20, _ = cp.open_products(root)
    sel = cc.load_selection(root, cc.thresholds())
    rows = []
    for cr in sel:
        f = cc.fit_crater(d20, cr)
        if f is None or not f["accepted"]:
            continue
        f.update(_regional_and_detrended(d20, f, cr))
        rows.append(f)
    T = np.array([[r["dx_m"], r["dy_m"]] for r in rows])
    R = np.array([[r["x_m"], r["y_m"]] for r in rows])
    G = np.array([[r["gx"], r["gy"]] for r in rows])
    a = np.array([r["a_m"] for r in rows])
    D = np.array([r["D_km"] for r in rows]) * 1000.0
    p0, keep = cc.estimate(T, R)
    Td = np.array([[r["dx_detrended_m"], r["dy_detrended_m"]] for r in rows])
    pd, keep_d = cc.estimate(Td, R)
    Rk, Tk, Gk, ak, Dk = R[keep], T[keep], G[keep], a[keep], D[keep]
    n = len(Rk)
    s = np.hypot(Rk[:, 0], Rk[:, 1])
    u = Rk / s[:, None]
    b = np.empty(2 * n)
    b[0::2], b[1::2] = Tk[:, 0], Tk[:, 1]

    def model(extra):
        cols = [
            (np.ones(n), np.zeros(n)), (np.zeros(n), np.ones(n)),
            (-Rk[:, 1], Rk[:, 0]), (Rk[:, 0], Rk[:, 1]),
        ] + extra
        M = np.zeros((2 * n, len(cols)))
        for j, (cx, cy) in enumerate(cols):
            M[0::2, j], M[1::2, j] = cx, cy
        return M

    base = ["Tx_m", "Ty_m", "rotation_rad", "radial_scale"]
    slope = [(Gk[:, 0] * ak, Gk[:, 1] * ak)]
    fits = {
        "catalogue_check_model": _ols(model([]), b, base),
        "plus_uphill_bias": _ols(model(slope), b, base + ["uphill_beta"]),
        "plus_uphill_bias_and_constant_radial_offset": _ols(model(slope + [(u[:, 0], u[:, 1])]), b, base + ["uphill_beta", "radial_offset_m"]),
        "plus_uphill_bias_and_radial_offset_per_diameter": _ols(model(slope + [(u[:, 0] * Dk, u[:, 1] * Dk)]), b, base + ["uphill_beta", "radial_offset_per_D"]),
        "plus_uphill_bias_and_latlon_fit_term": _ols(model(slope + [(u[:, 0] * Dk**2 / s, u[:, 1] * Dk**2 / s)]), b, base + ["uphill_beta", "D2_over_s_coefficient"]),
    }
    grad_rad = (Gk * u).sum(1)
    return {
        "generated_utc": mf.utc_now(),
        "kind": "post-hoc diagnosis, not a pass/fail rule",
        "craters_used": int(n),
        "radial_scale_as_in_catalogue_report": float(p0[3]),
        "radial_scale_with_detrended_rim_fit": float(pd[3]),
        "mean_radial_component_of_regional_slope": {"value": float(grad_rad.mean()), "se": float(grad_rad.std() / np.sqrt(n)),
                                                    "sign": "negative = terrain rises towards the pole"},
        "fits": fits,
        "predictions_of_conventions": {
            "D2_over_s_coefficient_if_catalogue_circles_were_fitted_in_lat_lon_space": 0.125,
            "radial_scale_if_catalogue_positions_used_a_1737.1513_km_sphere_against_1737.4_km_metres": 1737151.3 / 1737400.0 - 1,
        },
    }


def main() -> None:
    rep = run()
    out = repo_data_dir() / "checkpoints" / "radial_scale_diagnosis.json"
    out.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
