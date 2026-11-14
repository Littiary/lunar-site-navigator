"""Absolute radius check at the lunar laser-ranging retroreflectors (independent of LOLA).

Criterion and reflector coordinates: data/checkpoints/thresholds_llr.json (committed before the first run).
Output: data/checkpoints/llr_report.json (``python -m lsn_data.llr``).

When a cylindrical tile is not fully downloaded, :class:`RangeTile` reads only the pixels around each reflector with
HTTP byte ranges from both mirrors and requires the two copies to be identical; such results are marked provisional
until the whole file is checksummed.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from . import catalog, manifest as mf
from .cylindrical import CylDEM, CylGrid, CylMosaic, _DTYPES
from .paths import data_root, raw_dir, repo_data_dir
from .pdslabel import parse_label


def thresholds() -> dict:
    return json.loads((repo_data_dir() / "checkpoints" / "thresholds_llr.json").read_text(encoding="utf-8"))


class RangeTile:
    """Level 0 of a cylindrical tile known only at a few pixels, read by HTTP byte ranges (two mirrors compared)."""

    kind = "cylindrical"

    def __init__(self, label_path: Path, urls: list[str]):
        lab = parse_label(label_path)
        self.label = lab
        self.grid0 = CylGrid.from_label(lab)
        self.product_id = str(lab.get("PRODUCT_ID")).upper()
        self.product_version = lab.get("PRODUCT_VERSION_ID")
        self.data_set_id = lab.get("DATA_SET_ID")
        self.dtype = _DTYPES[(lab["SAMPLE_TYPE"], int(lab["SAMPLE_BITS"]))]
        unit = str(lab.get("UNIT", "METER")).upper()
        to_m = 1000.0 if unit == "KILOMETER" else 1.0
        self.scale = float(lab.get("SCALING_FACTOR", 1.0)) * to_m
        self.reference_radius_m = float(lab["OFFSET"]) * to_m
        self.urls = urls
        self.levels = [0]
        self._levels = {("mean", 0): None}
        self._px: dict[tuple[int, int], float] = {}
        self.ranges_read: list[dict] = []
        self.label_path = label_path

    def grid(self, level: int = 0) -> CylGrid:
        return self.grid0

    def fetch_window(self, row: int, col: int, half: int = 4) -> None:
        from .fetch import _open

        size = np.dtype(self.dtype).itemsize
        c0, c1 = max(col - half, 0), min(col + half + 1, self.grid0.n_cols)
        for r in range(max(row - half, 0), min(row + half + 1, self.grid0.n_rows)):
            a = (r * self.grid0.n_cols + c0) * size
            b = (r * self.grid0.n_cols + c1) * size - 1
            copies = []
            for u in self.urls:
                with _open(u, {"Range": f"bytes={a}-{b}"}, timeout=120) as resp:
                    if resp.status != 206:
                        raise OSError(f"{u}: range request not honoured")
                    copies.append(resp.read())
            if len(set(copies)) != 1 or len(copies[0]) != b - a + 1:
                raise ValueError(f"{self.product_id}: the mirrors disagree at bytes {a}-{b}")
            vals = np.frombuffer(copies[0], dtype=self.dtype)
            for j, v in enumerate(vals):
                self._px[(r, c0 + j)] = float(v)
            self.ranges_read.append({"bytes": [a, b], "sources_identical": True, "n_sources": len(copies)})

    def values_at(self, rows, cols, level, statistic):
        out = np.array([self._px.get((int(r), int(c)), np.nan) for r, c in zip(np.ravel(rows), np.ravel(cols))])
        return out * self.scale

    def provenance(self, manifest=None) -> dict:
        return {"product_id": self.product_id, "product_version": self.product_version, "read_by": "HTTP byte ranges",
                "sources": self.urls, "ranges": self.ranges_read}


def _local_sigma(mosaic: CylMosaic, lon: float, lat: float) -> float:
    res = mosaic.res_ppd
    n_cols = int(round(360 * res))
    r = int(math.floor((90.0 - lat) * res))
    c = int(math.floor((lon % 360.0) * res))
    rr, cc = np.meshgrid(np.arange(r - 1, r + 2), np.mod(np.arange(c - 1, c + 2), n_cols), indexing="ij")
    v = mosaic._gather(rr.ravel(), cc.ravel(), 0, "mean")
    return float(np.sqrt(np.nanmean((v - np.nanmean(v)) ** 2)))


def evaluate(mosaic: CylMosaic, th: dict) -> dict:
    pa = {p["name"]: p for p in th["reflectors_DE421_PA_for_the_mixup_test"]}
    rows = []
    for ref in th["reflectors_DE421_ME"]:
        lon, lat = ref["lon_deg_east"], ref["lat_deg"]
        r_dem = float(mosaic.height_m(lon, lat)) + mosaic.reference_radius_m
        sig = _local_sigma(mosaic, lon, lat)
        p = pa[ref["name"]]
        r_pa = float(mosaic.height_m(p["lon_deg_east"], p["lat_deg"])) + mosaic.reference_radius_m
        d = r_dem - ref["radius_m"]
        tol = 5.0 + 2.0 * sig
        rows.append({
            "name": ref["name"], "lon_deg_east": lon, "lat_deg": lat, "reflector_radius_m": ref["radius_m"],
            "dem_radius_m": r_dem, "difference_m": d, "sigma_local_m": sig, "tolerance_m": tol,
            "passed": bool(abs(d) <= tol), "difference_at_PA_position_m": r_pa - ref["radius_m"],
        })
    d = np.array([x["difference_m"] for x in rows])
    return {
        "product": mosaic.product_id, "pixel_m": mosaic.pixel_m(0), "reflectors": rows,
        "mean_difference_m": float(d.mean()),
        "radius_or_datum_problem_indicated": bool((np.all(d > 0) or np.all(d < 0)) and abs(d.mean()) > 10.0),
        "passed": bool(all(x["passed"] for x in rows)),
    }


def run(root=None) -> dict:
    root = Path(root or data_root())
    th = thresholds()
    out = {"generated_utc": mf.utc_now(), "criterion": "data/checkpoints/thresholds_llr.json", "results": {}}
    l16 = CylMosaic([CylDEM(raw_dir(root) / "LDEM_16" / "ldem_16.lbl")])
    if (raw_dir(root) / "LDEM_128" / "ldem_128.img").exists():
        out["results"]["LDEM_128"] = evaluate(CylMosaic([CylDEM(raw_dir(root) / "LDEM_128" / "ldem_128.lbl")]), th)
    else:
        out["results"]["LDEM_128"] = {"pending": "LDEM_128 not downloaded yet"}
    # SLDEM2015 256: whole files when present, otherwise byte ranges from both mirrors (provisional)
    tiles, provisional = [], False
    for tid in catalog.SLDEM_256_TILES:
        lbl = raw_dir(root) / tid / f"{tid.lower()}.lbl"
        img = raw_dir(root) / tid / f"{tid.lower()}.img"
        if img.exists():
            tiles.append(CylDEM(lbl))
        elif lbl.exists():
            spec = catalog.PRODUCTS[tid].files[0]
            from .fetch import _urls

            tiles.append(RangeTile(lbl, _urls(spec, "mit")))
            provisional = True
    if tiles:
        mos = CylMosaic(tiles, product_id="SLDEM2015_256")
        res = mos.res_ppd
        for ref in th["reflectors_DE421_ME"] + th["reflectors_DE421_PA_for_the_mixup_test"]:
            for t in tiles:
                if isinstance(t, RangeTile) and t.grid0.covers(ref["lon_deg_east"], ref["lat_deg"]):
                    r, c = t.grid0.lonlat_to_rowcol(ref["lon_deg_east"], ref["lat_deg"])
                    t.fetch_window(int(round(float(r))), int(round(float(c))), half=3)
        r = evaluate(mos, th)
        r["provisional"] = provisional
        if provisional:
            r["provisional_why"] = "values read by HTTP byte ranges from the MIT mirror and PDS (identical copies); the whole tiles are not yet downloaded and checksummed"
            r["ranges"] = [t.provenance() for t in tiles if isinstance(t, RangeTile) and t.ranges_read]
        out["results"]["SLDEM2015_256"] = r
    out["results"]["LDEM_16_reported_only"] = evaluate(l16, th)
    judged = [v for k, v in out["results"].items() if k in ("LDEM_128", "SLDEM2015_256") and "passed" in v]
    out["passed"] = bool(judged) and all(v["passed"] for v in judged)
    out["complete"] = "pending" not in out["results"]["LDEM_128"] and not provisional
    return out


def main() -> None:
    rep = run()
    path = repo_data_dir() / "checkpoints" / "llr_report.json"
    path.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: (v if k != "results" else {n: {kk: vv for kk, vv in r.items() if kk != "ranges"} for n, r in v.items()}) for k, v in rep.items()}, indent=1))


if __name__ == "__main__":
    main()
