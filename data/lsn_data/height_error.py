"""Terrain height error of the polar products from LOLA laser returns.

Method: data/checkpoints/height_error_method.json (committed before the independent returns were compared).
Output: data/checkpoints/height_error_report.json (``python -m lsn_data.height_error``).

* independent: returns of mission phase LRO_ES_100 (2021), not used to make the products (data through LRO_ES_54);
* fit residual (lower bound): returns of LRO_SM_06 (2011), which were used to make the products.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import catalog, checkpoints as cp, independent as ind, manifest as mf
from .georef import lonlat_to_xy
from .paths import data_root, repo_data_dir

SLOPE_CLASSES = ((0, 5), (5, 10), (10, 20), (20, 30), (30, 90))
BANDS = {"LDEM_80S_20M": (-89.8, -80.5), "LDEM_60S_60M": (-79.5, -60.5)}


def _q(v: np.ndarray) -> dict:
    if v.size == 0:
        return {"n": 0}
    m = float(np.median(v))
    a = np.abs(v - m)
    return {
        "n": int(v.size),
        "median_m": m,
        "half_width_68_m": float(np.percentile(a, 68.27)),
        "half_width_95_m": float(np.percentile(a, 95.45)),
        "p99_abs_m": float(np.percentile(np.abs(v), 99)),
        "mean_m": float(np.mean(v)),
    }


def residuals(dem, files: list[Path], band) -> dict:
    lon, lat, rad = [], [], []
    for f in files:
        s = ind.read_rdr(f)
        ok = (s["flag"] == 0) & (s["lat"] >= band[0]) & (s["lat"] <= band[1]) & (s["radius_m"] > 1.7e6)
        lon.append(s["lon"][ok]); lat.append(s["lat"][ok]); rad.append(s["radius_m"][ok])
    lon, lat, rad = np.concatenate(lon), np.concatenate(lat), np.concatenate(rad)
    x, y = lonlat_to_xy(lon, lat, dem.grid0.radius_m, dem.grid0.pole)
    px = dem.grid0.pixel_m
    d = dem.height_xy(x, y) - (rad - dem.reference_radius_m)
    gx = (dem.height_xy(x + px, y) - dem.height_xy(x - px, y)) / (2 * px)
    gy = (dem.height_xy(x, y + px) - dem.height_xy(x, y - px)) / (2 * px)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    ok = np.isfinite(d) & np.isfinite(slope)
    d, slope = d[ok], slope[ok]
    out = {"all": _q(d)}
    for lo, hi in SLOPE_CLASSES:
        out[f"slope_{lo}_{hi}_deg"] = _q(d[(slope >= lo) & (slope < hi)])
    return out


SITES_RC = {"shackleton_rim_crest": (15465.3284, 15071.1714), "de_gerlache_rim_crest": (14454.1922, 13316.0647),
            "malapert_massif_summit": (9117.9973, 15417.9997)}  # LDEM_80S_20M row/col, test_mapping_by_hand.py
LDEC_URLS = ["https://imbrium.mit.edu/DATA/LOLA_GDR/POLAR/IMG/LDEC_80S_20M.IMG",
             "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/img/ldec_80s_20m.img"]


def site_counts(half: int = 75) -> dict:
    """LOLA returns per 20 m pixel (companion product LDEC_80S_20M, uint8) in a window around each site, by byte ranges.

    Every 30th row is read from both mirrors and must be identical."""
    import time

    from .fetch import _open

    n = 30400

    def get(url, a, b):
        for k in range(6):
            try:
                with _open(url, {"Range": f"bytes={a}-{b}"}, timeout=120) as r:
                    if r.status != 206:
                        raise ValueError("range not honoured")
                    return r.read()
            except OSError:
                time.sleep(5 * (k + 1))
        raise OSError(url)

    out = {}
    for name, (r, c) in SITES_RC.items():
        r, c = int(round(r)), int(round(c))
        rows, checked = [], 0
        for i, rr in enumerate(range(r - half, r + half + 1)):
            a = rr * n + c - half
            x = get(LDEC_URLS[0], a, a + 2 * half)
            if i % 30 == 0:
                if get(LDEC_URLS[1], a, a + 2 * half) != x:
                    raise ValueError("mirrors disagree")
                checked += 1
            rows.append(np.frombuffer(x, dtype=np.uint8))
        w = np.array(rows)
        gaps = [int(np.max(np.diff(np.flatnonzero(np.r_[1, row, 1])))) - 1 for row in (w > 0).astype(int)]
        out[name] = {"window_m": 20 * w.shape[0], "fraction_no_return": float((w == 0).mean()),
                     "median_returns_per_pixel": float(np.median(w)), "longest_row_gap_m": 20 * max(gaps),
                     "rows_compared_between_mirrors": checked}
    return out


def gap_interpolation_proxy(dem, half: int = 75) -> dict:
    """Error of interpolating the DEM linearly across a gap of g pixels (mid-gap point), rows and columns, around
    each site: a proxy for the error at pixels without returns. Not a measurement of the product's error."""
    a = dem._array(0, "mean")
    out = {}
    for name, (r, c) in SITES_RC.items():
        r, c = int(round(r)), int(round(c))
        w = np.asarray(a[r - half : r + half + 1, c - half : c + half + 1]).astype(float) * dem.scale
        res = {}
        for g in (6, 10, 14):
            e = []
            for m in (w, w.T):
                e.append((0.5 * (m[:, :-g] + m[:, g:]) - m[:, g // 2 : m.shape[1] - g + g // 2]).ravel())
            res[f"gap_{20 * g}_m"] = _q(np.concatenate(e))
        out[name] = res
    return out


def run(root=None) -> dict:
    root = Path(root or data_root())
    d20, d60 = cp.open_products(root)
    def present(names):
        return [root / "raw" / "lola_rdr" / n / f"{n.lower()}.dat" for n in names if (root / "raw" / "lola_rdr" / n / f"{n.lower()}.dat").exists()]
    indep, fit = present(catalog.RDR_INDEPENDENT), present(catalog.RDR_SAMPLE)
    rep = {
        "generated_utc": mf.utc_now(),
        "method": "data/checkpoints/height_error_method.json",
        "difference": "d = DEM height (bilinear) - laser return height, metres; half-widths of |d - median|",
        "independent_files": [f.stem.upper() for f in indep],
        "independent_files_expected": len(catalog.RDR_INDEPENDENT),
        "fit_residual_files": [f.stem.upper() for f in fit],
        "independent_returns_available": "no: the LRO_ES_100 files (2021) and probes of LRO_ES_56, 60, 70, 80 and 90 contain no valid ranges (every spot flagged, radius field empty); LOLA altimetry effectively ends with the data the products use (through LRO_ES_54). The method's independent sample does not exist; this is a deviation from height_error_method.json",
        "interpolated_vs_constrained": "returns used by the 20 m product only fall in pixels with count >= 1, so the residuals describe data-constrained pixels; pixels without returns are characterised by site_counts and gap_interpolation_proxy",
        "products": {},
    }
    for dem in (d20, d60):
        band = BANDS[dem.product_id]
        rep["products"][dem.product_id] = {
            "band_deg": band,
            "independent_LRO_ES_100": residuals(dem, indep, band) if indep else None,
            "fit_residual_LRO_SM_06_lower_bound": residuals(dem, fit, band),
        }
    rep["site_counts_LDEC_80S_20M"] = site_counts()
    rep["gap_interpolation_proxy_LDEM_80S_20M"] = gap_interpolation_proxy(d20)
    return rep


def main() -> None:
    rep = run()
    out = repo_data_dir() / "checkpoints" / "height_error_report.json"
    out.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
