"""Overview levels (pyramids) of a polar DEM.

Level ``k`` has pixels of ``2**k`` x ``2**k`` base pixels, aligned with the base
grid (so the georeferencing of level ``k`` is the base grid decimated, see
``PolarGrid.decimated``). Two statistics are stored, both as int16 in the same
units as the raw file (DN, 0.5 m):

* ``mean``: block average (rounded to the nearest DN). Use for lighting, slope and display.
* ``max``: block maximum. Use for a conservative horizon over far terrain: it can
  only over-estimate the horizon elevation, never miss a ridge.

Level 0 is the raw file and is not copied. The files are ``mean_L<k>.npy`` and
``max_L<k>.npy`` plus ``pyramid.json`` (provenance) in the derived folder of
the product.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import manifest as mf
from .dem import PolarDEM


def max_levels(n_rows: int, n_cols: int, wanted: int = 6) -> int:
    k = 0
    while k < wanted and n_rows % 2 ** (k + 1) == 0 and n_cols % 2 ** (k + 1) == 0:
        k += 1
    return k


def build(dem: PolarDEM, out_dir: str | Path, levels: int = 6, source_sha256: str | None = None, log=print) -> dict:
    """Build mean and max pyramids for levels 1..``levels`` (fewer if the size is not divisible)."""
    g = dem.grid0
    top = max_levels(g.n_rows, g.n_cols, levels)
    if top == 0:
        raise ValueError("raster size is odd; no overview level possible")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = dem._array(0, "mean")
    block = 2**top
    mm = {}
    for stat in ("mean", "max"):
        for k in range(1, top + 1):
            lg = g.decimated(2**k)
            mm[(stat, k)] = np.lib.format.open_memmap(
                out / f"{stat}_L{k}.npy", mode="w+", dtype="<i2", shape=(lg.n_rows, lg.n_cols)
            )
    strips = g.n_rows // block
    for s in range(strips):
        strip = np.asarray(base[s * block : (s + 1) * block, :])  # int16
        f = strip.astype(np.float32)
        for k in range(1, top + 1):
            b = 2**k
            r = f.reshape(block // b, b, g.n_cols // b, b)
            row0 = s * (block // b)
            m = r.mean(axis=(1, 3))
            mm[("mean", k)][row0 : row0 + block // b, :] = np.rint(m).astype("<i2")
            mm[("max", k)][row0 : row0 + block // b, :] = r.max(axis=(1, 3)).astype("<i2")
        if s % 50 == 0:
            log(f"  {dem.product_id}: strip {s}/{strips}")
    for a in mm.values():
        a.flush()
    del mm
    files = {}
    for stat in ("mean", "max"):
        for k in range(1, top + 1):
            f = out / f"{stat}_L{k}.npy"
            files[f.name] = {"size_bytes": f.stat().st_size, "sha256": mf.sha256_file(f)}
    meta = {
        "product_id": dem.product_id,
        "product_version": dem.product_version,
        "base_file": dem.data_path.name,
        "base_sha256": source_sha256,
        "base_size_bytes": dem.data_path.stat().st_size,
        "files": files,
        "levels": list(range(1, top + 1)),
        "statistics": ["mean", "max"],
        "dtype": "<i2",
        "units": "DN; height_m = DN * scale",
        "scale": dem.scale,
        "reference_radius_m": dem.reference_radius_m,
        "level_pixel_m": {str(k): dem.pixel_m(0) * 2**k for k in range(1, top + 1)},
        "method": "area mean (rounded to nearest DN) and maximum over 2**k x 2**k blocks aligned to the base grid; "
        "each level is computed directly from the base raster",
        "built_utc": mf.utc_now(),
        "numpy": np.__version__,
    }
    (out / "pyramid.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def add_file_hashes(out_dir: str | Path) -> dict:
    """Record size and SHA-256 of the existing level files in ``pyramid.json`` (read-only on the arrays).

    ``build`` does this itself; this is for pyramids built before the hashes were recorded.
    """
    out = Path(out_dir)
    meta_path = out / "pyramid.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    files = {}
    for stat in meta["statistics"]:
        for k in meta["levels"]:
            f = out / f"{stat}_L{k}.npy"
            files[f.name] = {"size_bytes": f.stat().st_size, "sha256": mf.sha256_file(f)}
    meta["files"] = files
    meta["hashes_added_utc"] = mf.utc_now()
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta
