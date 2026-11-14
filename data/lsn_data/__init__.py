"""Lunar Site Navigator, stream C: LOLA data, manifest, reader and pyramids."""

from __future__ import annotations

from pathlib import Path

__version__ = "0.1.0"

DEFAULT_PRODUCTS = ("LDEM_80S_20M", "LDEM_60S_60M")

# Whole-Moon terrain (``open_terrain(products="moon")``): polar products by pole, then cylindrical mosaics.
MOON_POLAR = {-1: ("LDEM_80S_20M", "LDEM_60S_60M"), 1: ("LDEM_80N_20M", "LDEM_60N_60M")}


def open_terrain(label_paths=None, products=DEFAULT_PRODUCTS, root=None, near_field=False):
    """Open terrain for horizon work.

    ``label_paths``: explicit PDS3 label files (e.g. the synthetic test DEM). Otherwise the
    ``products`` are looked up under the data root (``LSN_DATA_ROOT``), with their pyramids
    when those have been built.

    ``near_field=True`` adds the 5 m/pixel LOLA site DEMs of Barker et al. (2021) that are present
    (``lsn_data.catalog.SITE_DEM_PRODUCTS``): 5 m inside their extents, the polar products beyond and in
    their no-data pixels; ``Terrain.source`` reports the product used for each point. Opt-in, because the
    core adapter takes its neighbourhood bound from the shallowest overview pyramid of all products.

    ``products="moon"`` returns a :class:`lsn_data.moon.MoonTerrain` that serves any latitude and
    longitude with the best product present (both polar pairs, then the cylindrical mosaics of
    ``lsn_data.catalog.MOON_CYLINDRICAL``, finest first) and reports with ``source()`` which product
    and level it read. The default (south-polar pair, a ``Terrain``) is unchanged.
    """
    if isinstance(products, str) and products == "moon":
        if label_paths is not None:
            raise ValueError("label_paths and products='moon' exclude each other")
        return open_moon(root, near_field=near_field)
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
    if near_field:
        dems += site_dems(root)
    return Terrain(dems)


def site_dems(root=None):
    """The 5 m/pixel site DEMs present under ``<root>/raw/lola_5mpp`` (south pole), as polar products."""
    from . import catalog
    from .dem import PolarDEM
    from .paths import data_root, derived_dir

    root = Path(root) if root else data_root()
    out = []
    for site in catalog.SITE_DEM_SITES:
        pid = f"LOLA5MPP_{site.upper()}"
        f = root / "raw" / "lola_5mpp" / pid / f"{site}_final_adj_5mpp_surf.tif"
        if f.exists():
            out.append(PolarDEM.from_geotiff(f, product_id=pid, pyramid_dir=derived_dir(root) / pid,
                                             data_set_id="PGDA LOLA_5mpp (Barker et al. 2021)"))
    return out


def open_moon(root=None, near_field=False):
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
        if near_field and pole < 0:
            dems += site_dems(root)
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
