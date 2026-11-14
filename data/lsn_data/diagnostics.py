"""Post-hoc diagnostics for checkpoint 2. NOT part of the pass/fail rules (those are fixed in
thresholds.json). They measure how well the georeferencing is pinned and how far the IAU outlines are
from the DEM crests. Output: data/checkpoints/diagnostics.json."""

from __future__ import annotations

import json

import numpy as np

from . import checkpoints as c
from . import manifest as mf
from .georef import lonlat_to_xy
from .paths import data_root, raw_dir, repo_data_dir
from .pdslabel import parse_label


def outline_shift(d20, name: str) -> dict:
    det = c._best_outline(c.features()[name])
    pts = np.array(det["outline_lon_lat_deg"])
    if np.allclose(pts[0], pts[-1]):
        pts = pts[:-1]
    x, y = lonlat_to_xy(pts[:, 0], pts[:, 1])
    sh = np.arange(-4000, 4001, 100.0)
    S = np.array([[np.nanmean(d20.height_xy(x + dx, y + dy)) for dx in sh] for dy in sh])
    i, j = np.unravel_index(np.nanargmax(S), S.shape)
    return {
        "distance_of_outline_centroid_from_pole_km": float(np.hypot(x.mean(), y.mean()) / 1000),
        "mean_height_at_outline_m": float(np.nanmean(d20.height_xy(x, y))),
        "best_rigid_shift_dx_m": float(sh[j]),
        "best_rigid_shift_dy_m": float(sh[i]),
        "mean_height_at_best_shift_m": float(S[i, j]),
    }


def ldem16_sensitivity(d20, root) -> dict:
    arr = np.fromfile(raw_dir(root) / "LDEM_16" / "ldem_16.img", dtype="<i2").reshape(2880, 5760)
    lat = (1439.5 - np.arange(2880)) / 16
    sel = np.arange(2880)[lat <= -80.5]
    lon = (180 + (np.arange(5760) - 2879.5) / 16) % 360
    LON, LAT = np.meshgrid(lon, lat[sel])
    v16 = arr[sel].astype(float) * 0.5
    x, y = lonlat_to_xy(LON, LAT)

    def stat(xx, yy):
        d = (d20.height_xy(xx, yy, level=6) - v16)
        d = d[np.isfinite(d)]
        return {"rmse_m": float(np.sqrt(np.mean(d**2))), "median_abs_m": float(np.median(np.abs(d)))}

    out = {"shift_m": {}, "rotation_deg": {}, "scale": {}}
    for dx, dy in [(0, 0), (250, 0), (500, 0), (0, 500), (1000, 0), (2000, 0)]:
        out["shift_m"][f"{dx},{dy}"] = stat(x + dx, y + dy)
    for rot in (0.05, 0.1, 0.25, 0.5):
        t = np.radians(rot)
        out["rotation_deg"][str(rot)] = stat(x * np.cos(t) - y * np.sin(t), x * np.sin(t) + y * np.cos(t))
    for sc in (0.999, 1.001, 1.003):
        out["scale"][str(sc)] = stat(x * sc, y * sc)
    return out


def main() -> None:
    root = data_root()
    d20, _ = c.open_products(root)
    res = {
        "generated_utc": mf.utc_now(),
        "note": "post-hoc diagnostics, not pass/fail rules",
        "outline_best_rigid_shift": {n: outline_shift(d20, n) for n in ("Shackleton", "Shoemaker", "Faustini", "Cabeus", "de Gerlache", "Haworth")},
        "ldem16_comparison_sensitivity_to_artificial_errors": ldem16_sensitivity(d20, root),
    }
    out = repo_data_dir() / "checkpoints" / "diagnostics.json"
    out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
