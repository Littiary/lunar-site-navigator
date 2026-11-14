"""Lunar Site Navigator, stream C: LOLA data, manifest, reader and pyramids."""

from __future__ import annotations

from pathlib import Path

__version__ = "0.1.0"

DEFAULT_PRODUCTS = ("LDEM_80S_20M", "LDEM_60S_60M")

# Whole-Moon terrain (``open_terrain(products="moon")``): polar products by pole, then cylindrical mosaics.
MOON_POLAR = {-1: ("LDEM_80S_20M", "LDEM_60S_60M"), 1: ("LDEM_80N_20M", "LDEM_60N_60M")}


def open_terrain(label_paths=None, products=DEFAULT_PRODUCTS, root=None):
    """Open terrain for horizon work.

    ``label_paths``: explicit PDS3 label files (e.g. the synthetic test DEM). Otherwise the
    ``products`` are looked up under the data root (``LSN_DATA_ROOT``), with their pyramids
    when those have been built.

    ``products="moon"`` returns a :class:`lsn_data.moon.MoonTerrain` that serves any latitude and
    longitude with the best product present (both polar pairs, then the cylindrical mosaics of
    ``lsn_data.catalog.MOON_CYLINDRICAL``, finest first) and reports with ``source()`` which product
    and level it read. The default (south-polar pair, a ``Terrain``) is unchanged.
    """
    if isinstance(products, str) and products == "moon":
        if label_paths is not None:
            raise ValueError("label_paths and products='moon' exclude each other")
        return open_moon(root)
    from .dem import PolarDEM, Terrain
    from .paths import data_root, derived_dir, raw_dir

    if label_paths is not None:
        return Terrain([PolarDEM(p) for p in label_paths])
    root = Path(root) if root else data_root()
    dems = []
    for pid in products:
        lbl = raw_dir(root) / pid / f"{pid.lower()}.lbl"
        if not lbl.exists():
            raise FileNotFoundError(f"{lbl} not found; run `python -m lsn_data fetch` (data root {root})")
        dems.append(PolarDEM(lbl, pyramid_dir=derived_dir(root) / pid))
    return Terrain(dems)


def open_moon(root=None):
    """Whole-Moon terrain from every product of the moon set that is present under the data root."""
    from . import catalog
    from .cylindrical import CylDEM, CylMosaic
    from .dem import PolarDEM, Terrain
    from .moon import MoonTerrain
    from .paths import data_root, derived_dir, raw_dir

    root = Path(root) if root else data_root()
    missing = []
    polar = []
    for pole, pids in MOON_POLAR.items():
        dems = []
        for pid in pids:
            lbl = raw_dir(root) / pid / f"{pid.lower()}.lbl"
            img = raw_dir(root) / pid / f"{pid.lower()}.img"
            if lbl.exists() and img.exists():
                dems.append(PolarDEM(lbl, pyramid_dir=derived_dir(root) / pid))
            else:
                missing.append(pid)
        if dems:
            polar.append(Terrain(dems))
    cyl = []
    for mosaic_id, tile_ids in catalog.MOON_CYLINDRICAL:
        tiles = []
        for tid in tile_ids:
            lbl = raw_dir(root) / tid / f"{tid.lower()}.lbl"
            img = raw_dir(root) / tid / f"{tid.lower()}.img"
            if lbl.exists() and img.exists():
                tiles.append(CylDEM(lbl, pyramid_dir=derived_dir(root) / tid))
        if tiles and len(tiles) == len(tile_ids):
            cyl.append(CylMosaic(tiles, product_id=mosaic_id))
        else:
            missing.append(mosaic_id + (f" ({len(tiles)} of {len(tile_ids)} tiles)" if tiles else ""))
    return MoonTerrain(polar, cyl, missing)
