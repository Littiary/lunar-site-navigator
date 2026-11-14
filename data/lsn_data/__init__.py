"""Lunar Site Navigator, stream C: LOLA data, manifest, reader and pyramids."""

from __future__ import annotations

from pathlib import Path

__version__ = "0.1.0"

DEFAULT_PRODUCTS = ("LDEM_80S_20M", "LDEM_60S_60M")


def open_terrain(label_paths=None, products=DEFAULT_PRODUCTS, root=None):
    """Open terrain for horizon work.

    ``label_paths``: explicit PDS3 label files (e.g. the synthetic test DEM). Otherwise the
    ``products`` are looked up under the data root (``LSN_DATA_ROOT``), with their pyramids
    when those have been built.
    """
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
