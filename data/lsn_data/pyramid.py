"""Overview levels (pyramids) of a polar or cylindrical DEM.

Level ``k`` has pixels of ``2**k`` x ``2**k`` base pixels, aligned with the base
grid (so the georeferencing of level ``k`` is the base grid decimated, see
``PolarGrid.decimated``). Two statistics are stored, both as int16 in the same
units as the raw file (DN, 0.5 m):

* ``mean``: block average (rounded to the nearest DN). Use for lighting, slope and display.
* ``max``: block maximum. Use for a conservative horizon over far terrain: it can
  only over-estimate the horizon elevation, never miss a ridge.

Integer products keep int16 DN (means rounded to the nearest DN); float products (SLDEM2015) keep float32 in
their own unit. Level 0 is the raw file and is not copied. The files are ``mean_L<k>.npy`` and
``max_L<k>.npy`` plus ``pyramid.json`` (provenance) in the derived folder of
the product.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import manifest as mf


def max_levels(n_rows: int, n_cols: int, wanted: int = 6) -> int:
    k = 0
    while k < wanted and n_rows % 2 ** (k + 1) == 0 and n_cols % 2 ** (k + 1) == 0:
        k += 1
    return k


def build(dem, out_dir: str | Path, levels: int = 6, source_sha256: str | None = None, log=print) -> dict:
    """Build mean and max pyramids for levels 1..``levels`` (fewer if the size is not divisible)."""
    g = dem.grid0
    top = max_levels(g.n_rows, g.n_cols, levels)
    if top == 0:
        raise ValueError("raster size is odd; no overview level possible")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = dem._array(0, "mean")
    dt = np.dtype(base.dtype).newbyteorder("<").str
    integer = np.issubdtype(base.dtype, np.integer)
    block = 2**top
    mm = {}
    for stat in ("mean", "max"):
        for k in range(1, top + 1):
            lg = g.decimated(2**k)
            mm[(stat, k)] = np.lib.format.open_memmap(
                out / f"{stat}_L{k}.npy", mode="w+", dtype=dt, shape=(lg.n_rows, lg.n_cols)
            )
    strips = g.n_rows // block
    for s in range(strips):
        strip = np.asarray(base[s * block : (s + 1) * block, :])
        f = strip.astype(np.float64 if not integer else np.float32)
        for k in range(1, top + 1):
            b = 2**k
            r = f.reshape(block // b, b, g.n_cols // b, b)
            row0 = s * (block // b)
            m = r.mean(axis=(1, 3))
            mm[("mean", k)][row0 : row0 + block // b, :] = (np.rint(m) if integer else m).astype(dt)
            mm[("max", k)][row0 : row0 + block // b, :] = r.max(axis=(1, 3)).astype(dt)
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
        "dtype": dt,
        "units": "DN; height_m = DN * scale",
        "scale": dem.scale,
        "reference_radius_m": dem.reference_radius_m,
        "level_pixel_m": {str(k): dem.pixel_m(0) * 2**k for k in range(1, top + 1)},
        "method": ("area mean (rounded to nearest DN)" if integer else "area mean") + " and maximum over 2**k x 2**k blocks aligned to the base grid; "
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


def open_product(pid: str, root: Path):
    """The product ``pid`` as stored under the data root: polar PDS3, cylindrical PDS3 tile, or 5 m site GeoTIFF."""
    from . import catalog
    from .cylindrical import CylDEM
    from .dem import PolarDEM
    from .paths import raw_dir
    from .pdslabel import parse_label

    if pid in catalog.SITE_DEM_PRODUCTS:
        site = next(s for s in catalog.SITE_DEM_SITES if f"LOLA5MPP_{s.upper()}" == pid)
        return PolarDEM.from_geotiff(Path(root) / "raw" / "lola_5mpp" / pid / f"{site}_final_adj_5mpp_surf.tif", product_id=pid)
    lbl = raw_dir(root) / pid / f"{pid.lower()}.lbl"
    kind = parse_label(lbl).get("MAP_PROJECTION_TYPE")
    return CylDEM(lbl) if kind == "SIMPLE CYLINDRICAL" else PolarDEM(lbl)


def build_product(pid: str, root: Path, levels: int = 6) -> dict:
    from . import manifest as mf
    from .paths import derived_dir, manifest_path

    dem = open_product(pid, root)
    m = mf.load(manifest_path())["files"]
    sha = next((r["sha256"] for k, r in m.items() if r["role"] == "data" and k.split("/")[-2] == pid), None)
    return build(dem, derived_dir(root) / pid, levels, source_sha256=sha)


def write_record(root: Path) -> Path:
    """Commit-able record of every pyramid under the data root: data/manifest/pyramids.json (sizes and SHA-256)."""
    from .paths import derived_dir, repo_data_dir

    out = {}
    for meta_path in sorted(Path(derived_dir(root)).glob("*/pyramid.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        out[meta_path.parent.name] = {
            "base_file": meta.get("base_file"),
            "base_sha256": meta.get("base_sha256"),
            "levels": meta.get("levels"),
            "dtype": meta.get("dtype"),
            "built_utc": meta.get("built_utc"),
            "files": meta.get("files", {}),
            "pyramid_json_sha256": mf.sha256_file(meta_path),
        }
    path = repo_data_dir() / "manifest" / "pyramids.json"
    path.write_text(json.dumps({"schema_version": 1, "pyramids": out}, indent=1) + "\n", encoding="utf-8")
    return path
